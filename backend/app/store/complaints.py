"""Complaints and their message threads. The only SQL for complaints.

reply_to (the consumer's WhatsApp number) is read here for delivery only; no row helper that feeds an API returns it.
"""

import json
import secrets
import sqlite3
import string
from datetime import UTC, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.domain import complaint_types
from app.domain.bill import ExtractedBill
from app.store import handoffs, policy
from app.store.db import IntegrityError, tx
from app.store.units import Conflict, covered_sql, norm

INDIA = ZoneInfo("Asia/Kolkata")

Status = Literal["Open", "In progress", "Resolved", "Rejected"]
OPEN_STATUSES = ("Open", "In progress")
AuthorKind = Literal["consumer", "officer", "system"]
Kind = Literal["general", "wrong_reading"]
Delivery = Literal["sent", "queued", "failed", "stored"]  # queued: in the outbox, retried


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
    type: str | None = None


class Intake(BaseModel):
    """What a complaint is about and how it came in. Hashes only: the plain numbers never reach this table."""

    type: str
    priority: str
    due_at: str
    source: str
    raised_by: str | None = None
    service_number_hash: str | None = None
    contact_hash: str | None = None
    description: str | None = None
    ownership: str = "not_needed"
    demo: bool = False


def intake_for(type_code: str, source: str, discom: str | None, *, created: datetime | None = None,
               **fields: Any) -> Intake:
    """Priority and due date come from the type; a reading check falls due on the DISCOM's review SLA."""
    kind = complaint_types.get(type_code)
    due = complaint_types.due_at(type_code, created or datetime.now(UTC), policy.get(discom).decision_sla_days)
    return Intake(type=type_code, priority=kind.priority, due_at=due, source=source, **fields)


def _source(channel: str | None, kind: str) -> str:
    if channel == "whatsapp":
        return "whatsapp"
    return "consumer_web" if kind == "wrong_reading" else "consumer_chat"


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
# Whose move it is: the consumer's while a request or the chat waits for their answer, staff's while it is open.
WAITING_ON = ("CASE WHEN c.status NOT IN ('Open', 'In progress') THEN 'none' WHEN EXISTS (SELECT 1 FROM case_requests "
              "r WHERE r.ticket = c.ticket AND r.status = 'open') OR EXISTS (SELECT 1 FROM users u WHERE "
              "u.user_id = c.user_id AND u.awaiting = 'info:' || c.ticket) THEN 'consumer' ELSE 'staff' END")
_PRIORITY_RANK = "CASE c.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'low' THEN 3 ELSE 2 END"
# What one staff account may see: complaints whose unit or matched section is in its tree, anything assigned to it,
# and complaints from before units existed that only carry a DISCOM. Takes the account id VISIBLE_PARAMS times.
VISIBLE = (f"(c.assigned_to = ? OR c.unit_id IN {covered_sql()} OR c.section_id IN {covered_sql()} OR "
           f"(c.unit_id IS NULL AND EXISTS (SELECT 1 FROM units d WHERE d.kind = 'discom' AND d.name = c.discom "
           f"AND d.id IN {covered_sql()})))")
VISIBLE_PARAMS = 7
_ROW = ("SELECT c.ticket, c.created_at, c.updated_at, c.status, c.service_masked, c.bill_month, c.discom, c.issue, "
        f"c.amount, c.language, c.channel, c.kind, c.unit_id, c.section_id, c.assigned_to, {_TRIAGE} AS triage, CASE WHEN {_FAILED} THEN 1 ELSE 0 END AS delivery_failed, "
        "c.type, c.priority, c.due_at, c.source, c.ownership, c.demo, c.description, "
        "(SELECT r.name FROM accounts r WHERE r.id = c.raised_by) AS raised_by, "
        "(SELECT u.name FROM units u WHERE u.id = c.section_id) AS section, "
        "(SELECT p.name FROM accounts p WHERE p.id = c.assigned_to) AS assignee_name, "
        f"{WAITING_ON} AS waiting_on, c.handed_by, c.handoff_note, c.handed_at, "
        "(SELECT h.name FROM accounts h WHERE h.id = c.handed_by) AS handed_by_name, "
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


def _insert(conn: sqlite3.Connection, values: dict[str, Any], intake: Intake, first_message: str,
            author_kind: AuthorKind = "consumer", author_id: str | None = None) -> str:
    """One insert for every way a complaint comes in. Column names are fixed here; every value is a parameter."""
    ticket = _new_ticket(conn)
    row = {"ticket": ticket, "status": "Open", **values, **intake.model_dump(), "demo": int(intake.demo)}
    conn.execute(f"INSERT INTO complaints ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})", list(row.values()))
    conn.execute("INSERT INTO complaint_messages (ticket, author_kind, author_id, body, delivery) "
                 "VALUES (?, ?, ?, ?, 'stored')", (ticket, author_kind, author_id, first_message))
    return ticket


def create(user_id: str, bill_id: str | None, bill: ExtractedBill, issue: str, amount: float, language: str,
           channel: str, reply_to: str | None, first_message: str, triage: str | None = None, *,
           kind: Kind = "general", placement: Placement | None = None,
           case_facts: dict[str, Any] | None = None, intake: Intake | None = None) -> str:
    """Record a complaint about a bill and open its thread with the consumer's own words."""
    where = placement or Placement(section_id=None, unit_id=None)
    type_code = complaint_types.WRONG_READING if kind == "wrong_reading" else complaint_types.LEGACY_GENERAL
    intake = intake or intake_for(type_code, _source(channel, kind), bill.discom,
                                  ownership="verified" if bill_id else "not_needed")
    values = {"user_id": user_id, "bill_id": bill_id, "service_masked": bill.masked_service_number(),
              "bill_month": bill.bill_month, "discom": bill.discom, "issue": issue, "amount": amount,
              "language": language, "channel": channel, "reply_to": reply_to, "triage": triage, "kind": kind,
              "unit_id": where.unit_id, "section_id": where.section_id, "section_name": bill.section,
              "assigned_to": where.assigned_to, "case_facts": json.dumps(case_facts) if case_facts else None}
    with tx() as conn:
        if kind == "wrong_reading" and bill_id and conn.execute(
                f"SELECT 1 FROM complaints WHERE bill_id = ? AND kind = ? AND status IN ({_MARKS})",
                (bill_id, kind, *OPEN_STATUSES)).fetchone():
            raise Conflict("A check is already open for this bill.")
        ticket = _insert(conn, values, intake, first_message)
    if where.assigned_to:
        handoffs.routed(ticket, kind, where.assigned_to, where.unit_id)
    return ticket


class General(BaseModel):
    """A complaint that may have no bill: typed in chat, on the web, or logged by staff."""

    user_id: str
    discom: str | None
    issue: str
    language: str
    channel: str | None
    reply_to: str | None = None
    bill_id: str | None = None
    service_masked: str | None = None
    bill_month: str | None = None
    section_name: str | None = None


def create_general(complaint: General, placement: Placement, intake: Intake, first_message: str,
                   author_kind: AuthorKind = "consumer", author_id: str | None = None,
                   created_at: str | None = None) -> str:
    values = {**complaint.model_dump(), "amount": 0.0, "kind": "general", "unit_id": placement.unit_id,
              "section_id": placement.section_id, "assigned_to": placement.assigned_to}
    if created_at:
        values |= {"created_at": created_at, "updated_at": created_at}
    with tx() as conn:
        ticket = _insert(conn, values, intake, first_message, author_kind, author_id)
    if placement.assigned_to:
        handoffs.routed(ticket, "general", placement.assigned_to, placement.unit_id)
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


def open_of_type(user_id: str, type_code: str, service_number_hash: str | None, *, unknown_is_any: bool = True) -> str | None:
    """The newest open general complaint of this type from this consumer. With a service number, only one for the
    same number or for none, so two connections of one consumer do not merge. Without one, any of them, or with
    `unknown_is_any` False only one that has no number either."""
    number = (" AND (service_number_hash = ? OR service_number_hash IS NULL)" if service_number_hash else
              "" if unknown_is_any else " AND service_number_hash IS NULL")
    sql = (f"SELECT ticket FROM complaints WHERE user_id = ? AND kind = 'general' AND type = ? AND status IN ({_MARKS})"
           + number)
    params = (user_id, type_code, *OPEN_STATUSES, *((service_number_hash,) if service_number_hash else ()))
    with tx() as conn:
        row = conn.execute(sql + " ORDER BY created_at DESC, rowid DESC LIMIT 1", params).fetchone()
    return row[0] if row else None


class Filters(BaseModel):
    """The inbox filters on the new intake columns."""

    type: str | None = None
    priority: str | None = None
    source: str | None = None
    holder: str | None = None  # an account id: only complaints it holds
    waiting_on: str | None = None


def _filter(status: str | None, discom: str | None, q: str | None, owner: str | None,
            triage: str | None = None, failed_only: bool = False, viewer: str | None = None,
            kind: str | None = None, more: Filters | None = None) -> tuple[str, list[str]]:
    """`viewer` is a staff account id whose scope limits the rows; None means no limit."""
    where, params = ["1 = 1"], []
    extra = more or Filters()
    if failed_only:
        where.append(f"{_OPEN} AND {_FAILED}")
    if extra.holder:
        # "With me" is work in hand: a closed complaint keeps its holder but is no longer anyone's to do.
        where.append(_OPEN)
    for column, value in (("c.status", status), ("c.discom", discom), ("c.user_id", owner), (_TRIAGE, triage),
                          ("c.kind", kind), ("c.type", extra.type), ("c.priority", extra.priority),
                          ("c.source", extra.source), ("c.assigned_to", extra.holder),
                          (f"({WAITING_ON})", extra.waiting_on)):
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
         failed_only: bool = False, overdue_days: int = 7, viewer: str | None = None, kind: str | None = None,
         more: Filters | None = None) -> Page:
    clause, params = _filter(status, discom, q, owner, triage, failed_only, viewer, kind, more)
    order_params: list[Any] = []
    if sort == "priority":
        # Needs you first: open, then overdue, then urgent types, then overcharges by size, then the oldest.
        # Overdue means past the due time the type set; only complaints without one fall back to the days rule.
        overdue = ("CASE WHEN c.due_at IS NOT NULL THEN datetime(c.due_at) < datetime('now') "
                   "ELSE c.created_at < datetime('now', ?) END")
        order = (f"{_OPEN} DESC, ({_OPEN} AND {overdue}) DESC, {_PRIORITY_RANK}, "
                 f"{_TRIAGE_RANK}, c.amount DESC, c.created_at ASC, c.ticket ASC")
        order_params = [f"-{overdue_days} days"]
    else:
        direction = "DESC" if sort == "newest" else "ASC"
        order = f"c.created_at {direction}, c.ticket {direction}"
    with tx() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM complaints c{clause}", params).fetchone()[0]
        # Choose the page's tickets on the bare table first; the row's per-message lookups then run for those few
        # tickets only, instead of for every complaint the sort has to look at.
        tickets = [r[0] for r in conn.execute(f"SELECT c.ticket FROM complaints c{clause} ORDER BY {order} LIMIT ? OFFSET ?",
                                              [*params, *order_params, page_size, (page_no - 1) * page_size])]
        found = {r["ticket"]: dict(r) for r in conn.execute(
            f"{_ROW} WHERE c.ticket IN ({', '.join('?' * len(tickets))})", tickets)} if tickets else {}
    return Page(items=[found[t] for t in tickets if t in found], total=total, page=page_no, page_size=page_size)


def export(*, status: str | None = None, discom: str | None = None, q: str | None = None,
           newest: bool = True, viewer: str | None = None, kind: str | None = None,
           more: Filters | None = None) -> list[dict[str, Any]]:
    """Rows for the CSV download. Never selects reply_to. days_open stops counting once a complaint is closed."""
    clause, params = _filter(status, discom, q, None, viewer=viewer, kind=kind, more=more)
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
                             "unit_id, section_id, assigned_to, type FROM complaints WHERE ticket = ?",
                             (ticket,)).fetchone()
    return Complaint(**dict(found)) if found else None


def add_message(ticket: str, author_kind: AuthorKind, author_id: str | None, body: str, delivery: Delivery,
                delivery_note: str | None = None, media_id: str | None = None, wamid: str | None = None,
                outbox_id: int | None = None) -> int | None:
    """The new message id. A consumer message only reaches an open complaint (None otherwise) and tells its holder.
    `outbox_id` links the outbox row delivering it, so a later retry updates this message's delivery."""
    with tx() as conn:
        if author_kind == "consumer" and not conn.execute(
                f"SELECT 1 FROM complaints c WHERE c.ticket = ? AND {_OPEN}", (ticket,)).fetchone():
            return None
        cursor = conn.execute("INSERT INTO complaint_messages (ticket, author_kind, author_id, body, delivery, "
                              "delivery_note, media_id, wa_message_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                              (ticket, author_kind, author_id, body, delivery, delivery_note, media_id, wamid))
        message_id = int(cursor.fetchall()[0][0])
        conn.execute("UPDATE complaints SET updated_at = CURRENT_TIMESTAMP WHERE ticket = ?", (ticket,))
        if outbox_id:
            conn.execute("UPDATE outbox SET message_id = ? WHERE id = ?", (message_id, outbox_id))
    if author_kind == "consumer":
        handoffs.consumer_replied(ticket, bool(media_id))
    return message_id


def message(ticket: str, message_id: int) -> dict[str, Any] | None:
    with tx() as conn:
        found = conn.execute("SELECT id, author_kind, body, delivery FROM complaint_messages WHERE ticket = ? AND id = ?",
                             (ticket, message_id)).fetchone()
    return dict(found) if found else None


def set_delivery(message_id: int, delivery: Delivery, note: str | None, wamid: str | None = None,
                 outbox_id: int | None = None) -> None:
    with tx() as conn:
        conn.execute("UPDATE complaint_messages SET delivery = ?, delivery_note = ?, "
                     "wa_message_id = COALESCE(?, wa_message_id) WHERE id = ?", (delivery, note, wamid, message_id))
        if outbox_id:
            conn.execute("UPDATE outbox SET message_id = ? WHERE id = ?", (message_id, outbox_id))


def by_wamid(wamid: str) -> dict[str, Any] | None:
    """The message WhatsApp gave this id to, so a delivery status reported later lands on it."""
    with tx() as conn:
        found = conn.execute("SELECT id, ticket, author_kind, delivery FROM complaint_messages "
                             "WHERE wa_message_id = ? ORDER BY id DESC LIMIT 1", (wamid,)).fetchone()
    return dict(found) if found else None


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
    except IntegrityError as exc:
        raise AlreadyOpen(ticket) from exc
