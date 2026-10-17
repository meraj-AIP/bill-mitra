"""Any line on the bill can be asked about, and the meter status code is read, explained and flagged.

Bills are the real ones in tests/real.py; a test that needs another status changes that one printed code."""

import pytest

from app.domain import capture, meter_status
from app.domain.audit import audit
from app.domain.conversation import terms
from app.domain.conversation.lang import PACKS
from app.flows.analysis import analyse
from tests.real import OCT_2025, SOLAR_SEP_2026, reading, variant
from tests.test_conversation import bodies, new_user, run


@pytest.mark.parametrize(("message", "code"), [
    ("what is ACD?", "acd"), ("ACD అంటే ఏమిటి", "acd"), ("what is sd available", "sd"),
    ("why is there a surcharge", "surcharge"), ("what is loss/gain", "loss_gain"), ("what is MD on my bill", "md"),
    ("what does kVAh mean", "kvah"), ("what is MF", "mf"), ("what is the status 05", "meter_status"),
    ("when is the disc date", "disc_date"), ("how much solar did I export", "solar"), ("what is my usc", "usc"),
    ("బకాయి ఎందుకు", "arrears"), ("मेरा पावर फैक्टर क्या है", "pf"), ("سولر کیا ہے", "solar"),
])
def test_terms_are_recognised_in_every_language(message, code):
    found = terms.match(message)
    assert found is not None and found.code == code


def test_short_codes_match_whole_words_only():
    assert terms.match("please command the officer") is None  # "md" inside "command"
    assert terms.match("my category") is not None and terms.match("my category").code == "category"


def test_every_term_and_status_has_words_in_every_language():
    keys = {f"term_{t.code}" for t in terms.TERMS} | {f"sts_{k}" for k in meter_status.STAFF_LABEL}
    for code, pack in PACKS.items():
        assert keys <= set(pack.T), (code, keys - set(pack.T))


def test_term_answer_quotes_this_bill():
    a = analyse(SOLAR_SEP_2026, new_user())
    sd = terms.answer(terms.match("what is sd available"), a.bill, a.facts, "en")
    assert "security deposit" in sd and "Rs 58,326" in sd
    solar = terms.answer(terms.match("export"), a.bill, a.facts, "en")
    assert "3101 units imported, 9 exported, 3092 billed" in solar
    assert "On your bill: Rs 0." in terms.answer(terms.match("acd"), a.bill, a.facts, "en")  # printed as 0.00
    house = analyse(OCT_2025, new_user())
    assert "not printed" in terms.answer(terms.match("sd available"), house.bill, house.facts, "en")
    assert "door was locked" in terms.answer(terms.match("status"), variant(SOLAR_SEP_2026, present_status="05"),
                                             a.facts, "en")


def test_chat_answers_a_bill_term_but_keeps_real_intents(reader):
    user = new_user()
    reader(reading(SOLAR_SEP_2026))
    run(user, kind="image")
    assert "Recorded MD" in bodies(run(user, kind="text", text="what is MD?"))
    assert "Power factor" in bodies(run(user, kind="text", text="why is my power factor 0.99"))
    disputed = bodies(run(user, kind="text", text="my reading is wrong"))
    assert "Prs (present)" not in disputed  # a dispute is still a dispute, not a glossary answer


def test_estimated_reading_is_explained_flagged_and_never_drafted_correct(reader):
    door = variant(OCT_2025, present_status="05")
    rep = capture.report(door)
    assert rep.trusted and {c.key: c.status for c in rep.checks}["reading_status"] == "fail"
    a = analyse(door, new_user())
    assert "estimated_reading" in audit(door, a.comp).notes
    reader(reading(door))
    said = bodies(run(new_user(), kind="image"))
    assert "status on this bill is 05" in said and "door was locked" in said
    normal = capture.report(variant(OCT_2025, present_status="01"))
    assert {c.key: c.status for c in normal.checks}["reading_status"] == "pass"
