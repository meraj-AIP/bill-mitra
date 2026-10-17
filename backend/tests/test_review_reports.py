"""Revision 2 of bill review: consumer reports from web, button and text, the evidence pack, the automatic request
for earlier bills, attaching uploads, final amounts and the staff timeline. Consumers never see who reviews.

Bills are real fixtures from tests/real.py or labelled variants of them (tests/review_kit.py). Logins are fake.
"""

import asyncio
import logging
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core import service
from app.core.messages import Inbound
from app.core.trace import Event
from app.domain.conversation import guard
from app.domain.conversation.facts import rs, with_revision
from app.domain.conversation.intents import classify, says_no_bills
from app.domain.conversation.lang import PACKS
from app.flows.analysis import analyse
from app.main import app
from app.services import billing_records
from app.store import media, repos
from app.store.db import tx
from tests.real import OCT_2025, PLACEHOLDER_USC, reading, variant
from tests.review_kit import NORMAL, SPIKED, USUAL_MONTHS, Tree, printed, tree
from tests.test_bills_api import PHOTO
from tests.test_complaints import WA_NUMBER

NOTE = "Meter photo shows 351, the reader keyed 693 by mistake."
# Labelled variant: the misread October bill whose printed table only shows June and July 2025.
SHORT = variant(SPIKED, usage_history=USUAL_MONTHS[:2])


def earlier(month: str):
    """Labelled variant: the real October 2025 bill as if it were the bill for an earlier month."""
    return variant(OCT_2025, bill_month=month)


@pytest.fixture
def area() -> Tree:
    return tree()


def _consumer(sign_in) -> tuple[TestClient, str]:
    client = TestClient(app)
    return client, sign_in(client).user_id


def _staff(sign_in, role: str, *scopes: str) -> tuple[TestClient, str]:
    client = TestClient(app)
    return client, sign_in(client, role, scopes=list(scopes) or None).id


def _report(client: TestClient, bill, user_id: str) -> tuple[str, dict]:
    bill_id = repos.save_bill(user_id, bill, media.save(b"synthetic-photo", "image/jpeg"), "verified", 0.0)
    response = client.post(f"/api/bills/{bill_id}/review-request", params={"language": "en"}, json={})
    assert response.status_code == 200, response.text
    return bill_id, response.json()


def _decide(client: TestClient, ticket: str, evidence: list[dict] | None = None, **body) -> dict:
    detail = client.get(f"/api/review/cases/{ticket}").json()
    refs = evidence or [{"kind": "message", "id": str(detail["messages"][0]["id"])}]
    payload = {"reason_code": "photo_misread", "note": NOTE, "evidence": refs, **body}
    response = client.post(f"/api/review/cases/{ticket}/decisions", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


class Chat:
    """A WhatsApp consumer talking to the real conversation engine, with what they were sent."""

    def __init__(self, language: str = "en") -> None:
        self.user = f"wa:{secrets.token_hex(10)}"
        self.language = language
        self.sent: list[dict] = []

    def say(self, **fields) -> list[dict]:
        start = len(self.sent)

        async def keep(event: Event) -> None:
            if event.kind == "message" and event.message is not None:
                self.sent.append(event.message.model_dump())

        inbound = Inbound(channel="whatsapp", user_id=self.user, reply_to=WA_NUMBER, **fields)
        asyncio.run(service.handle(inbound, keep, language=self.language))
        return self.sent[start:]

    def photo(self, reader: Callable, bill) -> list[dict]:
        reader(reading(bill))
        return self.say(kind="image", media_id=media.save(b"synthetic-photo", "image/jpeg"), mime_type="image/jpeg")

    def ticket(self) -> str:
        found = re.findall(r"BM-\d{6}-[A-Z0-9]{5}", " ".join(m.get("body") or "" for m in self.sent))
        assert found
        return found[-1]


def _bodies(messages: list[dict]) -> str:
    return "\n".join(m.get("body") or "" for m in messages)


def _audit(ticket: str) -> list[tuple[str | None, str, str | None]]:
    with tx() as conn:
        return [tuple(r) for r in conn.execute("SELECT actor_id, action, detail FROM audit_log WHERE target = ? "
                                               "ORDER BY id", (ticket,))]


def test_web_report_builds_the_pack_and_asks_only_for_months_not_on_file(sign_in, area):
    staff, _ = _staff(sign_in, "section_ae", area.section_a.id)
    consumer, user = _consumer(sign_in)
    repos.save_bill(user, earlier("2025-08"), None, "verified", 0.0)  # August is already on file as an upload
    _, summary = _report(consumer, printed(SHORT, area.section_a.name), user)
    assert summary["state"] == "waiting_for_you" and summary["requested_months"] == ["2025-09"]
    assert summary["received_months"] == [] and summary["revision"] is None

    detail = staff.get(f"/api/review/cases/{summary['ticket']}").json()
    assert detail["state"] == "info_requested" and detail["requests"][0]["status"] == "open"
    told = detail["messages"][-1]
    assert told["author_kind"] == "system" and told["delivery"] == "stored"
    assert told["body"] == ("To check your October 2025 bill we need your bills for September 2025. "
                            "Please send a photo of each one here.")
    sources = {s["key"]: s for s in detail["evidence_pack"]["sources"]}
    assert list(sources) == ["this_bill", "printed_history", "uploads", "discom_records", "spike", "requested_bills"]
    assert sources["this_bill"]["status"] == "included" and "213 to 693" in sources["this_bill"]["detail"]
    assert sources["printed_history"]["months"] == ["2025-06", "2025-07"]
    assert sources["uploads"]["months"] == ["2025-08"] and sources["uploads"]["status"] == "included"
    assert sources["discom_records"]["status"] == "not_connected"
    assert sources["requested_bills"]["status"] == "missing"
    assert detail["evidence_pack"]["requested_months"] == ["2025-09"]
    automatic = [(actor, action) for actor, action, _ in _audit(summary["ticket"])]
    assert automatic == [(None, "case.route"), (None, "case.pack"), (None, "case.request")]


def test_no_request_when_the_three_months_are_on_file(sign_in, area):
    consumer, user = _consumer(sign_in)
    _, summary = _report(consumer, printed(SPIKED, area.section_a.name), user)
    assert summary["state"] == "received" and summary["requested_months"] == []


@dataclass
class Billing:
    requests: list[httpx.Request] = field(default_factory=list)
    replies: list[httpx.Response] = field(default_factory=list)  # queued answers; empty means the default months


@pytest.fixture
def discom_connected(monkeypatch: pytest.MonkeyPatch) -> Billing:
    """The DISCOM billing system answers through httpx's mock transport; nothing leaves the machine."""
    settings = get_settings()
    monkeypatch.setattr(settings, "billing_records_url", "https://billing.example.test/api/")
    monkeypatch.setattr(settings, "billing_records_token", "test-token-not-real")
    billing = Billing()

    def handler(request: httpx.Request) -> httpx.Response:
        billing.requests.append(request)
        return billing.replies.pop(0) if billing.replies else httpx.Response(200, json={"months": [
            {"month": "2025-08", "units": 140}, {"month": "2025-09", "units": 136}, {"month": "2025-09", "units": 137}]})

    real = httpx.AsyncClient
    monkeypatch.setattr(billing_records.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return billing


def test_connected_billing_records_join_the_pack_and_the_history(sign_in, area, discom_connected):
    staff, _ = _staff(sign_in, "section_ae", area.section_a.id)
    consumer, user = _consumer(sign_in)
    _, summary = _report(consumer, printed(SHORT, area.section_a.name), user)
    request = discom_connected.requests[-1]
    assert request.url.path == f"/api/consumers/{PLACEHOLDER_USC}/history" and request.url.params["months"] == "12"
    assert request.headers["Authorization"] == "Bearer test-token-not-real"
    assert summary["requested_months"] == [] and summary["state"] == "received"  # August and September came from it
    detail = staff.get(f"/api/review/cases/{summary['ticket']}").json()
    records = next(s for s in detail["evidence_pack"]["sources"] if s["key"] == "discom_records")
    assert records["status"] == "included" and records["months"] == ["2025-08", "2025-09"]
    assert [(h["month"], h["source"]) for h in detail["history"]][-3:] == [
        ("2025-08", "discom"), ("2025-09", "discom"), ("2025-10", "this_bill")]
    assert detail["history"][-2]["units"] == 137  # the last copy of a repeated month wins
    discom_connected.replies.append(httpx.Response(200, json={"months": [{"month": "2025-13", "units": 1}]}))
    assert asyncio.run(billing_records.fetch(PLACEHOLDER_USC)).status == "missing"


def test_billing_records_failures_are_missing_and_never_log_the_service_number(discom_connected, caplog,
                                                                               monkeypatch):
    caplog.set_level(logging.DEBUG)
    down = [httpx.Response(500, json={})] * billing_records.LOOKUP.attempts  # a 5xx is retried, then missing
    for replies in (down, [httpx.Response(200, text="not json")], [httpx.Response(200, json={"rows": []})],
                    [httpx.Response(200, json={"months": [{"month": "Sep"}]})]):
        discom_connected.replies.extend(replies)
        assert asyncio.run(billing_records.fetch(PLACEHOLDER_USC)) == billing_records.Records("missing")
    assert PLACEHOLDER_USC not in caplog.text and "test-token-not-real" not in caplog.text
    monkeypatch.setattr(get_settings(), "billing_records_token", "")
    assert asyncio.run(billing_records.fetch(PLACEHOLDER_USC)).status == "not_connected"


def test_dispute_rules_in_four_languages():
    for message in ("My bill is wrong", "the reading is wrong, too high", "బిల్లు తప్పుగా వచ్చింది",
                    "రీడింగ్ తప్పు", "मेरा बिल गलत है", "रीडिंग ग़लत है", "میرا بل غلط ہے", "ریڈنگ غلط ہے"):
        assert classify(message).intent == "dispute", message
    assert classify("why is my bill so much").intent == "why_high"
    assert classify("I want to raise a complaint").intent == "complain"
    for message in ("I don't have them", "నా దగ్గర లేవు", "మెరే", "मेरे पास नहीं हैं", "میرے پاس نہیں ہیں", "no"):
        assert says_no_bills(message) != (message == "మెరే"), message
    assert not says_no_bills("next month")


def test_chat_report_by_card_button_by_flag_button_and_by_text(reader, sign_in, area):
    officer, _ = _staff(sign_in, "officer", area.division.id)
    mismatch = Chat()
    card = [m for m in mismatch.photo(reader, variant(OCT_2025, charge=("energy", 140.0))) if m["type"] == "buttons"]
    assert card[0]["buttons"][0] == {"id": "report_bill", "title": "Bill looks wrong"} and len(card[0]["buttons"]) <= 3
    filed = _bodies(mismatch.say(kind="button_reply", reply_id="report_bill"))
    assert "has gone to TGSPDCL" in filed

    flagged = Chat()
    offers = [m for m in flagged.photo(reader, printed(SPIKED, area.section_a.name))
              if m["type"] == "buttons" and m["buttons"][0]["id"] == "report_bill"]
    assert len(offers) == 1 and "TGSPDCL will check it" in offers[0]["body"]
    flagged.say(kind="button_reply", reply_id="report_bill")
    assert officer.get(f"/api/review/cases/{flagged.ticket()}").json()["channel"] == "whatsapp"

    for language, words in (("en", "The bill is wrong"), ("te", "బిల్లు తప్పుగా వచ్చింది")):
        typed = Chat(language)
        typed.photo(reader, printed(NORMAL, area.section_a.name))
        reply = _bodies(typed.say(kind="text", text=words))
        assert typed.ticket() in reply and "TGSPDCL" in reply
        assert officer.get(f"/api/review/cases/{typed.ticket()}").status_code == 200
        again = _bodies(typed.say(kind="text", text=words))
        assert typed.ticket() in again and typed.ticket() == re.findall(r"BM-\S{12}", reply)[0]


def test_chat_request_attach_and_i_dont_have_it(reader, sign_in, area):
    staff, _ = _staff(sign_in, "section_ae", area.section_a.id)
    chat = Chat()
    chat.photo(reader, printed(SHORT, area.section_a.name))
    asked = _bodies(chat.say(kind="text", text="this bill is wrong"))
    ticket = chat.ticket()
    assert "we need your bills for August 2025 and September 2025" in asked
    detail = staff.get(f"/api/review/cases/{ticket}").json()
    assert detail["messages"][-1]["delivery"] == "sent"  # said in the chat turn itself

    got = _bodies(chat.photo(reader, earlier("2025-08")))
    assert f"Your August 2025 bill is added to report {ticket}" in got
    assert "Okay, we have noted" in _bodies(chat.say(kind="text", text="Sorry, I don't have the other one"))
    detail = staff.get(f"/api/review/cases/{ticket}").json()
    assert detail["state"] == "awaiting_review" and detail["requests"][0]["status"] == "answered"
    pack = detail["evidence_pack"]
    assert pack["received_months"] == ["2025-08"] and pack["attached_bills"][0]["month"] == "2025-08"
    requested = next(s for s in pack["sources"] if s["key"] == "requested_bills")
    assert requested["status"] == "partial" and "do not have the rest" in requested["detail"]


def test_dashboard_uploads_attach_and_complete_the_request(reader, sign_in, area):
    staff, _ = _staff(sign_in, "section_ae", area.section_a.id)
    consumer, user = _consumer(sign_in)
    bill_id, summary = _report(consumer, printed(SHORT, area.section_a.name), user)
    other, other_user = _consumer(sign_in)
    reader(reading(earlier("2025-08")))
    other.post("/api/bills", files=PHOTO)  # same placeholder number, another account: never attached
    assert consumer.get(f"/api/bills/{bill_id}").json()["review"]["received_months"] == []

    consumer.post("/api/bills", files=PHOTO)
    half = consumer.get(f"/api/bills/{bill_id}", params={"language": "en"}).json()["review"]
    assert half["received_months"] == ["2025-08"] and half["state"] == "waiting_for_you"
    reader(reading(earlier("2025-09")))
    consumer.post("/api/bills", files=PHOTO)
    done = consumer.get(f"/api/bills/{bill_id}").json()["review"]
    assert done["received_months"] == ["2025-08", "2025-09"] and done["state"] == "received"
    detail = staff.get(f"/api/review/cases/{summary['ticket']}").json()
    assert detail["requests"][0]["status"] == "answered" and detail["state"] == "awaiting_review"
    attached = detail["evidence_pack"]["attached_bills"]
    assert [b["month"] for b in attached] == ["2025-08", "2025-09"] and attached[0]["media_url"]
    decided = _decide(staff, summary["ticket"], [{"kind": "bill", "id": attached[0]["bill_id"]}], kind="correct",
                      reason_code="bill_correct", note="August bill shows the same pattern of use.")
    assert decided["decisions"][0]["evidence"][0]["label"] == "Bill 2025-08"


def test_no_bills_from_the_web(sign_in, area):
    consumer, user = _consumer(sign_in)
    bill_id, summary = _report(consumer, printed(SHORT, area.section_a.name), user)
    other, _ = _consumer(sign_in)
    url = f"/api/bills/{bill_id}/review-request/no-bills"
    assert other.post(url).status_code == 404
    answered = consumer.post(url, params={"language": "en"})
    assert answered.status_code == 200 and answered.json()["state"] == "received"
    assert answered.json()["requested_months"] == ["2025-08", "2025-09"]
    assert consumer.post(url).status_code == 409
    normal_id, _ = _report(consumer, printed(variant(SPIKED, bill_month="2025-11"), area.section_a.name), user)
    assert consumer.post(f"/api/bills/{normal_id}/review-request/no-bills").status_code == 409


REVIEW_KEYS = re.compile(r"^(review_|spike_|btn_report|reason_|office_unknown|join_last)")
WHO = re.compile(r"\bAE\b|officer|section|ఆఫీసర్|సెక్షన్|అధికారి|अधिकारी|सेक्शन|افسر|سیکشن", re.IGNORECASE)


def test_no_consumer_string_names_who_checks():
    for code, pack in PACKS.items():
        keys = [k for k in pack.T if REVIEW_KEYS.match(k)]
        assert len(keys) >= 20, code
        assert "btn_review" not in pack.T and "review_request" not in pack.T
        assert len(pack.T["btn_report"]) <= 20
        for key in keys:
            assert not WHO.search(pack.T[key]), (code, key)


def test_final_amounts_everywhere_after_approval_with_no_names(reader, sign_in, area):
    ae_client = TestClient(app)
    ae = sign_in(ae_client, "section_ae", scopes=[area.section_a.id])
    chat = Chat()
    chat.photo(reader, printed(SPIKED, area.section_a.name))
    chat.say(kind="button_reply", reply_id="report_bill")
    _decide(ae_client, chat.ticket(), kind="corrected_reading", corrected_present_reading=351)
    revised_total = OCT_2025.bill_amount + OCT_2025.arrears
    due = _bodies(chat.say(kind="text", text="when to pay"))
    assert f"Rs {rs(revised_total)}" in due and rs(SPIKED.total_payable) not in due

    consumer, user = _consumer(sign_in)
    bill_id, filed = _report(consumer, printed(variant(SPIKED, bill_month="2025-11"), area.section_a.name), user)
    _decide(ae_client, filed["ticket"], kind="corrected_reading", corrected_present_reading=351)
    report = consumer.get(f"/api/bills/{bill_id}", params={"language": "en"})
    body = report.json()
    assert body["final"] == {"bill_amount": OCT_2025.bill_amount, "total_payable": revised_total, "revised": True,
                             "status": "pending_update"}
    assert body["bill"]["total_payable"] == SPIKED.total_payable  # the original is never edited
    revision = body["review"]["revision"]
    assert body["review"]["state"] == "revised" and revision["office"] == "TGSPDCL"
    assert revision["original_total"] == SPIKED.total_payable and revision["revised_total"] == revised_total
    row = next(r for r in consumer.get("/api/bills").json()["items"] if r["id"] == bill_id)
    assert row["total_payable"] == revised_total and row["original_total_payable"] == SPIKED.total_payable
    for text in (report.text, consumer.get("/api/bills").text, consumer.post(
            f"/api/bills/{bill_id}/review-request/no-bills").text):
        assert ae.name not in text and not re.search(r"\bAE\b", text)
    plain = consumer.get(f"/api/bills/{repos.save_bill(user, NORMAL, None, 'verified', 0.0)}").json()
    assert plain["final"]["revised"] is False and plain["final"]["total_payable"] == NORMAL.total_payable


def test_revised_figures_pass_the_number_guard():
    facts = with_revision(analyse(SPIKED, "guard-test").facts, OCT_2025.bill_amount)
    assert facts.total_payable == OCT_2025.bill_amount + OCT_2025.arrears
    assert guard.check(f"Please pay Rs {rs(facts.total_payable)}, it was Rs {rs(SPIKED.total_payable)}.",
                       facts).passed
    assert not guard.check("Please pay Rs 1,111.", facts).passed


def test_timeline_runs_in_order_with_system_consumer_and_staff(reader, sign_in, area):
    officer, _ = _staff(sign_in, "officer", area.division.id)
    _, ae_id = _staff(sign_in, "section_ae", area.section_a.id)
    consumer, user = _consumer(sign_in)
    _, summary = _report(consumer, printed(SHORT, area.section_a.name), user)
    reader(reading(earlier("2025-09")))
    consumer.post("/api/bills", files=PHOTO)
    officer.post(f"/api/review/cases/{summary['ticket']}/assign", json={"account_id": ae_id})
    timeline = officer.get(f"/api/review/cases/{summary['ticket']}").json()["timeline"]
    kinds = [(e["actor"]["kind"], e["text"].split(":")[0]) for e in timeline]
    assert kinds == [("consumer", "Reported the bill as wrong"), ("system", "Routed"),
                     ("system", "Evidence pack built"), ("system", "Asked the consumer for"),
                     ("consumer", "Sent a requested bill"), ("staff", "Assigned")]
    assert [e["at"] for e in timeline] == sorted(e["at"] for e in timeline)
    assert timeline[1]["actor"]["name"] == "System" and timeline[-1]["actor"]["name"].startswith("Test officer")
    assert "earlier bills for 2025-08, 2025-09" in timeline[3]["text"]
    assert timeline[1]["text"].startswith(f"Routed: section {area.section_a.name}, assignee Test section_ae")
    assert timeline[-1]["text"].startswith("Assigned: to Test section_ae")
