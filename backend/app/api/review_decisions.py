"""Decisions on wrong reading cases: record, approve, reject, withdraw, mark applied.

Every amount is the engine's (app/domain/review.py) or the printed bill's. Whatever the role, nobody approves or
marks applied a decision they proposed, and every decision carries a reason, a real note and evidence.
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints

from app.api.deps import require_perm
from app.api.review import DECIDABLE, CaseDetail, Preview, case_analysis, corrected_preview, detail, find_case
from app.domain import review as rules
from app.domain.conversation.facts import rs
from app.domain.review import MIN_NOTE, DecisionKind, ReasonCode
from app.flows import cases, drafts, handoff
from app.store import accounts, repos
from app.store import complaints as complaint_store
from app.store import policy as policy_store
from app.store import review as store
from app.store.accounts import Account
from app.store.complaints import OPEN_STATUSES, Complaint

router = APIRouter(prefix="/api/review", tags=["bill review"])

Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
Decider = Annotated[Account, Depends(require_perm("cases.decide"))]
Approver = Annotated[Account, Depends(require_perm("cases.approve"))]
OWN = "You cannot approve or apply a decision you proposed."


class EvidenceRef(BaseModel):
    kind: Literal["message", "bill", "note"]
    id: str = Field(min_length=1, max_length=40)


class DecisionBody(BaseModel):
    kind: DecisionKind
    corrected_present_reading: float | None = Field(default=None, ge=0, le=10_000_000)
    reduction: float | None = Field(default=None, gt=0, le=10_000_000)
    reason_code: ReasonCode
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=MIN_NOTE, max_length=1000)]
    evidence: Annotated[list[EvidenceRef], Field(min_length=1, max_length=20)]


class ApproveBody(BaseModel):
    note: Note | None = None


class RejectBody(BaseModel):
    note: Note


class AppliedBody(BaseModel):
    billing_ref: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


def _evidence(complaint: Complaint, refs: list[EvidenceRef]) -> list[dict[str, str]]:
    """Each item must point at something on this case. Labels are built here and never copy consumer text."""
    request_ids = {str(r["id"]): r["kind"] for r in store.requests(complaint.ticket)}
    out = []
    for ref in dict.fromkeys((r.kind, r.id) for r in refs):
        kind, item_id = ref
        label = None
        if kind == "message" and item_id.isdigit():
            found = complaint_store.message(complaint.ticket, int(item_id))
            label = f"{found['author_kind'].title()} message {item_id}" if found else None
        elif kind == "bill":
            bill = repos.get_own_bill(complaint.user_id, item_id)
            label = f"Bill {bill.bill.bill_month or bill.created_at[:10]}" if bill else None
        elif kind == "note" and item_id in request_ids:
            label = f"Request {item_id}: {request_ids[item_id].replace('_', ' ')}"
        if label is None:
            raise HTTPException(400, f"Evidence {kind} {item_id} is not part of this case.")
        out.append({"kind": kind, "id": item_id, "label": label})
    return out


def _outcome(body: DecisionBody, complaint: Complaint) -> tuple[rules.Outcome, str | None]:
    found = case_analysis(complaint)
    if found is None:
        raise HTTPException(409, "The bill for this case is no longer available.")
    a, policy = found[0], policy_store.get(complaint.discom)
    try:
        if body.kind == "correct":
            return rules.correct(a.bill, a.comp), a.bill.bill_month
        if body.kind == "corrected_reading":
            if body.corrected_present_reading is None:
                raise ValueError("Give the corrected present reading.")
            return rules.corrected_reading(a.bill, body.corrected_present_reading, policy), a.bill.bill_month
        if body.reduction is None:
            raise ValueError("Give the reduction in rupees.")
        return rules.custom(a.bill, body.reduction, policy), a.bill.bill_month
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


async def _settled(complaint: Complaint, decision_id: int, actor_id: str, bill_month: str | None) -> None:
    """An approved decision is told to the consumer. A bill found correct closes the case; a revision waits to be
    applied in the billing system first."""
    decision = store.decision(decision_id)
    assert decision is not None
    await cases.tell_decision(complaint, actor_id, bill_month, decision)
    complaint_store.set_status(complaint.ticket, "In progress" if decision["revision"] else "Resolved")


def _decision(account: Account, decision_id: int) -> tuple[dict[str, Any], Complaint]:
    found = store.decision(decision_id)
    if found is None:
        raise HTTPException(404, "Decision not found.")
    return found, find_case(account, found["ticket"])


class DraftOut(drafts.Draft):
    preview: Preview | None  # the engine's figures for a corrected reading; null on a correct draft


@router.get("/cases/{ticket}/draft", response_model=DraftOut | None)
async def draft(ticket: str, account: Decider) -> DraftOut | None:
    """A suggested decision from the rules, for the AE to use or ignore. Null when no rule is sure enough."""
    complaint = find_case(account, ticket)
    row = store.row(ticket)
    found = case_analysis(complaint)
    if complaint.status not in OPEN_STATUSES or row is None or row["state"] not in DECIDABLE or found is None:
        return None
    a = found[0]
    suggested = drafts.from_misread(complaint, a)
    if suggested and suggested.corrected_present_reading is not None:
        try:
            return DraftOut(**suggested.model_dump(),
                            preview=corrected_preview(complaint, a, suggested.corrected_present_reading))
        except ValueError:
            pass  # the engine cannot price it (no reduction), so it is no draft; fall back to the other rules
    correct = drafts.clear_correct(complaint, a, cases.spike_for(a), store.requests(ticket))
    return DraftOut(**correct.model_dump(), preview=None) if correct else None


@router.post("/cases/{ticket}/decisions", response_model=CaseDetail)
async def decide(ticket: str, body: DecisionBody, account: Decider) -> CaseDetail:
    complaint = find_case(account, ticket)
    row = store.row(ticket)
    if complaint.status not in OPEN_STATUSES or row is None or row["state"] not in DECIDABLE:
        raise HTTPException(409, "This case is not waiting for a decision.")
    outcome, bill_month = _outcome(body, complaint)
    values = {"kind": body.kind, "original_amount": outcome.original_amount, "revised_amount": outcome.revised_amount,
              "reduction": outcome.reduction, "corrected_units": outcome.corrected_units,
              "corrected_present_reading": body.corrected_present_reading if body.kind == "corrected_reading" else None,
              "reason_code": body.reason_code, "note": body.note, "evidence": _evidence(complaint, body.evidence)}
    approved = not outcome.needs_approval
    try:
        decision_id = store.create_decision(ticket, complaint.bill_id or "", values, account.id, approved)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    accounts.audit(account.id, "decision.create", ticket, f"decision {decision_id}, {body.kind}, reduction Rs "
                   f"{rs(outcome.reduction)}, {'approved by policy' if approved else 'awaiting approval'}",
                   unit_id=complaint.unit_id)
    if approved:
        await _settled(complaint, decision_id, account.id, bill_month)
    else:
        complaint_store.set_status(ticket, "In progress")
    return detail(account, find_case(account, ticket))


@router.post("/decisions/{decision_id}/approve", response_model=CaseDetail)
async def approve(decision_id: int, body: ApproveBody, account: Approver) -> CaseDetail:
    found, complaint = _decision(account, decision_id)
    if found["proposed_by"]["id"] == account.id:
        raise HTTPException(403, OWN)
    if not store.approve(decision_id, account.id, body.note):
        raise HTTPException(409, "This decision is not waiting for approval.")
    accounts.audit(account.id, "decision.approve", complaint.ticket, f"decision {decision_id}",
                   unit_id=complaint.unit_id)
    await _settled(complaint, decision_id, account.id, (store.row(complaint.ticket) or {}).get("bill_month"))
    return detail(account, find_case(account, complaint.ticket))


@router.post("/decisions/{decision_id}/reject", response_model=CaseDetail)
async def reject(decision_id: int, body: RejectBody, account: Approver) -> CaseDetail:
    found, complaint = _decision(account, decision_id)
    if found["proposed_by"]["id"] == account.id:
        raise HTTPException(403, "Withdraw your own decision instead of rejecting it.")
    if not store.reject(decision_id, account.id, body.note):
        raise HTTPException(409, "This decision is not waiting for approval.")
    accounts.audit(account.id, "decision.reject", complaint.ticket, f"decision {decision_id}",
                   unit_id=complaint.unit_id)
    handoff.decision_returned(complaint.ticket, decision_id, found["proposed_by"]["id"], account)
    return detail(account, complaint)


@router.post("/decisions/{decision_id}/withdraw", response_model=CaseDetail)
async def withdraw(decision_id: int,
                   account: Annotated[Account, Depends(require_perm("cases.decide", "cases.approve"))]) -> CaseDetail:
    found, complaint = _decision(account, decision_id)
    if found["proposed_by"]["id"] != account.id and not account.can("cases.approve"):
        raise HTTPException(403, "Only the proposer or an approver can withdraw a decision.")
    if found["applied_at"]:
        raise HTTPException(409, "This revision is already applied in the billing system.")
    # The consumer was already told about an approved revision, so they are told it no longer stands.
    announced = found["status"] == "approved" and bool(found["revision"])
    if not store.withdraw(decision_id):
        raise HTTPException(409, "This decision can no longer be withdrawn.")
    complaint_store.set_status(complaint.ticket, "In progress")
    accounts.audit(account.id, "decision.withdraw", complaint.ticket, f"decision {decision_id}",
                   unit_id=complaint.unit_id)
    if announced:
        bill_month = (store.row(complaint.ticket) or {}).get("bill_month")
        await cases.tell_consumer(complaint, account.id, bill_month, "review_withdrawn",
                                  original=rs(found["original_amount"]))
    return detail(account, find_case(account, complaint.ticket))


@router.post("/decisions/{decision_id}/applied", response_model=CaseDetail)
async def applied(decision_id: int, body: AppliedBody,
                  account: Annotated[Account, Depends(require_perm("cases.mark_applied"))]) -> CaseDetail:
    found, complaint = _decision(account, decision_id)
    if found["proposed_by"]["id"] == account.id:
        raise HTTPException(403, OWN)
    if not store.mark_applied(decision_id, account.id, body.billing_ref):
        raise HTTPException(409, "Only an approved revision that is not yet applied can be marked applied.")
    complaint_store.set_status(complaint.ticket, "Resolved")
    accounts.audit(account.id, "decision.applied", complaint.ticket, f"decision {decision_id}, ref {body.billing_ref}",
                   unit_id=complaint.unit_id)
    bill_month = (store.row(complaint.ticket) or {}).get("bill_month")
    await cases.tell_consumer(complaint, account.id, bill_month, "review_applied",
                              revised=rs(found["revised_amount"]))
    return detail(account, find_case(account, complaint.ticket))
