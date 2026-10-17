"""A complaint the consumer is putting together in the chat, one message at a time. Holds a typed service number
until the complaint is sent or cancelled, then it is deleted. A draft left for a day is treated as gone."""

import json
from typing import Any

from app.store.db import tx

MAX_AGE = "-1 day"


def get(user_id: str) -> dict[str, Any] | None:
    with tx() as conn:
        row = conn.execute("SELECT data FROM chat_drafts WHERE user_id = ? AND updated_at > datetime('now', ?)",
                           (user_id, MAX_AGE)).fetchone()
    return json.loads(row[0]) if row else None


def save(user_id: str, data: dict[str, Any]) -> None:
    with tx() as conn:
        conn.execute("INSERT INTO chat_drafts (user_id, data) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE "
                     "SET data = excluded.data, updated_at = CURRENT_TIMESTAMP", (user_id, json.dumps(data)))


def drop(user_id: str) -> None:
    with tx() as conn:
        conn.execute("DELETE FROM chat_drafts WHERE user_id = ?", (user_id,))
