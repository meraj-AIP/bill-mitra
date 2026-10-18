"""The conversation as the person saw it: what they sent and what Bill Mitra answered, kept with their account.

Stored per channel user (acct:<id> or wa:<hash>), erased with STOP, account deletion and the retention sweep.
The WhatsApp number is never part of a stored message.
"""

import json
from typing import Any, Literal

from pydantic import BaseModel

from app.core.messages import Inbound
from app.store.db import tx

MAX_PAGE = 100


class ChatItem(BaseModel):
    id: int
    at: str
    sender: Literal["user", "bot"]
    body: dict[str, Any]


class ChatPage(BaseModel):
    items: list[ChatItem]  # oldest first
    has_more: bool


def record_in(inbound: Inbound) -> int:
    body = inbound.model_dump(include={"kind", "text", "reply_id", "media_id", "mime_type"}, exclude_none=True)
    with tx() as conn:
        return int(conn.execute("INSERT INTO chat_messages (user_id, sender, body) VALUES (?, 'user', ?) RETURNING id",
                                (inbound.user_id, json.dumps(body, ensure_ascii=False))).fetchall()[0][0])

def record_out(user_id: str, message: dict[str, Any]) -> None:
    with tx() as conn:
        conn.execute("INSERT INTO chat_messages (user_id, sender, body) VALUES (?, 'bot', ?)",
                     (user_id, json.dumps(message, ensure_ascii=False)))


def add_transcript(message_id: int, text: str) -> None:
    """A voice note's words arrive after it is stored; keep them with it so the history reads back."""
    with tx() as conn:
        row = conn.execute("SELECT body FROM chat_messages WHERE id = ?", (message_id,)).fetchone()
        if row is None:
            return
        body = {**json.loads(row["body"]), "transcript": text}
        conn.execute("UPDATE chat_messages SET body = ? WHERE id = ?", (json.dumps(body, ensure_ascii=False), message_id))


def page(user_id: str, before: int | None, limit: int) -> ChatPage:
    """The newest `limit` messages before `before`, returned oldest first so the client can prepend them."""
    limit = max(1, min(limit, MAX_PAGE))
    with tx() as conn:
        rows = conn.execute("SELECT id, ts, sender, body FROM chat_messages WHERE user_id = ? AND (? IS NULL OR id < ?) "
                            "ORDER BY id DESC LIMIT ?", (user_id, before, before, limit + 1)).fetchall()
    newest_first = [ChatItem(id=r["id"], at=r["ts"], sender=r["sender"], body=json.loads(r["body"])) for r in rows]
    return ChatPage(items=list(reversed(newest_first[:limit])), has_more=len(rows) > limit)


def last_inbound(user_id: str) -> str | None:
    """When the person last wrote, so a send can tell whether WhatsApp's 24 hour window is still open."""
    with tx() as conn:
        row = conn.execute("SELECT MAX(ts) FROM chat_messages WHERE user_id = ? AND sender = 'user'",
                           (user_id,)).fetchone()
    return row[0] if row else None
