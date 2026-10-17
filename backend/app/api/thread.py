"""What staff see of a complaint's conversation: messages with their photos, and requests with the message that
answered each. Photo links point at the complaint's own media route, so a file opens only for staff who can see the
complaint (app/api/complaint_actions.py)."""

from typing import Any, Literal

from pydantic import BaseModel

from app.domain.complaint_reply import RequestKind
from app.flows.complaint import PHOTO_NOTE
from app.flows.evidence import staff_media as media_url
from app.store import complaints, media
from app.store import review as review_store


def media_type(media_id: str | None) -> str | None:
    return media.mime_for(media_id) if media_id else None


class ComplaintMessage(BaseModel):
    id: int
    author_kind: Literal["consumer", "officer", "system"]
    author_name: str | None
    body: str
    created_at: str
    delivery: Literal["sent", "failed", "stored"]
    delivery_note: str | None
    media_url: str | None
    media_type: str | None


class RequestAnswer(BaseModel):
    message_id: int
    media_url: str | None
    media_type: str | None
    body: str | None  # null when the answer is a photo sent without words
    at: str


class RequestOut(BaseModel):
    id: int
    kind: RequestKind
    note: str | None
    status: Literal["open", "answered"]
    created_at: str
    answered_at: str | None
    answer: RequestAnswer | None


def messages(ticket: str) -> list[ComplaintMessage]:
    return [ComplaintMessage(**{k: v for k, v in m.items() if k != "media_id"},
                             media_url=media_url(ticket, m["media_id"]), media_type=media_type(m["media_id"]))
            for m in complaints.messages(ticket)]


def _answer(ticket: str, row: dict[str, Any]) -> RequestAnswer | None:
    if row["answer_id"] is None:
        return None
    body = None if row["answer_media_id"] and row["answer_body"] == PHOTO_NOTE else row["answer_body"]
    return RequestAnswer(message_id=row["answer_id"], media_url=media_url(ticket, row["answer_media_id"]),
                         media_type=media_type(row["answer_media_id"]), body=body, at=row["answer_at"])


def requests(ticket: str) -> list[RequestOut]:
    """Newest first."""
    return [RequestOut(id=r["id"], kind=r["kind"], note=r["note"], status=r["status"], created_at=r["created_at"],
                       answered_at=r["answered_at"], answer=_answer(ticket, r))
            for r in review_store.requests(ticket)]
