"""Bill dashboard API. An account sees only the bills it uploaded. Refusals are in the consumer's language."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Path, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import ChatUser, require_perm
from app.core.errors import api_error
from app.core.ratelimit import per_ip
from app.core.uploads import DOCUMENTS, read_checked
from app.domain.conversation.lang import text
from app.flows import case_bills, cases, extract, report
from app.flows.analysis import analyse
from app.store import case_evidence, complaints, extract_jobs, media, repos
from app.store.accounts import Account
from app.store.units import Conflict

router = APIRouter(prefix="/api/bills", tags=["bill dashboard"])

Language = Literal["te", "en", "hi", "ur"]


# Each read costs two to four vision calls, so a single account cannot run up the bill.
UPLOAD_LIMIT = Depends(per_ip("bill-upload", 20))


def _not_found(language: str) -> HTTPException:
    return api_error(404, "bill_not_found", text(language, "err_bill_not_found"))


@router.post("", response_model=report.BillReport, dependencies=[UPLOAD_LIMIT],
             responses={202: {"model": extract.ReadJob, "description": "The reader is down for now; poll the job."}})
async def upload(file: UploadFile, account: ChatUser, language: Annotated[Language, Form()] = "te"
                 ) -> report.BillReport | JSONResponse:
    data, mime = await read_checked(file, DOCUMENTS, language)
    found = await report.check_upload(account.user_id, data, mime, media.save(data, mime), language)
    if isinstance(found, report.BillReport):
        return found
    return JSONResponse(extract.view(found).model_dump(), status_code=202)


@router.get("/jobs/{job_id}", response_model=extract.ReadJob)
def read_job(job_id: Annotated[str, Path(max_length=40)], account: ChatUser,
             language: Language = "te") -> extract.ReadJob:
    """A queued read, for the page to poll. Only the account that uploaded the bill sees it."""
    found = extract_jobs.get_own(account.user_id, job_id)
    if found is None:
        raise api_error(404, "read_not_found", text(language, "err_read_not_found"))
    return extract.view(found)


@router.get("", response_model=repos.BillPage)
def list_bills(
    account: ChatUser,
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(10, ge=5, le=50),
    audit_status: Literal["verified", "mismatch", "partial", "not_checkable", "calculated"] | None = None,
    sort: Literal["newest", "oldest"] = "newest",
) -> repos.BillPage:
    return repos.list_bills(account.user_id, page, page_size, audit_status, sort == "newest")


@router.get("/{bill_id}", response_model=report.BillReport)
def get_bill(bill_id: str, account: ChatUser, language: Language = "te") -> report.BillReport:
    found = report.load(account.user_id, bill_id, language)
    if found is None:
        raise _not_found(language)
    return found


Owner = Annotated[Account, Depends(require_perm("self.bills"))]


class ReviewRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)


@router.post("/{bill_id}/review-request", response_model=cases.ReviewSummary,
             dependencies=[Depends(per_ip("review-request", 10))])
async def review_request(bill_id: str, body: ReviewRequest, account: Owner,
                         language: Language = "te") -> cases.ReviewSummary:
    """The owner reports the bill as wrong. Updates come back in the web app."""
    stored = repos.get_own_bill(account.user_id, bill_id)
    if stored is None:
        raise _not_found(language)
    note = body.note.strip() if body.note and body.note.strip() else None
    try:
        ticket = await cases.report(account.user_id, bill_id, analyse(stored.bill, account.user_id), language, "web",
                                    None, note)
    except Conflict as exc:  # the one clash here: a check is already open on this bill
        raise api_error(409, "check_open", text(language, "err_check_open")) from exc
    return _summary(ticket, language)


@router.post("/{bill_id}/review-request/no-bills", response_model=cases.ReviewSummary,
             dependencies=[Depends(per_ip("review-request", 10))])
async def no_bills(bill_id: str, account: Owner, language: Language = "te") -> cases.ReviewSummary:
    """The owner does not have the earlier bills asked for: the open request is answered with that note."""
    if repos.get_own_bill(account.user_id, bill_id) is None:
        raise _not_found(language)
    ticket = complaints.open_for_bill(bill_id, cases.KIND)
    request = case_evidence.month_request(ticket) if ticket else None
    if ticket is None or request is None or request["status"] != "open":
        raise api_error(409, "no_request_open", text(language, "err_no_bill_request"))
    case_bills.no_bills(ticket, request["id"])
    return _summary(ticket, language)


def _summary(ticket: str, language: str) -> cases.ReviewSummary:
    summary = cases.summary(ticket, language)
    assert summary is not None
    return summary
