"""SQL for the development demo complaints and review cases (app/tools/demo_complaints.py, demo_review.py).
Touches only rows marked demo: complaints with demo = 1 or on a demo bill, bills with source = 'demo', and the one
staff account the review seed made for itself."""

import json
import sqlite3

from app.store.db import tx

STAFF_MARK = "account.demo_review_seed"  # audit entry that says the review seed made this account
# Rows that hang off a ticket, deleted with it. Column names are fixed here; every value is a parameter.
_BY_TICKET = ("complaint_messages", "case_requests", "review_decisions", "case_bills", "case_records",
              "case_suggestions")
# Every timestamp a case can carry, so a backdated case keeps its steps in order.
_CASE_TIMES = (("complaints", ("created_at", "updated_at", "due_at")), ("complaint_messages", ("created_at",)),
               ("case_requests", ("created_at", "answered_at", "reminded_at")),
               ("review_decisions", ("proposed_at", "decided_at", "applied_at")), ("case_bills", ("created_at",)),
               ("case_records", ("fetched_at",)), ("case_suggestions", ("created_at",)), ("alerts", ("created_at",)))
_DEMO_TICKETS = ("SELECT ticket FROM complaints WHERE demo = 1 OR bill_id IN "
                 "(SELECT id FROM bills WHERE source = 'demo')")


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


def mark(ticket: str) -> None:
    """A review case opened through the real report path is flagged demo straight after, so remove finds it."""
    with tx() as conn:
        conn.execute("UPDATE complaints SET demo = 1 WHERE ticket = ?", (ticket,))


def backdate(ticket: str, bill_ids: list[str], hours: int) -> None:
    """Move everything the case has so far back by `hours`. Called after each step, so earlier steps end up
    further back and the timeline reads like days of work rather than one second."""
    shift = f"-{int(hours)} hours"
    with tx() as conn:
        for table, columns in _CASE_TIMES:
            sets = ", ".join(f"{c} = datetime({c}, ?)" for c in columns)
            conn.execute(f"UPDATE {table} SET {sets} WHERE ticket = ?", (*[shift] * len(columns), ticket))
        conn.execute("UPDATE audit_log SET ts = datetime(ts, ?) WHERE target = ?", (shift, ticket))
        conn.execute("UPDATE bills SET created_at = datetime(created_at, ?) WHERE source = 'demo' AND id IN "
                     "(SELECT value FROM json_each(?))", (shift, json.dumps(bill_ids)))


def staff(login: str) -> tuple[str, bool] | None:
    """The account on this login, and whether the review seed made it (only that one is ever changed)."""
    with tx() as conn:
        row = conn.execute("SELECT id, EXISTS (SELECT 1 FROM audit_log WHERE action = ? AND target = accounts.id) "
                           "FROM accounts WHERE login = ?", (STAFF_MARK, login)).fetchone()
    return (row[0], bool(row[1])) if row else None


def _remove_staff(conn: sqlite3.Connection, login: str) -> None:
    row = conn.execute("SELECT a.id FROM accounts a WHERE a.login = ? AND EXISTS (SELECT 1 FROM audit_log l WHERE "
                       "l.action = ? AND l.target = a.id)", (login, STAFF_MARK)).fetchone()
    if row is None:
        return
    for table in ("sessions", "account_scopes", "alert_reads"):
        conn.execute(f"DELETE FROM {table} WHERE account_id = ?", (row[0],))
    conn.execute("DELETE FROM audit_log WHERE target = ? OR actor_id = ?", (row[0], row[0]))
    conn.execute("DELETE FROM accounts WHERE id = ?", (row[0],))


def remove(staff_login: str | None = None) -> tuple[int, int]:
    """Delete demo complaints and cases with everything hanging off them, their demo bills, and the review seed's
    own staff account. Returns (complaints, bills) deleted."""
    with tx() as conn:
        tickets = json.dumps([r[0] for r in conn.execute(_DEMO_TICKETS)])
        within = "ticket IN (SELECT value FROM json_each(?))"
        conn.execute(f"DELETE FROM alert_reads WHERE alert_id IN (SELECT id FROM alerts WHERE {within})", (tickets,))
        conn.execute(f"DELETE FROM alerts WHERE {within}", (tickets,))
        conn.execute("DELETE FROM audit_log WHERE target IN (SELECT value FROM json_each(?))", (tickets,))
        for table in _BY_TICKET:
            conn.execute(f"DELETE FROM {table} WHERE {within}", (tickets,))
        conn.execute("DELETE FROM case_bills WHERE bill_id IN (SELECT id FROM bills WHERE source = 'demo')")
        complaints = conn.execute(f"DELETE FROM complaints WHERE {within}", (tickets,)).rowcount
        bills = conn.execute("DELETE FROM bills WHERE source = 'demo'").rowcount
        if staff_login:
            _remove_staff(conn, staff_login)
    return complaints, bills


def counts() -> list[tuple[str, int]]:
    with tx() as conn:
        rows = conn.execute("SELECT type, COUNT(*) FROM complaints WHERE demo = 1 GROUP BY type ORDER BY 2 DESC, 1")
        return [(r[0], r[1]) for r in rows]
