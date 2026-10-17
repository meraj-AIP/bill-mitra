"""Wrong reading cases for section AEs, officers and billing approvers (staff only, so names appear). Decisions live in review_decisions.py.

A case outside the caller's scope is a 404, never a 403, so its existence does not leak.
"""

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.complaints import AuditLineOut, ComplaintMessage, visible_to
from app.api.deps import require_perm, viewer
from app.core import csvsafe
from app.domain import review as rules
from app.domain.complaint_reply import RequestKind
from app.domain.review import DecisionKind, Policy, ReasonCode, Spike
from app.flows import cases, evidence
from app.flows import complaint as complaint_flow
from app.flows.analysis import Analysis, analyse
from app.flows.complaint import LABEL_EN
from app.flows.evidence import EvidencePack, TimelineEntry
from app.flows.report import bill_out, history_rows
from app.store import accounts, media, repos, units
from app.store import case_evidence as evidence_store
from app.store import complaints as complaint_store
from app.store import policy as policy_store
from app.store import review as store
from app.store.accounts import Account
from app.store.complaints import OPEN_STATUSES, Complaint, Placement

router = APIRouter(prefix="/api/review", tags=["bill review"])

NOT_FOUND = "Case not found."
DECIDABLE = ("awaiting_review", "info_requested", "rejected")
CaseKind = Literal["earlier_bills", "meter_photo", "note"]
Viewer = Annotated[Account, Depends(require_perm("cases.view"))]
DAY = r"^\d{4}-\d{2}-\d{2}$"


class Person(BaseModel):
    id: str
    name: str


class CaseRow(BaseModel):
    ticket: str
    created_at: str
    state: store.State
    overdue: bool
    days_open: int
    section: str | None
    discom: str
    bill_month: str | None
    service_masked: str | None
    units: int | None
    median_units: float | None
    printed_amount: float | None
    usual_amount: float | None
    assignee: Person | None
    channel: Literal["whatsapp", "web"]
    bill_id: str | None  # cite it as evidence of kind 'bill'
    section_id: str | None


class Evidence(BaseModel):
    kind: Literal["message", "bill", "note"]
    id: str
    label: str


class Decision(BaseModel):
    id: int
    kind: DecisionKind
    status: Literal["approved", "pending_approval", "rejected", "withdrawn"]
    original_amount: float
    revised_amount: float
    reduction: float
    corrected_present_reading: float | None
    corrected_units: int | None
    reason_code: ReasonCode
    note: str
    evidence: list[Evidence]
    proposed_by: Person
    proposed_at: str
    decided_by: Person | None
    decided_at: str | None
    decision_note: str | None
    applied_at: str | None
    billing_ref: str | None
    revision: int | None


class CaseRequest(BaseModel):
    id: int
    kind: CaseKind
    note: str | None
    status: Literal["open", "answered"]
    created_at: str


class HistoryMonth(BaseModel):
    month: str
    units: int
    amount: float
    source: Literal["printed", "uploaded", "discom", "this_bill"]


class Can(BaseModel):
    decide: bool
    approve: bool
    mark_applied: bool
    request_info: bool
    reassign: bool
    unmask: bool


class CaseDetail(CaseRow):
    bill: dict[str, Any] | None
    media_url: str | None
    mime_type: str | None
    audit_lines: list[AuditLineOut]
    spike: Spike
    history: list[HistoryMonth]
    messages: list[ComplaintMessage]
    requests: list[CaseRequest]
    decisions: list[Decision]
    policy: Policy
    can: Can
    assignable: list[Person]
    evidence_pack: EvidencePack
    timeline: list[TimelineEntry]


class CasePage(BaseModel):
    items: list[CaseRow]
    total: int
    page: int
    page_size: int
    counts: dict[str, int]


class AssignBody(BaseModel):
    account_id: str = Field(max_length=40)


class RequestBody(BaseModel):
    kind: CaseKind
    note: str | None = Field(default=None, max_length=500)


class PreviewBody(BaseModel):
    corrected_present_reading: float = Field(ge=0, le=10_000_000)


class Preview(BaseModel):
    corrected_units: int
    revised_amount: float
    reduction: float
    needs_approval: bool


def find_case(account: Account, ticket: str) -> Complaint:
    complaint = complaint_store.get(ticket)
    if complaint is None or complaint.kind != cases.KIND or not visible_to(account, complaint):
        raise HTTPException(404, NOT_FOUND)
    return complaint


def case_analysis(complaint: Complaint) -> tuple[Analysis, str | None] | None:
    """The engine's view of the case's bill, and its media id. None once the consumer has erased the bill."""
    found = repos.get_bill(complaint.bill_id) if complaint.bill_id else None
    if found is None:
        return None
    records = evidence_store.records(complaint.ticket)
    discom = [(m["month"], m["units"]) for m in records[1]] if records else []
    return analyse(found[0], complaint.user_id, discom), found[1]


def _assignable(complaint: Complaint) -> list[Person]:
    """Deciders whose scope covers the case: a scope on its unit, any unit above it, or the section's ERO."""
    anchor = complaint.section_id or complaint.unit_id
    if anchor is None:
        return []
    chain = units.ancestors(anchor)
    ids = [u.id for u in chain] + [u.ero_id for u in chain[:1] if u.ero_id]
    return [Person(**p) for p in store.deciders_covering(ids)]


def _can(account: Account, complaint: Complaint, row: dict[str, Any], decisions: list[dict[str, Any]],
         has_bill: bool) -> Can:
    is_open = complaint.status in OPEN_STATUSES
    live = next((d for d in decisions if d["status"] != "withdrawn"), None)
    not_mine = live is not None and live["proposed_by"]["id"] != account.id
    return Can(
        decide=account.can("cases.decide") and is_open and has_bill and row["state"] in DECIDABLE,
        approve=account.can("cases.approve") and row["state"] == "awaiting_approval" and not_mine,
        mark_applied=account.can("cases.mark_applied") and row["state"] == "decided" and not_mine
        and live is not None and live["revision"] is not None,
        request_info=account.can("cases.request_info") and is_open,
        reassign=account.can("cases.reassign") and is_open,
        unmask=account.can("consumer.unmask") and is_open and has_bill)


def detail(account: Account, complaint: Complaint) -> CaseDetail:
    row = store.row(complaint.ticket)
    if row is None:
        raise HTTPException(404, NOT_FOUND)
    found = case_analysis(complaint)
    decisions = store.decisions(complaint.ticket)
    bill, lines, media_url, mime, history = None, [], None, None, []
    spike = Spike(flagged=False, reason=None, units=row["units"] or 0, median_units=row["median_units"],
                  months_used=0, ratio=None, usual_amount=row["usual_amount"])
    if found:
        a, media_id = found
        bill, spike, history = bill_out(a.bill), cases.spike_for(a), history_rows(a)
        lines = [AuditLineOut(label=LABEL_EN.get(line.code, line.code), **line.model_dump()) for line in a.audit.lines]
        media_url = f"/api/media/{media_id}" if media_id else None
        mime = media.mime_for(media_id) if media_id else None
    can = _can(account, complaint, row, decisions, found is not None)
    return CaseDetail(
        **row, bill=bill, media_url=media_url, mime_type=mime, audit_lines=lines, spike=spike, history=history,
        messages=[ComplaintMessage(**m) for m in complaint_store.messages(complaint.ticket)],
        requests=store.requests(complaint.ticket), decisions=decisions, policy=policy_store.get(complaint.discom),
        can=can, assignable=_assignable(complaint) if can.reassign else [],
        evidence_pack=evidence.pack(complaint.ticket, found, spike),
        timeline=evidence.timeline(complaint.ticket, row["created_at"]))


@router.get("/cases", response_model=CasePage)
async def list_cases(account: Viewer, page: Annotated[int, Query(ge=1)] = 1,
                     page_size: Annotated[int, Query(ge=5, le=50)] = 10, state: store.State | None = None,
                     mine: bool = False, overdue: bool | None = None,
                     section_id: Annotated[str | None, Query(max_length=40)] = None,
                     q: Annotated[str | None, Query(max_length=40)] = None, sort: store.CaseSort = "oldest"
                     ) -> store.CasePage:
    return store.page(page, page_size, viewer=viewer(account), state=state, mine=account.id if mine else None,
                      overdue=overdue, section_id=section_id, q=q, sort=sort)


@router.get("/sections")
async def sections(account: Viewer) -> list[dict[str, str]]:
    """Sections that hold cases this account can see, for the queue's section filter."""
    return store.sections(viewer(account))


@router.get("/cases/{ticket}", response_model=CaseDetail)
async def get_case(ticket: str, account: Viewer) -> CaseDetail:
    return detail(account, find_case(account, ticket))


@router.post("/cases/{ticket}/unmask")
async def unmask(ticket: str, account: Annotated[Account, Depends(require_perm("consumer.unmask"))]
                 ) -> dict[str, str]:
    complaint = find_case(account, ticket)
    found = case_analysis(complaint)
    if complaint.status not in OPEN_STATUSES or found is None or not found[0].bill.service_number:
        raise HTTPException(409, "The service number is only shown on an open case with its bill.")
    # Who looked is recorded every time; the number itself never goes in the log.
    accounts.audit(account.id, "case.unmask", ticket, None, unit_id=complaint.unit_id)
    return {"service_number": found[0].bill.service_number}


@router.post("/cases/{ticket}/assign", response_model=CaseDetail)
async def assign(ticket: str, body: AssignBody,
                 account: Annotated[Account, Depends(require_perm("cases.reassign"))]) -> CaseDetail:
    complaint = find_case(account, ticket)
    if complaint.status not in OPEN_STATUSES:
        raise HTTPException(409, "This case is closed.")
    chosen = next((p for p in _assignable(complaint) if p.id == body.account_id), None)
    if chosen is None:
        raise HTTPException(400, "Choose someone who can decide cases in this section.")
    complaint_store.place(ticket, Placement(section_id=complaint.section_id, unit_id=complaint.unit_id,
                                            assigned_to=body.account_id))
    accounts.audit(account.id, "case.assign", ticket, f"to {chosen.name}", unit_id=complaint.unit_id)
    return detail(account, find_case(account, ticket))


@router.post("/cases/{ticket}/request", response_model=CaseDetail)
async def request_info(ticket: str, body: RequestBody,
                       account: Annotated[Account, Depends(require_perm("cases.request_info"))]) -> CaseDetail:
    complaint = find_case(account, ticket)
    if complaint.status not in OPEN_STATUSES:
        raise HTTPException(409, "This case is closed.")
    kind: RequestKind = body.kind
    outcome = await complaint_flow.ask(complaint, kind, account.id, body.note)
    store.add_request(ticket, body.kind, body.note, account.id)
    accounts.audit(account.id, "case.request", ticket, f"{body.kind}, delivery {outcome.delivery}",
                   unit_id=complaint.unit_id)
    return detail(account, complaint)


@router.post("/cases/{ticket}/preview", response_model=Preview)
async def preview(ticket: str, body: PreviewBody,
                  account: Annotated[Account, Depends(require_perm("cases.decide"))]) -> Preview:
    complaint = find_case(account, ticket)
    found = case_analysis(complaint)
    if found is None:
        raise HTTPException(409, "The bill for this case is no longer available.")
    try:
        return corrected_preview(complaint, found[0], body.corrected_present_reading)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def corrected_preview(complaint: Complaint, a: Analysis, present: float) -> Preview:
    """The engine's price of the case's bill at a corrected reading. ValueError when it cannot be priced."""
    result = rules.corrected_reading(a.bill, present, policy_store.get(complaint.discom))
    return Preview(corrected_units=result.corrected_units or 0, revised_amount=result.revised_amount,
                   reduction=result.reduction, needs_approval=result.needs_approval)


CSV_COLUMNS = ("ticket", "revision", "bill_month", "service_masked", "section", "discom", "kind", "reason_code",
               "original_amount", "revised_amount", "reduction", "corrected_units", "proposed_by", "approved_by",
               "decided_at", "status", "applied_at", "billing_ref")


@router.get("/revisions.csv")
async def export(account: Annotated[Account, Depends(require_perm("cases.export"))],
                 since: Annotated[str | None, Query(alias="from", pattern=DAY)] = None,
                 until: Annotated[str | None, Query(alias="to", pattern=DAY)] = None,
                 ero_id: Annotated[str | None, Query(max_length=40)] = None) -> StreamingResponse:
    rows = store.revisions(viewer=viewer(account), since=since, until=until, ero_id=ero_id)
    accounts.audit(account.id, "revision.export", None, f"{len(rows)} rows")
    name = f"bill-mitra-revisions-{datetime.now(UTC):%Y%m%d}.csv"
    return StreamingResponse(csvsafe.stream(CSV_COLUMNS, rows), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})
