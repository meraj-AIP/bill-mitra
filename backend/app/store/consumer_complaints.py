"""A consumer's own complaints. Selects no staff name, no assignee and no reply_to, so nothing here can leak who
handles a complaint."""

from typing import Any

from app.store.db import tx

# Waiting for the consumer: an open request on the case, or the chat waiting for their answer to this complaint.
_WAITING = ("(c.status IN ('Open', 'In progress') AND (EXISTS (SELECT 1 FROM case_requests r WHERE r.ticket = c.ticket "
            "AND r.status = 'open') OR EXISTS (SELECT 1 FROM users u WHERE u.user_id = c.user_id "
            "AND u.awaiting = 'info:' || c.ticket)))")
# Staff have acted (replied, asked something, handed it on): an Open complaint is under way for the consumer, so their
# progress never steps back to "received" after they answer a request.
_ACTED = ("(c.handed_by IS NOT NULL OR EXISTS (SELECT 1 FROM complaint_messages m WHERE m.ticket = c.ticket "
          "AND m.author_kind = 'officer') OR EXISTS (SELECT 1 FROM case_requests r WHERE r.ticket = c.ticket))")
_STATE = (f"CASE WHEN {_WAITING} THEN 'waiting_for_you' WHEN c.status = 'Open' AND {_ACTED} THEN 'in_progress' "
          "WHEN c.status = 'Open' THEN 'received' "
          "WHEN c.status = 'In progress' THEN 'in_progress' WHEN c.status = 'Resolved' THEN 'resolved' ELSE 'closed' END")
# Older complaints have no description: the consumer's first message stands in for it.
_SELECT = (f"SELECT c.ticket, c.type, {_STATE} AS state, c.created_at, COALESCE(c.updated_at, c.created_at) AS updated_at, "
           "COALESCE(c.description, (SELECT m.body FROM complaint_messages m WHERE m.ticket = c.ticket "
           "AND m.author_kind = 'consumer' ORDER BY m.id LIMIT 1)) AS description, c.service_masked, c.bill_month "
           "FROM complaints c")


def page(user_id: str, page_no: int, page_size: int, state: str | None = None) -> tuple[list[dict[str, Any]], int]:
    """`state` is one of the neutral codes; the state expression is fixed text, the value a parameter."""
    where, params = "c.user_id = ?", [user_id]
    if state:
        where += f" AND ({_STATE}) = ?"
        params.append(state)
    with tx() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM complaints c WHERE {where}", params).fetchone()[0]
        rows = conn.execute(f"{_SELECT} WHERE {where} ORDER BY c.created_at DESC, c.ticket DESC LIMIT ? OFFSET ?",
                            [*params, page_size, (page_no - 1) * page_size]).fetchall()
    return [dict(r) for r in rows], total


def one(user_id: str, ticket: str) -> dict[str, Any] | None:
    """Only the owner's complaint; anyone else gets None, the same as a ticket that does not exist."""
    with tx() as conn:
        found = conn.execute(f"{_SELECT} WHERE c.ticket = ? AND c.user_id = ?", (ticket, user_id)).fetchone()
        if found is None:
            return None
        thread = conn.execute("SELECT author_kind, body, created_at, CASE WHEN author_kind = 'consumer' THEN media_id "
                              "END AS media_id FROM complaint_messages WHERE ticket = ? ORDER BY id LIMIT 500",
                              (ticket,)).fetchall()
    return {**dict(found), "messages": [dict(m) for m in thread]}
