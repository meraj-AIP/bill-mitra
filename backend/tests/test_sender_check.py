"""Registered mobile: is the consumer writing from the number the DISCOM holds for the connection, and which
connections does that number have. The DISCOM is faked at its HTTP boundary; numbers are synthetic (99 prefix)."""

import asyncio
import json
import logging
import secrets
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.hashing import service_hash
from app.flows import sender_check
from app.main import app
from app.services import discom_bills
from app.store import account_connections, accounts, complaints, sender_checks
from app.store.complaints import General, Intake, Placement
from app.store.db import DISCOM_UNITS, tx
from tests.test_complaint_intake import fake_usc, run, sent

SENDER = "919999999001"  # the number tests.test_complaint_intake.run sends WhatsApp turns from


@pytest.fixture
def discom(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[dict[str, str]]]:
    """A connected DISCOM whose mobile lookup answers from this dict, keyed by DISCOM. Set "fail" to make it fail."""
    settings = get_settings()
    monkeypatch.setattr(settings, "discom_bills_url", "https://discom.invalid/api")
    monkeypatch.setattr(settings, "discom_bills_token", "test-token-not-real")
    registry: dict[str, list[dict[str, str]]] = {}
    asked: list[str] = []

    async def fake(path: str, which: str, what: str) -> dict[str, object] | None:
        asked.append(path)
        if "fail" in registry:
            raise discom_bills.LookupFailed(what)
        found = registry.get(which)
        return {"consumers": found} if found else None

    monkeypatch.setattr(discom_bills, "_request", fake)
    monkeypatch.setattr(sender_check, "BATCH", 100_000)  # the test database is shared; reach this test's rows
    registry["asked"] = asked  # type: ignore[assignment]
    return registry


def _complaint(reply_to: str | None, usc: str | None, channel: str = "whatsapp", user_id: str | None = None) -> str:
    return complaints.create_general(
        General(user_id=user_id or f"wa:{secrets.token_hex(8)}", discom="TGSPDCL", issue="Bill too high", language="en",
                channel=channel, reply_to=reply_to),
        Placement(section_id=None, unit_id=DISCOM_UNITS["TGSPDCL"]),
        Intake(type="high_bill", priority="normal", due_at="2099-01-01 00:00:00", source="whatsapp",
               service_number_hash=service_hash(usc) if usc else None), "My bill is too high")


def _run() -> None:
    asyncio.run(sender_check.run_due(datetime.now(UTC)))


def test_status_rules():
    assert sender_check.status_for("a", ["a", "b"], "discom") == "verified"
    assert sender_check.status_for("c", ["a"], "discom") == "other_connection"
    assert sender_check.status_for(None, ["a"], "discom") == "registered"
    assert sender_check.status_for("a", [], "discom") == "not_registered"
    assert sender_check.status_for("a", ["a"], "none") == "not_checked"


def test_whatsapp_complaint_from_the_registered_mobile_is_verified_with_its_connections(discom, caplog):
    own, other = fake_usc(), fake_usc()
    discom["TGSPDCL"] = [{"service_number": own, "section": "Isnapur"}]
    discom["TGNPDCL"] = [{"service_number": other}]
    ticket = _complaint("919999990123", own)
    with caplog.at_level(logging.DEBUG):
        _run()
    found = sender_checks.for_ticket(ticket)
    assert found.status == "verified" and found.source == "discom"
    assert {(c.discom, c.this_one) for c in found.connections} == {("TGSPDCL", True), ("TGNPDCL", False)}
    assert all(c.service_masked.endswith(n[-4:]) and n not in c.service_masked
               for c, n in zip(sorted(found.connections, key=lambda c: c.discom), [other, own], strict=True))
    assert "9999990123" not in caplog.text and own not in caplog.text  # neither mobile nor number is logged
    with tx() as conn:
        stored = json.dumps([dict(r) for r in conn.execute("SELECT * FROM sender_connections WHERE ticket = ?", (ticket,))])
    assert own not in stored and other not in stored  # only hashes and masked numbers are kept


def test_other_connection_unregistered_mobile_and_web_complaints_are_flagged(discom):
    discom["TGSPDCL"] = [{"service_number": fake_usc()}]
    other = _complaint("919999990124", fake_usc())
    no_number = _complaint("919999990125", None)
    web = _complaint(None, fake_usc(), channel="web")
    _run()
    assert sender_checks.for_ticket(other).status == "other_connection"
    assert sender_checks.for_ticket(no_number).status == "registered"
    assert sender_checks.for_ticket(web).status == "no_mobile"
    discom.pop("TGSPDCL")
    unknown = _complaint("919999990126", fake_usc())
    _run()
    assert sender_checks.for_ticket(unknown).status == "not_registered"


def test_a_failed_lookup_is_tried_again_later(discom):
    discom["fail"] = []
    ticket = _complaint("919999990127", fake_usc())
    _run()
    assert sender_checks.for_ticket(ticket).status is None
    asked = len(discom["asked"])  # type: ignore[arg-type]
    _run()  # inside the retry wait: not asked again
    assert len(discom["asked"]) == asked  # type: ignore[arg-type]
    with tx() as conn:
        conn.execute("UPDATE complaints SET mobile_checked_at = ? WHERE ticket = ?",
                     ((datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"), ticket))
    discom.pop("fail")
    discom["TGSPDCL"] = []
    _run()
    assert sender_checks.for_ticket(ticket).status == "not_registered"


def test_without_a_connected_lookup_nothing_is_claimed(monkeypatch):
    monkeypatch.setattr(sender_check, "BATCH", 100_000)
    ticket = _complaint("919999990128", fake_usc())
    _run()
    found = sender_checks.for_ticket(ticket)
    assert found.status == "not_checked" and found.source == "none" and found.connections == []


def test_staff_see_the_flag_on_the_complaint(discom, sign_in):
    own = fake_usc()
    discom["TGSPDCL"] = [{"service_number": own, "section": "Isnapur"}]
    ticket = _complaint("919999990129", own)
    _run()
    client = TestClient(app)
    sign_in(client, "officer", "TGSPDCL")
    body = client.get(f"/api/console/complaints/{ticket}")
    assert body.status_code == 200
    assert body.json()["sender"]["status"] == "verified" and own not in body.text


def test_whatsapp_chat_offers_the_registered_connections_to_tap(discom):
    own = fake_usc()
    discom["TGNPDCL"] = [{"service_number": own, "section": "Hanamkonda"}]
    user = f"wa:{secrets.token_hex(8)}"
    run(user, "whatsapp", kind="text", text="I want to raise a complaint")
    run(user, "whatsapp", kind="button_reply", reply_id="ccat:supply")
    run(user, "whatsapp", kind="button_reply", reply_id="ctype:power_outage")
    listed = sent(run(user, "whatsapp", kind="button_reply", reply_id="cdis:TGNPDCL"))[-1]
    assert listed.type == "list" and [r.id for r in listed.rows] == ["cusc_pick:0", "cusc_type", "cusc_skip"]
    assert listed.rows[0].title.endswith(own[-4:]) and own not in listed.model_dump_json()
    run(user, "whatsapp", kind="button_reply", reply_id="cusc_pick:0")
    run(user, "whatsapp", kind="text", text="No power since the morning, only our house.")
    run(user, "whatsapp", kind="button_reply", reply_id="cfq_skip")
    run(user, "whatsapp", kind="button_reply", reply_id="cfq_skip")
    run(user, "whatsapp", kind="button_reply", reply_id="cdraft_send")
    [row] = complaints.page(1, 5, owner=user).items
    with tx() as conn:
        stored = conn.execute("SELECT service_number_hash, reply_to FROM complaints WHERE ticket = ?", (row["ticket"],)).fetchone()
    assert stored[0] == service_hash(own) and stored[1] == SENDER
    _run()
    assert sender_checks.for_ticket(row["ticket"]).status == "verified"


def test_web_chat_never_offers_connections(discom):
    discom["TGNPDCL"] = [{"service_number": fake_usc()}]
    user = f"web:{secrets.token_hex(8)}"
    run(user, kind="text", text="I want to raise a complaint")
    run(user, kind="button_reply", reply_id="ccat:supply")
    run(user, kind="button_reply", reply_id="ctype:power_outage")
    asked = sent(run(user, kind="button_reply", reply_id="cdis:TGNPDCL"))[-1]
    assert asked.type == "buttons" and discom["asked"] == []


def test_a_web_complaint_uses_the_mobile_the_discom_confirmed_at_sign_up(discom):
    usc = fake_usc()
    discom["TGSPDCL"] = [{"service_number": usc}]
    confirmed = accounts.create("consumer", "9999" + f"{secrets.randbelow(10**6):06d}", "Test", secrets.token_urlsafe(16))
    account_connections.replace(confirmed.id, [("TGSPDCL", service_hash(usc), "****" + usc[-4:], None)])
    unconfirmed = accounts.create("consumer", "9999" + f"{secrets.randbelow(10**6):06d}", "Test", secrets.token_urlsafe(16))
    ours = _complaint(None, usc, channel="web", user_id=confirmed.user_id)
    theirs = _complaint(None, usc, channel="web", user_id=unconfirmed.user_id)
    _run()
    assert sender_checks.for_ticket(ours).status == "verified"
    assert sender_checks.for_ticket(theirs).status == "no_mobile"  # a password account never proved its number
