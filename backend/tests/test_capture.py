"""The consistency gate, on the two real bills and on what the live model really misread."""

import pytest

from app.domain import capture
from tests.real import MAR_2024, OCT_2025, variant


@pytest.mark.parametrize("bill", [OCT_2025, MAR_2024])
def test_real_bills_pass_every_check_and_capture_every_field(bill):
    rep = capture.report(bill)
    assert rep.trusted and rep.problem is None
    assert rep.captured == rep.expected - 1  # section is dropped from the fixtures
    assert {c.key: c.status for c in rep.checks} == {"readings": "pass", "charges_sum": "pass", "total": "pass",
                                                      "days": "pass"}


def test_service_number_never_leaves_unmasked():
    fields = {f.key: f.value for f in capture.report(OCT_2025).fields}
    assert fields["service_number"] == "••••••••1111"


def test_row_shift_misread_is_caught():
    # Live model output for a tilted photo of the March 2024 slip.
    misread = variant(MAR_2024, line_items=[{**i.model_dump(), "amount": 9.42} if i.code == "customer"
                                            else i.model_dump() for i in MAR_2024.line_items])
    rep = capture.report(misread)
    assert not rep.trusted and "do not add up" in (rep.problem or "")
    assert capture.failed_check(misread) == "Charges add up to the bill amount"


def test_consistent_misread_of_both_readings_is_still_caught_by_charges():
    # Live model output for an extremely blurred October slip: 189 units, readings misread to agree.
    misread = variant(OCT_2025, units=189, present_reading=402.0, line_items=[
        {**i.model_dump(), "amount": 108.2} if i.code == "energy" else i.model_dump() for i in OCT_2025.line_items])
    assert not capture.report(misread).trusted


@pytest.mark.parametrize("changes", [{"units": None}, {"unreadable_fields": ["bill_amount"]}, {"confidence": 0.4},
                                     {"total_payable": 1345.0}, {"present_reading": 352.0, "previous_reading": 200.0}])
def test_untrusted_readings(changes):
    assert not capture.report(variant(OCT_2025, **changes)).trusted


def test_cut_off_bottom_skips_checks_and_asks_again():
    rep = capture.report(variant(OCT_2025, bill_amount=None, total_payable=None,
                                 unreadable_fields=["bill_amount", "total_payable"]))
    assert {c.key: c.status for c in rep.checks}["charges_sum"] == "skipped" and not rep.trusted


def test_days_check_uses_reading_dates():
    rep = capture.report(variant(OCT_2025, billing_days=45))
    assert {c.key: c.status for c in rep.checks}["days"] == "fail"
