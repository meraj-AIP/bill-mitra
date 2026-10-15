"""Complaints in the officer console. Consumers raise them and get replies on WhatsApp, not in the web app.

Staff see complaints within their DISCOM. reply_to never leaves the store layer.
"""

import csv
import io
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, StringConstraints, computed_field, model_validator

from app.api.deps import Staff
from app.config import get_settings
from app.domain.complaint_reply import Triage
from app.flows.analysis import analyse
from app.flows.complaint import LABEL_EN
from app.services import notify
from app.store import accounts, repos
from app.store import complaints as store
from app.store.accounts import Account
from app.store.complaints import OPEN_STATUSES, Complaint, Sort, Status

router = APIRouter(tags=["complaints"])

Discom = Literal["TGSPDCL", "TGNPDCL"]
Text1000 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=5, le=50)]
NOT_FOUND = "Complaint not found."


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
    triage: Triage
    delivery_failed: bool
    days_open: int
    overdue: bool = False
    messages_count: int
    last_message_at: str | None

    @model_validator(mode="after")
    def _overdue(self) -> "ComplaintRow":
        # One rule for the list, the detail and the console: open past the promised reply time.
        self.overdue = self.status in OPEN_STATUSES and self.days_open > get_settings().complaint_reply_days
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


class ComplaintDetail(ComplaintRow):
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


def _detail(complaint: Complaint) -> ComplaintDetail:
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
    return ComplaintDetail(**row, bill=bill, audit_lines=lines, media_url=media_url,
                           messages=[ComplaintMessage(**m) for m in store.messages(complaint.ticket)],
                           reply_channel=notify.reply_channel(complaint),  # type: ignore[arg-type]
                           whatsapp_ready=get_settings().whatsapp_enabled)


def _staff_scope(account: Account) -> str | None:
    return account.discom if account.role == "officer" else None


def _for_staff(account: Account, ticket: str) -> Complaint:
    complaint = store.get(ticket)
    scope = _staff_scope(account)
    if complaint is None or (scope and complaint.discom != scope):
        raise HTTPException(404, NOT_FOUND)
    return complaint


async def _change_status(complaint: Complaint, new_status: Status, account: Account) -> None:
    if new_status == complaint.status:
        return
    store.set_status(complaint.ticket, new_status)
    line, outcome = await notify.status(complaint, new_status)
    store.add_message(complaint.ticket, "system", account.id, line, outcome.delivery, outcome.note)
    accounts.audit(account.id, "complaint.status", complaint.ticket,
                   f"{complaint.status} to {new_status}, delivery {outcome.delivery}")


@router.get("/api/console/complaints", response_model=RowPage)
async def console_list(account: Staff, page: PageNo = 1, page_size: PageSize = 10, status: Status | None = None,
                       discom: Discom | None = None, q: Annotated[str | None, Query(max_length=40)] = None,
                       sort: Sort = "priority", triage: Triage | None = None, failed: bool = False) -> store.Page:
    scope = _staff_scope(account)
    if scope and discom and discom != scope:
        return store.Page(items=[], total=0, page=page, page_size=page_size)
    return store.page(page, page_size, status=status, discom=scope or discom, q=q, sort=sort, triage=triage,
                      failed_only=failed, overdue_days=get_settings().complaint_reply_days)


CSV_COLUMNS = ("ticket", "created_at", "updated_at", "status", "discom", "bill_month", "service_masked", "issue",
               "amount", "channel", "days_open")
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _cell(value: Any) -> Any:
    # A spreadsheet runs a cell that starts like a formula; the quote makes it plain text.
    return f"'{value}" if isinstance(value, str) and value.startswith(FORMULA_START) else value


def _csv(rows: list[dict[str, Any]]) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for line in (CSV_COLUMNS, *([_cell(r[c]) for c in CSV_COLUMNS] for r in rows)):
        writer.writerow(line)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate()


@router.get("/api/console/complaints.csv")
async def console_export(account: Staff, status: Status | None = None, discom: Discom | None = None,
                         q: Annotated[str | None, Query(max_length=40)] = None,
                         sort: Literal["newest", "oldest"] = "newest") -> StreamingResponse:
    scope = _staff_scope(account)
    rows = [] if scope and discom and discom != scope else store.export(
        status=status, discom=scope or discom, q=q, newest=sort == "newest")
    accounts.audit(account.id, "complaint.export", None, f"{len(rows)} rows")
    name = f"bill-mitra-complaints-{datetime.now(UTC):%Y%m%d}.csv"
    return StreamingResponse(_csv(rows), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/api/console/complaints/{ticket}", response_model=ComplaintDetail)
async def console_detail(ticket: str, account: Staff) -> ComplaintDetail:
    return _detail(_for_staff(account, ticket))


@router.post("/api/console/complaints/{ticket}/reply", response_model=ComplaintDetail)
async def console_reply(ticket: str, body: OfficerReply, account: Staff) -> ComplaintDetail:
    complaint = _for_staff(account, ticket)
    outcome = await notify.reply(complaint, body.body)
    store.add_message(ticket, "officer", account.id, body.body, outcome.delivery, outcome.note)
    accounts.audit(account.id, "complaint.reply", ticket, f"delivery {outcome.delivery}")
    if body.status:
        await _change_status(complaint, body.status, account)
    return _detail(complaint)


@router.post("/api/console/complaints/{ticket}/status", response_model=ComplaintDetail)
async def console_status(ticket: str, body: StatusChange, account: Staff) -> ComplaintDetail:
    complaint = _for_staff(account, ticket)
    await _change_status(complaint, body.status, account)
    return _detail(complaint)
