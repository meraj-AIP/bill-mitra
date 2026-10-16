"""Consumption history from what the consumer actually gave us: the usage table printed on the bill and their
own earlier uploads for the same connection. Nothing is invented or fetched."""

from datetime import date

from app.domain.bill import ExtractedBill
from app.domain.prediction import MonthUsage
from app.domain.tariff.engine import Category, compute
from app.store import repos

MAX_MONTHS = 12


def _month(key: str) -> date:
    return date(int(key[:4]), int(key[5:]), 1)


def history(bill: ExtractedBill, user_id: str, load_kw: float, gruha_jyothi: bool,
            category: Category = "domestic") -> list[MonthUsage]:
    """Months before this bill, oldest first. An earlier upload wins over a printed table row for the same month."""
    current = bill.bill_month or bill.month_date().strftime("%Y-%m")
    units: dict[str, tuple[int, str, float]] = {
        p.month: (p.units, "printed", 1.0) for p in bill.usage_history if p.month < current}
    if bill.service_number:
        for past in repos.bills_for_service(user_id, bill.service_number):
            if past.bill_month and past.bill_month < current and past.units is not None:
                units[past.bill_month] = (past.net_units(), "uploaded", past.period())
    out = [MonthUsage(month=m, units=u, source=src, amount=compute(u, _month(m), load_kw, gruha_jyothi, period, category).net)
           for m, (u, src, period) in sorted(units.items())]
    return out[-MAX_MONTHS:]
