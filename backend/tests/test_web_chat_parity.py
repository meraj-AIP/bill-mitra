"""Web chat parity: with WhatsApp not connected, one device is the consumer in the web chat and another is staff.
Everything WhatsApp would carry to the consumer lands in their web chat, and what they send there reaches staff.

Each test plays both devices through the real API with two signed in TestClient sessions. The vision provider and
the language model are stubbed at their boundary (the `reader` fixture). Bills are real fixtures or labelled
variants; logins and numbers are obviously synthetic.
"""

import asyncio
import json
import re
import secrets
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.domain.conversation.lang import text
from app.flows import automation, case_bills, extract, recovery
from app.main import app
from app.services import notify
from app.services.openai_client import ProviderError
from app.store import case_evidence as evidence_store
from app.store import complaints as complaint_store
from app.store import repos
from app.store.db import tx
from tests.real import OCT_2025, reading, variant
from tests.review_kit import SPIKED, USUAL_MONTHS, Tree, printed, tree
from tests.test_bills_api import PHOTO
from tests.test_complaints import OVERCHARGED

TICKET = re.compile(r"BM-\d{6}-[A-Z0-9]{5}")
DOWN = ProviderError("HTTPStatusError", transient=True)
TELUGU = re.compile("[\\u0C00-\\u0C7F]")


@pytest.fixture
def area() -> Tree:
    return tree()


class Device:
    """One signed in browser: a consumer in the web chat, or a staff member in the console."""

    def __init__(self, sign_in, role: str = "consumer", *scopes: str, discom: str | None = None) -> None:
        self.client = TestClient(app)
        self.account = sign_in(self.client, role, discom, scopes=list(scopes) or None)
        self.seen = 0  # the newest chat id this device has read, as the open page keeps it

    def say(self, language: str = "en", **message: object) -> list[dict]:
        response = self.client.post("/api/web/messages", json={"language": language, **message})
        assert response.status_code == 200, response.text
        return [json.loads(line) for line in response.text.splitlines() if line]

    def photo(self, language: str = "en") -> list[dict]:
        # Each photo is a new file, as real photos are: the same file sent again reuses its earlier reading.
        name, data, mime = PHOTO["file"]
        uploaded = self.client.post("/api/web/upload", files={"file": (name, data + secrets.token_bytes(8), mime)}).json()
        return self.say(language, kind="image", media_id=uploaded["media_id"], mime_type=uploaded["mime_type"])

    def new_in_chat(self) -> list[dict]:
        """What the page's poll would append: bot messages after the last one read."""
        items = self.client.get(f"/api/web/history?after={self.seen}").json()["items"]
        if items:
            self.seen = items[-1]["id"]
        return [i["body"] for i in items if i["sender"] == "bot"]


def said(messages: list[dict]) -> str:
    return "\n".join(m.get("body") or "" for m in messages)


def _chat_complaint(consumer: Device, reader) -> str:
    reader(reading(OVERCHARGED))
    consumer.photo()
    consumer.say(kind="button_reply", reply_id="complain")
    filed = consumer.say(kind="button_reply", reply_id="complaint_send")
    found = TICKET.findall(said([e["message"] for e in filed if e["kind"] == "message"]))
    assert found
    consumer.new_in_chat()
    return found[-1]


def _thread(staff: Device, ticket: str) -> list[dict]:
    return staff.client.get(f"/api/console/complaints/{ticket}").json()["messages"]


def test_a_web_chat_complaint_round_trip_with_staff_on_another_device(sign_in, reader, area):
    consumer = Device(sign_in)
    officer = Device(sign_in, "officer", discom="TGSPDCL")
    ae = Device(sign_in, "section_ae", area.section_a.id)
    ticket = _chat_complaint(consumer, reader)

    officer.client.post(f"/api/console/complaints/{ticket}/reply", json={"body": "We are checking the energy charge."})
    assert "We are checking the energy charge." in said(consumer.new_in_chat())

    asked = officer.client.post(f"/api/console/complaints/{ticket}/request",
                                json={"kind": "note", "note": "When was the meter last read?"})
    assert asked.status_code == 200 and asked.json()["messages"][-1]["delivery"] == "sent"
    assert "When was the meter last read?" in said(consumer.new_in_chat())
    answered = consumer.say(kind="text", text="On the third of this month.")
    assert text("en", "complaint_info_received", ticket=ticket) in said(
        [e["message"] for e in answered if e["kind"] == "message"])
    assert _thread(officer, ticket)[-1]["body"] == "On the third of this month."

    meter = {"kind": "note", "note": "Please send a photo of the meter."}
    officer.client.post(f"/api/console/complaints/{ticket}/request", json=meter)
    consumer.photo()
    last = _thread(officer, ticket)[-1]
    assert last["author_kind"] == "consumer" and last["media_url"]

    consumer.new_in_chat()
    target = next(p for p in officer.client.get(f"/api/console/complaints/{ticket}").json()["assignable"]
                  if p["id"] == ae.account.id)
    handed = officer.client.post(f"/api/console/complaints/{ticket}/assign",
                                 json={"account_id": target["id"], "note": "Section AE to check the meter."})
    assert handed.status_code == 200
    assert consumer.new_in_chat() == []  # a hand over is between staff; the consumer never hears a name

    for status in ("Resolved", "In progress", "Rejected"):  # resolve, reopen, reject
        assert ae.client.post(f"/api/console/complaints/{ticket}/status", json={"status": status}).status_code == 200
        line = text("en", "complaint_status", ticket=ticket, status=notify.status_label("en", status))
        assert said(consumer.new_in_chat()) == line
    assert ae.account.name not in json.dumps(consumer.client.get("/api/web/history").json())


def test_a_call_centre_complaint_for_a_consumer_mobile_reaches_their_web_chat(sign_in, area):
    consumer = Device(sign_in)
    agent = Device(sign_in, "call_centre", area.division.id)
    raised = agent.client.post("/api/console/complaints", json={
        "type": "power_outage", "discom": "TGSPDCL", "section_id": area.section_a.id, "source": "call_centre",
        "contact_mobile": consumer.account.login, "description": "Caller says supply is off since morning."})
    assert raised.status_code == 201, raised.text
    ticket = raised.json()["ticket"]
    assert complaint_store.get(ticket).user_id == consumer.account.user_id  # type: ignore[union-attr]
    agent.client.post(f"/api/console/complaints/{ticket}/status", json={"status": "Resolved"})
    assert ticket in said(consumer.new_in_chat())


def _report(consumer: Device, bill, language: str) -> tuple[str, str]:
    bill_id = repos.save_bill(consumer.account.user_id, bill, None, "verified", 0.0)
    response = consumer.client.post(f"/api/bills/{bill_id}/review-request", params={"language": language}, json={})
    assert response.status_code == 200, response.text
    return bill_id, response.json()["ticket"]


def _decide(ae: Device, ticket: str, **body: object) -> dict:
    detail = ae.client.get(f"/api/review/cases/{ticket}").json()
    payload = {"reason_code": "photo_misread", "note": "Meter photo shows 351, the reader keyed 693.",
               "evidence": [{"kind": "message", "id": str(detail["messages"][0]["id"])}], **body}
    response = ae.client.post(f"/api/review/cases/{ticket}/decisions", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _told(staff: Device, ticket: str) -> list[str]:
    """What the case says it sent the consumer: every message must be in their chat, marked sent."""
    sent = [m for m in staff.client.get(f"/api/review/cases/{ticket}").json()["messages"]
            if m["author_kind"] == "system" and m["delivery"] == "sent"]
    return [m["body"] for m in sent]


def test_a_wrong_reading_case_tells_the_web_chat_every_step_in_telugu(sign_in, reader, area):
    consumer = Device(sign_in)
    ae = Device(sign_in, "section_ae", area.section_a.id)
    approver = Device(sign_in, "billing_approver", area.division.id)
    bill = printed(variant(SPIKED, usage_history=USUAL_MONTHS[:2]), area.section_a.name)
    _, ticket = _report(consumer, bill, "te")
    requested = evidence_store.month_request(ticket)
    assert requested is not None
    need = text("te", "review_need_bills", month=case_bills.month_name("te", "2025-10"),
                months=case_bills.month_list("te", requested["months"]))
    assert need in said(consumer.new_in_chat())

    reader(reading(printed(variant(OCT_2025, bill_month=requested["months"][0]), area.section_a.name)))
    sent = consumer.photo("te")
    assert any(e["kind"] == "message" and ticket in (e["message"].get("body") or "") for e in sent)
    assert any(m["author_kind"] == "consumer" for m in ae.client.get(f"/api/review/cases/{ticket}").json()["messages"])
    consumer.new_in_chat()

    corrected = _decide(ae, ticket, kind="corrected_reading", corrected_present_reading=351)
    told = _told(ae, ticket)[-1]
    assert TELUGU.search(told) and told in said(consumer.new_in_chat())
    applied = approver.client.post(f"/api/review/decisions/{corrected['decisions'][0]['id']}/applied",
                                   json={"billing_ref": "SYN-REF-1"})
    assert applied.status_code == 200 and _told(ae, ticket)[-1] in said(consumer.new_in_chat())

    for month, body in (("2025-11", {"kind": "custom", "reduction": 100}),
                        ("2025-12", {"kind": "correct", "reason_code": "bill_correct"})):
        _, other = _report(consumer, printed(variant(SPIKED, bill_month=month), area.section_a.name), "te")
        consumer.new_in_chat()
        _decide(ae, other, **body)
        decided = _told(ae, other)[-1]
        assert TELUGU.search(decided) and decided in said(consumer.new_in_chat())


def _ts(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def test_the_automatic_reminder_and_lapse_reach_the_web_chat(sign_in, area):
    consumer = Device(sign_in)
    _, ticket = _report(consumer, printed(SPIKED, area.section_a.name), "en")
    months = ["2025-07", "2025-08", "2025-09"]
    evidence_store.add_month_request(ticket, months, "Earlier bills")
    start = datetime(2030, 1, 1, 6, 0, tzinfo=UTC)
    with tx() as conn:
        conn.execute("UPDATE case_requests SET created_at = ? WHERE ticket = ?", (_ts(start), ticket))
    consumer.new_in_chat()
    values = {"ticket": ticket, "month": case_bills.month_name("en", "2025-10"),
              "months": case_bills.month_list("en", months)}
    asyncio.run(automation.run_reminders(start + timedelta(days=3, minutes=1)))
    assert text("en", "request_reminder", **values) in said(consumer.new_in_chat())
    asyncio.run(automation.run_lapses(start + timedelta(days=7, minutes=1)))
    assert text("en", "request_lapsed", **values) in said(consumer.new_in_chat())


def test_a_bill_read_deferred_in_the_web_chat_arrives_there_when_it_finishes(sign_in, reader):
    consumer = Device(sign_in)
    reader(DOWN, reading(OCT_2025))
    first = consumer.photo()
    assert said([e["message"] for e in first if e["kind"] == "message"]) == text("en", "reading_later")
    consumer.new_in_chat()
    assert asyncio.run(recovery.run_extracts(datetime.now(UTC) + timedelta(seconds=61))) >= 1
    report = consumer.new_in_chat()
    assert any(m["type"] == "buttons" for m in report)  # interactive messages are stored as the models the chat shows

    reader(DOWN)
    consumer.photo()
    consumer.new_in_chat()
    for seconds in (61, 400, 1400):  # the last try offers Try again and typed units, as on WhatsApp
        asyncio.run(recovery.run_extracts(datetime.now(UTC) + timedelta(seconds=seconds)))
    assert text("en", "read_failed") in said(consumer.new_in_chat())


def test_a_deferred_read_that_breaks_on_its_last_try_says_so_in_the_web_chat(sign_in, reader, monkeypatch):
    consumer = Device(sign_in)
    reader(DOWN)
    consumer.photo()
    consumer.new_in_chat()

    async def broken(*_: object, **__: object) -> str:
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(extract.service, "resume_document", broken)
    for seconds in (61, 400, 1400):
        asyncio.run(recovery.run_extracts(datetime.now(UTC) + timedelta(seconds=seconds)))
    assert said(consumer.new_in_chat()) == text("en", "read_gave_up")


def test_the_after_route_returns_only_this_users_newer_messages(sign_in):
    one, other = Device(sign_in), Device(sign_in)
    events = one.say(kind="text", text="hello")
    other.say(kind="text", text="hello")
    stream_ids = [e["chat_id"] for e in events if e["kind"] in ("state", "message")]
    everything = one.client.get("/api/web/history?after=0").json()["items"]
    assert [i["id"] for i in everything] == stream_ids  # the page can tell what it already shows
    newer = one.client.get(f"/api/web/history?after={stream_ids[0]}").json()["items"]
    assert [i["id"] for i in newer] == stream_ids[1:]
    theirs = {i["id"] for i in other.client.get("/api/web/history?after=0").json()["items"]}
    assert theirs and not theirs & set(stream_ids)
    assert one.client.get("/api/web/history?after=1&before=5").status_code == 422
    assert TestClient(app).get("/api/web/history?after=0").status_code == 401


def test_a_staff_ask_made_while_the_consumers_turn_runs_is_kept(sign_in):
    consumer = Device(sign_in)
    user = consumer.account.user_id
    state = repos.get_user(user, "web")  # the turn has loaded its state
    repos.set_awaiting(user, "info:BM-000000-SYNTH")  # staff ask meanwhile
    repos.save_user(state)  # the turn ends and saves what it loaded
    assert repos.get_user(user, "web").awaiting == "info:BM-000000-SYNTH"
    state = repos.get_user(user, "web")
    state.awaiting = None  # a turn that answers the ask clears it
    repos.save_user(state)
    assert repos.get_user(user, "web").awaiting is None
