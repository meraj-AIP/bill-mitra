"""Console shortcuts that save officers a round trip: a ready reply, asking for a photo, retrying a failed
delivery and acting on many complaints at once. Every write is audited like a single reply."""

from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.api.complaints import ComplaintDetail, _change_status, _detail, _for_staff
from app.api.deps import Staff
from app.domain import complaint_reply
from app.domain.complaint_reply import RequestKind, Triage
from app.flows import complaint as complaint_flow
from app.services import notify
from app.store import accounts, repos
from app.store import complaints as store
from app.store.accounts import Account
from app.store.complaints import OPEN_STATUSES, Status

router = APIRouter(prefix="/api/console/complaints", tags=["complaints"])
BULK_MAX = 25


class Suggestion(BaseModel):
    text: str | None
    triage: Triage | None
    worded_by: str | None
    quick: list[str]


class InfoRequest(BaseModel):
    kind: RequestKind


class BulkAction(BaseModel):
    tickets: Annotated[list[str], Field(min_length=1, max_length=BULK_MAX)]
    status: Status | None = None
    send_explanation: bool = False

    @model_validator(mode="after")
    def _something_to_do(self) -> "BulkAction":
        if not self.status and not self.send_explanation:
            raise ValueError("Choose a status, the checked explanation, or both.")
        self.tickets = list(dict.fromkeys(self.tickets))
        return self


class BulkResult(BaseModel):
    done: list[str]
    skipped: list[dict[str, str]]


@router.get("/{ticket}/suggestion", response_model=Suggestion)
async def suggestion(ticket: str, account: Staff) -> Suggestion:
    complaint = _for_staff(account, ticket)
    language = complaint.language or "te"
    found = await complaint_flow.suggest_reply(complaint)
    quick = complaint_reply.quick_replies(language)
    if found is None:
        return Suggestion(text=None, triage=None, worded_by=None, quick=quick)
    return Suggestion(text=found.text, triage=found.triage, worded_by=found.worded_by, quick=quick)


@router.post("/{ticket}/request", response_model=ComplaintDetail)
async def request_info(ticket: str, body: InfoRequest, account: Staff) -> ComplaintDetail:
    complaint = _for_staff(account, ticket)
    if complaint.status not in OPEN_STATUSES:
        raise HTTPException(409, "This complaint is closed. Reopen it before asking the consumer for more.")
    message = complaint_reply.request_text(body.kind, complaint.language or "te", ticket)
    outcome = await notify.send(complaint, message)
    store.add_message(ticket, "officer", account.id, message, outcome.delivery, outcome.note)
    # The consumer's next photo or message in the chat is filed under this complaint.
    repos.set_awaiting(complaint.user_id, complaint_flow.INFO_PREFIX + ticket)
    accounts.audit(account.id, "complaint.request", ticket, f"{body.kind}, delivery {outcome.delivery}")
    return _detail(complaint)


@router.post("/{ticket}/messages/{message_id}/retry", response_model=ComplaintDetail)
async def retry(ticket: str, message_id: int, account: Staff) -> ComplaintDetail:
    complaint = _for_staff(account, ticket)
    found = store.message(ticket, message_id)
    if found is None or found["author_kind"] == "consumer" or found["delivery"] != "failed":
        raise HTTPException(404, "No failed message to retry.")
    if found["author_kind"] == "officer":
        outcome = await notify.reply(complaint, found["body"])
    else:
        outcome = await notify.send(complaint, found["body"], complaint.status)
    store.set_delivery(message_id, outcome.delivery, outcome.note)
    accounts.audit(account.id, "complaint.retry", ticket, f"message {message_id}, delivery {outcome.delivery}")
    return _detail(complaint)


async def _apply(ticket: str, body: BulkAction, account: Account) -> str | None:
    """Returns why a ticket was skipped, or None when it was done."""
    try:
        complaint = _for_staff(account, ticket)
    except HTTPException:
        return "not found"
    if body.send_explanation:
        if complaint.status not in OPEN_STATUSES:
            return "already closed"
        text = complaint_flow.checked_reply(complaint)
        if text is None:
            return "no bill to explain"
        outcome = await notify.reply(complaint, text)
        store.add_message(ticket, "officer", account.id, text, outcome.delivery, outcome.note)
        accounts.audit(account.id, "complaint.reply", ticket, f"bulk explanation, delivery {outcome.delivery}")
    if body.status:
        await _change_status(complaint, body.status, account)
    return None


@router.post("/bulk", response_model=BulkResult)
async def bulk(body: BulkAction, account: Staff) -> BulkResult:
    done, skipped = [], []
    for ticket in body.tickets:
        reason = await _apply(ticket, body, account)
        if reason:
            skipped.append({"ticket": ticket, "reason": reason})
        else:
            done.append(ticket)
    return BulkResult(done=done, skipped=skipped)
