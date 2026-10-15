"""Bill dashboard API. An account sees only the bills it uploaded."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile

from app.api.deps import AnyAccount
from app.core.ratelimit import per_ip
from app.core.uploads import DOCUMENTS, read_checked
from app.flows import report
from app.store import media, repos

router = APIRouter(prefix="/api/bills", tags=["bill dashboard"])

Language = Literal["te", "en", "hi", "ur"]


# Each read costs two to four vision calls, so a single account cannot run up the bill.
UPLOAD_LIMIT = Depends(per_ip("bill-upload", 20))


@router.post("", response_model=report.BillReport, dependencies=[UPLOAD_LIMIT])
async def upload(file: UploadFile, account: AnyAccount, language: Annotated[Language, Form()] = "te"
                 ) -> report.BillReport:
    data, mime = await read_checked(file, DOCUMENTS)
    return await report.check_upload(account.user_id, data, mime, media.save(data, mime), language)


@router.get("", response_model=repos.BillPage)
async def list_bills(
    account: AnyAccount,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=5, le=50),
    audit_status: Literal["verified", "mismatch", "partial", "not_checkable", "calculated"] | None = None,
    sort: Literal["newest", "oldest"] = "newest",
) -> repos.BillPage:
    return repos.list_bills(account.user_id, page, page_size, audit_status, sort == "newest")


@router.get("/{bill_id}", response_model=report.BillReport)
async def get_bill(bill_id: str, account: AnyAccount, language: Language = "te") -> report.BillReport:
    found = report.load(account.user_id, bill_id, language)
    if found is None:
        raise HTTPException(404, "Bill not found.")
    return found
