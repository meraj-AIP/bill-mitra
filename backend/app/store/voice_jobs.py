"""Voice notes that were not ready while the turn waited: the words went as text, and the note follows when Soniox
has made it (docs/reliability-contract.md). The only SQL for voice jobs; app/flows/voice.py runs them.

The first try comes FIRST_WAIT_S after the turn, so a clip the turn left still being made is usually in the cache by
then. Later tries wait 1, 5 and 15 minutes; after MAX_ATTEMPTS the job is parked as `failed` and nothing more is sent,
because the consumer already has the words. The script holds bill figures only, and the WhatsApp number is held only
while the job is open.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from app.store.db import ts, tx

FIRST_WAIT_S = 30
BACKOFF_S = (60, 300, 900)
MAX_ATTEMPTS = 4
LEASE_SECONDS = 300  # one note takes well under a minute with its retries; longer means the worker died
Channel = Literal["whatsapp", "web"]

_DDL = (
    "CREATE TABLE IF NOT EXISTS voice_jobs (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, channel TEXT NOT NULL, "
    "address TEXT, language TEXT NOT NULL, script TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'queued', "
    "attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT, last_error TEXT, claimed_at TEXT, "
    "created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT)",
    "CREATE INDEX IF NOT EXISTS idx_voice_due ON voice_jobs(state, next_attempt_at)",
    "CREATE INDEX IF NOT EXISTS idx_voice_user ON voice_jobs(user_id)",
)
_COLUMNS = "id, user_id, channel, address, language, script, attempts"


@dataclass(frozen=True)
class Job:
    id: str
    user_id: str
    channel: Channel
    address: str | None
    language: str
    script: str
    attempts: int


def ensure(conn: Any) -> None:
    for statement in _DDL:
        conn.execute(statement)


def create(user_id: str, channel: Channel, address: str | None, language: str, script: str,
           now: datetime | None = None) -> str | None:
    """The job id, or None when the same note is already on its way to this person."""
    moment = now or datetime.now(UTC)
    with tx(immediate=True) as conn:
        if conn.execute("SELECT 1 FROM voice_jobs WHERE user_id = ? AND language = ? AND script = ? AND state IN "
                        "('queued', 'running')", (user_id, language, script)).fetchone():
            return None
        job_id = secrets.token_urlsafe(12)
        conn.execute("INSERT INTO voice_jobs (id, user_id, channel, address, language, script, next_attempt_at, "
                     "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (job_id, user_id, channel, address, language, script,
                      ts(moment + timedelta(seconds=FIRST_WAIT_S)), ts(moment), ts(moment)))
    return job_id


def claim_due(now: datetime | None = None, limit: int = 10) -> list[Job]:
    with tx(immediate=True) as conn:
        rows = conn.execute(
            "UPDATE voice_jobs SET state = 'running', claimed_at = ? WHERE id IN (SELECT id FROM voice_jobs "
            "WHERE state = 'queued' AND COALESCE(next_attempt_at, '') <= ? ORDER BY created_at LIMIT ?) "
            f"RETURNING {_COLUMNS}", (ts(now), ts(now), limit)).fetchall()
    return [Job(**dict(r)) for r in rows]


def done(job_id: str, now: datetime | None = None) -> None:
    with tx() as conn:
        conn.execute("UPDATE voice_jobs SET state = 'done', address = NULL, claimed_at = NULL, next_attempt_at = NULL, "
                     "updated_at = ? WHERE id = ?", (ts(now), job_id))


def later(job_id: str, error: str, now: datetime | None = None) -> bool:
    """Another failed try: back in the queue for the next slot, or parked after the last. True when parked."""
    moment = now or datetime.now(UTC)
    with tx() as conn:
        attempts = conn.execute("UPDATE voice_jobs SET attempts = attempts + 1, last_error = ?, claimed_at = NULL, "
                                "updated_at = ? WHERE id = ? RETURNING attempts",
                                (error[:80], ts(moment), job_id)).fetchone()[0]
        if attempts >= MAX_ATTEMPTS:
            conn.execute("UPDATE voice_jobs SET state = 'failed', address = NULL, next_attempt_at = NULL WHERE id = ?",
                         (job_id,))
            return True
        wait = BACKOFF_S[min(attempts, len(BACKOFF_S)) - 1]
        conn.execute("UPDATE voice_jobs SET state = 'queued', next_attempt_at = ? WHERE id = ?",
                     (ts(moment + timedelta(seconds=wait)), job_id))
    return False


def requeue_stuck(now: datetime | None = None) -> list[str]:
    moment = now or datetime.now(UTC)
    with tx() as conn:
        return [r[0] for r in conn.execute(
            "UPDATE voice_jobs SET state = 'queued', claimed_at = NULL WHERE state = 'running' AND claimed_at <= ? "
            "RETURNING id", (ts(moment - timedelta(seconds=LEASE_SECONDS)),))]


def erase(conn: Any, user_id: str) -> None:
    conn.execute("DELETE FROM voice_jobs WHERE user_id = ?", (user_id,))


def sweep(conn: Any, days: int) -> None:
    conn.execute("DELETE FROM voice_jobs WHERE state IN ('done', 'failed') AND created_at < datetime('now', ?)",
                 (f"-{days} days",))
