"""Complaints and their message threads. The only SQL for complaints.

reply_to (the consumer's WhatsApp number) is read here for delivery only; no row helper that feeds an API returns it.
"""

import json
import secrets
import sqlite3
import string
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.domain.bill import ExtractedBill
from app.store.db import tx
from app.store.units import Conflict, covered_sql, norm

INDIA = ZoneInfo("Asia/Kolkata")

Status = Literal["Open", "In progress", "Resolved", "Rejected"]
OPEN_STATUSES = ("Open", "In progress")
AuthorKind = Literal["consumer", "officer", "system"]
Kind = Literal["general", "wrong_reading"]
Delivery = Literal["sent", "failed", "stored"]


class Complaint(BaseModel):
    """Internal record. Carries reply_to for delivery, so it is never returned by an API as is."""

    ticket: str
    user_id: str
    bill_id: str | None
    discom: str | None
    status: Status
    language: str | None
    channel: str | None
    reply_to: str | None
    kind: Kind = "general"
    unit_id: str | None = None
    section_id: str | None = None
    assigned_to: str | None = None


class Placement(BaseModel):
    """Where a complaint sits in the hierarchy: the matched section, the unit that owns it, who works it."""

    section_id: str | None
    unit_id: str | None
    assigned_to: str | None = None


class Page(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


# Complaints recorded before triage existed fall back on the amount: money claimed means an overcharge to check.
_TRIAGE = "COALESCE(c.triage, CASE WHEN c.amount > 0 THEN 'overcharge' ELSE 'needs_check' END)"
_TRIAGE_RANK = f"CASE {_TRIAGE} WHEN 'overcharge' THEN 0 WHEN 'needs_check' THEN 1 ELSE 2 END"
# True when the newest message we sent the consumer did not reach them.
_FAILED = ("(SELECT m.delivery FROM complaint_messages m WHERE m.ticket = c.ticket AND m.author_kind != 'consumer' "
           "ORDER BY m.id DESC LIMIT 1) = 'failed'")
_OPEN = "c.status IN ('Open', 'In progress')"
# What one staff account may see: complaints whose unit or matched section is in its tree, anything assigned to it,
# and complaints from before units existed that only carry a DISCOM. Takes the account id VISIBLE_PARAMS times.
VISIBLE = (f"(c.assigned_to = ? OR c.unit_id IN {covered_sql()} OR c.section_id IN {covered_sql()} OR "
           f"(c.unit_id IS NULL AND EXISTS (SELECT 1 FROM units d WHERE d.kind = 'discom' AND d.name = c.discom "
           f"AND d.id IN {covered_sql()})))")
VISIBLE_PARAMS = 7
_ROW = ("SELECT c.ticket, c.created_at, c.updated_at, c.status, c.service_masked, c.bill_month, c.discom, c.issue, "
        f"c.amount, c.language, c.channel, c.kind, c.unit_id, c.section_id, c.assigned_to, {_TRIAGE} AS triage, COALESCE({_FAILED}, 0) AS delivery_failed, "
        "CAST(julianday('now') - julianday(c.created_at) AS INTEGER) AS days_open, "
        "(SELECT COUNT(*) FROM complaint_messages m WHERE m.ticket = c.ticket) AS messages_count, "
        "(SELECT MAX(m.created_at) FROM complaint_messages m WHERE m.ticket = c.ticket) AS last_message_at "
        "FROM complaints c")


TICKET_ALPHABET = string.ascii_uppercase + string.digits
TICKET_TRIES = 5
EXPORT_LIMIT = 5000
_MARKS = ", ".join("?" * len(OPEN_STATUSES))


def _new_ticket(conn: sqlite3.Connection) -> str:
    """Random, so a number is never reused after a deletion and does not reveal how many complaints exist."""
    # The date in a ticket is the day the consumer raised it, in India, not the server's UTC day.
    prefix = f"BM-{datetime.now(INDIA):%y%m%d}-"
    for _ in range(TICKET_TRIES):
        ticket = prefix + "".join(secrets.choice(TICKET_ALPHABET) for _ in range(5))
        if not conn.execute("SELECT 1 FROM complaints WHERE ticket = ?", (ticket,)).fetchone():
            return ticket
    raise RuntimeError("Could not find a free ticket number.")


def create(user_id: str, bill_id: str | None, bill: ExtractedBill, issue: str, amount: float, language: str,
           channel: str, reply_to: str | None, first_message: str, triage: str | None = None, *,
           kind: Kind = "general", placement: Placement | None = None,
           case_facts: dict[str, Any] | None = None) -> str:
    """Record a complaint and open its thread with the consumer's own words."""
    where = placement or Placement(section_id=None, unit_id=None)
    with tx() as conn:
        ticket = _new_ticket(conn)
        if kind == "wrong_reading" and bill_id and conn.execute(
                f"SELECT 1 FROM complaints WHERE bill_id = ? AND kind = ? AND status IN ({_MARKS})",
                (bill_id, kind, *OPEN_STATUSES)).fetchone():
            raise Conflict("A check is already open for this bill.")
        conn.execute(
            "INSERT INTO complaints (ticket, user_id, bill_id, service_masked, bill_month, discom, issue, amount, "
            "status, language, channel, reply_to, triage, kind, unit_id, section_id, section_name, assigned_to, "
            "case_facts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ticket, user_id, bill_id, bill.masked_service_number(), bill.bill_month, bill.discom, issue, amount,
             language, channel, reply_to, triage, kind, where.unit_id, where.section_id, bill.section,
             where.assigned_to, json.dumps(case_facts) if case_facts else None))
        conn.execute("INSERT INTO complaint_messages (ticket, author_kind, author_id, body, delivery) "
                     "VALUES (?, 'consumer', NULL, ?, 'stored')", (ticket, first_message))
    return ticket


def place(ticket: str, placement: Placement) -> None:
    with tx() as conn:
        conn.execute("UPDATE complaints SET unit_id = ?, section_id = ?, assigned_to = ?, "
                     "updated_at = CURRENT_TIMESTAMP WHERE ticket = ?",
                     (placement.unit_id, placement.section_id, placement.assigned_to, ticket))


def unrouted(discom: str, section_name_norms: set[str]) -> list[tuple[str, str]]:
    """(ticket, printed section) of open cases in a DISCOM with no matched section, printed as one of the names."""
    with tx() as conn:
        rows = conn.execute("SELECT ticket, section_name FROM complaints WHERE discom = ? AND section_id IS NULL "
                            f"AND kind = 'wrong_reading' AND status IN ({_MARKS}) LIMIT 1000",
                            (discom, *OPEN_STATUSES)).fetchall()
    return [(r["ticket"], r["section_name"]) for r in rows
            if r["section_name"] and norm(r["section_name"]) in section_name_norms]


def open_for_bill(bill_id: str, kind: Kind) -> str | None:
    with tx() as conn:
        row = conn.execute(f"SELECT ticket FROM complaints WHERE bill_id = ? AND kind = ? AND status IN ({_MARKS}) "
                           "ORDER BY created_at DESC LIMIT 1", (bill_id, kind, *OPEN_STATUSES)).fetchone()
    return row[0] if row else None


def latest_for_bill(user_id: str, bill_id: str, kind: Kind) -> str | None:
    with tx() as conn:
        row = conn.execute("SELECT ticket FROM complaints WHERE user_id = ? AND bill_id = ? AND kind = ? "
                           "ORDER BY created_at DESC, rowid DESC LIMIT 1", (user_id, bill_id, kind)).fetchone()
    return row[0] if row else None


def _filter(status: str | None, discom: str | None, q: str | None, owner: str | None,
            triage: str | None = None, failed_only: bool = False, viewer: str | None = None,
            kind: str | None = None) -> tuple[str, list[str]]:
    """`viewer` is a staff account id whose scope limits the rows; None means no limit."""
    where, params = ["1 = 1"], []
    if failed_only:
        where.append(f"{_OPEN} AND {_FAILED}")
    for column, value in (("c.status", status), ("c.discom", discom), ("c.user_id", owner), (_TRIAGE, triage),
                          ("c.kind", kind)):
        if value:
            where.append(f"{column} = ?")
            params.append(value)
    if q:
        where.append("instr(upper(c.ticket), ?) > 0")
        params.append(q.strip().upper())
    if viewer:
        where.append(VISIBLE)
        params += [viewer] * VISIBLE_PARAMS
    # Only fixed column names are joined into the SQL; every value is a parameter.
    return " WHERE " + " AND ".join(where), params


Sort = Literal["newest", "oldest", "priority"]


def page(page_no: int, page_size: int, *, status: str | None = None, discom: str | None = None,
         q: str | None = None, sort: Sort = "newest", owner: str | None = None, triage: str | None = None,
         failed_only: bool = False, overdue_days: int = 7, viewer: str | None = None, kind: str | None = None) -> Page:
    clause, params = _filter(status, discom, q, owner, triage, failed_only, viewer, kind)
    order_params: list[Any] = []
    if sort == "priority":
        # Needs you first: open, then overdue, then overcharges by size, then the oldest.
        order = (f"{_OPEN} DESC, ({_OPEN} AND c.created_at < datetime('now', ?)) DESC, {_TRIAGE_RANK}, "
                 "c.amount DESC, c.created_at ASC, c.ticket ASC")
        order_params = [f"-{overdue_days} days"]
    else:
        direction = "DESC" if sort == "newest" else "ASC"
        order = f"c.created_at {direction}, c.ticket {direction}"
    with tx() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM complaints c{clause}", params).fetchone()[0]
        rows = conn.execute(f"{_ROW}{clause} ORDER BY {order} LIMIT ? OFFSET ?",
                            [*params, *order_params, page_size, (page_no - 1) * page_size]).fetchall()
    return Page(items=[dict(r) for r in rows], total=total, page=page_no, page_size=page_size)


def export(*, status: str | None = None, discom: str | None = None, q: str | None = None,
           newest: bool = True, viewer: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
    """Rows for the CSV download. Never selects reply_to. days_open stops counting once a complaint is closed."""
    clause, params = _filter(status, discom, q, None, viewer=viewer, kind=kind)
    order = "DESC" if newest else "ASC"
    with tx() as conn:
        rows = conn.execute(
            "SELECT c.ticket, c.created_at, c.updated_at, c.status, c.discom, c.bill_month, c.service_masked, c.issue, "
            "c.amount, c.channel, CAST(julianday(CASE WHEN c.status IN (?, ?) THEN 'now' "
            "ELSE COALESCE(c.updated_at, c.created_at) END) - julianday(c.created_at) AS INTEGER) AS days_open "
            f"FROM complaints c{clause} ORDER BY c.created_at {order}, c.ticket {order} LIMIT ?",
            [*OPEN_STATUSES, *params, EXPORT_LIMIT]).fetchall()
    return [dict(r) for r in rows]


def row(ticket: str) -> dict[str, Any] | None:
    with tx() as conn:
        found = conn.execute(f"{_ROW} WHERE c.ticket = ?", (ticket,)).fetchone()
    return dict(found) if found else None


def get(ticket: str) -> Complaint | None:
    with tx() as conn:
        found = conn.execute("SELECT ticket, user_id, bill_id, discom, status, language, channel, reply_to, kind, "
                             "unit_id, section_id, assigned_to FROM complaints WHERE ticket = ?", (ticket,)).fetchone()
    return Complaint(**dict(found)) if found else None


def add_message(ticket: str, author_kind: AuthorKind, author_id: str | None, body: str, delivery: Delivery,
                delivery_note: str | None = None, media_id: str | None = None) -> None:
    with tx() as conn:
        conn.execute("INSERT INTO complaint_messages (ticket, author_kind, author_id, body, delivery, delivery_note, "
                     "media_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (ticket, author_kind, author_id, body, delivery, delivery_note, media_id))
        conn.execute("UPDATE complaints SET updated_at = CURRENT_TIMESTAMP WHERE ticket = ?", (ticket,))


def message(ticket: str, message_id: int) -> dict[str, Any] | None:
    with tx() as conn:
        found = conn.execute("SELECT id, author_kind, body, delivery FROM complaint_messages WHERE ticket = ? AND id = ?",
                             (ticket, message_id)).fetchone()
    return dict(found) if found else None


def set_delivery(message_id: int, delivery: Delivery, note: str | None) -> None:
    with tx() as conn:
        conn.execute("UPDATE complaint_messages SET delivery = ?, delivery_note = ? WHERE id = ?",
                     (delivery, note, message_id))


def messages(ticket: str) -> list[dict[str, Any]]:
    """The thread, oldest first. Only officers carry a name; a consumer stays anonymous to everyone."""
    with tx() as conn:
        rows = conn.execute(
            "SELECT m.id, m.author_kind, CASE WHEN m.author_kind = 'officer' THEN a.name END AS author_name, "
            "m.body, m.created_at, m.delivery, m.delivery_note, m.media_id FROM complaint_messages m "
            "LEFT JOIN accounts a ON a.id = m.author_id WHERE m.ticket = ? ORDER BY m.id LIMIT 500",
            (ticket,)).fetchall()
    return [dict(r) for r in rows]


class AlreadyOpen(Exception):
    """Reopening would leave two open reading checks on one bill, which the database forbids."""


def set_status(ticket: str, status: Status) -> None:
    try:
        with tx() as conn:
            conn.execute("UPDATE complaints SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE ticket = ?",
                         (status, ticket))
    except sqlite3.IntegrityError as exc:
        raise AlreadyOpen(ticket) from exc
