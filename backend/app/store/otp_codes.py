"""One-time sign in codes, keyed by what they are for and a hash of the mobile. Only a hash of the code is kept, with
its expiry, the wrong tries so far and any lock. A code works once."""

from typing import Any

from app.store.db import tx

_DDL = ("CREATE TABLE IF NOT EXISTS otp_codes (purpose TEXT NOT NULL, mobile_hash TEXT NOT NULL, code_hash TEXT NOT NULL, "
        "expires_at TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, locked_until TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (purpose, mobile_hash))",)


def ensure(conn: Any) -> None:
    for statement in _DDL:
        conn.execute(statement)


def get(purpose: str, mobile_hash: str) -> dict[str, Any] | None:
    with tx() as conn:
        row = conn.execute("SELECT code_hash, expires_at, attempts, locked_until, created_at FROM otp_codes "
                           "WHERE purpose = ? AND mobile_hash = ?", (purpose, mobile_hash)).fetchone()
    return dict(row) if row else None


def put(purpose: str, mobile_hash: str, code_hash: str, expires_at: str) -> None:
    """A new code replaces the old one and resets the tries. Never called while the row is locked."""
    with tx() as conn:
        conn.execute("INSERT INTO otp_codes (purpose, mobile_hash, code_hash, expires_at) VALUES (?, ?, ?, ?) "
                     "ON CONFLICT(purpose, mobile_hash) DO UPDATE SET code_hash = excluded.code_hash, "
                     "expires_at = excluded.expires_at, attempts = 0, locked_until = NULL, created_at = CURRENT_TIMESTAMP",
                     (purpose, mobile_hash, code_hash, expires_at))


def failed(purpose: str, mobile_hash: str, max_attempts: int, locked_until: str) -> bool:
    """Count a wrong code. True when that was the last try and the row is now locked."""
    with tx() as conn:
        conn.execute("UPDATE otp_codes SET attempts = attempts + 1, locked_until = CASE WHEN attempts + 1 >= ? THEN ? "
                     "ELSE locked_until END WHERE purpose = ? AND mobile_hash = ?",
                     (max_attempts, locked_until, purpose, mobile_hash))
        row = conn.execute("SELECT attempts FROM otp_codes WHERE purpose = ? AND mobile_hash = ?",
                           (purpose, mobile_hash)).fetchone()
    return bool(row and row[0] >= max_attempts)


def used(purpose: str, mobile_hash: str) -> None:
    with tx() as conn:
        conn.execute("DELETE FROM otp_codes WHERE purpose = ? AND mobile_hash = ?", (purpose, mobile_hash))


def sweep() -> int:
    """Codes past their expiry and any lock are of no use; the retention sweep drops them."""
    with tx() as conn:
        return conn.execute("DELETE FROM otp_codes WHERE expires_at < CURRENT_TIMESTAMP AND "
                            "(locked_until IS NULL OR locked_until < CURRENT_TIMESTAMP)").rowcount
