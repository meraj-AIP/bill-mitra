"""One AI brief per complaint or case, shared by every staff member who opens it.

A brief is kept with a fingerprint of what it was written from. When the complaint moves on (a message, a status, a
new holder, a request, a decision), the fingerprint changes and the next reader gets a fresh one; until then everyone
reads the same stored brief, so the model is called once per state of the case, not once per person.
"""

import hashlib
import json
from typing import Any, Literal

from app.store.db import tx

Kind = Literal["complaint", "case"]

_STATE = (
    "SELECT c.status, c.assigned_to, c.type, c.bill_id, c.section_id, "
    "(SELECT MAX(m.id) FROM complaint_messages m WHERE m.ticket = c.ticket), "
    "(SELECT COUNT(*) || ':' || COALESCE(SUM(r.status = 'open'), 0) || ':' || COALESCE(MAX(r.id), 0) "
    " FROM case_requests r WHERE r.ticket = c.ticket), "
    "(SELECT COUNT(*) || ':' || COALESCE(MAX(d.id), 0) || ':' || COALESCE(GROUP_CONCAT(d.status), '') "
    " FROM review_decisions d WHERE d.ticket = c.ticket) "
    "FROM complaints c WHERE c.ticket = ?")


def fingerprint(ticket: str) -> str:
    with tx() as conn:
        row = conn.execute(_STATE, (ticket,)).fetchone()
    return hashlib.sha256(json.dumps(list(row) if row else [], default=str).encode()).hexdigest()[:32]


def get(ticket: str, kind: Kind) -> dict[str, Any] | None:
    with tx() as conn:
        row = conn.execute("SELECT fingerprint, payload, generated_at FROM assist_briefs WHERE ticket = ? AND kind = ?",
                           (ticket, kind)).fetchone()
    if row is None:
        return None
    return {"fingerprint": row["fingerprint"], "payload": json.loads(row["payload"]), "generated_at": row["generated_at"]}


def put(ticket: str, kind: Kind, fp: str, payload: dict[str, Any]) -> str:
    """Stores the brief and returns its time. A newer brief for the same case replaces the old one."""
    with tx() as conn:
        conn.execute("INSERT INTO assist_briefs (ticket, kind, fingerprint, payload, generated_at) "
                     "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP) ON CONFLICT(ticket, kind) DO UPDATE SET "
                     "fingerprint = excluded.fingerprint, payload = excluded.payload, generated_at = CURRENT_TIMESTAMP",
                     (ticket, kind, fp, json.dumps(payload)))
        return conn.execute("SELECT generated_at FROM assist_briefs WHERE ticket = ? AND kind = ?",
                            (ticket, kind)).fetchone()[0]
