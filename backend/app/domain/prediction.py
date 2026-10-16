"""Next-bill estimate from consumption history, with a seasonal fallback."""

from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.domain.tariff.engine import Category, compute

# Typical Telangana domestic load shape: summer peak, monsoon dip, mild winter.
SEASONAL_FACTOR = {1: 0.85, 2: 0.92, 3: 1.12, 4: 1.30, 5: 1.38, 6: 1.15,
                   7: 0.98, 8: 0.95, 9: 0.96, 10: 1.00, 11: 0.90, 12: 0.85}


class MonthUsage(BaseModel):
    month: str  # YYYY-MM
    units: int
    amount: float
    source: Literal["printed", "uploaded", "this_bill"] = "printed"


class Prediction(BaseModel):
    month: str
    units_low: int
    units_high: int
    units: int
    amount: float
    method: str
    crosses: int | None  # threshold the estimate is likely to cross, if any


def next_month(month: date) -> date:
    return date(month.year + (month.month == 12), month.month % 12 + 1, 1)


def _key(month: date) -> str:
    return month.strftime("%Y-%m")


def _from_history(target: date, history: list[MonthUsage]) -> tuple[float, str] | None:
    by_month = {h.month: h.units for h in history}
    last_year = by_month.get(_key(date(target.year - 1, target.month, 1)))
    if last_year is None or len(history) < 6:
        return None
    recent = [h.units for h in history[-3:]]
    year_ago = [by_month.get(_key(date(int(h.month[:4]) - 1, int(h.month[5:]), 1))) for h in history[-3:]]
    pairs = [(r, y) for r, y in zip(recent, year_ago, strict=True) if y]
    trend = sum(r for r, _ in pairs) / sum(y for _, y in pairs) if pairs else 1.0
    return last_year * min(max(trend, 0.7), 1.4), "same month last year, adjusted for recent trend"


def _from_recent(target: date, history: list[MonthUsage]) -> tuple[float, str] | None:
    recent = history[-3:]
    if len(recent) < 3:
        return None
    # Bring each month to a season-neutral level before averaging, then project into the target month.
    level = sum(h.units / SEASONAL_FACTOR[int(h.month[5:])] for h in recent) / len(recent)
    return level * SEASONAL_FACTOR[target.month], "your last 3 months, adjusted for the season"


def predict(
    current_month: date,
    current_units: int,
    history: list[MonthUsage],
    gruha_jyothi: bool,
    load_kw: float = 1.0,
    category: Category = "domestic",
) -> Prediction:
    target = next_month(current_month)
    estimate = _from_history(target, history) or _from_recent(target, history)
    if estimate is None:
        ratio = SEASONAL_FACTOR[target.month] / SEASONAL_FACTOR[current_month.month]
        estimate = (current_units * ratio, "this bill, adjusted for the season")
    units = max(round(estimate[0]), 0)
    low, high = round(units * 0.92), round(units * 1.08)
    crosses = None
    # The 100 and 200 unit steps are household tariff steps; a shop's bill has no such warning.
    for threshold in (100, 200) if category == "domestic" else ():
        if current_units <= threshold < high:
            crosses = threshold
            break
    amount = compute(units, target, load_kw, gruha_jyothi, category=category).net
    return Prediction(month=_key(target), units_low=low, units_high=high, units=units,
                      amount=amount, method=estimate[1], crosses=crosses)
