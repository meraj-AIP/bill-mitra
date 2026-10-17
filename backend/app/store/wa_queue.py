"""WhatsApp turns waiting to be handled, shared by every worker on the host.

A person's messages are handled one at a time and in the order they arrived, whichever worker received them: a worker
claims the oldest waiting message of a sender only when no other worker is handling one for that sender. A row holds
the sender's number and text only until its turn is done, then it is deleted.

A turn that fails is tried again after 1, 5 and 15 minutes; the sender's later messages wait behind it so the order
holds. After MAX_ATTEMPTS it is parked as `failed` for staff to retry or dismiss (docs/reliability-contract.md
section 2), and the sender's later messages go ahead.
"""

import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any, NamedTuple

from app.channels.whatsapp.mapper import IncomingWhatsApp
from app.store.db import ts, tx

# A turn that has run this long belongs to a worker that died; another worker may take it over.
LEASE_SECONDS = 300
BACKOFF_S = (60, 300, 900)
MAX_ATTEMPTS = 4

_DDL = ("CREATE TABLE IF NOT EXISTS wa_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT NOT NULL, "
        "payload TEXT NOT NULL, claimed_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE INDEX IF NOT EXISTS idx_wa_turns_sender ON wa_turns(sender, id)")
# Added with retries; SQLite has no ADD COLUMN IF NOT EXISTS.
_COLUMNS = {"state": "TEXT NOT NULL DEFAULT 'queued'", "attempts": "INTEGER NOT NULL DEFAULT 0",
            "next_attempt_at": "TEXT", "last_error": "TEXT", "updated_at": "TEXT"}


class Claimed(NamedTuple):
    id: int
    incoming: IncomingWhatsApp
    attempts: int  # failed tries before this one


def ensure(conn: Any) -> None:
    for statement in _DDL:
        conn.execute(statement)
    present = {row[1] for row in conn.execute("PRAGMA table_info(wa_turns)")}
    for name, kind in _COLUMNS.items():
        if name not in present:
            conn.execute(f"ALTER TABLE wa_turns ADD COLUMN {name} {kind}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wa_turns_state ON wa_turns(state, next_attempt_at)")


def add(incoming: IncomingWhatsApp) -> None:
    with tx() as conn:
        conn.execute("INSERT INTO wa_turns (sender, payload) VALUES (?, ?)",
                     (incoming.wa_id, json.dumps(asdict(incoming))))


def claim(sender: str, now: datetime | None = None) -> Claimed | None:
    """The sender's next message, if nobody is handling one of theirs and its retry time has come. One statement, so
    two workers never both win. A message waiting for its retry holds back the sender's later ones."""
    lease = f"-{LEASE_SECONDS} seconds"
    with tx() as conn:
        row = conn.execute(
            "UPDATE wa_turns SET claimed_at = CURRENT_TIMESTAMP WHERE id = ("
            "  SELECT id FROM wa_turns w WHERE w.sender = ? AND w.claimed_at IS NULL AND w.state = 'queued' "
            "  ORDER BY w.id LIMIT 1) "
            "AND COALESCE(next_attempt_at, '') <= ? "
            "AND NOT EXISTS (SELECT 1 FROM wa_turns r WHERE r.sender = ? AND r.claimed_at IS NOT NULL "
            "  AND r.claimed_at > datetime('now', ?)) "
            "RETURNING id, payload, attempts", (sender, ts(now), sender, lease)).fetchone()
        if row is None:
            # A turn left behind by a dead worker: take it over, oldest first.
            row = conn.execute(
                "UPDATE wa_turns SET claimed_at = CURRENT_TIMESTAMP WHERE id = ("
                "  SELECT id FROM wa_turns WHERE sender = ? AND state = 'queued' "
                "  AND claimed_at <= datetime('now', ?) ORDER BY id LIMIT 1) "
                "RETURNING id, payload, attempts", (sender, lease)).fetchone()
    return Claimed(row[0], IncomingWhatsApp(**json.loads(row[1])), row[2]) if row else None


def done(turn_id: int) -> None:
    with tx() as conn:
        conn.execute("DELETE FROM wa_turns WHERE id = ?", (turn_id,))


def fail(turn_id: int, error: str, now: datetime | None = None) -> tuple[int, bool]:
    """Record a failed try: (attempts so far, parked). `error` is an exception class name, never message text."""
    moment = now or datetime.now(UTC)
    with tx() as conn:
        attempts = conn.execute("UPDATE wa_turns SET attempts = attempts + 1 WHERE id = ? RETURNING attempts",
                                (turn_id,)).fetchone()[0]
        parked = attempts >= MAX_ATTEMPTS
        retry_at = None if parked else ts(moment + timedelta(seconds=BACKOFF_S[min(attempts, len(BACKOFF_S)) - 1]))
        conn.execute("UPDATE wa_turns SET claimed_at = NULL, last_error = ?, next_attempt_at = ?, state = ?, "
                     "updated_at = ? WHERE id = ?",
                     (error[:80], retry_at, "failed" if parked else "queued", ts(moment), turn_id))
    return attempts, parked


def waiting_senders(limit: int = 1000) -> list[str]:
    """Senders with turns left from before a restart, so they are picked up at start."""
    with tx() as conn:
        return [r[0] for r in conn.execute("SELECT DISTINCT sender FROM wa_turns WHERE state = 'queued' LIMIT ?",
                                           (limit,))]


def due_senders(now: datetime | None = None, limit: int = 200) -> list[str]:
    """Senders with an unclaimed turn whose retry time has come."""
    with tx() as conn:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT sender FROM wa_turns WHERE state = 'queued' AND claimed_at IS NULL "
            "AND COALESCE(next_attempt_at, '') <= ? LIMIT ?", (ts(now), limit))]


def requeue_expired() -> list[int]:
    """Claims whose lease ran out (the worker died): released, so the next drain takes them."""
    with tx() as conn:
        return [r[0] for r in conn.execute(
            "UPDATE wa_turns SET claimed_at = NULL WHERE state = 'queued' AND claimed_at IS NOT NULL "
            "AND claimed_at <= datetime('now', ?) RETURNING id", (f"-{LEASE_SECONDS} seconds",))]


def sender_of(turn_id: int) -> str | None:
    with tx() as conn:
        row = conn.execute("SELECT sender FROM wa_turns WHERE id = ?", (turn_id,)).fetchone()
    return row[0] if row else None


def retry(turn_id: int) -> bool:
    """A parked turn goes back to the queue, due now. One more failure parks it again at once."""
    with tx() as conn:
        return conn.execute("UPDATE wa_turns SET state = 'queued', next_attempt_at = NULL, attempts = ?, "
                            "updated_at = CURRENT_TIMESTAMP WHERE id = ? AND state = 'failed'",
                            (MAX_ATTEMPTS - 1, turn_id)).rowcount == 1


def dismiss(turn_id: int) -> bool:
    """Staff decided not to retry: the row, with the number and text it holds, is deleted."""
    with tx() as conn:
        return conn.execute("DELETE FROM wa_turns WHERE id = ? AND state = 'failed'", (turn_id,)).rowcount == 1


def counts() -> tuple[int, int, str | None]:
    """(queued, failed, oldest queued created_at)."""
    with tx() as conn:
        row = conn.execute("SELECT COALESCE(SUM(state = 'queued'), 0), COALESCE(SUM(state = 'failed'), 0), "
                           "MIN(CASE WHEN state = 'queued' THEN created_at END) FROM wa_turns").fetchone()
    return row[0], row[1], row[2]
