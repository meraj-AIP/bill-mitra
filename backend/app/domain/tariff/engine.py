"""Deterministic bill calculation. No language model touches these numbers."""

from dataclasses import dataclass, field
from datetime import date

from app.domain.tariff.tables import Group, TariffVersion, version_for


@dataclass(frozen=True)
class SlabLine:
    start: int
    end: int
    units: int
    rate: float
    amount: float


@dataclass(frozen=True)
class Computation:
    tariff_id: str
    tariff_order: str
    group: str
    units: int
    slab_lines: tuple[SlabLine, ...]
    energy: float
    fixed: float
    customer: float
    duty: float
    fsa: float
    gross: float
    subsidy: float
    net: float
    gruha_jyothi_applied: bool
    verify: tuple[str, ...] = field(default=())

    def charges(self) -> dict[str, float]:
        return {
            "energy": self.energy,
            "fixed": self.fixed,
            "customer": self.customer,
            "duty": self.duty,
            "fsa": self.fsa,
        }


def money(value: float) -> float:
    return round(value + 1e-9, 2)


def _scaled(limit: int, period: float) -> int:
    return round(limit * period)


def group_for(units: int, version: TariffVersion, period: float = 1.0) -> Group:
    for group in version.groups:
        if group.max_units is None or units <= _scaled(group.max_units, period):
            return group
    return version.groups[-1]


def slab_lines(units: int, group: Group, period: float = 1.0) -> tuple[SlabLine, ...]:
    lines: list[SlabLine] = []
    start = 0
    for slab in group.slabs:
        end = units if slab.upto is None else min(units, _scaled(slab.upto, period))
        if end <= start:
            break
        count = end - start
        lines.append(SlabLine(start + 1, end, count, slab.rate, money(count * slab.rate)))
        start = end
    return tuple(lines)


def customer_charge(units: int, version: TariffVersion) -> float:
    for band in version.customer_charges:
        if band.upto is None or units <= band.upto:
            return band.amount
    return version.customer_charges[-1].amount


def compute(
    units: int,
    bill_month: date,
    load_kw: float = 1.0,
    gruha_jyothi_eligible: bool = False,
    period: float = 1.0,
) -> Computation:
    """Price a month of use. `period` is the billing period as a fraction of a month: real TGSPDCL bills
    stretch every slab by it (31 days read from a 30 day month bills the first 103 units at the first rate)."""
    if units < 0:
        raise ValueError("units cannot be negative")
    if not 0.5 <= period <= 2.0:
        raise ValueError("billing period out of range")
    version = version_for(bill_month)
    group = group_for(units, version, period)
    lines = slab_lines(units, group, period)
    energy = money(sum(line.amount for line in lines))
    fixed = money(version.fixed_charge_per_kw * max(load_kw, 1.0))
    customer = customer_charge(units, version)
    duty = money(units * version.duty_per_unit)
    fsa = money(units * version.fsa_per_unit.get(bill_month.strftime("%Y-%m"), 0.0))
    gross = money(energy + fixed + customer + duty + fsa)
    applied = gruha_jyothi_eligible and units <= version.gruha_jyothi_limit
    subsidy = gross if applied else 0.0
    return Computation(
        tariff_id=version.id,
        tariff_order=version.order,
        group=group.code,
        units=units,
        slab_lines=lines,
        energy=energy,
        fixed=fixed,
        customer=customer,
        duty=duty,
        fsa=fsa,
        gross=gross,
        subsidy=subsidy,
        net=money(gross - subsidy),
        gruha_jyothi_applied=applied,
        verify=version.verify,
    )


def true_up_rate(bill_month: date, first_billed: date | None = None) -> float | None:
    """Per-unit true-up recovery rate in force for a bill month, if any."""
    version = version_for(bill_month)
    rule = version.true_up
    if rule is None or bill_month < rule.starts:
        return None
    first = first_billed or rule.starts
    same_month = (bill_month.year, bill_month.month) == (first.year, first.month)
    return rule.first_month_rate if same_month else rule.later_rate
