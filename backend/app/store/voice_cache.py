"""What costs money to make once: voice notes by their exact text, and the language model's bill explanation
by the bill's figures. In the database, so every worker and instance shares one cache and a write is never lost.

Neither table holds a name, number or address: keys are hashes, explanations carry only bill figures. Rows go with
the retention sweep, and a consumer's explanations go when they erase their account.
"""

import json
from typing import Any

from app.config import get_settings
from app.store.db import tx

_DDL = (
    "CREATE TABLE IF NOT EXISTS tts_cache (key TEXT PRIMARY KEY, media_ids TEXT NOT NULL, "
    "created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
    "CREATE TABLE IF NOT EXISTS explain_cache (key TEXT PRIMARY KEY, user_id TEXT NOT NULL, text TEXT NOT NULL, "
    "created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
    "CREATE INDEX IF NOT EXISTS idx_explain_cache_user ON explain_cache(user_id)",
)


def ensure(conn: Any) -> None:
    for statement in _DDL:
        conn.execute(statement)
    # The cache used to be a JSON file beside the database; its entries move over once, so nothing is paid twice.
    legacy = get_settings().data_dir / "tts_index.json"
    if legacy.exists():
        entries = json.loads(legacy.read_text() or "{}")
        conn.executemany("INSERT OR IGNORE INTO tts_cache (key, media_ids) VALUES (?, ?)",
                         [(k, json.dumps(v)) for k, v in entries.items() if isinstance(v, list)])
        legacy.rename(legacy.with_suffix(".json.moved"))


def voice(key: str) -> list[str] | None:
    with tx() as conn:
        row = conn.execute("SELECT media_ids FROM tts_cache WHERE key = ?", (key,)).fetchone()
    return list(json.loads(row[0])) if row else None


def remember_voice(key: str, media_ids: list[str]) -> None:
    # A newer clip replaces one whose files the retention sweep removed.
    with tx() as conn:
        conn.execute("INSERT INTO tts_cache (key, media_ids) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET "
                     "media_ids = excluded.media_ids, created_at = CURRENT_TIMESTAMP", (key, json.dumps(media_ids)))


def explanation(key: str) -> str | None:
    with tx() as conn:
        row = conn.execute("SELECT text FROM explain_cache WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def remember_explanation(key: str, user_id: str, text: str) -> None:
    with tx() as conn:
        conn.execute("INSERT OR IGNORE INTO explain_cache (key, user_id, text) VALUES (?, ?, ?)", (key, user_id, text))


def sweep(conn: Any, days: int) -> None:
    for table in ("tts_cache", "explain_cache"):
        conn.execute(f"DELETE FROM {table} WHERE created_at < datetime('now', ?)", (f"-{days} days",))


def erase(conn: Any, user_id: str) -> None:
    conn.execute("DELETE FROM explain_cache WHERE user_id = ?", (user_id,))
