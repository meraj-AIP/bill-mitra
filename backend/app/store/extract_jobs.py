"""Bill photos whose read failed for a passing reason (provider down, timeout, rate limit), kept and read again
(docs/reliability-contract.md section 4). The only SQL for extract jobs; app/flows/extract.py runs them.

Making the job counts as the first failed try. It is tried again after 1, 5 and 15 minutes; after MAX_ATTEMPTS it is
parked as `failed`. The WhatsApp number is held only while the job is open.
"""

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from app.store.db import ts, tx

BACKOFF_S = (60, 300, 900)
MAX_ATTEMPTS = 4
LEASE_SECONDS = 600  # a read takes up to about two minutes with its retries; longer means the worker died
Channel = Literal["whatsapp", "dashboard"]
State = Literal["queued", "running", "done", "failed", "dismissed"]

_DDL = (
    "CREATE TABLE IF NOT EXISTS extract_jobs (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, channel TEXT NOT NULL, "
    "media_id TEXT NOT NULL, mime TEXT NOT NULL, language TEXT NOT NULL, address TEXT, "
    "state TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 1, next_attempt_at TEXT, last_error TEXT, "
    "claimed_at TEXT, bill_id TEXT, result TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT)",
    "CREATE INDEX IF NOT EXISTS idx_extract_due ON extract_jobs(state, next_attempt_at)",
    "CREATE INDEX IF NOT EXISTS idx_extract_user ON extract_jobs(user_id)",
)
_COLUMNS = "id, user_id, channel, media_id, mime, language, address, state, attempts, bill_id, result"


@dataclass(frozen=True)
class Job:
    id: str
    user_id: str
    channel: Channel
    media_id: str
    mime: str
    language: str
    address: str | None
    state: State
    attempts: int
    bill_id: str | None
    result: dict[str, Any] | None  # the dashboard report when the read ended without a saved bill

    @property
    def last_try(self) -> bool:
        return self.attempts + 1 >= MAX_ATTEMPTS


def ensure(conn: Any) -> None:
    for statement in _DDL:
        conn.execute(statement)


def _job(found: Any) -> Job:
    data = dict(found)
    data["result"] = json.loads(data["result"]) if data["result"] else None
    return Job(**data)


def create(user_id: str, channel: Channel, media_id: str, mime: str, language: str, address: str | None,
           error: str, now: datetime | None = None) -> Job:
    moment = now or datetime.now(UTC)
    job_id = secrets.token_urlsafe(12)
    with tx() as conn:
        found = conn.execute(
            "INSERT INTO extract_jobs (id, user_id, channel, media_id, mime, language, address, next_attempt_at, "
            f"last_error, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING {_COLUMNS}",
            (job_id, user_id, channel, media_id, mime, language, address,
             ts(moment + timedelta(seconds=BACKOFF_S[0])), error[:80], ts(moment), ts(moment))).fetchone()
    return _job(found)


def get_own(user_id: str, job_id: str) -> Job | None:
    """Only for the account that made it."""
    with tx() as conn:
        found = conn.execute(f"SELECT {_COLUMNS} FROM extract_jobs WHERE id = ? AND user_id = ?",
                             (job_id, user_id)).fetchone()
    return _job(found) if found else None


def claim_due(now: datetime | None = None, limit: int = 20) -> list[Job]:
    with tx(immediate=True) as conn:
        rows = conn.execute(
            "UPDATE extract_jobs SET state = 'running', claimed_at = ? WHERE id IN (SELECT id FROM extract_jobs "
            "WHERE state = 'queued' AND COALESCE(next_attempt_at, '') <= ? ORDER BY created_at LIMIT ?) "
            f"RETURNING {_COLUMNS}", (ts(now), ts(now), limit)).fetchall()
    return [_job(r) for r in rows]


def finish(job_id: str, state: Literal["done", "failed"], bill_id: str | None, result: dict[str, Any] | None,
           error: str | None = None, now: datetime | None = None) -> None:
    """Done or parked. The number is dropped either way; a parked job has already told the consumer."""
    with tx() as conn:
        conn.execute("UPDATE extract_jobs SET state = ?, bill_id = ?, result = ?, last_error = COALESCE(?, last_error), "
                     "claimed_at = NULL, next_attempt_at = NULL, address = NULL, updated_at = ? WHERE id = ?",
                     (state, bill_id, json.dumps(result, ensure_ascii=False) if result else None,
                      error[:80] if error else None, ts(now), job_id))


def later(job_id: str, error: str, now: datetime | None = None) -> None:
    """Another passing failure, while tries remain: back in the queue for the next slot."""
    moment = now or datetime.now(UTC)
    with tx() as conn:
        attempts = conn.execute("UPDATE extract_jobs SET attempts = attempts + 1 WHERE id = ? RETURNING attempts",
                                (job_id,)).fetchone()[0]
        wait = BACKOFF_S[min(attempts, len(BACKOFF_S)) - 1]
        conn.execute("UPDATE extract_jobs SET state = 'queued', claimed_at = NULL, last_error = ?, next_attempt_at = ?, "
                     "updated_at = ? WHERE id = ?",
                     (error[:80], ts(moment + timedelta(seconds=wait)), ts(moment), job_id))


def requeue_stuck(now: datetime | None = None) -> list[str]:
    moment = now or datetime.now(UTC)
    with tx() as conn:
        return [r[0] for r in conn.execute(
            "UPDATE extract_jobs SET state = 'queued', claimed_at = NULL WHERE state = 'running' AND claimed_at <= ? "
            "RETURNING id", (ts(moment - timedelta(seconds=LEASE_SECONDS)),))]


def retry(job_id: str) -> bool:
    """A parked dashboard job goes back to the queue, due now, with one try left. A WhatsApp job cannot: its number
    is gone, and the consumer was already asked to type the units."""
    with tx() as conn:
        return conn.execute(
            "UPDATE extract_jobs SET state = 'queued', next_attempt_at = NULL, attempts = ?, result = NULL, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ? AND state = 'failed' AND channel = 'dashboard'",
            (MAX_ATTEMPTS - 1, job_id)).rowcount == 1


def dismiss(job_id: str) -> bool:
    with tx() as conn:
        return conn.execute("UPDATE extract_jobs SET state = 'dismissed', address = NULL, "
                            "updated_at = CURRENT_TIMESTAMP WHERE id = ? AND state = 'failed'", (job_id,)).rowcount == 1


def counts() -> tuple[int, int, str | None]:
    with tx() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(state IN ('queued', 'running')), 0), COALESCE(SUM(state = 'failed'), 0), "
            "MIN(CASE WHEN state IN ('queued', 'running') THEN created_at END) FROM extract_jobs").fetchone()
    return row[0], row[1], row[2]
