"""Complaints end to end: raised in chat, answered from the console, delivered honestly.

The only thing faked is the WhatsApp HTTP call (client.send), the real network boundary. Numbers and logins are
obviously synthetic."""

import asyncio
import secrets

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import auth, complaints, console
from app.channels.whatsapp import client as wa_client
from app.config import get_settings
from app.core import service
from app.core.messages import Inbound
from app.core.trace import Event
from app.services import notify
from app.store import accounts, media
from app.store import complaints as store
from tests.real import MAR_2024, OCT_2025, reading, variant

WA_NUMBER = "919999900001"
PASSWORD = secrets.token_urlsafe(16)
OVERCHARGED = variant(OCT_2025, charge=("energy", 140.0))  # real bill, energy printed Rs 140 higher

api = FastAPI()
for r in (auth.router, console.router, complaints.router):
    api.include_router(r)


def _account(role: str, login: str, discom: str | None = None) -> accounts.Account:
    return accounts.create(role, login, f"Test {role}", PASSWORD, discom)  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def people() -> dict[str, accounts.Account]:
    tag = secrets.token_hex(3)
    return {"admin": _account("admin", f"admin-{tag}@example.com"),
            "south": _account("officer", f"officer-s-{tag}@example.com", "TGSPDCL"),
            "north": _account("officer", f"officer-n-{tag}@example.com", "TGNPDCL"),
            "consumer": _account("consumer", "99999" + str(secrets.randbelow(10**5)).zfill(5)),
            "other": _account("consumer", "88888" + str(secrets.randbelow(10**5)).zfill(5))}


def signed_in(account: accounts.Account) -> TestClient:
    client = TestClient(api)
    assert client.post("/api/auth/login", json={"login": account.login, "password": PASSWORD}).status_code == 200
    return client


def chat(user: str, channel: str, **fields: object) -> None:
    async def emit(_: Event) -> None:
        return None

    if fields.get("kind") == "image":
        fields = {"media_id": media.save(b"synthetic-photo", "image/jpeg"), "mime_type": "image/jpeg", **fields}
    reply_to = WA_NUMBER if channel == "whatsapp" else None
    inbound = Inbound(channel=channel, user_id=user, reply_to=reply_to, **fields)  # type: ignore[arg-type]
    asyncio.run(service.handle(inbound, emit, language="en"))


def chat_complaint(reader, channel: str = "whatsapp", bill=OVERCHARGED) -> str:
    user = f"{'wa' if channel == 'whatsapp' else 'web'}:{secrets.token_hex(10)}"
    reader(reading(bill))
    chat(user, channel, kind="image")
    chat(user, channel, kind="button_reply", reply_id="complain")
    chat(user, channel, kind="button_reply", reply_id="complaint_send")
    page = store.page(1, 50, owner=user)
    assert page.total == 1
    return page.items[0]["ticket"]


def whatsapp_complaint(reader) -> str:
    return chat_complaint(reader)


@pytest.fixture
def whatsapp_on(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    settings = get_settings()
    for field in ("whatsapp_token", "whatsapp_phone_number_id", "whatsapp_verify_token"):
        monkeypatch.setattr(settings, field, "test-value-not-real")
    sent: list[dict] = []

    async def fake_send(payload: dict) -> None:
        sent.append(payload)

    monkeypatch.setattr(wa_client, "send", fake_send)
    return sent


def test_chat_complaint_stores_channel_and_opens_the_thread(reader):
    complaint = store.get(whatsapp_complaint(reader))
    assert complaint and complaint.channel == "whatsapp" and complaint.reply_to == WA_NUMBER
    first = store.messages(complaint.ticket)[0]
    assert first["author_kind"] == "consumer" and first["delivery"] == "stored" and "Energy charge" in first["body"]


def test_officer_reply_to_a_web_chat_complaint_is_stored(reader, people):
    ticket = chat_complaint(reader, "web")
    officer = signed_in(people["south"])
    detail = officer.get(f"/api/console/complaints/{ticket}").json()
    assert detail["channel"] == "web" and detail["reply_channel"] == "web"
    assert any(line["code"] == "energy" and line["status"] == "over" for line in detail["audit_lines"])
    assert detail["media_url"].startswith("/api/media/") and detail["bill"]["service_masked"].endswith("1111")

    listed = officer.get("/api/console/complaints", params={"q": ticket[-5:], "status": "Open"}).json()
    assert ticket in [row["ticket"] for row in listed["items"]]
    replied = officer.post(f"/api/console/complaints/{ticket}/reply",
                           json={"body": "We are checking the energy charge.", "status": "In progress"}).json()
    officer_msg = replied["messages"][1]
    assert officer_msg["author_kind"] == "officer" and officer_msg["delivery"] == "stored"
    assert officer_msg["author_name"] == "Test officer" and replied["status"] == "In progress"
    status_line = replied["messages"][2]  # in the consumer's language, Telugu by default
    assert status_line["author_kind"] == "system" and notify.status_label("en", "In progress") in status_line["body"]


def test_whatsapp_reply_without_whatsapp_is_recorded_failed(reader, people):
    ticket = whatsapp_complaint(reader)
    officer = signed_in(people["admin"])
    detail = officer.post(f"/api/console/complaints/{ticket}/reply", json={"body": "Please send the meter photo."})
    body = detail.json()
    assert body["reply_channel"] == "whatsapp" and body["whatsapp_ready"] is False
    assert body["messages"][-1]["delivery"] == "failed" and body["messages"][-1]["delivery_note"] == notify.NOT_CONNECTED
    assert WA_NUMBER not in detail.text


def test_whatsapp_reply_is_sent_and_falls_back_to_the_template(reader, people, whatsapp_on, monkeypatch):
    ticket = whatsapp_complaint(reader)
    officer = signed_in(people["admin"])
    body = officer.post(f"/api/console/complaints/{ticket}/reply", json={"body": "Corrected next bill."}).json()
    assert body["messages"][-1]["delivery"] == "sent" and whatsapp_on[-1]["to"] == WA_NUMBER
    assert whatsapp_on[-1]["text"]["body"].startswith(f"Update on your complaint {ticket}:")

    async def outside_window(payload: dict) -> None:
        if payload["type"] == "text":
            raise httpx.HTTPStatusError("re-engagement", request=httpx.Request("POST", "https://example.invalid"),
                                        response=httpx.Response(400))
        whatsapp_on.append(payload)

    monkeypatch.setattr(wa_client, "send", outside_window)
    failed = officer.post(f"/api/console/complaints/{ticket}/status", json={"status": "Resolved"}).json()
    assert failed["messages"][-1]["delivery"] == "failed" and "24 hours" in failed["messages"][-1]["delivery_note"]

    monkeypatch.setattr(get_settings(), "whatsapp_complaint_template", "complaint_update")
    done = officer.post(f"/api/console/complaints/{ticket}/status", json={"status": "Rejected"}).json()
    assert done["messages"][-1]["delivery"] == "sent" and done["messages"][-1]["delivery_note"] == notify.TEMPLATE_USED
    params = whatsapp_on[-1]["template"]["components"][0]["parameters"]
    assert [p["text"] for p in params] == [ticket, "Rejected"]


def test_officer_outside_the_discom_gets_404(reader, people):
    ticket = chat_complaint(reader, "web", variant(MAR_2024, charge=("energy", 140.0)))
    north = signed_in(people["north"])
    assert north.get(f"/api/console/complaints/{ticket}").status_code == 404
    assert north.post(f"/api/console/complaints/{ticket}/reply", json={"body": "x"}).status_code == 404
    rows = north.get("/api/console/complaints", params={"page_size": 50}).json()["items"]
    assert all(row["discom"] == "TGNPDCL" for row in rows)
    assert north.get("/api/console/complaints", params={"discom": "TGSPDCL"}).json()["total"] == 0


def test_consumers_have_no_complaint_routes_and_no_console(reader, people):
    ticket = chat_complaint(reader, "web")
    other = signed_in(people["other"])
    assert other.get("/api/me/complaints").status_code == 404
    assert other.get(f"/api/me/complaints/{ticket}").status_code == 404
    assert other.get(f"/api/console/complaints/{ticket}").status_code == 403
    assert other.get("/api/console/complaints").status_code == 403
    assert other.get("/api/console/summary").status_code == 403
    assert TestClient(api).get("/api/console/summary").status_code == 401
    assert signed_in(people["south"]).get("/api/console/summary").status_code == 200


def test_reply_to_never_appears_in_any_response(reader, people):
    ticket = whatsapp_complaint(reader)
    admin = signed_in(people["admin"])
    responses = [admin.get("/api/console/complaints", params={"page_size": 50}),
                 admin.get(f"/api/console/complaints/{ticket}"),
                 admin.post(f"/api/console/complaints/{ticket}/status", json={"status": "In progress"})]
    for response in responses:
        assert response.status_code == 200 and WA_NUMBER not in response.text and "reply_to" not in response.text
