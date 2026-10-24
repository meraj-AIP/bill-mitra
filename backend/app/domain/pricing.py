"""Price a bill's month with the engine, using what the bill itself says: month, load, period, category and
Gruha Jyothi. The chat, the dashboard and the AE's repricing all go through here, so they never disagree."""

from app.domain.bill import ExtractedBill
from app.domain.tariff.engine import Category, Computation, compute, has_tariff


def gruha_jyothi_eligible(bill: ExtractedBill) -> bool:
    return bool(bill.gruha_jyothi_household)


def category(bill: ExtractedBill) -> Category:
    # A non-domestic bill whose rates are not loaded (LT-II before April 2025, or industry, agriculture and the other
    # categories) is priced as household only for the engine's bookkeeping, and the audit reports it not checkable.
    printed = bill.tariff_category()
    return printed if printed != "other" and has_tariff(bill.month_date(), printed) else "domestic"


def checkable(bill: ExtractedBill) -> bool:
    """Whether the engine has this bill's own tariff, so its charges can be checked at all."""
    return bill.is_domestic or category(bill) == "non_domestic"


def price(bill: ExtractedBill, units: int, import_units: int | None = None) -> Computation:
    return compute(units, bill.month_date(), bill.load_kw or 1.0, gruha_jyothi_eligible(bill), bill.period(),
                   category(bill), import_units)
