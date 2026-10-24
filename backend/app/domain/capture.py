"""Did we read the whole bill, and does what we read add up? Pure rules over the extraction.

A misread digit on a blurred photo almost always breaks one of these sums, so the checks decide whether a
reading is trusted, not the model's own confidence alone.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.domain import meter_status
from app.domain.bill import ExtractedBill
from app.domain.pricing import checkable, price
from app.domain.tariff.engine import money

FieldStatus = Literal["captured", "missing", "unreadable"]
CheckStatus = Literal["pass", "fail", "skipped"]
ProblemCode = Literal["no_units", "unreadable", "check", "low_confidence"]
MONEY_TOLERANCE = 1.0  # bills round the payable amount to the rupee through a Loss/Gain line
MIN_CONFIDENCE = 0.6
# A failed check here means a number on the bill was misread, so the reading cannot be trusted.
BLOCKING = ("readings", "export_readings", "net_units", "energy_units", "charges_sum", "total")
# How far from the units read to look for the count the printed energy charge was worked out on.
ENERGY_SEARCH = 300
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
STATUS_FIELDS = (("present_status", "Meter status (present)"), ("previous_status", "Meter status (previous)"))


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
    # The printed figures and the rules' own result, so a failed check can be told to the consumer in their language.
    values: dict[str, float] = Field(default_factory=dict)


class CaptureReport(BaseModel):
    captured: int
    expected: int
    fields: list[FieldCapture]
    checks: list[Check]
    trusted: bool
    problem: str | None  # why the reading is not trusted, in plain words
    # The same as a stable code and the field or check it is about, for the consumer's message.
    problem_code: ProblemCode | None = None
    problem_key: str | None = None


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


def register_units(previous: float, present: float, mf: float | None) -> tuple[int, bool]:
    """Units a register shows between two readings, times the multiplying factor; True when the meter rolled over
    (passed 9999... back to 0). A meter has as many digits as its previous reading, or one more."""
    factor = mf if mf and mf > 0 else 1.0
    diff = present - previous
    if diff >= 0:
        return round(diff * factor), False
    digits = len(str(int(previous)))
    return round((present + 10 ** digits - previous) * factor), True


def _register_check(key: str, label: str, previous: float | None, present: float | None, units: int | None,
                    mf: float | None) -> Check:
    if previous is None or present is None or units is None:
        return Check(key=key, label=label, status="skipped", detail="A reading or the units is not on the bill")
    expected, rolled = register_units(previous, present, mf)
    factor = mf if mf and mf > 0 else 1.0
    ok = abs(expected - units) <= max(1, round(factor))
    shown = f"({present:g} - {previous:g})" + (f" x MF {factor:g}" if factor != 1 else "")
    note = ", the meter rolled over" if rolled else ""
    return Check(key=key, label=label, status="pass" if ok else "fail",
                 detail=f"{shown} = {expected}{note}, bill says {units}",
                 values={"previous": previous, "present": present, "difference": expected, "units": units})


def _readings(bill: ExtractedBill) -> Check:
    return _register_check("readings", "Present minus previous reading equals units", bill.previous_reading,
                           bill.present_reading, bill.units, bill.multiplying_factor)


def _export_readings(bill: ExtractedBill) -> Check:
    return _register_check("export_readings", "Export meter readings equal the units exported",
                           bill.export_previous_reading, bill.export_present_reading, bill.export_units,
                           bill.multiplying_factor)


def _net_units(bill: ExtractedBill) -> Check:
    """Import, export and banked units against the billed units. Units banked from earlier months are used first;
    when export (with them) is more than import, nothing is billed and the extra is carried on."""
    label = "Import minus solar export equals billed units"
    if None in (bill.units, bill.export_units, bill.billed_units):
        return Check(key="net_units", label=label, status="skipped", detail="Not a net-metered bill, or a figure is missing")
    assert bill.units is not None and bill.export_units is not None and bill.billed_units is not None
    banked_in, banked_on = bill.previous_carry_forward_units or 0, bill.carry_forward_units or 0
    left = bill.units - bill.export_units - banked_in
    billed, carried = max(left, 0), max(-left, 0)
    # Whole units on every side, so any gap is a misread digit. A banked figure not printed is not held against it.
    ok = billed == bill.billed_units and (bill.carry_forward_units is None or carried == banked_on)
    shown = f"{bill.units} - {bill.export_units}" + (f" - {banked_in} banked" if banked_in else "")
    extra = f", {carried} carried forward" if carried else ""
    return Check(key="net_units", label=label, status="pass" if ok else "fail",
                 detail=f"{shown} = {billed} billed{extra}; bill says {bill.billed_units}"
                        + (f", {banked_on} carried forward" if bill.carry_forward_units is not None else ""),
                 values={"units": bill.units, "export": bill.export_units, "net": billed, "billed": bill.billed_units,
                         "prev_cf": banked_in, "pres_cf": banked_on, "carried": carried})


def _energy_units(bill: ExtractedBill) -> Check:
    """The energy charge encodes the units through the slabs. A misread digit can make the readings and the units
    agree with each other and still be wrong; the printed energy charge then fits a different unit count exactly.
    A charge that fits no nearby count is a pricing difference for the audit to report, not a misread. On a solar
    bill the charge is on the units billed (import less export and banked units), so those are what it confirms."""
    label = "Units agree with the energy charge"
    energy = bill.item("energy")
    solar = bill.export_units is not None or bill.billed_units is not None
    units = bill.billed_units if solar else bill.units
    if not checkable(bill):  # no tariff for its category, so its slabs cannot say which units it was priced on
        return Check(key="energy_units", label=label, status="skipped", detail="No tariff loaded for this category")
    if energy is None or units is None:
        return Check(key="energy_units", label=label, status="skipped",
                     detail="No energy charge, or no billed units read on a solar bill")
    try:
        if abs(price(bill, units, bill.import_units()).energy - energy) <= MONEY_TOLERANCE:
            return Check(key="energy_units", label=label, status="pass",
                         detail=f"{units} {'billed ' if solar else ''}units give the printed energy charge of Rs {energy:.2f}")
        fits = next((u for u in range(max(units - ENERGY_SEARCH, 0), units + ENERGY_SEARCH + 1)
                     if abs(price(bill, u).energy - energy) <= 0.5), None)
    except (ValueError, KeyError, LookupError):
        return Check(key="energy_units", label=label, status="skipped", detail="No tariff for this bill to compare")
    if fits is None:
        return Check(key="energy_units", label=label, status="skipped",
                     detail="The energy charge does not follow the tariff for any nearby units, so it cannot confirm them")
    # On a solar bill the consumer is not offered the two counts to pick from: they are billed units, not units used.
    return Check(key="energy_units", label=label, status="fail",
                 detail=f"The printed energy charge fits {fits} units, the bill was read as {units}",
                 values={"energy": energy, "fits": fits, "units": units, **({"solar": 1} if solar else {})})


def _reading_status(bill: ExtractedBill) -> Check:
    """Not a misread check: it never blocks. It says whether the units came from the meter or were estimated."""
    label = "Units read from the meter, not estimated"
    code = bill.present_status
    if code is None:
        return Check(key="reading_status", label=label, status="skipped", detail="No meter status printed")
    detail = f"Status {code}: {meter_status.STAFF_LABEL[meter_status.kind(code) or 'other']}"
    return Check(key="reading_status", label=label, status="fail" if meter_status.estimated(code) else "pass",
                 detail=detail)


def _charges_sum(bill: ExtractedBill) -> Check:
    label = "Charges add up to the bill amount"
    if not bill.line_items or bill.bill_amount is None:
        return Check(key="charges_sum", label=label, status="skipped", detail="No charge breakdown or bill amount")
    total = money(sum(item.amount for item in bill.line_items))
    ok = abs(total - bill.bill_amount) <= MONEY_TOLERANCE
    return Check(key="charges_sum", label=label, status="pass" if ok else "fail",
                 detail=f"Charges add to {total:.2f}, bill amount is {bill.bill_amount:.2f}",
                 values={"sum": total, "bill_amount": bill.bill_amount, "gap": money(abs(total - bill.bill_amount))})


def _total(bill: ExtractedBill) -> Check:
    label = "Bill amount plus arrears equals total due"
    if bill.bill_amount is None or bill.total_payable is None:
        return Check(key="total", label=label, status="skipped", detail="Bill amount or total due is not on the bill")
    expected = money(bill.bill_amount + bill.arrears)
    ok = abs(expected - bill.total_payable) <= MONEY_TOLERANCE
    return Check(key="total", label=label, status="pass" if ok else "fail",
                 detail=f"{bill.bill_amount:.2f} + {bill.arrears:.2f} = {expected:.2f}, total due is "
                        f"{bill.total_payable:.2f}",
                 values={"bill_amount": bill.bill_amount, "arrears": bill.arrears, "expected": expected,
                         "total": bill.total_payable, "gap": money(abs(expected - bill.total_payable))})


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
    skip = {"readings", "export_readings"} if status.get("net_units") == "pass" else set()
    return [c for c in checks if c.key in BLOCKING and c.key not in skip and c.status == "fail"]


def _problem(bill: ExtractedBill, checks: list[Check]) -> tuple[ProblemCode, str | None, str] | None:
    """Why the reading is not trusted: a code, the field or check it is about, and the same in plain words."""
    if bill.units is None:
        return "no_units", "units", "The units used this month could not be read."
    unreadable = [key for key in KEY_FIELDS if key in bill.unreadable_fields]
    if unreadable:
        return "unreadable", unreadable[0], "Some key numbers are not clear enough to read with certainty."
    failed = _blocking(checks)
    if failed:
        return ("check", failed[0].key,
                f"The numbers we read do not add up ({failed[0].label.lower()}), so one of them is probably misread.")
    if bill.confidence < MIN_CONFIDENCE:
        return "low_confidence", None, "The photo is not clear enough to read every number with certainty."
    return None


def failed_check(bill: ExtractedBill) -> str | None:
    """Label of the first blocking consistency check that fails, or None."""
    failed = _blocking([_readings(bill), _export_readings(bill), _net_units(bill), _energy_units(bill),
                        _charges_sum(bill), _total(bill)])
    return failed[0].label if failed else None


def report(bill: ExtractedBill) -> CaptureReport:
    solar = bill.export_units is not None or bill.billed_units is not None
    status = bill.present_status is not None
    extra = (*(SOLAR_FIELDS if solar else ()), *(STATUS_FIELDS if status else ()))
    fields = [_field(bill, key, label) for key, label in (*FIELDS, *extra)]
    exported = bill.export_previous_reading is not None or bill.export_present_reading is not None
    checks = [_readings(bill), *([_net_units(bill)] if solar else []), *([_export_readings(bill)] if exported else []),
              _energy_units(bill), _charges_sum(bill), _total(bill), _days(bill),
              *([_reading_status(bill)] if status else [])]
    found = _problem(bill, checks)
    code, key, problem = found if found else (None, None, None)
    return CaptureReport(captured=sum(f.status == "captured" for f in fields), expected=len(fields), fields=fields,
                         checks=checks, trusted=found is None, problem=problem, problem_code=code, problem_key=key)


def confirm_units(bill: ExtractedBill, units: int) -> ExtractedBill:
    """The units the consumer picked when two printed figures disagreed. Meter readings that do not give those units
    are dropped, since one of them was misread, and the pick is marked as the consumer's own."""
    update: dict[str, object] = {
        "units": units, "unreadable_fields": [f for f in bill.unreadable_fields if f != "units"],
        "confirmed_by_consumer": sorted({*bill.confirmed_by_consumer, "units"})}
    if bill.previous_reading is not None and bill.present_reading is not None and \
            register_units(bill.previous_reading, bill.present_reading, bill.multiplying_factor)[0] != units:
        update.update(previous_reading=None, present_reading=None)
    return bill.model_copy(update=update)


REGISTERS = (("previous_reading", "present_reading"), ("export_previous_reading", "export_present_reading"))


def register_misreads(bill: ExtractedBill) -> list[str]:
    """Readings that fail their own register check on a bill whose net figures agree. The units are confirmed by
    import, export and billed units, so the bill stands, but a reading digit is wrong and must not be shown."""
    if _net_units(bill).status != "pass":
        return []
    failed = [_readings(bill).status == "fail", _export_readings(bill).status == "fail"]
    return [field for bad, pair in zip(failed, REGISTERS, strict=True) if bad for field in pair]
