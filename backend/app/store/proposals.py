"""Routine actions the system has prepared and a person approves (app/flows/proposals.py). The only SQL for them.

A proposal is made once per kind and complaint (`dedupe_key`), so a rejected one is never offered again. Taking a
decision is one conditional update, so two officers approving at once never both carry it out.
"""

import json
from typing import Any, Literal

from pydantic import BaseModel

from app.domain import complaint_types
from app.store.complaints import OPEN_STATUSES, VISIBLE, VISIBLE_PARAMS
from app.store.db import ts, tx

Kind = Literal["explain_correct", "request_bill", "request_meter", "decide_correct"]
State = Literal["pending", "approved", "rejected", "stale"]

_DDL = (
    "CREATE TABLE IF NOT EXISTS proposals (id INTEGER PRIMARY KEY AUTOINCREMENT, ticket TEXT NOT NULL, "
    "kind TEXT NOT NULL, why TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', dedupe_key TEXT NOT NULL UNIQUE, "
    "decided_by TEXT, decided_at TEXT, note TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
    "CREATE INDEX IF NOT EXISTS idx_proposals_state ON proposals(state, kind, id)",
    "CREATE INDEX IF NOT EXISTS idx_proposals_ticket ON proposals(ticket, state)",
)
_OPEN = "c.status IN ('Open', 'In progress')"


class Proposal(BaseModel):
    id: int
    ticket: str
    kind: Kind
    why: list[str]
    state: State
    created_at: str
    decided_by_name: str | None
    decided_at: str | None
    note: str | None
    complaint_type: str | None
    type_label: str | None = None
    complaint_kind: str
    discom: str | None
    section: str | None
    bill_month: str | None
    complaint_created_at: str


class Page(BaseModel):
    items: list[Proposal]
    total: int
    counts: dict[str, int]  # pending proposals the viewer may see, by kind; filters do not narrow it
    page: int
    page_size: int


def ensure(conn: Any) -> None:
    for statement in _DDL:
        conn.execute(statement)


_SELECT = ("SELECT p.id, p.ticket, p.kind, p.why, p.state, p.created_at, d.name AS decided_by_name, p.decided_at, "
           "p.note, c.type AS complaint_type, c.kind AS complaint_kind, c.discom, s.name AS section, c.bill_month, "
           "c.created_at AS complaint_created_at FROM proposals p JOIN complaints c ON c.ticket = p.ticket "
           "LEFT JOIN units s ON s.id = c.section_id LEFT JOIN accounts d ON d.id = p.decided_by")


def _row(found: Any) -> Proposal:
    data = dict(found)
    known = complaint_types.BY_CODE.get(data["complaint_type"] or "")
    return Proposal(**{**data, "why": json.loads(data["why"]), "type_label": known.label if known else None})


def _scope(kinds: list[Kind], viewer: str | None) -> tuple[list[str], list[Any]]:
    marks = ", ".join("?" * len(kinds)) or "NULL"
    where, params = [f"p.kind IN ({marks})"], list(kinds)
    if viewer:
        where.append(VISIBLE)
        params += [viewer] * VISIBLE_PARAMS
    return where, params


def page(page_no: int, page_size: int, kinds: list[Kind], viewer: str | None, *, kind: Kind | None = None,
         state: State = "pending") -> Page:
    """Proposals of the kinds the viewer may approve, in their scope. Pending ones oldest first, so nothing waits
    long; decided ones newest first."""
    where, params = _scope(kinds, viewer)
    order = "p.id ASC" if state == "pending" else "p.decided_at DESC, p.id DESC"
    shown = [*where, "p.state = ?", *(["p.kind = ?"] if kind else [])]
    shown_params = [*params, state, *([kind] if kind else [])]
    with tx() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM proposals p JOIN complaints c ON c.ticket = p.ticket "
                             f"WHERE {' AND '.join(shown)}", shown_params).fetchone()[0]
        rows = conn.execute(f"{_SELECT} WHERE {' AND '.join(shown)} ORDER BY {order} LIMIT ? OFFSET ?",
                            [*shown_params, page_size, (page_no - 1) * page_size]).fetchall()
        tally = conn.execute(f"SELECT p.kind, COUNT(*) FROM proposals p JOIN complaints c ON c.ticket = p.ticket "
                             f"WHERE {' AND '.join(where)} AND p.state = 'pending' GROUP BY p.kind", params).fetchall()
    return Page(items=[_row(r) for r in rows], total=total, counts={r[0]: r[1] for r in tally}, page=page_no,
                page_size=page_size)


def get(proposal_id: int) -> Proposal | None:
    with tx() as conn:
        found = conn.execute(f"{_SELECT} WHERE p.id = ?", (proposal_id,)).fetchone()
    return _row(found) if found else None


def pending_count(kinds: list[Kind], viewer: str | None) -> int:
    where, params = _scope(kinds, viewer)
    with tx() as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM proposals p JOIN complaints c ON c.ticket = p.ticket "
                                f"WHERE {' AND '.join(where)} AND p.state = 'pending'", params).fetchone()[0])


def add(ticket: str, kind: Kind, why: list[str]) -> bool:
    """False when this kind was already proposed for the complaint, whatever became of it."""
    with tx() as conn:
        return conn.execute("INSERT OR IGNORE INTO proposals (ticket, kind, why, dedupe_key) VALUES (?, ?, ?, ?)",
                            (ticket, kind, json.dumps(why), f"{kind}:{ticket}")).rowcount == 1


def take(proposal_id: int, state: Literal["approved", "rejected"], by: str, note: str | None) -> bool:
    """Decide a pending proposal. False when someone else already did, or it went stale."""
    with tx() as conn:
        return conn.execute("UPDATE proposals SET state = ?, decided_by = ?, decided_at = ?, note = ? "
                            "WHERE id = ? AND state = 'pending'", (state, by, ts(), note, proposal_id)).rowcount == 1


def mark_stale(proposal_id: int, note: str) -> None:
    """Approved, but the complaint had moved on by the time it was carried out: nothing was done."""
    with tx() as conn:
        conn.execute("UPDATE proposals SET state = 'stale', note = ? WHERE id = ?", (note[:200], proposal_id))


def expire_closed() -> int:
    """Pending proposals on complaints that have since closed are no longer worth anyone's time."""
    with tx() as conn:
        return conn.execute("UPDATE proposals SET state = 'stale', note = 'complaint closed', decided_at = ? "
                            "WHERE state = 'pending' AND ticket IN (SELECT ticket FROM complaints WHERE status NOT IN "
                            f"({', '.join('?' * len(OPEN_STATUSES))}))", (ts(), *OPEN_STATUSES)).rowcount


def candidates(limit: int, created_before: str) -> list[str]:
    """Open complaints made before `created_before` that changed since the rules last looked at them and have
    nothing waiting for approval."""
    with tx() as conn:
        return [r[0] for r in conn.execute(
            f"SELECT c.ticket FROM complaints c WHERE {_OPEN} AND c.created_at <= ? AND (c.proposal_checked_at IS NULL OR "
            "COALESCE(c.updated_at, c.created_at) > c.proposal_checked_at) AND NOT EXISTS (SELECT 1 FROM proposals p "
            "WHERE p.ticket = c.ticket AND p.state = 'pending') ORDER BY c.created_at LIMIT ?", (created_before, limit))]


def mark_checked(ticket: str) -> None:
    # Set to the complaint's own last change, so a change made while the rules were looking still counts as new.
    with tx() as conn:
        conn.execute("UPDATE complaints SET proposal_checked_at = COALESCE(updated_at, created_at) WHERE ticket = ?",
                     (ticket,))


def staff_replied(ticket: str) -> bool:
    """An officer already wrote on the thread, so a person is handling it."""
    with tx() as conn:
        return conn.execute("SELECT 1 FROM complaint_messages WHERE ticket = ? AND author_kind = 'officer' LIMIT 1",
                            (ticket,)).fetchone() is not None
