"""Reply options on the staff complaint page: chosen by type and context, figures only from the engine, an AI draft
only on request and held to the option's own figures, no staff words in consumer copy, permissions and scope.

Bills are the synthetic test bills; the text model is stubbed at its boundary (llm.word_reply)."""

import secrets
from dataclasses import replace
from itertools import product

import pytest

from app.domain import complaint_options as co
from app.domain.complaint_types import TYPES
from app.domain.conversation import guard
from app.domain.conversation.lang import PACKS
from app.flows.analysis import analyse
from app.services import llm
from app.store import accounts, db
from app.store import complaints as store
from tests.real import OCT_2025
from tests.test_complaint_actions import signed_in
from tests.test_complaints import OVERCHARGED, PASSWORD, chat_complaint

TICKET = "BM-TICKET"  # no digits, so any number in a text is one the option itself carries
BILL_KEYS = {"overcharge", "bill_correct", "needs_check"}
SUPPLY = ("power_outage", "voltage_fluctuation", "supply_other")


def ctx(type_code: str, bill=None, language: str = "en", **fields) -> co.Context:
    a = analyse(bill, "web:options-test") if bill is not None else None
    return co.Context(ticket=TICKET, type=type_code, status="Open", language=language,
                      facts=a.facts if a else None, audit=a.audit if a else None, **fields)


def keys(c: co.Context) -> list[str]:
    return [o.key for o in co.reply_options(c)]


def test_options_differ_by_type_and_fit_what_was_asked():
    verified = {t.code: keys(ctx(t.code, OCT_2025)) for t in TYPES}
    assert verified["high_bill"] == ["bill_correct", "ask_meter_photo"]
    assert verified["payment_not_updated"] == ["ask_payment_proof", "payment_posting"]
    assert verified["bill_not_received"] == ["bill_how_to", "bill_delivery_check"]
    assert verified["meter_burnt"][0] == "meter_burnt_visit" and verified["meter_issue"][0] == "meter_visit"
    assert keys(ctx("high_bill", OVERCHARGED))[0] == "overcharge"
    assert keys(ctx("high_bill"))[:2] == ["ask_bill_photo", "high_bill_checking"]
    assert len({tuple(k) for k in verified.values()}) >= 10
    for code, found in verified.items():
        assert 2 <= len(found) <= 4, code
        assert ("call_1912" in found) == (code in SUPPLY), code


@pytest.mark.parametrize("code", SUPPLY + ("meter_issue", "meter_burnt", "payment_not_updated", "bill_not_received"))
def test_supply_meter_and_payment_complaints_never_explain_the_bill(code):
    for bill in (OVERCHARGED, OCT_2025, None):
        c = ctx(code, bill)
        assert not BILL_KEYS & set(keys(c)), (code, bill)
        if code in SUPPLY:
            assert not {"bill_photo", "meter_photo"} & {a.kind for a in co.ask_options(c)}


def test_conversation_state_changes_the_options():
    base = ctx("high_bill", OCT_2025)
    assert "ask_meter_photo" not in keys(replace(base, asked=frozenset({"meter_photo"})))
    waiting = replace(base, asked=frozenset({"meter_photo"}), waiting=frozenset({"meter_photo"}))
    assert keys(waiting)[0] == "waiting_reminder" and "meter_photo" not in [a.kind for a in co.ask_options(waiting)]
    assert keys(replace(base, answered=True, sent_photo=True))[0] == "photo_thanks"
    assert keys(replace(base, answered=True))[0] == "answer_thanks"
    closed = replace(base, status="Resolved")
    assert keys(closed) == ["closing_resolved", "closing_followup"] and co.ask_options(closed) == []
    assert "bill_photo" not in co.allowed_asks(base) and "bill_photo" in co.allowed_asks(ctx("high_bill"))
    assert co.ask_options(ctx("payment_not_updated"))[0].kind == "payment_proof"


@pytest.mark.parametrize("language", sorted(PACKS))
def test_only_bill_options_carry_figures_and_only_the_engines(language):
    for t, bill in product(TYPES, (OVERCHARGED, OCT_2025, None)):
        c = ctx(t.code, bill, language)
        for option in co.reply_options(c):
            if option.key not in BILL_KEYS:
                assert guard.numbers_in(option.text) <= {1912.0}, (t.code, option.key)
                continue
            assert c.facts and c.audit, option.key
            lines = {abs(v) for ln in c.audit.lines for v in (ln.printed, ln.expected, ln.difference) if v}
            assert guard.check(option.text, c.facts, lines).passed, option.key


def test_consumer_copy_never_names_who_handles_it():
    for pack in PACKS.values():
        for key, value in pack.T.items():
            if key.startswith(("opt_", "request_", "reply_")):
                assert not co.STAFF_WORDS.search(value), (pack.CODE, key)
    assert co.STAFF_WORDS.search("A lineman will visit") and co.STAFF_WORDS.search("లైన్‌మ్యాన్ వస్తారు")


# Through the API


@pytest.fixture(scope="module")
def people() -> dict[str, accounts.Account]:
    tag = secrets.token_hex(3)
    make = accounts.create
    return {"south": make("officer", f"officer-ro-{tag}@example.com", "Test officer", PASSWORD, "TGSPDCL"),
            "north": make("officer", f"officer-rn-{tag}@example.com", "Test officer", PASSWORD, "TGNPDCL"),
            "auditor": make("auditor", f"auditor-ro-{tag}@example.com", "Test auditor", PASSWORD, "TGSPDCL")}


def _retype(ticket: str, type_code: str, description: str | None = None) -> None:
    conn = db.connection()
    conn.execute("UPDATE complaints SET type = ?, bill_id = NULL, description = COALESCE(?, description) "
                 "WHERE ticket = ?", (type_code, description, ticket))
    conn.commit()


def test_opening_the_page_calls_no_model(reader, people, monkeypatch):
    async def must_not_run(*_: object) -> str:
        raise AssertionError("the model was called without a click")

    monkeypatch.setattr(llm, "word_reply", must_not_run)
    ticket = chat_complaint(reader, "web")
    body = signed_in(people["south"]).get(f"/api/console/complaints/{ticket}/options").json()
    assert body["options"][0]["key"] == "overcharge" and all(o["why"] for o in body["options"])
    assert [r["kind"] for r in body["requests"]][0] == "meter_photo"


def test_supply_complaint_gets_supply_options_and_cannot_be_asked_for_a_bill(reader, people):
    ticket = chat_complaint(reader, "web")
    _retype(ticket, "power_outage")
    officer = signed_in(people["south"])
    body = officer.get(f"/api/console/complaints/{ticket}/options").json()
    assert [o["key"] for o in body["options"]] == ["crew_informed", "call_1912"] and body["triage"] is None
    assert [r["kind"] for r in body["requests"]] == ["details"]
    path = f"/api/console/complaints/{ticket}/request"
    assert officer.post(path, json={"kind": "bill_photo"}).status_code == 422
    assert officer.post(path, json={"kind": "details"}).status_code == 200
    after = officer.get(f"/api/console/complaints/{ticket}/options").json()
    assert after["options"][0]["key"] == "waiting_reminder" and after["requests"] == []


def test_ai_draft_falls_back_on_any_failed_check_and_sees_no_personal_numbers(reader, people, monkeypatch):
    ticket = chat_complaint(reader, "web")
    _retype(ticket, "payment_not_updated", "Paid on the app, call me on 9999999999, ref 99887766")
    officer = signed_in(people["south"])
    path = f"/api/console/complaints/{ticket}/draft"
    template = next(o["text"] for o in officer.get(f"/api/console/complaints/{ticket}/options").json()["options"]
                    if o["key"] == "payment_posting")
    assert officer.post(path, json={"option_key": "payment_posting"}).json() == {"text": template,
                                                                                 "worded_by": "rules"}
    seen: list[str] = []

    def stub(answer: str):
        async def word(draft: str, _language: str, topic: str, said: str) -> str:
            seen.append(said)
            assert topic == "Payment made but not shown"
            return answer
        return word

    for bad in ("It will be posted within 2 days.", "Our officer will post it."):
        monkeypatch.setattr(llm, "word_reply", stub(bad))
        assert officer.post(path, json={"option_key": "payment_posting"}).json()["worded_by"] == "rules"
    monkeypatch.setattr(llm, "word_reply", stub("Thank you for waiting. We are tracing your payment now."))
    assert officer.post(path, json={"option_key": "payment_posting"}).json()["worded_by"] == "ai"
    assert seen and all("9999999999" not in s and "99887766" not in s and "Paid on the app" in s for s in seen)
    assert officer.post(path, json={"option_key": "bill_correct"}).status_code == 404


def test_reply_that_asks_waits_for_the_answer(reader, people):
    ticket = chat_complaint(reader, "web", OCT_2025)
    officer = signed_in(people["south"])
    first = officer.get(f"/api/console/complaints/{ticket}/options").json()["options"]
    ask = next(o for o in first if o["key"] == "ask_meter_photo")
    assert ask["asks"] == "meter_photo"
    officer.post(f"/api/console/complaints/{ticket}/reply", json={"body": ask["text"], "asks": "meter_photo"})
    after = officer.get(f"/api/console/complaints/{ticket}/options").json()
    assert "ask_meter_photo" not in [o["key"] for o in after["options"]]
    assert after["options"][0]["key"] == "waiting_reminder"
    assert "meter_photo" not in [r["kind"] for r in after["requests"]]


def test_draft_needs_reply_permission_and_scope(reader, people):
    ticket = chat_complaint(reader, "web")
    body = {"option_key": "overcharge"}
    auditor = signed_in(people["auditor"])
    assert auditor.get(f"/api/console/complaints/{ticket}/options").status_code == 200
    assert auditor.post(f"/api/console/complaints/{ticket}/draft", json=body).status_code == 403
    north = signed_in(people["north"])
    assert north.get(f"/api/console/complaints/{ticket}/options").status_code == 404
    assert north.post(f"/api/console/complaints/{ticket}/draft", json=body).status_code == 404
    assert store.get(ticket) is not None
