"""Every bill is read twice and a key figure is trusted only when the reads agree; a third read decides by majority,
and a figure with no majority is never guessed. The model is faked; bills are the real fixtures in tests/real.py."""

import asyncio

import pytest

from app.config import get_settings
from app.domain import capture, second_read
from app.services import vision
from app.services.openai_client import ProviderError
from tests.real import OCT_2025, SOLAR_DOM_OCT_2026, variant

SEEN = vision.Classification(document_type="electricity_bill", quality="good", discom="TGSPDCL")


def test_reads_that_agree_have_nothing_to_settle():
    assert second_read.disagreements(OCT_2025, OCT_2025.model_copy()) == []


def test_the_majority_of_three_reads_wins_each_figure():
    misread = variant(OCT_2025, units=188, bill_amount=592.0)
    other = variant(OCT_2025, bill_amount=592.0)
    voted, undecided = second_read.vote([misread, OCT_2025, other])
    assert undecided == [] and voted.units == 138 and voted.bill_amount == 592.0
    assert capture.report(voted).checks  # a whole bill, ready for the checks


def test_charge_rows_are_voted_as_a_whole():
    wrong = variant(OCT_2025, charge=("energy", 581.2))
    voted, undecided = second_read.vote([wrong, OCT_2025, OCT_2025.model_copy()])
    assert undecided == [] and voted.item("energy") == 518.2


def test_a_figure_with_no_majority_is_cleared_and_the_bill_is_not_trusted():
    voted, undecided = second_read.vote([OCT_2025, variant(OCT_2025, units=188)])
    assert undecided == ["units"]
    marked = second_read.mark_undecided(voted, undecided)
    assert marked.units is None and "units" in marked.unreadable_fields and not capture.report(marked).trusted


def test_an_unsettled_date_is_shown_unclear_but_does_not_block():
    marked = second_read.mark_undecided(OCT_2025, ["due_date"])
    assert marked.due_date is None and "due_date" in marked.unreadable_fields and capture.report(marked).trusted


def test_unsettled_charges_block_through_the_energy_figure():
    marked = second_read.mark_undecided(OCT_2025, ["line_items"])
    assert "energy" in marked.unreadable_fields and not capture.report(marked).trusted


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Read twice on, with a fake reader that answers from a queue and records how it was asked."""
    monkeypatch.setattr(get_settings(), "read_twice", True)
    calls: list[dict[str, object]] = []
    answers: list[object] = []

    async def fake(_jpeg: bytes, _seen: object, failed_check: str | None = None, suspects: object = None,
                   doubts: list[str] | None = None, sharp: bool = False) -> object:
        calls.append({"sharp": sharp, "doubts": doubts})
        answer = answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    monkeypatch.setattr(vision, "extract", fake)
    calls.append({"answers": answers})  # the test fills this list; the first entry is only the handle
    return calls


def _run(model: list[dict[str, object]], *answers: object):
    model[0]["answers"].extend(answers)  # type: ignore[union-attr]
    return asyncio.run(vision._read_twice(b"jpeg", SEEN)), model[1:]


def test_two_agreeing_reads_are_made_at_once_one_of_them_sharpened(model):
    bill, calls = _run(model, OCT_2025, OCT_2025.model_copy())
    assert bill.units == 138 and [c["sharp"] for c in calls] == [False, True]


def test_a_disagreement_calls_a_third_read_told_only_which_figures(model):
    bill, calls = _run(model, variant(OCT_2025, units=188), OCT_2025, OCT_2025.model_copy())
    assert bill.units == 138 and len(calls) == 3 and calls[2]["doubts"] == ["units"]


def test_a_misread_both_ways_with_no_third_answer_is_unclear(model):
    bill, calls = _run(model, variant(SOLAR_DOM_OCT_2026, arrears=-52.0), SOLAR_DOM_OCT_2026,
                       ProviderError("down"))
    assert "arrears" in bill.unreadable_fields and "bill_amount" in bill.unreadable_fields
    assert not capture.report(bill).trusted


def test_one_read_failing_at_the_provider_leaves_the_other(model):
    bill, calls = _run(model, ProviderError("busy"), OCT_2025)
    assert bill.units == 138 and len(calls) == 2


def test_a_fault_that_is_not_the_provider_is_raised(model):
    with pytest.raises(KeyError):
        _run(model, KeyError("bug"), OCT_2025)
