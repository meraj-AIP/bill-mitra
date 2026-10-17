"""Evidence on wrong reading cases: the DISCOM records snapshot, the months the system asked for, the bills that
came back for them, final amounts and the case timeline. The only SQL for these."""

import json
from typing import Any

from app.store.complaints import OPEN_STATUSES
from app.store.db import tx
from app.store.review import ANSWERING

_MARKS = ", ".join("?" * len(OPEN_STATUSES))


def save_records(ticket: str, status: str, months: list[dict[str, Any]]) -> None:
    with tx() as conn:
        conn.execute("INSERT INTO case_records (ticket, status, months) VALUES (?, ?, ?) ON CONFLICT(ticket) DO UPDATE "
                     "SET status = excluded.status, months = excluded.months, fetched_at = CURRENT_TIMESTAMP",
                     (ticket, status, json.dumps(months)))


def records(ticket: str) -> tuple[str, list[dict[str, Any]]] | None:
    """(status, [{month, units}]) as fetched when the case was reported; None for a case from before that."""
    with tx() as conn:
        row = conn.execute("SELECT status, months FROM case_records WHERE ticket = ?", (ticket,)).fetchone()
    return (row["status"], json.loads(row["months"])) if row else None


def add_month_request(ticket: str, months: list[str], note: str) -> int:
    """A request the system raised (requested_by NULL) for earlier bills of these months."""
    with tx() as conn:
        cursor = conn.execute("INSERT INTO case_requests (ticket, kind, note, requested_by, months) "
                              "VALUES (?, 'earlier_bills', ?, NULL, ?)", (ticket, note, json.dumps(months)))
    return int(cursor.lastrowid or 0)


def month_request(ticket: str) -> dict[str, Any] | None:
    """The newest request for months on the case, with the months received for it."""
    with tx() as conn:
        row = conn.execute("SELECT id, months, status FROM case_requests WHERE ticket = ? AND months IS NOT NULL "
                           "ORDER BY id DESC LIMIT 1", (ticket,)).fetchone()
        if row is None:
            return None
        got = conn.execute("SELECT month FROM case_bills WHERE request_id = ? ORDER BY month LIMIT 24",
                           (row["id"],)).fetchall()
    return {"id": row["id"], "months": json.loads(row["months"]), "status": row["status"],
            "received": [r[0] for r in got]}


def open_month_requests(user_id: str, service_number: str) -> list[dict[str, Any]]:
    """Open month requests on this user's open cases whose bill is for this connection. Never another user's."""
    with tx() as conn:
        rows = conn.execute(
            "SELECT q.id, q.ticket, q.months FROM case_requests q JOIN complaints c ON c.ticket = q.ticket "
            "JOIN bills b ON b.id = c.bill_id WHERE c.user_id = ? AND c.kind = 'wrong_reading' "
            f"AND c.status IN ({_MARKS}) AND q.status = 'open' AND q.months IS NOT NULL AND b.service_number = ? "
            "ORDER BY q.id LIMIT 20", (user_id, *OPEN_STATUSES, service_number)).fetchall()
    return [{"id": r["id"], "ticket": r["ticket"], "months": json.loads(r["months"])} for r in rows]


def open_month_request_for_user(user_id: str) -> dict[str, Any] | None:
    """The user's newest open month request on an open case, for a chat reply such as "I don't have them"."""
    with tx() as conn:
        row = conn.execute(
            "SELECT q.id, q.ticket FROM case_requests q JOIN complaints c ON c.ticket = q.ticket WHERE c.user_id = ? "
            f"AND c.kind = 'wrong_reading' AND c.status IN ({_MARKS}) AND q.status = 'open' AND q.months IS NOT NULL "
            "ORDER BY q.id DESC LIMIT 1", (user_id, *OPEN_STATUSES)).fetchone()
    return dict(row) if row else None


def attach(ticket: str, request_id: int, month: str, bill_id: str) -> bool:
    """False when a bill for that month is already on the case."""
    with tx() as conn:
        cursor = conn.execute("INSERT OR IGNORE INTO case_bills (ticket, month, request_id, bill_id) VALUES (?, ?, ?, ?)",
                              (ticket, month, request_id, bill_id))
    return cursor.rowcount == 1


def answer(request_id: int) -> None:
    """Answered by the consumer's newest message on the case, so store that message first."""
    with tx() as conn:
        conn.execute(f"UPDATE case_requests SET status = 'answered', answered_at = CURRENT_TIMESTAMP, "
                     f"answer_message_id = {ANSWERING} WHERE id = ? AND status = 'open'", (request_id,))


def attached(ticket: str) -> list[dict[str, Any]]:
    """Bills attached to the case that still exist (a consumer may erase their data), oldest month first."""
    with tx() as conn:
        rows = conn.execute(
            "SELECT k.bill_id, k.month, b.units, json_extract(b.extraction, '$.bill_amount') AS amount, b.media_id "
            "FROM case_bills k JOIN bills b ON b.id = k.bill_id WHERE k.ticket = ? ORDER BY k.month LIMIT 24",
            (ticket,)).fetchall()
    return [dict(r) for r in rows]


def final_revision(bill_id: str) -> dict[str, Any] | None:
    """The bill's newest approved revision, whichever case it came from."""
    with tx() as conn:
        row = conn.execute("SELECT revised_amount, original_amount, applied_at FROM review_decisions WHERE bill_id = ? "
                           "AND status = 'approved' AND revision IS NOT NULL ORDER BY revision DESC LIMIT 1",
                           (bill_id,)).fetchone()
    return dict(row) if row else None


def timeline_rows(ticket: str) -> list[dict[str, Any]]:
    """Audit entries on the case, oldest first, with the staff name when a person acted."""
    with tx() as conn:
        rows = conn.execute("SELECT l.id, l.ts, l.actor_id, a.name AS actor_name, l.action, l.detail FROM audit_log l "
                            "LEFT JOIN accounts a ON a.id = l.actor_id WHERE l.target = ? ORDER BY l.id LIMIT 500",
                            (ticket,)).fetchall()
    return [dict(r) for r in rows]
