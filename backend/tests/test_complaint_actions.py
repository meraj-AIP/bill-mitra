"""Console shortcuts: reply options, triage, asking for a photo, retrying a failed send and bulk actions.

Only the real boundaries are faked: the vision reading, the text model and the WhatsApp HTTP call."""

import secrets

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import admin, auth, complaint_actions, complaints
from app.channels.whatsapp import client as wa_client
from app.services import llm
from app.store import accounts
from app.store import complaints as store
from tests.real import MAR_2024, OCT_2025, variant
from tests.test_complaints import OVERCHARGED, PASSWORD, chat, chat_complaint

api = FastAPI()
for r in (auth.router, admin.router, complaints.router, complaint_actions.router):
    api.include_router(r)


@pytest.fixture(scope="module")
def staff() -> dict[str, accounts.Account]:
    tag = secrets.token_hex(3)
    make = accounts.create
    return {"admin": make("admin", f"admin-a-{tag}@example.com", "Test admin", PASSWORD),
            "south": make("officer", f"officer-as-{tag}@example.com", "Test officer", PASSWORD, "TGSPDCL")}


def signed_in(account: accounts.Account) -> TestClient:
    client = TestClient(api)
    assert client.post("/api/auth/login", json={"login": account.login, "password": PASSWORD}).status_code == 200
    return client


def test_reply_options_carry_the_checked_draft_and_the_guard_rejects_new_figures(reader, staff, monkeypatch):
    ticket = chat_complaint(reader, "web")
    officer = signed_in(staff["south"])
    plain = officer.get(f"/api/console/complaints/{ticket}/options").json()
    over = next(o for o in plain["options"] if o["key"] == "overcharge")
    assert plain["triage"] == "overcharge" and "140" in over["text"] and 2 <= len(plain["options"]) <= 4

    async def invents(*_: object) -> str:
        return "Your bill is Rs 999 too high."

    monkeypatch.setattr(llm, "word_reply", invents)
    drafted = officer.post(f"/api/console/complaints/{ticket}/draft", json={"option_key": "overcharge"}).json()
    assert drafted == {"text": over["text"], "worded_by": "rules"}

    async def faithful(draft: str, *_: object) -> str:
        return "Sorry for the trouble. " + draft

    monkeypatch.setattr(llm, "word_reply", faithful)
    drafted = officer.post(f"/api/console/complaints/{ticket}/draft", json={"option_key": "overcharge"}).json()
    assert drafted["worded_by"] == "ai" and drafted["text"].startswith("Sorry")


def test_triage_filters_and_needs_you_first(reader, staff):
    over = chat_complaint(reader, "web")
    fine = chat_complaint(reader, "web", variant(OCT_2025, bill_month="2025-08"))
    officer = signed_in(staff["south"])
    correct = officer.get("/api/console/complaints", params={"triage": "bill_correct", "page_size": 50}).json()["items"]
    assert fine in [r["ticket"] for r in correct] and over not in [r["ticket"] for r in correct]
    ranked = [r["ticket"] for r in officer.get("/api/console/complaints", params={"page_size": 50}).json()["items"]]
    assert ranked.index(over) < ranked.index(fine)


def test_asked_for_photo_lands_on_the_complaint_once(reader, staff):
    ticket = chat_complaint(reader, "web")
    user = store.get(ticket).user_id
    officer = signed_in(staff["south"])
    asked = officer.post(f"/api/console/complaints/{ticket}/request", json={"kind": "meter_photo"}).json()
    assert asked["messages"][-1]["author_kind"] == "officer" and asked["messages"][-1]["delivery"] == "stored"

    chat(user, "web", kind="image")
    thread = officer.get(f"/api/console/complaints/{ticket}").json()["messages"]
    assert thread[-1]["author_kind"] == "consumer" and thread[-1]["media_url"].startswith("/api/media/")
    before = len(thread)
    reader(variant(OVERCHARGED, bill_month="2025-07"))
    chat(user, "web", kind="image")  # the next photo is a normal bill again
    assert len(officer.get(f"/api/console/complaints/{ticket}").json()["messages"]) == before


def test_failed_delivery_is_listed_and_retried(reader, staff, monkeypatch):
    from app.config import get_settings
    settings = get_settings()
    for field in ("whatsapp_token", "whatsapp_phone_number_id", "whatsapp_verify_token"):
        monkeypatch.setattr(settings, field, "test-value-not-real")
    sent: list[dict] = []

    async def refuse(_: dict) -> None:
        raise httpx.HTTPStatusError("down", request=httpx.Request("POST", "https://example.invalid"),
                                    response=httpx.Response(500))

    async def accept(payload: dict) -> None:
        sent.append(payload)

    ticket = chat_complaint(reader)
    officer = signed_in(staff["admin"])
    monkeypatch.setattr(wa_client, "send", refuse)
    failed = officer.post(f"/api/console/complaints/{ticket}/reply", json={"body": "Checking now."}).json()
    message_id = failed["messages"][-1]["id"]
    listed = officer.get("/api/console/complaints", params={"failed": True, "page_size": 50}).json()["items"]
    assert ticket in [r["ticket"] for r in listed]

    monkeypatch.setattr(wa_client, "send", accept)
    retried = officer.post(f"/api/console/complaints/{ticket}/messages/{message_id}/retry").json()
    assert retried["messages"][-1]["delivery"] == "sent" and sent
    assert officer.post(f"/api/console/complaints/{ticket}/messages/{message_id}/retry").status_code == 404


def test_bulk_explains_and_resolves_only_within_scope(reader, staff):
    mine = chat_complaint(reader, "web", variant(OCT_2025, bill_month="2025-06"))
    theirs = chat_complaint(reader, "web", variant(MAR_2024, charge=("energy", 140.0), discom="TGNPDCL"))
    officer = signed_in(staff["south"])
    result = officer.post("/api/console/complaints/bulk",
                          json={"tickets": [mine, theirs], "status": "Resolved", "send_explanation": True}).json()
    assert result["done"] == [mine] and result["skipped"] == [{"ticket": theirs, "reason": "not found"}]
    detail = officer.get(f"/api/console/complaints/{mine}").json()
    assert detail["status"] == "Resolved" and any(m["author_kind"] == "officer" for m in detail["messages"])
    assert officer.post("/api/console/complaints/bulk", json={"tickets": [mine]}).status_code == 422


def test_system_health_is_for_admins_only(staff):
    assert signed_in(staff["south"]).get("/api/admin/health").status_code == 403
    body = signed_in(staff["admin"]).get("/api/admin/health").json()
    assert "modes" in body and "failed_deliveries_open" in body and body["reply_days"] >= 1
