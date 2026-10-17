"""Complaint types (public) and a consumer's own complaints on the web: raise, list, read, answer a question.

The consumer view is neutral: statuses in plain words and every staff message shown as from Bill Mitra.
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.api.deps import require_perm
from app.core.hashing import clean_service_number
from app.core.ratelimit import per_ip
from app.domain import complaint_types
from app.domain.complaint_types import Category, Priority, Route, TypeCode
from app.domain.conversation.lang import text
from app.flows import intake
from app.store import complaints, repos
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
async def types(language: Language = "en") -> list[ComplaintTypeOut]:
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
    thread = [ThreadMessage(sender="you" if m["author_kind"] == "consumer" else "bill_mitra", body=m["body"],
                            at=m["created_at"]) for m in row["messages"]]
    return ConsumerComplaintDetail(**_view(row, language).model_dump(), messages=thread)


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
async def mine(account: Owner, page: Annotated[int, Query(ge=1)] = 1,
               page_size: Annotated[int, Query(ge=5, le=50)] = 10, language: Language = "te",
               status: State | None = None) -> ConsumerPage:
    rows, total = store.page(account.user_id, page, page_size, status)
    return ConsumerPage(items=[_view(r, language) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/api/complaints/{ticket}", response_model=ConsumerComplaintDetail)
async def one(ticket: str, account: Owner, language: Language = "te") -> ConsumerComplaintDetail:
    return _detail(account.user_id, ticket, language)


@router.post("/api/complaints/{ticket}/reply", response_model=ConsumerComplaintDetail,
             dependencies=[Depends(per_ip("consumer-complaint-reply", 20))])
async def reply(ticket: str, body: ConsumerReply, account: Owner, language: Language = "te") -> ConsumerComplaintDetail:
    found = store.one(account.user_id, ticket)
    if found is None:
        raise HTTPException(404, NOT_FOUND)
    if found["state"] != "waiting_for_you":
        raise HTTPException(409, "We have not asked anything on this complaint. We will write here when we do.")
    complaints.add_message(ticket, "consumer", None, body.body, "stored")
    review_store.answer_requests(ticket)
    repos.clear_awaiting(account.user_id, "info:" + ticket)
    return _detail(account.user_id, ticket, language)
