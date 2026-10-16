"""Bill dashboard API. An account sees only the bills it uploaded."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import ChatUser, require_perm
from app.core.ratelimit import per_ip
from app.core.uploads import DOCUMENTS, read_checked
from app.flows import cases, report
from app.flows.analysis import analyse
from app.store import media, repos
from app.store.accounts import Account
from app.store.units import Conflict

router = APIRouter(prefix="/api/bills", tags=["bill dashboard"])

Language = Literal["te", "en", "hi", "ur"]


# Each read costs two to four vision calls, so a single account cannot run up the bill.
UPLOAD_LIMIT = Depends(per_ip("bill-upload", 20))


@router.post("", response_model=report.BillReport, dependencies=[UPLOAD_LIMIT])
async def upload(file: UploadFile, account: ChatUser, language: Annotated[Language, Form()] = "te"
                 ) -> report.BillReport:
    data, mime = await read_checked(file, DOCUMENTS)
    return await report.check_upload(account.user_id, data, mime, media.save(data, mime), language)


@router.get("", response_model=repos.BillPage)
async def list_bills(
    account: ChatUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=5, le=50),
    audit_status: Literal["verified", "mismatch", "partial", "not_checkable", "calculated"] | None = None,
    sort: Literal["newest", "oldest"] = "newest",
) -> repos.BillPage:
    return repos.list_bills(account.user_id, page, page_size, audit_status, sort == "newest")


@router.get("/{bill_id}", response_model=report.BillReport)
async def get_bill(bill_id: str, account: ChatUser, language: Language = "te") -> report.BillReport:
    found = report.load(account.user_id, bill_id, language)
    if found is None:
        raise HTTPException(404, "Bill not found.")
    return found


class ReviewRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)


@router.post("/{bill_id}/review-request", response_model=cases.ReviewSummary,
             dependencies=[Depends(per_ip("review-request", 10))])
async def review_request(bill_id: str, body: ReviewRequest,
                         account: Annotated[Account, Depends(require_perm("self.bills"))],
                         language: Language = "te") -> cases.ReviewSummary:
    """The owner asks the section AE to check the reading. Replies come back in the web app."""
    stored = repos.get_own_bill(account.user_id, bill_id)
    if stored is None:
        raise HTTPException(404, "Bill not found.")
    note = body.note.strip() if body.note and body.note.strip() else None
    try:
        ticket = cases.open_case(account.user_id, bill_id, analyse(stored.bill, account.user_id), language, "web",
                                 None, note)
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    summary = cases.summary(ticket, language)
    assert summary is not None
    return summary
