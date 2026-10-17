"""SQL for the development demo complaints (app/tools/demo_complaints.py). Touches only rows marked demo."""

from app.store.db import tx


def add_message(ticket: str, author_kind: str, body: str, at: str) -> None:
    with tx() as conn:
        conn.execute("INSERT INTO complaint_messages (ticket, author_kind, author_id, body, delivery, created_at) "
                     "VALUES (?, ?, NULL, ?, 'stored', ?)", (ticket, author_kind, body, at))


def audit_system(ticket: str, action: str, detail: str, at: str) -> None:
    """An automatic step at a backdated time, so the demo timeline shows it as System like a real one."""
    with tx() as conn:
        conn.execute("INSERT INTO audit_log (ts, actor_id, action, target, detail) VALUES (?, NULL, ?, ?, ?)",
                     (at, action, ticket, detail))


def finish(ticket: str, status: str, updated_at: str, escalated_at: str | None) -> None:
    """Backdate the opening message and set the final state, so the demo reads like a month of real work."""
    with tx() as conn:
        conn.execute("UPDATE complaint_messages SET created_at = (SELECT created_at FROM complaints WHERE ticket = ?) "
                     "WHERE id = (SELECT MIN(id) FROM complaint_messages WHERE ticket = ?)", (ticket, ticket))
        conn.execute("UPDATE complaints SET status = ?, updated_at = ?, escalated_at = ? WHERE ticket = ? AND demo = 1",
                     (status, updated_at, escalated_at, ticket))


def remove() -> tuple[int, int]:
    """Delete demo complaints, their messages and their demo bills. Returns (complaints, bills) deleted."""
    with tx() as conn:
        conn.execute("DELETE FROM audit_log WHERE target IN (SELECT ticket FROM complaints WHERE demo = 1)")
        conn.execute("DELETE FROM complaint_messages WHERE ticket IN (SELECT ticket FROM complaints WHERE demo = 1)")
        complaints = conn.execute("DELETE FROM complaints WHERE demo = 1").rowcount
        bills = conn.execute("DELETE FROM bills WHERE source = 'demo'").rowcount
    return complaints, bills


def counts() -> list[tuple[str, int]]:
    with tx() as conn:
        rows = conn.execute("SELECT type, COUNT(*) FROM complaints WHERE demo = 1 GROUP BY type ORDER BY 2 DESC, 1")
        return [(r[0], r[1]) for r in rows]
