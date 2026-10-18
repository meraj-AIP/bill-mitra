"""Every message to a consumer, kept until WhatsApp accepts it (docs/reliability-contract.md section 3). The only SQL
for the outbox; sending lives in app/services/delivery.py.

One row per logical message (`dedupe_key`), so a retried turn or job never queues a message twice, and a row Meta
accepted (`wamid` stored) is never sent again. A send that fails for a passing reason is tried again after 1, 5, 15
and 60 minutes, then every 3 hours, until 24 hours after the row was made. Messages to one person leave in order: a
row is not sent while an earlier row for the same person is still waiting. The number and the message are cleared
once the row is sent or dismissed.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from app.store.db import ts, tx

BACKOFF_S = (60, 300, 900, 3600)
LATER_S = 3 * 3600
LIFETIME = timedelta(hours=24)
LEASE_SECONDS = 120  # a row in `sending` this long belongs to a worker that died
State = Literal["queued", "sending", "sent", "failed", "dismissed"]

_DDL = (
    "CREATE TABLE IF NOT EXISTS outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, dedupe_key TEXT NOT NULL UNIQUE, "
    "kind TEXT NOT NULL, recipient TEXT NOT NULL, address TEXT, message TEXT, template TEXT, ticket TEXT, "
    "message_id INTEGER, state TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0, "
    "next_attempt_at TEXT, last_error TEXT, note TEXT, wamid TEXT, deadline TEXT NOT NULL, claimed_at TEXT, "
    "created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)",
    "CREATE INDEX IF NOT EXISTS idx_outbox_due ON outbox(state, next_attempt_at)",
    "CREATE INDEX IF NOT EXISTS idx_outbox_recipient ON outbox(recipient, state, id)",
    "CREATE INDEX IF NOT EXISTS idx_outbox_wamid ON outbox(wamid) WHERE wamid IS NOT NULL",
)
_COLUMNS = ("id, dedupe_key, kind, recipient, address, message, template, ticket, message_id, state, attempts, "
            "last_error, note, wamid, deadline")


@dataclass(frozen=True)
class NewItem:
    dedupe_key: str
    kind: str  # reply | staff | status | request | reminder | notice | code
    recipient: str  # the pseudonymous user key (wa:...), never the number
    address: str | None  # the WhatsApp number; None when it must not be stored (one-time codes)
    message: dict[str, Any] | None  # an Outbound (app/core/messages.py) as JSON; None for a template-only row
    template: dict[str, Any] | None = None  # {"name", "language", "params", "button"} for outside the 24 h window
    ticket: str | None = None
    message_id: int | None = None  # the complaint thread message this delivers
    lifetime: timedelta = LIFETIME


@dataclass(frozen=True)
class Row:
    id: int
    dedupe_key: str
    kind: str
    recipient: str
    address: str | None
    message: dict[str, Any] | None
    template: dict[str, Any] | None
    ticket: str | None
    message_id: int | None
    state: State
    attempts: int
    last_error: str | None
    note: str | None
    wamid: str | None
    deadline: str


def ensure(conn: Any) -> None:
    for statement in _DDL:
        conn.execute(statement)


def _row(found: Any) -> Row:
    data = dict(found)
    for key in ("message", "template"):
        data[key] = json.loads(data[key]) if data[key] else None
    return Row(**data)


def put(item: NewItem, now: datetime | None = None) -> Row:
    """The row for this dedupe key: a new queued one, or the one already there, whatever its state."""
    moment = now or datetime.now(UTC)
    with tx() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO outbox (dedupe_key, kind, recipient, address, message, template, ticket, message_id, "
            "deadline, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item.dedupe_key, item.kind, item.recipient, item.address,
             json.dumps(item.message, ensure_ascii=False) if item.message else None,
             json.dumps(item.template, ensure_ascii=False) if item.template else None, item.ticket, item.message_id,
             ts(moment + item.lifetime), ts(moment), ts(moment)))
        return _row(conn.execute(f"SELECT {_COLUMNS} FROM outbox WHERE dedupe_key = ?", (item.dedupe_key,)).fetchone())


def get(row_id: int) -> Row | None:
    with tx() as conn:
        found = conn.execute(f"SELECT {_COLUMNS} FROM outbox WHERE id = ?", (row_id,)).fetchone()
    return _row(found) if found else None


def claim(row_id: int, now: datetime | None = None) -> Row | None:
    """Take a queued row for sending, unless an earlier row for the same person is still waiting."""
    with tx(immediate=True) as conn:
        found = conn.execute(
            f"UPDATE outbox SET state = 'sending', claimed_at = ? WHERE id = ? AND state = 'queued' AND NOT EXISTS ("
            "  SELECT 1 FROM outbox o WHERE o.recipient = outbox.recipient AND o.id < outbox.id "
            f"  AND o.state IN ('queued', 'sending')) RETURNING {_COLUMNS}", (ts(now), row_id)).fetchone()
    return _row(found) if found else None


def _finish(row_id: int, state: State, note: str | None, error: str | None, wamid: str | None,
            now: datetime | None) -> Row:
    """Sent and dismissed rows give up the number and the message; failed rows keep them for a staff retry."""
    clear = ", address = NULL, message = NULL, template = NULL" if state in ("sent", "dismissed") else ""
    with tx() as conn:
        found = conn.execute(
            f"UPDATE outbox SET state = ?, note = ?, last_error = COALESCE(?, last_error), wamid = COALESCE(?, wamid), "
            f"claimed_at = NULL, next_attempt_at = NULL, updated_at = ?{clear} WHERE id = ? RETURNING {_COLUMNS}",
            (state, note, error, wamid, ts(now), row_id)).fetchone()
    return _row(found)


def sent(row_id: int, wamid: str | None, note: str | None, now: datetime | None = None) -> Row:
    return _finish(row_id, "sent", note, None, wamid, now)


def failed(row_id: int, error: str, note: str, now: datetime | None = None) -> Row:
    with tx() as conn:
        conn.execute("UPDATE outbox SET attempts = attempts + 1 WHERE id = ?", (row_id,))
    return _finish(row_id, "failed", note, error[:80], None, now)


def later(row_id: int, error: str, note: str, gave_up_note: str, now: datetime | None = None) -> Row:
    """A passing failure: queued for the next slot on the backoff, or failed when that is past the deadline."""
    moment = now or datetime.now(UTC)
    with tx() as conn:
        attempts, deadline = conn.execute("UPDATE outbox SET attempts = attempts + 1 WHERE id = ? "
                                          "RETURNING attempts, deadline", (row_id,)).fetchone()
    wait = BACKOFF_S[attempts - 1] if attempts <= len(BACKOFF_S) else LATER_S
    retry_at = ts(moment + timedelta(seconds=wait))
    if retry_at > deadline:
        return _finish(row_id, "failed", gave_up_note, error[:80], None, now)
    with tx() as conn:
        found = conn.execute(
            f"UPDATE outbox SET state = 'queued', note = ?, last_error = ?, claimed_at = NULL, next_attempt_at = ?, "
            f"updated_at = ? WHERE id = ? RETURNING {_COLUMNS}", (note, error[:80], retry_at, ts(moment), row_id)
        ).fetchone()
    return _row(found)


def due(now: datetime | None = None, limit: int = 200) -> list[int]:
    with tx() as conn:
        return [r[0] for r in conn.execute(
            "SELECT id FROM outbox WHERE state = 'queued' AND COALESCE(next_attempt_at, '') <= ? ORDER BY id LIMIT ?",
            (ts(now), limit))]


def requeue_stuck(now: datetime | None = None) -> list[int]:
    moment = now or datetime.now(UTC)
    with tx() as conn:
        return [r[0] for r in conn.execute(
            "UPDATE outbox SET state = 'queued', claimed_at = NULL WHERE state = 'sending' AND claimed_at <= ? "
            "RETURNING id", (ts(moment - timedelta(seconds=LEASE_SECONDS)),))]


def by_wamid(wamid: str) -> Row | None:
    with tx() as conn:
        found = conn.execute(f"SELECT {_COLUMNS} FROM outbox WHERE wamid = ? ORDER BY id DESC LIMIT 1",
                             (wamid,)).fetchone()
    return _row(found) if found else None


def retry(row_id: int, now: datetime | None = None) -> bool:
    """A parked row goes back to the queue, due now, with a fresh 24 hours. False when it has nothing to send."""
    moment = now or datetime.now(UTC)
    with tx() as conn:
        return conn.execute(
            "UPDATE outbox SET state = 'queued', next_attempt_at = NULL, deadline = ?, updated_at = ? "
            "WHERE id = ? AND state = 'failed' AND address IS NOT NULL", (ts(moment + LIFETIME), ts(moment), row_id)
        ).rowcount == 1


def dismiss(row_id: int, now: datetime | None = None) -> bool:
    with tx() as conn:
        exists = conn.execute("SELECT 1 FROM outbox WHERE id = ? AND state = 'failed'", (row_id,)).fetchone()
    if not exists:
        return False
    _finish(row_id, "dismissed", None, None, None, now)
    return True


def counts() -> tuple[int, int, str | None]:
    """(queued or sending, failed, oldest waiting created_at)."""
    with tx() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(state IN ('queued', 'sending')), 0), COALESCE(SUM(state = 'failed'), 0), "
            "MIN(CASE WHEN state IN ('queued', 'sending') THEN created_at END) FROM outbox").fetchone()
    return row[0], row[1], row[2]
