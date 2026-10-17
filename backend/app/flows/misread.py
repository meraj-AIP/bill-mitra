"""Misread found from the next bill. A meter cannot run backwards, so when the next month's bill starts below the
present reading printed on the month before, that earlier present reading was read too high.

Printed readings only. No money is worked out here; the engine prices a correction when the AE previews it.
Every automatic step is audited with no actor, so the case timeline shows it as the system.
"""

from pydantic import BaseModel

from app.domain.bill import ExtractedBill
from app.domain.review import months_before
from app.store import accounts, alerts, complaints
from app.store import suggestions as store

CASE_KIND = "wrong_reading"  # app.flows.cases.KIND; not imported because cases calls this module


class Misread(BaseModel):
    """What the next bill's report offers: report the earlier month. Readings as printed."""

    earlier_bill_id: str
    earlier_month: str
    printed_present: float
    next_previous: float


def signal(earlier: ExtractedBill, following: ExtractedBill) -> bool:
    """The next bill starts below this bill's present reading, but not below its previous one (that would be a
    different meter or a reset, not a misread)."""
    if None in (earlier.previous_reading, earlier.present_reading, following.previous_reading):
        return False
    assert earlier.previous_reading is not None and earlier.present_reading is not None
    assert following.previous_reading is not None
    return earlier.previous_reading <= following.previous_reading < earlier.present_reading


def _next_month(month: str) -> str:
    year, number = int(month[:4]), int(month[5:7])
    return f"{year + number // 12:04d}-{number % 12 + 1:02d}"


def earlier_for(user_id: str, bill: ExtractedBill) -> tuple[str, ExtractedBill] | None:
    """The previous month's bill this one proves misread, newest copy first."""
    if not bill.service_number or not bill.bill_month:
        return None
    month = months_before(bill.bill_month, 1)[0]
    return next(((i, b) for i, b in store.bills_for_month(user_id, bill.service_number, month) if signal(b, bill)),
                None)


def _misread(earlier_id: str, earlier: ExtractedBill, following: ExtractedBill) -> Misread:
    assert earlier.bill_month and earlier.present_reading is not None and following.previous_reading is not None
    return Misread(earlier_bill_id=earlier_id, earlier_month=earlier.bill_month,
                   printed_present=earlier.present_reading, next_previous=following.previous_reading)


def find(user_id: str, bill: ExtractedBill) -> Misread | None:
    """The offer on this bill's report, only while no check is open on the earlier bill."""
    found = earlier_for(user_id, bill)
    if found is None or complaints.open_for_bill(found[0], CASE_KIND):
        return None
    return _misread(found[0], found[1], bill)


def _suggest(ticket: str, earlier: ExtractedBill, following_id: str, following: ExtractedBill) -> bool:
    complaint = complaints.get(ticket)
    if complaint is None or following.previous_reading is None:
        return False
    corrected = round(following.previous_reading)
    if not store.save(ticket, "corrected_reading", corrected, following_id):
        return False
    accounts.audit(None, "case.suggestion", ticket, f"corrected present reading {corrected}, from the "
                   f"{following.bill_month} bill", unit_id=complaint.unit_id)
    alerts.raise_alert("misread_found", complaint.section_id or complaint.unit_id, f"Misread found on {ticket}",
                       f"The {following.bill_month} bill starts at {following.previous_reading:g}, below the present "
                       f"reading of {earlier.present_reading:g} on the {earlier.bill_month} bill. A corrected reading "
                       "is suggested on the case.", "cases.decide", f"misread_found:{ticket}", ticket=ticket)
    return True


def after_bill_saved(user_id: str, bill: ExtractedBill, bill_id: str) -> Misread | None:
    """Run once a checked bill is stored. With a check open on the earlier bill, the case gets the suggestion;
    without one, the new bill's report carries the offer."""
    found = earlier_for(user_id, bill)
    if found is None:
        return None
    ticket = complaints.open_for_bill(found[0], CASE_KIND)
    if ticket is None:
        return _misread(found[0], found[1], bill)
    _suggest(ticket, found[1], bill_id, bill)
    return None


def on_case_opened(ticket: str, user_id: str, bill: ExtractedBill) -> bool:
    """A check opened on a bill whose next month is already on file."""
    if not bill.service_number or not bill.bill_month:
        return False
    following = next(((i, b) for i, b in store.bills_for_month(user_id, bill.service_number,
                                                                _next_month(bill.bill_month)) if signal(bill, b)), None)
    return _suggest(ticket, bill, *following) if following else False
