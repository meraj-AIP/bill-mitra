"""Did we read the whole bill, and does what we read add up? Pure rules over the extraction.

A misread digit on a blurred photo almost always breaks one of these sums, so the checks decide whether a
reading is trusted, not the model's own confidence alone.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.domain.bill import ExtractedBill
from app.domain.tariff.engine import money

FieldStatus = Literal["captured", "missing", "unreadable"]
CheckStatus = Literal["pass", "fail", "skipped"]
MONEY_TOLERANCE = 1.0  # bills round the payable amount to the rupee through a Loss/Gain line
MIN_CONFIDENCE = 0.6
# A failed check here means a number on the bill was misread, so the reading cannot be trusted.
BLOCKING = ("readings", "net_units", "charges_sum", "total")
KEY_FIELDS = ("units", "energy", "bill_amount")

FIELDS = (
    ("discom", "DISCOM"), ("service_number", "Service number (USC)"), ("section", "Section"),
    ("category", "Category"), ("bill_date", "Bill date"), ("due_date", "Due date"),
    ("previous_reading_date", "Previous reading date"), ("billing_days", "Billing days"),
    ("previous_reading", "Previous reading"), ("present_reading", "Present reading"), ("units", "Units"),
    ("load_kw", "Contracted load"), ("energy", "Energy charges"), ("fixed", "Fixed charges"),
    ("customer", "Customer charges"), ("duty", "Electricity duty"), ("bill_amount", "Bill amount"),
    ("total_payable", "Total due"),
)
# Only solar net-metered bills print these, so other bills are not marked down for lacking them.
SOLAR_FIELDS = (("export_units", "Units exported (solar)"), ("billed_units", "Billed units (net)"))


class FieldCapture(BaseModel):
    key: str
    label: str
    status: FieldStatus
    value: str | None


class Check(BaseModel):
    key: str
    label: str
    status: CheckStatus
    detail: str


class CaptureReport(BaseModel):
    captured: int
    expected: int
    fields: list[FieldCapture]
    checks: list[Check]
    trusted: bool
    problem: str | None  # why the reading is not trusted, in plain words


def _value(bill: ExtractedBill, key: str) -> str | None:
    if key == "service_number":
        return bill.masked_service_number()
    if key in ("energy", "fixed", "customer", "duty"):
        amount = bill.item(key)
        return None if amount is None else f"{amount:.2f}"
    raw = getattr(bill, key)
    if raw is None or raw == "UNKNOWN":
        return None
    return f"{raw:g}" if isinstance(raw, float) else str(raw)


def _field(bill: ExtractedBill, key: str, label: str) -> FieldCapture:
    value = _value(bill, key)
    if key in bill.unreadable_fields or (key in ("energy", "fixed", "customer", "duty")
                                         and "line_items" in bill.unreadable_fields and value is None):
        return FieldCapture(key=key, label=label, status="unreadable", value=value)
    return FieldCapture(key=key, label=label, status="missing" if value is None else "captured", value=value)


def _readings(bill: ExtractedBill) -> Check:
    label = "Present minus previous reading equals units"
    if None in (bill.present_reading, bill.previous_reading, bill.units):
        return Check(key="readings", label=label, status="skipped", detail="A reading or the units is not on the bill")
    assert bill.present_reading is not None and bill.previous_reading is not None
    diff = round(bill.present_reading - bill.previous_reading)
    ok = abs(diff - (bill.units or 0)) <= 1
    return Check(key="readings", label=label, status="pass" if ok else "fail",
                 detail=f"{bill.present_reading:g} - {bill.previous_reading:g} = {diff}, bill says {bill.units}")


def _net_units(bill: ExtractedBill) -> Check:
    label = "Import minus solar export equals billed units"
    if None in (bill.units, bill.export_units, bill.billed_units):
        return Check(key="net_units", label=label, status="skipped", detail="Not a net-metered bill, or a figure is missing")
    assert bill.units is not None and bill.export_units is not None and bill.billed_units is not None
    net = bill.units - bill.export_units
    ok = net == bill.billed_units  # whole units on both sides, so any gap is a misread digit
    return Check(key="net_units", label=label, status="pass" if ok else "fail",
                 detail=f"{bill.units} - {bill.export_units} = {net}, bill says {bill.billed_units}")


def _charges_sum(bill: ExtractedBill) -> Check:
    label = "Charges add up to the bill amount"
    if not bill.line_items or bill.bill_amount is None:
        return Check(key="charges_sum", label=label, status="skipped", detail="No charge breakdown or bill amount")
    total = money(sum(item.amount for item in bill.line_items))
    ok = abs(total - bill.bill_amount) <= MONEY_TOLERANCE
    return Check(key="charges_sum", label=label, status="pass" if ok else "fail",
                 detail=f"Charges add to {total:.2f}, bill amount is {bill.bill_amount:.2f}")


def _total(bill: ExtractedBill) -> Check:
    label = "Bill amount plus arrears equals total due"
    if bill.bill_amount is None or bill.total_payable is None:
        return Check(key="total", label=label, status="skipped", detail="Bill amount or total due is not on the bill")
    expected = money(bill.bill_amount + bill.arrears)
    ok = abs(expected - bill.total_payable) <= MONEY_TOLERANCE
    return Check(key="total", label=label, status="pass" if ok else "fail",
                 detail=f"{bill.bill_amount:.2f} + {bill.arrears:.2f} = {expected:.2f}, total due is "
                        f"{bill.total_payable:.2f}")


def _days(bill: ExtractedBill) -> Check:
    label = "Billing days match the reading dates"
    try:
        start = date.fromisoformat(bill.previous_reading_date or "")
        end = date.fromisoformat(bill.bill_date or "")
    except ValueError:
        return Check(key="days", label=label, status="skipped", detail="Reading dates are not both on the bill")
    days = (end - start).days
    if bill.billing_days is None:
        return Check(key="days", label=label, status="skipped", detail=f"{days} days between readings")
    ok = abs(days - bill.billing_days) <= 1
    return Check(key="days", label=label, status="pass" if ok else "fail",
                 detail=f"{days} days between the dates, bill says {bill.billing_days}")


def _blocking(checks: list[Check]) -> list[Check]:
    """Failed checks that mean a number was misread. On a net-metered bill the exact import, export and billed
    figures already confirm the units, so a misread meter reading alone no longer blocks it."""
    status = {c.key: c.status for c in checks}
    skip = {"readings"} if status.get("net_units") == "pass" else set()
    return [c for c in checks if c.key in BLOCKING and c.key not in skip and c.status == "fail"]


def _problem(bill: ExtractedBill, checks: list[Check]) -> str | None:
    if bill.units is None:
        return "The units used this month could not be read."
    unreadable = [key for key in KEY_FIELDS if key in bill.unreadable_fields]
    if unreadable:
        return "Some key numbers are not clear enough to read with certainty."
    failed = _blocking(checks)
    if failed:
        return f"The numbers we read do not add up ({failed[0].label.lower()}), so one of them is probably misread."
    if bill.confidence < MIN_CONFIDENCE:
        return "The photo is not clear enough to read every number with certainty."
    return None


def failed_check(bill: ExtractedBill) -> str | None:
    """Label of the first blocking consistency check that fails, or None."""
    failed = _blocking([_readings(bill), _net_units(bill), _charges_sum(bill), _total(bill)])
    return failed[0].label if failed else None


def report(bill: ExtractedBill) -> CaptureReport:
    solar = bill.export_units is not None or bill.billed_units is not None
    fields = [_field(bill, key, label) for key, label in (*FIELDS, *(SOLAR_FIELDS if solar else ()))]
    checks = [_readings(bill), *([_net_units(bill)] if solar else []), _charges_sum(bill), _total(bill), _days(bill)]
    problem = _problem(bill, checks)
    return CaptureReport(captured=sum(f.status == "captured" for f in fields), expected=len(fields), fields=fields,
                         checks=checks, trusted=problem is None, problem=problem)
