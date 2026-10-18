"""DPDP Act 2023: erasing a consumer on request and keeping data no longer than the stated retention period.

Complaints are the department's record, so they stay; only the consumer's WhatsApp address is cut from them.
"""

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from app.config import get_settings
from app.store import media, repos, voice_cache
from app.store.db import tx

log = logging.getLogger(__name__)

SEEN_DAYS = 7  # Meta stops retrying a webhook long before this


def erase_account(account_id: str, user_id: str) -> None:
    """Delete the consumer's bills, chat state and sessions, and leave an account row nobody can sign in to."""
    with tx() as conn:
        used = repos.erase_chat(conn, user_id)
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        voice_cache.erase(conn, user_id)
        conn.execute("DELETE FROM sessions WHERE account_id = ?", (account_id,))
        # Not a valid scrypt record, so no password can ever match it.
        conn.execute("UPDATE accounts SET active = 0, login = ?, name = 'Deleted account', password_hash = ?, "
                     "failed_logins = 0, locked_until = NULL WHERE id = ?",
                     (f"deleted:{account_id}", f"erased${secrets.token_hex(16)}", account_id))
    media.discard_unreferenced(used)


@dataclass(frozen=True)
class SweepResult:
    sessions: int
    whatsapp_seen: int
    bills: int
    media: int


def sweep() -> SweepResult:
    """Drop what has outlived its purpose. A bill an open or closed complaint points at is kept with that record."""
    days = get_settings().retention_days
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    with tx() as conn:
        sessions = conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,)).rowcount
        seen = conn.execute("DELETE FROM whatsapp_seen WHERE ts < datetime('now', ?)",
                            (f"-{SEEN_DAYS} days",)).rowcount
        old = conn.execute("SELECT id, media_id FROM bills WHERE created_at < datetime('now', ?) AND id NOT IN "
                           "(SELECT bill_id FROM complaints WHERE bill_id IS NOT NULL)", (f"-{days} days",)).fetchall()
        conn.executemany("DELETE FROM bills WHERE id = ?", [(r["id"],) for r in old])
        conn.execute("DELETE FROM chat_messages WHERE ts < datetime('now', ?)", (f"-{days} days",))
        voice_cache.sweep(conn, days)
        conn.execute("UPDATE users SET current_bill_id = NULL WHERE current_bill_id IS NOT NULL AND "
                     "current_bill_id NOT IN (SELECT id FROM bills)")
    files = media.discard_unreferenced(r["media_id"] for r in old) + media.discard_stale(days)
    result = SweepResult(sessions=sessions, whatsapp_seen=seen, bills=len(old), media=files)
    log.info("retention sweep removed %d sessions, %d webhook ids, %d bills, %d media files",
             result.sessions, result.whatsapp_seen, result.bills, result.media)
    return result
