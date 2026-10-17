"""One-time codes for getting a bill by service number. Only a hash of the code is stored, keyed by the account and
the hashed service number, with its expiry, the wrong attempts so far and any lock."""

from typing import Any

from app.store.db import tx


def get(user_id: str, discom: str, service_hash: str) -> dict[str, Any] | None:
    with tx() as conn:
        row = conn.execute("SELECT code_hash, expires_at, attempts, locked_until FROM usc_codes WHERE user_id = ? "
                           "AND discom = ? AND service_hash = ?", (user_id, discom, service_hash)).fetchone()
    return dict(row) if row else None


def put(user_id: str, discom: str, service_hash: str, code_hash: str, expires_at: str) -> None:
    """A new code replaces the old one and resets the attempts. Never called while the row is locked."""
    with tx() as conn:
        conn.execute("INSERT INTO usc_codes (user_id, discom, service_hash, code_hash, expires_at) VALUES (?, ?, ?, ?, ?) "
                     "ON CONFLICT(user_id, discom, service_hash) DO UPDATE SET code_hash = excluded.code_hash, "
                     "expires_at = excluded.expires_at, attempts = 0, locked_until = NULL, "
                     "created_at = CURRENT_TIMESTAMP", (user_id, discom, service_hash, code_hash, expires_at))


def failed(user_id: str, discom: str, service_hash: str, max_attempts: int, locked_until: str) -> bool:
    """Count a wrong code. Returns True when this attempt used up the last one and the row is now locked."""
    with tx() as conn:
        conn.execute("UPDATE usc_codes SET attempts = attempts + 1, locked_until = CASE WHEN attempts + 1 >= ? "
                     "THEN ? ELSE locked_until END WHERE user_id = ? AND discom = ? AND service_hash = ?",
                     (max_attempts, locked_until, user_id, discom, service_hash))
        row = conn.execute("SELECT attempts FROM usc_codes WHERE user_id = ? AND discom = ? AND service_hash = ?",
                           (user_id, discom, service_hash)).fetchone()
    return bool(row and row[0] >= max_attempts)


def used(user_id: str, discom: str, service_hash: str) -> None:
    """A code works once."""
    with tx() as conn:
        conn.execute("DELETE FROM usc_codes WHERE user_id = ? AND discom = ? AND service_hash = ?",
                     (user_id, discom, service_hash))
