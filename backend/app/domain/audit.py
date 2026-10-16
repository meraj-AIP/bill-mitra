"""Line-by-line comparison of the printed bill against the tariff engine."""

from typing import Literal

from pydantic import BaseModel

from app.domain.bill import ExtractedBill
from app.domain.tariff.engine import Computation, money, true_up_rate

TOLERANCE = 1.0
LineStatus = Literal["match", "over", "under", "missing", "not_checkable"]
AuditStatus = Literal["verified", "mismatch", "partial", "not_checkable", "calculated"]

CHECKED_CODES = ("energy", "fixed", "customer", "duty", "fsa")


class AuditLine(BaseModel):
    code: str
    printed: float | None
    expected: float | None
    difference: float | None
    status: LineStatus


class AuditResult(BaseModel):
    status: AuditStatus
    lines: list[AuditLine]
    overcharge: float
    undercharge: float
    notes: list[str]


def _line(code: str, printed: float | None, expected: float) -> AuditLine:
    if printed is None:
        status: LineStatus = "match" if expected == 0 else "missing"
        return AuditLine(code=code, printed=None, expected=expected, difference=None, status=status)
    diff = money(printed - expected)
    if abs(diff) <= TOLERANCE:
        status = "match"
    else:
        status = "over" if diff > 0 else "under"
    return AuditLine(code=code, printed=printed, expected=expected, difference=diff, status=status)


def audit(bill: ExtractedBill, comp: Computation) -> AuditResult:
    if not bill.is_domestic and comp.category != "non_domestic":
        return AuditResult(status="not_checkable", lines=[], overcharge=0, undercharge=0, notes=["non_domestic"])

    expected = comp.charges()
    notes: list[str] = []
    if not bill.line_items:
        if bill.bill_amount is None:
            return AuditResult(status="calculated", lines=[], overcharge=0, undercharge=0, notes=["from_units"])
        # A total without a breakdown can confirm a bill but never accuse one.
        line = _line("total", bill.bill_amount, comp.net)
        status: AuditStatus = "verified" if line.status == "match" else "partial"
        notes.append("total_only" if status == "verified" else "total_differs")
        return AuditResult(status=status, lines=[line], overcharge=0, undercharge=0, notes=notes)
    else:
        lines = [_line(code, bill.item(code), expected[code]) for code in CHECKED_CODES]

    true_up = bill.item("true_up")
    if true_up is not None:
        lines.append(AuditLine(code="true_up", printed=true_up, expected=None, difference=None, status="not_checkable"))
        notes.append("true_up_explained")
        if true_up_rate(bill.month_date()) is None:
            notes.append("true_up_before_order")

    if bill.export_units:
        notes.append("net_metering")
    if bill.arrears:
        notes.append("arrears")
    if comp.gruha_jyothi_applied:
        notes.append("gruha_jyothi_applied")
    elif bill.gruha_jyothi_household and comp.units > 200:
        notes.append("gruha_jyothi_lost")

    over = money(sum(line.difference or 0 for line in lines if line.status == "over"))
    under = money(-sum(line.difference or 0 for line in lines if line.status == "under"))
    missing = any(line.status == "missing" for line in lines)
    if over or under:
        status = "mismatch"
    elif missing:
        status = "partial"
    else:
        status = "verified"
    return AuditResult(status=status, lines=lines, overcharge=over, undercharge=under, notes=notes)
