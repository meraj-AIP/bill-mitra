from datetime import date

import pytest

from app.domain.tariff.engine import compute, true_up_rate
from tests.real import MAR_2024, OCT_2025, SOLAR_SEP_2026

OCT = date(2026, 10, 1)


@pytest.mark.parametrize(
    ("units", "group", "energy"),
    [
        (0, "LT-I(A)", 0.0),
        (50, "LT-I(A)", 97.5),
        (100, "LT-I(A)", 252.5),
        (101, "LT-I(B)", 344.8),
        (156, "LT-I(B)", 608.8),
        (200, "LT-I(B)", 820.0),
        (201, "LT-I(C)", 1027.7),
        (230, "LT-I(C)", 1251.0),
        (450, "LT-I(C)", 3165.0),
        (900, "LT-I(C)", 7490.0),
    ],
)
def test_energy_by_slab(units, group, energy):
    comp = compute(units, OCT)
    assert comp.group == group
    assert comp.energy == energy


def test_charges_add_up():
    comp = compute(156, OCT)
    assert comp.gross == round(comp.energy + comp.fixed + comp.customer + comp.duty + comp.fsa, 2)
    assert comp.net == comp.gross


def test_gruha_jyothi_zero_bill_up_to_200():
    comp = compute(200, OCT, gruha_jyothi_eligible=True)
    assert comp.gruha_jyothi_applied and comp.net == 0 and comp.subsidy == comp.gross


def test_gruha_jyothi_lost_at_201():
    comp = compute(201, OCT, gruha_jyothi_eligible=True)
    assert not comp.gruha_jyothi_applied and comp.net == comp.gross > 1000


@pytest.mark.parametrize(("month", "tariff"), [
    (date(2024, 3, 1), "TGERC-RST-2023-24"), (date(2024, 6, 1), "TGERC-RST-2024-25"),
    (date(2026, 3, 1), "TGERC-RST-2025-26"), (OCT, "TGERC-RST-2026-27"),
])
def test_each_month_uses_the_order_in_force(month, tariff):
    assert compute(150, month).tariff_id == tariff


@pytest.mark.parametrize(("units", "customer"), [(40, 40.0), (90, 70.0), (138, 90.0), (250, 100.0), (350, 120.0),
                                                 (600, 140.0), (900, 160.0)])
def test_customer_charges_follow_the_tgerc_schedule(units, customer):
    assert compute(units, OCT).customer == customer


@pytest.mark.parametrize(("bill", "energy", "slabs"), [
    (OCT_2025, 518.20, [(103, 3.40), (35, 4.80)]),  # 31 days read from a 30 day September
    (MAR_2024, 599.60, [(110, 3.40), (47, 4.80)]),  # 32 days read from a 29 day February
])
def test_engine_reproduces_real_bills_to_the_paisa(bill, energy, slabs):
    comp = compute(bill.units, bill.month_date(), bill.load_kw, False, bill.period())
    assert comp.energy == energy == bill.item("energy")
    assert [(line.units, line.rate) for line in comp.slab_lines] == slabs
    for code in ("fixed", "customer", "duty"):
        assert comp.charges()[code] == bill.item(code)


def test_billing_period_out_of_range_rejected():
    with pytest.raises(ValueError):
        compute(100, OCT, period=3.0)


def test_true_up_rates():
    assert true_up_rate(date(2026, 10, 1)) is None
    assert true_up_rate(date(2026, 11, 1)) == 0.30
    assert true_up_rate(date(2026, 12, 1)) == 0.50


def test_negative_units_rejected():
    with pytest.raises(ValueError):
        compute(-1, OCT)


def test_lt2_commercial_solar_bill_matches_to_the_paisa():
    """A real 2B net-metered bill: 3101 imported, 9 exported, 3092 billed over 33 days from an August reading."""
    from app.domain.audit import audit
    from app.domain.capture import report

    bill = SOLAR_SEP_2026
    comp = compute(bill.net_units(), bill.month_date(), bill.load_kw or 1.0, period=bill.period(),
                   category="non_domestic", import_units=bill.units)
    assert (comp.group, comp.units) == ("LT-II(B)", 3092)
    assert (comp.energy, comp.fixed, comp.customer, comp.duty) == (33384.90, 4000.0, 160.0, 186.06)
    result = audit(bill, comp)
    assert result.status == "verified" and "net_metering" in result.notes
    rep = report(bill)
    assert rep.trusted and {c.key: c.status for c in rep.checks}["net_units"] == "pass"


def test_lt2_needs_a_version_with_lt2_rates_and_never_gets_gruha_jyothi():
    with pytest.raises(ValueError):
        compute(100, date(2024, 3, 1), category="non_domestic")
    shop = compute(40, date(2025, 6, 1), gruha_jyothi_eligible=True, category="non_domestic")
    assert shop.group == "LT-II(A)" and shop.energy == 280.0 and not shop.gruha_jyothi_applied and shop.net > 0
