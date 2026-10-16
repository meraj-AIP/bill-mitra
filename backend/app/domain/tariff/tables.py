"""Versioned TGERC retail supply tariff tables: LT-I domestic and, from FY 2025-26, LT-II non-domestic.

Every figure the assistant quotes comes from these tables. A new tariff order is
added as a new version with its effective dates; old bills keep being checked
against the version that was in force in their bill month.

Rates marked `verify=True` are working assumptions for the pilot and must be
confirmed by the DISCOM billing team before consumers see them.
"""

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Slab:
    upto: int | None  # inclusive upper bound in units; None means no upper bound
    rate: float  # Rs per unit


@dataclass(frozen=True)
class Group:
    code: str  # LT-I(A), LT-I(B), LT-I(C)
    max_units: int | None  # the group applies when monthly units are <= this
    slabs: tuple[Slab, ...]


@dataclass(frozen=True)
class CustomerChargeBand:
    upto: int | None
    amount: float


@dataclass(frozen=True)
class TrueUpRule:
    starts: date
    first_month_rate: float
    later_rate: float


@dataclass(frozen=True)
class NonDomesticTariff:
    """LT-II commercial. Groups work like LT-I: the group follows monthly units, slabs are telescopic in it."""

    groups: tuple[Group, ...]
    fixed_charge_per_kw: dict[str, float]  # by group code, Rs per kW of contracted load per month
    customer_charges: tuple[CustomerChargeBand, ...]
    duty_per_unit: float  # charged on units imported from the grid, before solar export is netted off


@dataclass(frozen=True)
class TariffVersion:
    id: str
    order: str
    effective_from: date
    effective_to: date | None
    groups: tuple[Group, ...]
    customer_charges: tuple[CustomerChargeBand, ...]
    fixed_charge_per_kw: float
    duty_per_unit: float
    fsa_per_unit: dict[str, float] = field(default_factory=dict)  # "YYYY-MM" -> Rs/unit
    true_up: TrueUpRule | None = None
    gruha_jyothi_limit: int = 200
    verify: tuple[str, ...] = ()
    non_domestic: NonDomesticTariff | None = None


_DOMESTIC_GROUPS = (
    Group("LT-I(A)", 100, (Slab(50, 1.95), Slab(100, 3.10))),
    Group("LT-I(B)", 200, (Slab(100, 3.40), Slab(200, 4.80))),
    Group(
        "LT-I(C)",
        None,
        (Slab(200, 5.10), Slab(300, 7.70), Slab(400, 9.00), Slab(800, 9.50), Slab(None, 10.00)),
    ),
)

# Customer charges by monthly units, Rs/month. Source: TGERC tariff schedule FY 2023-24, section 8, and matched
# by real TGSPDCL bills in March 2024 and October 2025 (Rs 90 at 157 and 138 units).
_CUSTOMER_CHARGES = (
    CustomerChargeBand(50, 40.0),
    CustomerChargeBand(100, 70.0),
    CustomerChargeBand(200, 90.0),
    CustomerChargeBand(300, 100.0),
    CustomerChargeBand(400, 120.0),
    CustomerChargeBand(800, 140.0),
    CustomerChargeBand(None, 160.0),
)

# Slab pro-rating by billing days is not in the schedule; it is inferred from two real bills (see engine.compute).
_VERIFY = ("fsa_per_unit", "billing_period_proration")

# LT-II rates from the TGERC FY 2025-26 schedule (FY 2026-27 retains them). The LT-II(B) slabs, the Rs 100 per kW
# fixed charge, Rs 160 customer charge and duty on import units reproduce a real TGSPDCL net-metered 2B bill of
# September 2026 to the paisa (3092 billed units over 33 days). LT-II(A), the customer charge bands and the fixed
# charge for smaller loads are not yet seen on a real bill.
_NON_DOMESTIC = NonDomesticTariff(
    groups=(
        Group("LT-II(A)", 50, (Slab(50, 7.00),)),
        Group("LT-II(B)", None, (Slab(100, 8.50), Slab(300, 9.90), Slab(500, 10.40), Slab(None, 11.00))),
    ),
    fixed_charge_per_kw={"LT-II(A)": 100.0, "LT-II(B)": 100.0},
    customer_charges=_CUSTOMER_CHARGES,
    duty_per_unit=0.06,
)
_NON_DOMESTIC_VERIFY = ("non_domestic_lt2a", "non_domestic_customer_charges", "non_domestic_fixed_small_loads")

TARIFF_VERSIONS: tuple[TariffVersion, ...] = (
    TariffVersion(
        id="TGERC-RST-2023-24",
        order="TGERC Retail Supply Tariff Order FY 2023-24",
        effective_from=date(2023, 4, 1),
        effective_to=date(2024, 3, 31),
        groups=_DOMESTIC_GROUPS,
        customer_charges=_CUSTOMER_CHARGES,
        fixed_charge_per_kw=10.0,
        duty_per_unit=0.06,
        verify=_VERIFY,
    ),
    TariffVersion(
        id="TGERC-RST-2024-25",
        order="TGERC Retail Supply Tariff Order FY 2024-25 (domestic rates retained)",
        effective_from=date(2024, 4, 1),
        effective_to=date(2025, 3, 31),
        groups=_DOMESTIC_GROUPS,
        customer_charges=_CUSTOMER_CHARGES,
        fixed_charge_per_kw=10.0,
        duty_per_unit=0.06,
        verify=(*_VERIFY, "customer_charges"),
    ),
    TariffVersion(
        id="TGERC-RST-2025-26",
        order="TGERC Retail Supply Tariff Order FY 2025-26",
        effective_from=date(2025, 4, 1),
        effective_to=date(2026, 3, 31),
        groups=_DOMESTIC_GROUPS,
        customer_charges=_CUSTOMER_CHARGES,
        fixed_charge_per_kw=10.0,
        duty_per_unit=0.06,
        verify=(*_VERIFY, *_NON_DOMESTIC_VERIFY),
        non_domestic=_NON_DOMESTIC,
    ),
    TariffVersion(
        id="TGERC-RST-2026-27",
        order="TGERC Retail Supply Tariff Order FY 2026-27 (domestic rates retained)",
        effective_from=date(2026, 4, 1),
        effective_to=None,
        groups=_DOMESTIC_GROUPS,
        customer_charges=_CUSTOMER_CHARGES,
        fixed_charge_per_kw=10.0,
        duty_per_unit=0.06,
        true_up=TrueUpRule(starts=date(2026, 11, 1), first_month_rate=0.30, later_rate=0.50),
        verify=(*_VERIFY, *_NON_DOMESTIC_VERIFY),
        non_domestic=_NON_DOMESTIC,
    ),
)


def version_for(bill_month: date) -> TariffVersion:
    """Return the tariff version in force for the given bill month."""
    for version in TARIFF_VERSIONS:
        ends = version.effective_to or date.max
        if version.effective_from <= bill_month <= ends:
            return version
    earliest = TARIFF_VERSIONS[0]
    if bill_month < earliest.effective_from:
        return earliest
    return TARIFF_VERSIONS[-1]
