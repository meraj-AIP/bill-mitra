"""Complaint types (public) and a consumer's own complaints on the web: raise, list, read, answer a question.

The consumer view is neutral: statuses in plain words and every staff message shown as from Bill Mitra.
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.api.deps import require_perm
from app.core.hashing import clean_service_number
from app.core.ratelimit import per_ip
from app.core.uploads import DOCUMENTS, read_checked
from app.domain import complaint_types
from app.domain.complaint_types import Category, Priority, Route, TypeCode
from app.domain.conversation.lang import text
from app.flows import intake
from app.flows.complaint import PHOTO_NOTE
from app.store import complaints, handoffs, media, repos
from app.store import consumer_complaints as store
from app.store import review as review_store
from app.store.accounts import Account

router = APIRouter(tags=["complaints"])

Language = Literal["te", "en", "hi", "ur"]
Discom = Literal["TGSPDCL", "TGNPDCL"]
State = Literal["received", "in_progress", "waiting_for_you", "resolved", "closed"]
Text1000 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]
Owner = Annotated[Account, Depends(require_perm("self.bills"))]
NOT_FOUND = "Complaint not found."


class ComplaintTypeOut(BaseModel):
    code: str
    category: Category
    category_label: str
    label: str
    label_key: str
    needs_bill: bool
    priority: Priority
    target_days: int | None
    route: Route


@router.get("/api/complaint-types", response_model=list[ComplaintTypeOut])
def types(language: Language = "en") -> list[ComplaintTypeOut]:
    return [ComplaintTypeOut(code=t.code, category=t.category, category_label=text(language, f"ccat_{t.category}"),
                             label=text(language, t.label_key), label_key=t.label_key, needs_bill=t.needs_bill,
                             priority=t.priority, target_days=t.target_days, route=t.route)
            for t in complaint_types.TYPES]


class ConsumerRaise(BaseModel):
    type: TypeCode
    discom: Discom
    service_number: str | None = None
    bill_id: str | None = None
    description: Text1000

    @field_validator("service_number")
    @classmethod
    def _usc(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        cleaned = clean_service_number(value)
        if cleaned is None:
            raise ValueError("A service number is 5 to 16 digits.")
        return cleaned


class ThreadMessage(BaseModel):
    # "from" is a Python keyword, so the field carries it as an alias.
    model_config = ConfigDict(populate_by_name=True)

    sender: Literal["you", "bill_mitra"] = Field(alias="from")
    body: str
    at: str
    media_url: str | None = None  # only on the consumer's own photos
    media_type: str | None = None


class ConsumerComplaint(BaseModel):
    ticket: str
    type: str | None
    type_label: str
    status: State
    status_label: str
    created_at: str
    updated_at: str
    description: str | None
    service_masked: str | None
    bill_month: str | None


class ConsumerComplaintDetail(ConsumerComplaint):
    messages: list[ThreadMessage]


class ConsumerPage(BaseModel):
    items: list[ConsumerComplaint]
    total: int
    page: int
    page_size: int


class ConsumerReply(BaseModel):
    body: Text1000


def _view(row: dict[str, Any], language: str) -> ConsumerComplaint:
    code = row["type"] if row["type"] in complaint_types.BY_CODE else complaint_types.LEGACY_GENERAL
    return ConsumerComplaint(ticket=row["ticket"], type=row["type"], type_label=text(language, f"ctype_{code}"),
                             status=row["state"], status_label=text(language, f"cstate_{row['state']}"),
                             created_at=row["created_at"], updated_at=row["updated_at"],
                             description=row["description"], service_masked=row["service_masked"],
                             bill_month=row["bill_month"])


def _detail(user_id: str, ticket: str, language: str) -> ConsumerComplaintDetail:
    row = store.one(user_id, ticket)
    if row is None:
        raise HTTPException(404, NOT_FOUND)
    return ConsumerComplaintDetail(**_view(row, language).model_dump(),
                                   messages=[_message(ticket, m, language) for m in row["messages"]])


def _message(ticket: str, m: dict[str, Any], language: str) -> ThreadMessage:
    if m["author_kind"] != "consumer":
        return ThreadMessage(sender="bill_mitra", body=m["body"], at=m["created_at"])
    media_id = m["media_id"]
    body = text(language, "cthread_photo") if media_id and m["body"] == PHOTO_NOTE else m["body"]
    return ThreadMessage(sender="you", body=body, at=m["created_at"],
                         media_url=f"/api/complaints/{ticket}/media/{media_id}" if media_id else None,
                         media_type=media.mime_for(media_id) if media_id else None)


@router.post("/api/complaints", response_model=ConsumerComplaintDetail, status_code=201,
             dependencies=[Depends(per_ip("consumer-complaint", 10))])
async def create(body: ConsumerRaise, account: Owner, language: Language = "te") -> ConsumerComplaintDetail:
    if body.bill_id and repos.get_own_bill(account.user_id, body.bill_id) is None:
        raise HTTPException(404, "Bill not found.")
    if body.type == complaint_types.WRONG_READING and body.bill_id and \
            complaints.open_for_bill(body.bill_id, "wrong_reading"):
        raise HTTPException(409, "This bill is already being checked.")
    ticket = await intake.submit(intake.Raise(
        user_id=account.user_id, type=body.type, discom=body.discom, description=body.description,
        language=language, channel="web", source="consumer_web", service_number=body.service_number,
        bill_id=body.bill_id))
    return _detail(account.user_id, ticket, language)


@router.get("/api/complaints", response_model=ConsumerPage)
def mine(account: Owner, page: Annotated[int, Query(ge=1, le=1000)] = 1,
         page_size: Annotated[int, Query(ge=5, le=50)] = 10, language: Language = "te",
         status: State | None = None) -> ConsumerPage:
    rows, total = store.page(account.user_id, page, page_size, status)
    return ConsumerPage(items=[_view(r, language) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/api/complaints/{ticket}", response_model=ConsumerComplaintDetail)
def one(ticket: str, account: Owner, language: Language = "te") -> ConsumerComplaintDetail:
    return _detail(account.user_id, ticket, language)


@router.post("/api/complaints/{ticket}/reply", response_model=ConsumerComplaintDetail,
             dependencies=[Depends(per_ip("consumer-complaint-reply", 20))])
async def reply(ticket: str, body: ConsumerReply, account: Owner, language: Language = "te") -> ConsumerComplaintDetail:
    _waiting(account, ticket)
    _answer(account, ticket, body.body, None)
    return _detail(account.user_id, ticket, language)


def _waiting(account: Account, ticket: str) -> None:
    found = store.one(account.user_id, ticket)
    if found is None:
        raise HTTPException(404, NOT_FOUND)
    if found["state"] != "waiting_for_you":
        raise HTTPException(409, "We have not asked anything on this complaint. We will write here when we do.")


def _answer(account: Account, ticket: str, body: str, media_id: str | None) -> None:
    """The consumer's answer answers every open request. A complaint closed meanwhile takes nothing."""
    if complaints.add_message(ticket, "consumer", None, body, "stored", media_id=media_id) is None:
        raise HTTPException(409, "This complaint is closed.")
    review_store.answer_requests(ticket)
    repos.clear_awaiting(account.user_id, "info:" + ticket)


@router.post("/api/complaints/{ticket}/photo", response_model=ConsumerComplaintDetail,
             dependencies=[Depends(per_ip("consumer-complaint-photo", 10))])
async def photo(ticket: str, file: UploadFile, account: Owner, language: Language = "te",
                caption: Annotated[str | None, Form(max_length=1000)] = None) -> ConsumerComplaintDetail:
    """A photo in answer to what we asked. Checked like a bill upload: the bytes decide the type, and the size limit
    holds. Nothing is stored unless the complaint is waiting for the consumer."""
    _waiting(account, ticket)
    data, mime = await read_checked(file, DOCUMENTS)
    words = caption.strip() if caption and caption.strip() else PHOTO_NOTE
    _answer(account, ticket, words, media.save(data, mime))
    return _detail(account.user_id, ticket, language)


@router.get("/api/complaints/{ticket}/media/{media_id}")
def own_media(ticket: str, media_id: str, account: Owner) -> FileResponse:
    """Only a photo the consumer sent on their own complaint; anything else is a 404."""
    path = media.path_for(media_id)
    if path is None or not handoffs.consumer_media(account.user_id, ticket, media_id):
        raise HTTPException(404, "Not found")
    return FileResponse(path, media_type=media.mime_for(media_id), headers={"Cache-Control": "private, max-age=3600"})
