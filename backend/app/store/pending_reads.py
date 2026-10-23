"""What the chat holds between a failed read and the person's next tap: the bill whose units they are choosing, the
message to try again, or a meter reading waiting for its bill. One row per person, kept for a day, erased with their
data. The bill held here is the same extraction the bills table keeps; nothing else about the person is stored."""

import json
from typing import Any

from app.store.db import tx

MAX_AGE = "-1 day"
_DDL = ("CREATE TABLE IF NOT EXISTS pending_reads (user_id TEXT PRIMARY KEY, data TEXT NOT NULL, "
        "updated_at TEXT DEFAULT CURRENT_TIMESTAMP)",)


def ensure(conn: Any) -> None:
    for statement in _DDL:
        conn.execute(statement)


def _load(conn: Any, user_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT data FROM pending_reads WHERE user_id = ? AND updated_at > datetime('now', ?)",
                       (user_id, MAX_AGE)).fetchone()
    return dict(json.loads(row[0])) if row else {}


def put(user_id: str, key: str, value: Any) -> None:
    with tx(immediate=True) as conn:
        data = {**_load(conn, user_id), key: value}
        conn.execute("INSERT INTO pending_reads (user_id, data) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE "
                     "SET data = excluded.data, updated_at = CURRENT_TIMESTAMP", (user_id, json.dumps(data)))


def peek(user_id: str, key: str) -> Any:
    with tx() as conn:
        return _load(conn, user_id).get(key)


def take(user_id: str, key: str) -> Any:
    """The value, removed so a second tap on the same button cannot use it again. None when there is none."""
    with tx(immediate=True) as conn:
        data = _load(conn, user_id)
        value = data.pop(key, None)
        if value is not None:
            conn.execute("UPDATE pending_reads SET data = ? WHERE user_id = ?", (json.dumps(data), user_id))
    return value


def sweep(conn: Any) -> None:
    conn.execute("DELETE FROM pending_reads WHERE updated_at < datetime('now', ?)", (MAX_AGE,))
