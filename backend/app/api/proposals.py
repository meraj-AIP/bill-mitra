"""Approvals: routine actions the rules prepared (app/flows/proposals.py), carried out only when an officer approves.

Approving checks the proposal again against the complaint as it is now, then runs the same route an officer would use
by hand, with every permission and state check that route has. A proposal the complaint has outgrown is marked stale
and nothing is done. Each approval and rejection is audited under the officer's name.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, StringConstraints

from app.api import complaint_actions, review_decisions
from app.api.complaints import visible_to
from app.api.deps import require_perm, viewer
from app.flows import drafts
from app.flows import proposals as flow
from app.store import accounts, complaints
from app.store import proposals as store
from app.store.accounts import Account
from app.store.proposals import Kind, Page, Proposal, State

router = APIRouter(prefix="/api/console/proposals", tags=["approvals"])
Approver = Annotated[Account, Depends(require_perm(*sorted(set(flow.PERMISSION.values()))))]
BATCH_MAX = 25
NOT_FOUND = "No proposal with this id."
MOVED_ON = "The complaint has changed since this was proposed, so nothing was done."


class RejectBody(BaseModel):
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None


class Batch(BaseModel):
    ids: Annotated[list[int], Field(min_length=1, max_length=BATCH_MAX)]


class BatchResult(BaseModel):
    done: list[int]
    skipped: list[dict[str, str | int]]


def kinds_for(account: Account) -> list[Kind]:
    return [kind for kind, perm in flow.PERMISSION.items() if account.can(perm)]


def _mine(account: Account, proposal_id: int) -> Proposal:
    """The proposal, when its kind is one this account may approve and its complaint is in their scope."""
    found = store.get(proposal_id)
    complaint = complaints.get(found.ticket) if found else None
    if found is None or complaint is None or found.kind not in kinds_for(account) or \
            not visible_to(account, complaint):
        raise HTTPException(404, NOT_FOUND)
    return found


async def _carry_out(proposal: Proposal, account: Account) -> str | None:
    """None when done, else why nothing was done."""
    complaint = complaints.get(proposal.ticket)
    now = flow.assess(complaint) if complaint else None
    if complaint is None or now is None or now[0] != proposal.kind:
        return MOVED_ON
    try:
        if proposal.kind == "explain_correct":
            return await complaint_actions.apply_one(proposal.ticket, complaint_actions.BulkAction(
                tickets=[proposal.ticket], status="Resolved", send_explanation=True), account)
        if proposal.kind in ("request_bill", "request_meter"):
            kind = "bill_photo" if proposal.kind == "request_bill" else "meter_photo"
            await complaint_actions.request_info(proposal.ticket, complaint_actions.InfoRequest(kind=kind), account)
            return None
        await review_decisions.decide(proposal.ticket, review_decisions.DecisionBody(
            kind="correct", reason_code="bill_correct", note=drafts.CORRECT_NOTE,
            evidence=[review_decisions.EvidenceRef(kind="bill", id=complaint.bill_id or "")]), account)
        return None
    except HTTPException as exc:
        return str(exc.detail)


async def _approve(account: Account, proposal_id: int) -> str | None:
    proposal = _mine(account, proposal_id)
    if not store.take(proposal_id, "approved", account.id, None):
        return "Already decided."
    reason = await _carry_out(proposal, account)
    if reason:
        store.mark_stale(proposal_id, reason)
    accounts.audit(account.id, "proposal.approve", proposal.ticket,
                   f"proposal {proposal_id}, {proposal.kind}, {'done' if reason is None else 'nothing done'}")
    return reason


@router.get("", response_model=Page)
def list_proposals(account: Approver, page: Annotated[int, Query(ge=1, le=1000)] = 1,
                   page_size: Annotated[int, Query(ge=5, le=100)] = 20, kind: Kind | None = None,
                   state: State = "pending") -> Page:
    return store.page(page, page_size, kinds_for(account), viewer(account), kind=kind, state=state)


@router.get("/count")
def pending_count(account: Approver) -> dict[str, int]:
    return {"pending": store.pending_count(kinds_for(account), viewer(account))}


@router.post("/{proposal_id}/approve", response_model=Proposal)
async def approve(proposal_id: int, account: Approver) -> Proposal:
    reason = await _approve(account, proposal_id)
    if reason == "Already decided.":
        raise HTTPException(409, "Someone has already decided this proposal.")
    found = store.get(proposal_id)
    assert found is not None
    return found


@router.post("/{proposal_id}/reject", response_model=Proposal)
def reject(proposal_id: int, body: RejectBody, account: Approver) -> Proposal:
    proposal = _mine(account, proposal_id)
    if not store.take(proposal_id, "rejected", account.id, body.note or None):
        raise HTTPException(409, "Someone has already decided this proposal.")
    accounts.audit(account.id, "proposal.reject", proposal.ticket, f"proposal {proposal_id}, {proposal.kind}")
    found = store.get(proposal_id)
    assert found is not None
    return found


@router.post("/approve", response_model=BatchResult)
async def approve_many(body: Batch, account: Approver) -> BatchResult:
    """Approve several at once. Each is checked and carried out on its own; one that cannot go is skipped."""
    done: list[int] = []
    skipped: list[dict[str, str | int]] = []
    for proposal_id in dict.fromkeys(body.ids):
        try:
            reason = await _approve(account, proposal_id)
        except HTTPException as exc:
            reason = str(exc.detail)
        if reason:
            skipped.append({"id": proposal_id, "reason": reason})
        else:
            done.append(proposal_id)
    return BatchResult(done=done, skipped=skipped)
