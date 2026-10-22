"""AE bill review rules: when a bill looks like a wrong reading, and what a decision does to the amount.

Pure rules over the bill and the engine. No model, no I/O. Every amount comes from app/domain/pricing.py.
"""

import statistics
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.domain import capture
from app.domain.bill import ExtractedBill
from app.domain.prediction import MonthUsage
from app.domain.pricing import price
from app.domain.tariff.engine import Computation, money

HISTORY_MONTHS = 6
MIN_NOTE = 20
ReasonCode = Literal["photo_misread", "wrong_meter", "estimated_reading", "meter_faulty", "category_wrong",
                     "bill_correct", "other"]
DecisionKind = Literal["correct", "corrected_reading", "custom"]
SpikeReason = Literal["above_normal", "reading_went_back"]


class Policy(BaseModel):
    """Per DISCOM. The defaults are the owner's: no AE limit, custom reductions need no approval."""

    discom: Literal["TGSPDCL", "TGNPDCL"]
    ae_limit: float | None = Field(default=None, ge=0, le=10_000_000)
    custom_needs_approval: bool = False
    spike_ratio: float = Field(default=2.0, gt=1, le=20)
    spike_min_increase: float = Field(default=500, ge=0, le=10_000_000)
    min_history_months: int = Field(default=3, ge=1, le=HISTORY_MONTHS)
    decision_sla_days: int = Field(default=3, ge=1, le=90)


class Spike(BaseModel):
    flagged: bool
    reason: SpikeReason | None
    units: int
    median_units: float | None
    months_used: int
    ratio: float | None
    usual_amount: float | None


def _rolled_over(bill: ExtractedBill) -> bool:
    """A lower present reading that is the meter passing 9999... back to 0, with the units printed to match."""
    assert bill.previous_reading is not None and bill.present_reading is not None
    units, rolled = capture.register_units(bill.previous_reading, bill.present_reading, bill.multiplying_factor)
    return rolled and bill.units is not None and abs(units - bill.units) <= 1


def detect(bill: ExtractedBill, comp: Computation, history: list[MonthUsage], policy: Policy) -> Spike:
    """Flag a bill whose units jump well above the household's usual month, or whose meter went backwards."""
    recent = [h.units for h in history[-HISTORY_MONTHS:]]
    median = float(statistics.median(recent)) if recent else None
    usual = price(bill, round(median)).net if median is not None else None
    ratio = round(comp.units / median, 2) if median else None
    reason: SpikeReason | None = None
    went_back = bill.present_reading is not None and bill.previous_reading is not None and \
        bill.present_reading < bill.previous_reading and not _rolled_over(bill)
    if went_back:
        reason = "reading_went_back"
    elif (median and usual is not None and len(recent) >= policy.min_history_months
          and comp.units > policy.spike_ratio * median and comp.net - usual >= policy.spike_min_increase):
        reason = "above_normal"
    return Spike(flagged=reason is not None, reason=reason, units=comp.units, median_units=median,
                 months_used=len(recent), ratio=ratio, usual_amount=usual)


@dataclass(frozen=True)
class Outcome:
    original_amount: float
    revised_amount: float
    reduction: float
    corrected_units: int | None
    needs_approval: bool


def printed_amount(bill: ExtractedBill) -> float:
    if bill.bill_amount is None:
        raise ValueError("This bill has no printed amount to revise.")
    return bill.bill_amount


def _checked(original: float, revised: float, corrected_units: int | None, needs_approval: bool) -> Outcome:
    reduction = money(original - revised)
    if reduction <= 0:
        raise ValueError("The revised amount must be lower than the printed amount.")
    if reduction > original:
        raise ValueError("The reduction cannot be more than the printed amount.")
    return Outcome(original, money(revised), reduction, corrected_units, needs_approval)


def corrected_reading(bill: ExtractedBill, present: float, policy: Policy) -> Outcome:
    """Reprice the bill month at the corrected reading. On a net metered bill the export stays as printed."""
    original = printed_amount(bill)
    if bill.previous_reading is None:
        raise ValueError("This bill has no previous reading, so a corrected reading cannot be priced.")
    if present < bill.previous_reading:
        raise ValueError("The corrected reading cannot be lower than the previous reading.")
    drawn = round(present - bill.previous_reading)
    units = max(drawn - (bill.export_units or 0), 0)
    # Only the tariff part of a bill follows the reading. Surcharge, interest and rounding lines stay as printed,
    # so the reduction is the tariff difference between the printed and the corrected units, nothing else.
    tariff_change = price(bill, bill.net_units(), bill.import_units()).net - price(bill, units, drawn).net
    revised = original - tariff_change
    reduction = money(original - revised)
    needs = policy.ae_limit is not None and reduction > policy.ae_limit
    return _checked(original, revised, units, needs)


def custom(bill: ExtractedBill, reduction: float, policy: Policy) -> Outcome:
    original = printed_amount(bill)
    return _checked(original, original - reduction, None, policy.custom_needs_approval)


def correct(bill: ExtractedBill, comp: Computation) -> Outcome:
    """The bill stands. The printed amount when there is one, else the engine's own figure for it."""
    original = bill.bill_amount if bill.bill_amount is not None else comp.net
    return Outcome(original, original, 0.0, None, False)


LOOKBACK_MONTHS = 3


def months_before(bill_month: str, count: int = LOOKBACK_MONTHS) -> list[str]:
    """The calendar months just before a YYYY-MM month, oldest first."""
    year, month = int(bill_month[:4]), int(bill_month[5:7])
    out = []
    for _ in range(count):
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
        out.append(f"{year:04d}-{month:02d}")
    return out[::-1]


def missing_months(bill_month: str, on_file: set[str]) -> list[str]:
    """Which of the months before the bill nobody has given us yet, from any source."""
    return [m for m in months_before(bill_month) if m not in on_file]


def final_total(revised_amount: float, arrears: float, printed_total: float | None) -> float | None:
    """Total payable after a revision: the revised bill amount plus the printed arrears. None when the bill printed
    no total, so nothing is shown that the bill itself did not have."""
    return money(revised_amount + arrears) if printed_total is not None else None


class Final(BaseModel):
    """The consumer's bill for the month as it stands now. The original bill is never edited."""

    bill_amount: float
    total_payable: float | None
    revised: bool
    status: Literal["pending_update", "applied"] | None


def final(printed_amount: float, printed_total: float | None, arrears: float, revised_amount: float | None,
          applied: bool) -> Final:
    if revised_amount is None:
        return Final(bill_amount=printed_amount, total_payable=printed_total, revised=False, status=None)
    return Final(bill_amount=revised_amount, total_payable=final_total(revised_amount, arrears, printed_total),
                 revised=True, status="applied" if applied else "pending_update")
