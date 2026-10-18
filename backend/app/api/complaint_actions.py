"""Console shortcuts that save officers a round trip: replies that fit the complaint, asking for a photo, retrying a failed
delivery and acting on many complaints at once. Every write is audited like a single reply."""

from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator

from app.api.complaints import ComplaintDetail, Replier, Viewer, _change_status, _detail, _for_staff, visible_to
from app.api.deps import require_perm
from app.domain import complaint_options
from app.domain.complaint_reply import AskKind, RequestKind, Triage
from app.flows import complaint as complaint_flow
from app.services import notify
from app.store import accounts, handoffs, media
from app.store import complaints as store
from app.store import review as review_store
from app.store.accounts import Account
from app.store.complaints import OPEN_STATUSES, Status

router = APIRouter(prefix="/api/console/complaints", tags=["complaints"])
BULK_MAX = 25
# A reading check's files also open for case reviewers (billing approvers hold cases.view, not complaints.view).
MediaViewer = Annotated[Account, Depends(require_perm("complaints.view", "cases.view"))]


class ReplyOption(BaseModel):
    key: str
    label: str
    text: str
    why: str
    asks: AskKind | None


class RequestOption(BaseModel):
    kind: AskKind
    label: str
    text: str
    why: str


class Options(BaseModel):
    triage: Triage | None
    options: list[ReplyOption]
    requests: list[RequestOption]


class DraftBody(BaseModel):
    option_key: str = Field(min_length=1, max_length=40)


class Draft(BaseModel):
    text: str
    worded_by: Literal["ai", "rules"]


class InfoRequest(BaseModel):
    kind: RequestKind
    note: str | None = Field(default=None, min_length=3, max_length=300)  # the question itself, for kind "note"

    @model_validator(mode="after")
    def _note_for_a_question(self) -> "InfoRequest":
        if (self.kind == "note") != bool(self.note and self.note.strip()):
            raise ValueError("A note request carries its question; other kinds carry none.")
        if self.note and complaint_options.STAFF_WORDS.search(self.note):
            raise ValueError("The consumer is never told who handles their complaint.")
        return self


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


@router.get("/{ticket}/options", response_model=Options)
def options(ticket: str, account: Viewer) -> Options:
    """Replies and requests that fit this complaint. Rules only: no model is called when the page opens."""
    ctx = complaint_flow.options_context(_for_staff(account, ticket))
    return Options(triage=ctx.triage,
                   options=[ReplyOption(**asdict(o)) for o in complaint_options.reply_options(ctx)],
                   requests=[RequestOption(**asdict(o)) for o in complaint_options.ask_options(ctx)])


@router.post("/{ticket}/draft", response_model=Draft)
async def draft(ticket: str, body: DraftBody, account: Replier) -> Draft:
    """One option reworded on request. Its figures are held to the option's own; any failure gives the template."""
    found = await complaint_flow.word_option(_for_staff(account, ticket), body.option_key)
    if found is None:
        raise HTTPException(404, "That reply option is not offered for this complaint.")
    return Draft(text=found.text, worded_by="ai" if found.worded_by == "ai" else "rules")


@router.post("/{ticket}/request", response_model=ComplaintDetail)
async def request_info(ticket: str, body: InfoRequest, account: Replier) -> ComplaintDetail:
    complaint = _for_staff(account, ticket)
    if complaint.status not in OPEN_STATUSES:
        raise HTTPException(409, "This complaint is closed. Reopen it before asking the consumer for more.")
    # A reading check's requests are part of its case, so they need the case permission too.
    if complaint.kind == "wrong_reading" and not account.can("cases.request_info"):
        raise HTTPException(403, "Ask for this from the review case, which needs the case request permission.")
    if body.kind != "note" and \
            body.kind not in complaint_options.allowed_asks(complaint_flow.options_context(complaint)):
        raise HTTPException(422, "That request does not fit this complaint.")
    outcome = await complaint_flow.ask(complaint, body.kind, account.id, body.note)
    review_store.add_request(ticket, body.kind, body.note, account.id)
    accounts.audit(account.id, "complaint.request", ticket, f"{body.kind}, delivery {outcome.delivery}")
    return _detail(complaint, account)


@router.get("/{ticket}/media/{media_id}")
def ticket_media(ticket: str, media_id: str, account: MediaViewer) -> FileResponse:
    """A photo or bill on this complaint, for staff who can see it. Anything else is a 404, never a 403."""
    complaint = store.get(ticket)
    path = media.path_for(media_id)
    allowed = ("complaints.view", "cases.view") if complaint and complaint.kind == "wrong_reading" \
        else ("complaints.view",)
    if complaint is None or path is None or not account.can(*allowed) or not visible_to(account, complaint) \
            or not handoffs.on_ticket(ticket, media_id):
        raise HTTPException(404, "Not found")
    return FileResponse(path, media_type=media.mime_for(media_id), headers={"Cache-Control": "private, max-age=3600"})


@router.post("/{ticket}/messages/{message_id}/retry", response_model=ComplaintDetail)
async def retry(ticket: str, message_id: int, account: Replier) -> ComplaintDetail:
    complaint = _for_staff(account, ticket)
    found = store.message(ticket, message_id)
    if found is None or found["author_kind"] == "consumer" or found["delivery"] != "failed":
        raise HTTPException(404, "No failed message to retry.")
    if found["author_kind"] == "officer":
        outcome = await notify.reply(complaint, found["body"])
    else:
        outcome = await notify.send(complaint, found["body"], complaint.status)
    store.set_delivery(message_id, outcome.delivery, outcome.note, wamid=outcome.wamid, outbox_id=outcome.outbox_id)
    accounts.audit(account.id, "complaint.retry", ticket, f"message {message_id}, delivery {outcome.delivery}")
    return _detail(complaint, account)


async def apply_one(ticket: str, body: BulkAction, account: Account) -> str | None:
    """Returns why a ticket was skipped, or None when it was done."""
    try:
        complaint = _for_staff(account, ticket)
    except HTTPException:
        return "not found"
    if complaint.kind == "wrong_reading":
        return "reading check, decide it in its review case"
    if body.send_explanation:
        if complaint.status not in OPEN_STATUSES:
            return "already closed"
        text = complaint_flow.checked_reply(complaint)
        if text is None:
            return "no bill to explain"
        outcome = await notify.reply(complaint, text)
        store.add_message(ticket, "officer", account.id, text, outcome.delivery, outcome.note, wamid=outcome.wamid, outbox_id=outcome.outbox_id)
        accounts.audit(account.id, "complaint.reply", ticket, f"bulk explanation, delivery {outcome.delivery}")
    if body.status:
        await _change_status(complaint, body.status, account)
    return None


@router.post("/bulk", response_model=BulkResult)
async def bulk(body: BulkAction, account: Replier) -> BulkResult:
    done, skipped = [], []
    for ticket in body.tickets:
        reason = await apply_one(ticket, body, account)
        if reason:
            skipped.append({"ticket": ticket, "reason": reason})
        else:
            done.append(ticket)
    return BulkResult(done=done, skipped=skipped)
