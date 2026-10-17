"""Complaints in the officer console. Consumers raise them and get replies on WhatsApp, not in the web app.

Staff see complaints within their unit scope. reply_to never leaves the store layer.
"""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, StringConstraints, computed_field, model_validator

from app.api.deps import require_perm, viewer
from app.config import get_settings
from app.core import csvsafe
from app.domain import complaint_types
from app.domain.complaint_reply import Triage
from app.domain.complaint_types import Ownership, Priority, Source, TypeCode
from app.flows.analysis import analyse
from app.flows.complaint import LABEL_EN
from app.flows.complaint_timeline import timeline
from app.flows.evidence import TimelineEntry
from app.services import notify
from app.store import accounts, repos, units
from app.store import complaints as store
from app.store import review as review_store
from app.store.accounts import Account
from app.store.complaints import OPEN_STATUSES, Complaint, Kind, Sort, Status
from app.store.db import DISCOM_UNITS

router = APIRouter(tags=["complaints"])

Discom = Literal["TGSPDCL", "TGNPDCL"]
Text1000 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=5, le=50)]
NOT_FOUND = "Complaint not found."
Viewer = Annotated[Account, Depends(require_perm("complaints.view"))]
Replier = Annotated[Account, Depends(require_perm("complaints.reply"))]


class ComplaintRow(BaseModel):
    ticket: str
    created_at: str
    updated_at: str | None
    status: Status
    service_masked: str | None
    bill_month: str | None
    discom: str | None
    issue: str
    amount: float | None
    language: str | None
    channel: Literal["whatsapp", "web"] | None
    kind: Kind = "general"
    triage: Triage
    delivery_failed: bool
    days_open: int
    overdue: bool = False
    messages_count: int
    last_message_at: str | None
    type: TypeCode | None = None
    type_label: str | None = None
    priority: Priority | None = None
    due_at: str | None = None
    source: Source | None = None
    raised_by: str | None = None  # the staff member's name when staff logged it; consumers raise their own
    ownership: Ownership | None = None
    demo: bool = False
    section: str | None = None  # the matched section's name; None while it sits in a DISCOM or division queue

    @model_validator(mode="after")
    def _overdue(self) -> "ComplaintRow":
        # One rule for the list, the detail and the console: open past its due date, or, for a complaint from
        # before due dates existed, past the promised reply time.
        if self.status not in OPEN_STATUSES:
            self.overdue = False
        elif self.due_at:
            self.overdue = self.due_at < datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        else:
            self.overdue = self.days_open > get_settings().complaint_reply_days
        if self.type in complaint_types.BY_CODE:
            self.type_label = complaint_types.get(self.type).label
        return self


class ComplaintMessage(BaseModel):
    id: int
    author_kind: Literal["consumer", "officer", "system"]
    author_name: str | None
    body: str
    created_at: str
    delivery: Literal["sent", "failed", "stored"]
    delivery_note: str | None
    media_id: str | None = Field(default=None, exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def media_url(self) -> str | None:
        return f"/api/media/{self.media_id}" if self.media_id else None


class BillSummary(BaseModel):
    bill_month: str | None
    units: float | None
    total_payable: float | None
    bill_amount: float | None
    service_masked: str | None
    discom: str


class AuditLineOut(BaseModel):
    code: str
    label: str
    printed: float | None
    expected: float | None
    difference: float | None
    status: str


class Person(BaseModel):
    id: str
    name: str


class ComplaintDetail(ComplaintRow):
    description: str | None = None
    assignee: Person | None = None
    assignable: list[Person] = Field(default_factory=list)  # only for a viewer who may assign
    timeline: list[TimelineEntry] = Field(default_factory=list)
    bill: BillSummary | None
    audit_lines: list[AuditLineOut]
    media_url: str | None
    messages: list[ComplaintMessage]
    reply_channel: Literal["whatsapp", "web"]
    whatsapp_ready: bool


class RowPage(BaseModel):
    items: list[ComplaintRow]
    total: int
    page: int
    page_size: int


class OfficerReply(BaseModel):
    body: Text1000
    status: Status | None = None


class StatusChange(BaseModel):
    status: Status


ASSIGNABLE_MAX = 50


def assignable(complaint: Complaint) -> list[Person]:
    """Active staff who can see complaints and hold a scope on the complaint's unit, a unit above it, or its ERO."""
    anchor = complaint.section_id or complaint.unit_id or DISCOM_UNITS.get(complaint.discom or "")
    if anchor is None:
        return []
    chain = units.ancestors(anchor)
    ids = [u.id for u in chain] + [u.ero_id for u in chain[:1] if u.ero_id]
    return [Person(**p) for p in review_store.staff_covering(ids, "complaints.view", ASSIGNABLE_MAX)]


def _detail(complaint: Complaint, account: Account | None = None) -> ComplaintDetail:
    row = store.row(complaint.ticket)
    if row is None:
        raise HTTPException(404, NOT_FOUND)
    bill, lines, media_url = None, [], None
    found = repos.get_bill(complaint.bill_id) if complaint.bill_id else None
    if found:
        extracted, media_id = found
        bill = BillSummary(bill_month=extracted.bill_month, units=extracted.net_units(),
                           total_payable=extracted.total_payable, bill_amount=extracted.bill_amount,
                           service_masked=extracted.masked_service_number(), discom=extracted.discom)
        lines = [AuditLineOut(label=LABEL_EN.get(line.code, line.code), **line.model_dump())
                 for line in analyse(extracted, complaint.user_id).audit.lines]
        media_url = f"/api/media/{media_id}" if media_id else None
    assignee = Person(id=complaint.assigned_to, name=row["assignee_name"]) \
        if complaint.assigned_to and row["assignee_name"] else None
    people = assignable(complaint) if account and account.can("complaints.assign") else []
    return ComplaintDetail(**row, bill=bill, audit_lines=lines, media_url=media_url, assignee=assignee,
                           assignable=people, timeline=timeline(complaint.ticket, row),
                           messages=[ComplaintMessage(**m) for m in store.messages(complaint.ticket)],
                           reply_channel=notify.reply_channel(complaint),  # type: ignore[arg-type]
                           whatsapp_ready=get_settings().whatsapp_enabled)


def visible_to(account: Account, complaint: Complaint) -> bool:
    """Global staff see everything; others the complaints whose unit or section is in their tree, or assigned to
    them. A complaint from before units existed only carries its DISCOM, so it sits on that DISCOM's unit."""
    if account.is_global or (complaint.assigned_to and complaint.assigned_to == account.id):
        return True
    return units.covers(account.id, complaint.unit_id or DISCOM_UNITS.get(complaint.discom or "")) or \
        units.covers(account.id, complaint.section_id)


def _for_staff(account: Account, ticket: str) -> Complaint:
    complaint = store.get(ticket)
    if complaint is None or not visible_to(account, complaint):
        raise HTTPException(404, NOT_FOUND)
    return complaint


async def _change_status(complaint: Complaint, new_status: Status, account: Account) -> None:
    if new_status == complaint.status:
        return
    try:
        store.set_status(complaint.ticket, new_status)
    except store.AlreadyOpen as exc:
        raise HTTPException(409, "Another reading check is already open for this bill. Continue in that one.") from exc
    line, outcome = await notify.status(complaint, new_status)
    store.add_message(complaint.ticket, "system", account.id, line, outcome.delivery, outcome.note)
    accounts.audit(account.id, "complaint.status", complaint.ticket,
                   f"{complaint.status} to {new_status}, delivery {outcome.delivery}")


@router.get("/api/console/complaints", response_model=RowPage)
async def console_list(account: Viewer, page: PageNo = 1, page_size: PageSize = 10, status: Status | None = None,
                       discom: Discom | None = None, q: Annotated[str | None, Query(max_length=40)] = None,
                       sort: Sort = "priority", triage: Triage | None = None, failed: bool = False,
                       kind: Kind | None = None, type: TypeCode | None = None, priority: Priority | None = None,
                       source: Source | None = None) -> store.Page:
    return store.page(page, page_size, status=status, discom=discom, q=q, sort=sort, triage=triage,
                      failed_only=failed, overdue_days=get_settings().complaint_reply_days, viewer=viewer(account),
                      kind=kind, more=store.Filters(type=type, priority=priority, source=source))


CSV_COLUMNS = ("ticket", "created_at", "updated_at", "status", "discom", "bill_month", "service_masked", "issue",
               "amount", "channel", "days_open")


@router.get("/api/console/complaints.csv")
async def console_export(account: Viewer, status: Status | None = None, discom: Discom | None = None,
                         q: Annotated[str | None, Query(max_length=40)] = None,
                         sort: Literal["newest", "oldest"] = "newest", kind: Kind | None = None,
                         type: TypeCode | None = None, priority: Priority | None = None,
                         source: Source | None = None) -> StreamingResponse:
    rows = store.export(status=status, discom=discom, q=q, newest=sort == "newest", viewer=viewer(account), kind=kind,
                        more=store.Filters(type=type, priority=priority, source=source))
    accounts.audit(account.id, "complaint.export", None, f"{len(rows)} rows")
    name = f"bill-mitra-complaints-{datetime.now(UTC):%Y%m%d}.csv"
    return StreamingResponse(csvsafe.stream(CSV_COLUMNS, rows), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/api/console/complaints/{ticket}", response_model=ComplaintDetail)
async def console_detail(ticket: str, account: Viewer) -> ComplaintDetail:
    return _detail(_for_staff(account, ticket), account)


@router.post("/api/console/complaints/{ticket}/reply", response_model=ComplaintDetail)
async def console_reply(ticket: str, body: OfficerReply, account: Replier) -> ComplaintDetail:
    complaint = _for_staff(account, ticket)
    outcome = await notify.reply(complaint, body.body)
    store.add_message(ticket, "officer", account.id, body.body, outcome.delivery, outcome.note)
    accounts.audit(account.id, "complaint.reply", ticket, f"delivery {outcome.delivery}")
    if body.status:
        await _change_status(complaint, body.status, account)
    return _detail(complaint, account)


@router.post("/api/console/complaints/{ticket}/status", response_model=ComplaintDetail)
async def console_status(ticket: str, body: StatusChange, account: Replier) -> ComplaintDetail:
    complaint = _for_staff(account, ticket)
    await _change_status(complaint, body.status, account)
    return _detail(complaint, account)
