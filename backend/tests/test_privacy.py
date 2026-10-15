"""DPDP: the notice, first contact on WhatsApp, erasure from the web app and from chat, and retention.

Logins, WhatsApp numbers and media bytes are obviously synthetic; bills are the real fixtures from tests/real.py."""

import asyncio
import os
import secrets
import time

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core import service
from app.core.messages import Inbound
from app.core.trace import Event
from app.domain.conversation.lang import text
from app.main import app
from app.store import accounts, media, privacy, repos
from app.store import complaints as store
from app.store.db import tx
from tests.real import MAR_2024, OCT_2025

FAKE_WA = "test-wa-address-2"  # obviously synthetic WhatsApp address


def _say(user: str, channel: str, message: str) -> str:
    events: list[Event] = []

    async def emit(event: Event) -> None:
        events.append(event)

    inbound = Inbound(channel=channel, user_id=user, kind="text", text=message,  # type: ignore[arg-type]
                      reply_to=FAKE_WA if channel == "whatsapp" else None)
    asyncio.run(service.handle(inbound, emit))
    return "\n".join(getattr(e.message, "body", "") or "" for e in events if e.kind == "message")


def _photo() -> str:
    return media.save(f"synthetic-photo-{secrets.token_hex(8)}".encode(), "image/jpeg")


def _complaint(user_id: str, bill_id: str | None, reply_to: str | None = FAKE_WA) -> str:
    ticket = store.create(user_id, bill_id, OCT_2025, "Energy charge above tariff.", 140.0, "en", "whatsapp",
                          reply_to, "Energy charge looks too high.")
    assert ticket
    return ticket


def _reply_to(ticket: str) -> str | None:
    complaint = store.get(ticket)
    assert complaint
    return complaint.reply_to


def test_privacy_notice_is_public():
    with TestClient(app) as client:
        body = client.get("/api/privacy").json()
    assert body["version"] == get_settings().privacy_notice_version and body["retention_days"] == 180
    assert body["contact"] is None and any("never sold" in p for p in body["purposes"])


def test_whatsapp_first_contact_gets_the_notice_once(monkeypatch: pytest.MonkeyPatch):
    notice = text("te", "privacy_notice", days=180)  # a new number starts in Telugu, the first language
    user = f"wa:{secrets.token_hex(10)}"
    assert notice in _say(user, "whatsapp", "hello")
    assert notice not in _say(user, "whatsapp", "hello")
    assert text("hi", "privacy_notice", days=180) in _say(f"wa:{secrets.token_hex(10)}", "whatsapp", "नमस्ते")
    monkeypatch.setattr(get_settings(), "privacy_contact", "privacy@example.com")
    assert "privacy@example.com" in _say(f"wa:{secrets.token_hex(10)}", "whatsapp", "hello")
    assert notice not in _say(f"web-{secrets.token_hex(4)}", "web", "hello")


def test_consumer_deletes_their_account(sign_in):
    with TestClient(app) as client:
        account = sign_in(client)
        mine, shared = _photo(), _photo()
        bill_id = repos.save_bill(account.user_id, OCT_2025, mine, "mismatch", 140.0)
        repos.save_bill(account.user_id, MAR_2024, shared, "verified", 0.0)
        repos.save_bill(f"other-{secrets.token_hex(4)}", MAR_2024, shared, "verified", 0.0)
        ticket = _complaint(account.user_id, bill_id)

        response = client.delete("/api/me")
        assert response.status_code == 204 and "bm_session" in response.headers.get("set-cookie", "")
        assert client.get("/api/auth/me").status_code == 401

    assert media.path_for(mine) is None and media.path_for(shared) is not None
    assert repos.list_bills(account.user_id, 1, 10, None, True).total == 0
    assert store.get(ticket) is not None and _reply_to(ticket) is None
    gone = accounts.get(account.id)
    assert gone and not gone.active and gone.login == f"deleted:{account.id}" and gone.name == "Deleted account"
    assert accounts.authenticate(account.login, "test-only-passphrase") is None
    assert accounts.list_audit(1, 50, "account.delete_self").items[0].target == account.id


def test_staff_cannot_delete_themselves_and_anonymous_gets_401(sign_in):
    with TestClient(app) as client:
        assert client.delete("/api/me").status_code == 401
        sign_in(client, "officer", "TGSPDCL")
        response = client.delete("/api/me")
    assert response.status_code == 403 and response.json()["detail"] == "Staff accounts are closed by an administrator."


def test_stop_in_chat_deletes_media_and_cuts_the_reply_address():
    user = f"wa:{secrets.token_hex(10)}"
    photo = _photo()
    bill_id = repos.save_bill(user, OCT_2025, photo, "mismatch", 140.0)
    ticket = _complaint(user, bill_id)
    _say(user, "whatsapp", "STOP")
    assert media.path_for(photo) is None and repos.get_bill(bill_id) is None
    assert store.get(ticket) is not None and _reply_to(ticket) is None


def _backdate(bill_ids: list[str], message_id: str) -> None:
    with tx() as conn:
        conn.executemany("UPDATE bills SET created_at = datetime('now', '-200 days') WHERE id = ?",
                         [(b,) for b in bill_ids])
        conn.execute("UPDATE whatsapp_seen SET ts = datetime('now', '-8 days') WHERE message_id = ?", (message_id,))


def test_retention_sweep_keeps_only_what_is_still_needed():
    user = f"test-{secrets.token_hex(4)}"
    old_photo, kept_photo, fresh_photo = _photo(), _photo(), _photo()
    old_bill = repos.save_bill(user, OCT_2025, old_photo, "verified", 0.0)
    kept_bill = repos.save_bill(f"{user}-b", OCT_2025, kept_photo, "mismatch", 140.0)
    fresh_bill = repos.save_bill(f"{user}-c", MAR_2024, fresh_photo, "verified", 0.0)
    _complaint(f"{user}-b", kept_bill)
    stray = _photo()
    stale = time.time() - 200 * 86400
    for media_id in (stray, fresh_photo):
        path = media.path_for(media_id)
        assert path
        os.utime(path, (stale, stale))
    assert repos.first_delivery(f"wamid.{user}")
    _backdate([old_bill, kept_bill], f"wamid.{user}")

    result = privacy.sweep()

    assert result.bills >= 1 and result.whatsapp_seen >= 1 and result.media >= 2
    assert repos.get_bill(old_bill) is None and media.path_for(old_photo) is None
    assert repos.get_bill(kept_bill) is not None and media.path_for(kept_photo) is not None
    assert repos.get_bill(fresh_bill) is not None and media.path_for(fresh_photo) is not None
    assert media.path_for(stray) is None
    assert repos.first_delivery(f"wamid.{user}")
