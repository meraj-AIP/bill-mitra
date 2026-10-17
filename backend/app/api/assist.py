"""AI assist for staff: one shared brief per complaint or case, kept until the case changes. Opening the page reads
it (GET); Refresh writes a new one (POST). A model call is audited only when a brief is written, with no text."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.complaints import Replier, _for_staff
from app.api.deps import require_perm
from app.api.review import case_analysis, find_case
from app.flows import assist, assist_case, cases
from app.store import accounts
from app.store.accounts import Account

router = APIRouter(tags=["assist"])

CaseViewer = Annotated[Account, Depends(require_perm("cases.view"))]


async def _complaint(ticket: str, account: Account, refresh: bool) -> assist.ComplaintBrief:
    complaint = _for_staff(account, ticket)
    found, made = await assist.brief(account, complaint, refresh)
    if made:
        accounts.audit(account.id, "assist.complaint", ticket, f"worded by {found.worded_by}", unit_id=complaint.unit_id)
    return found


async def _case(ticket: str, account: Account, refresh: bool) -> assist_case.CaseBrief:
    complaint = find_case(account, ticket)
    found = case_analysis(complaint)
    if found is None:
        raise HTTPException(409, "The bill for this case is no longer available.")
    a = found[0]
    result, made = await assist_case.brief(complaint, a, cases.spike_for(a), refresh)
    if made:
        accounts.audit(account.id, "assist.case", ticket, f"worded by {result.worded_by}", unit_id=complaint.unit_id)
    return result


@router.get("/api/console/complaints/{ticket}/assist", response_model=assist.ComplaintBrief)
async def complaint_brief(ticket: str, account: Replier) -> assist.ComplaintBrief:
    return await _complaint(ticket, account, refresh=False)


@router.post("/api/console/complaints/{ticket}/assist", response_model=assist.ComplaintBrief)
async def complaint_refresh(ticket: str, account: Replier) -> assist.ComplaintBrief:
    return await _complaint(ticket, account, refresh=True)


@router.get("/api/review/cases/{ticket}/assist", response_model=assist_case.CaseBrief)
async def case_brief(ticket: str, account: CaseViewer) -> assist_case.CaseBrief:
    return await _case(ticket, account, refresh=False)


@router.post("/api/review/cases/{ticket}/assist", response_model=assist_case.CaseBrief)
async def case_refresh(ticket: str, account: CaseViewer) -> assist_case.CaseBrief:
    return await _case(ticket, account, refresh=True)
