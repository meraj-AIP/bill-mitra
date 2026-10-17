"""AI assist for staff, on a button press only: never on page load. Audited with no text in the detail."""

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


@router.post("/api/console/complaints/{ticket}/assist", response_model=assist.ComplaintAssist)
async def complaint_assist(ticket: str, account: Replier) -> assist.ComplaintAssist:
    complaint = _for_staff(account, ticket)
    found = await assist.for_complaint(account, complaint)
    accounts.audit(account.id, "assist.complaint", ticket, f"worded by {found.worded_by}", unit_id=complaint.unit_id)
    return found


@router.post("/api/review/cases/{ticket}/assist", response_model=assist_case.CaseAssist)
async def case_assist(ticket: str, account: CaseViewer) -> assist_case.CaseAssist:
    complaint = find_case(account, ticket)
    found = case_analysis(complaint)
    if found is None:
        raise HTTPException(409, "The bill for this case is no longer available.")
    a = found[0]
    result = await assist_case.for_case(complaint, a, cases.spike_for(a))
    accounts.audit(account.id, "assist.case", ticket, f"worded by {result.worded_by}", unit_id=complaint.unit_id)
    return result
