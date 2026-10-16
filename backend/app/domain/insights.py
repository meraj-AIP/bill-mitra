"""Advice the consumer can act on: slab cliffs, savings in appliance terms, what-if curve."""

from datetime import date

from pydantic import BaseModel

from app.domain.prediction import MonthUsage
from app.domain.tariff.engine import Category, compute, money

THRESHOLDS = (100, 200)
AC_KWH_PER_HOUR = 1.5  # 1.5 ton split AC, typical
MAX_CUT_SHARE = 0.2  # advice to cut more than a fifth of a month's use is not advice a family can follow
GEYSER_KWH_PER_HOUR = 2.0


class CurvePoint(BaseModel):
    units: int
    amount: float


class Cliff(BaseModel):
    threshold: int
    amount_at: float
    amount_after: float
    jump: float


class Saving(BaseModel):
    target_units: int
    cut_units: int
    saving: float
    ac_minutes_per_day: int
    geyser_minutes_per_day: int


class Comparison(BaseModel):
    previous_month: str
    previous_units: int
    previous_amount: float
    delta_units: int
    delta_amount: float


class Insights(BaseModel):
    curve: list[CurvePoint]
    cliffs: list[Cliff]
    saving: Saving | None
    comparison: Comparison | None


def what_if_curve(month: date, load_kw: float, gruha_jyothi: bool, upto: int,
                  category: Category = "domestic") -> list[CurvePoint]:
    step = max(2 if upto > 300 else 1, upto // 500)
    return [CurvePoint(units=u, amount=compute(u, month, load_kw, gruha_jyothi, category=category).net)
            for u in range(0, upto + 1, step)]


def cliffs(month: date, load_kw: float, gruha_jyothi: bool) -> list[Cliff]:
    result = []
    for t in THRESHOLDS:
        at = compute(t, month, load_kw, gruha_jyothi).net
        after = compute(t + 1, month, load_kw, gruha_jyothi).net
        result.append(Cliff(threshold=t, amount_at=at, amount_after=after, jump=money(after - at)))
    return result


def saving(units: int, month: date, load_kw: float, gruha_jyothi: bool) -> Saving | None:
    """If the home is just over a threshold, show what staying under it is worth."""
    for t in reversed(THRESHOLDS):
        cut = units - t
        if 0 < cut <= min(60, units * MAX_CUT_SHARE):
            now = compute(units, month, load_kw, gruha_jyothi).net
            target = compute(t, month, load_kw, gruha_jyothi).net
            per_day = cut / 30
            return Saving(
                target_units=t,
                cut_units=cut,
                saving=money(now - target),
                ac_minutes_per_day=round(per_day / AC_KWH_PER_HOUR * 60),
                geyser_minutes_per_day=round(per_day / GEYSER_KWH_PER_HOUR * 60),
            )
    return None


def comparison(month: date, units: int, amount: float, history: list[MonthUsage]) -> Comparison | None:
    prev_key = date(month.year - (month.month == 1), (month.month - 2) % 12 + 1, 1).strftime("%Y-%m")
    prev = next((h for h in history if h.month == prev_key), None)
    if prev is None:
        return None
    return Comparison(previous_month=prev.month, previous_units=prev.units, previous_amount=prev.amount,
                      delta_units=units - prev.units, delta_amount=money(amount - prev.amount))


def build(month: date, units: int, amount: float, load_kw: float, gruha_jyothi: bool,
          history: list[MonthUsage], category: Category = "domestic") -> Insights:
    upto = max(400, ((units + 150) // 50) * 50)
    household = category == "domestic"
    # Cliffs and the AC and geyser saving tip describe household slabs and habits, so shops get the curve only.
    return Insights(
        curve=what_if_curve(month, load_kw, gruha_jyothi, upto, category),
        cliffs=cliffs(month, load_kw, gruha_jyothi) if household else [],
        saving=saving(units, month, load_kw, gruha_jyothi) if household else None,
        comparison=comparison(month, units, amount, history),
    )
