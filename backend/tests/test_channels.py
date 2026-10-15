"""WhatsApp mapping and signature, the number guard, and the HTTP API surface."""

import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.channels.whatsapp.mapper import parse_webhook, to_payload, user_key
from app.channels.whatsapp.router import signature_valid
from app.core.messages import AudioOut, Button, ButtonsOut, ImageOut, TextOut
from app.domain.conversation import guard
from app.flows.analysis import analyse
from app.main import app
from tests.real import OCT_2025

WEBHOOK = {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"messages": [
    {"from": "919999999999", "id": "wamid.A", "type": "image", "image": {"id": "MEDIA1", "mime_type": "image/jpeg"}},
    {"from": "919999999999", "id": "wamid.B", "type": "interactive",
     "interactive": {"type": "button_reply", "button_reply": {"id": "why", "title": "Why this amount?"}}},
    {"from": "919999999999", "id": "wamid.C", "type": "audio", "audio": {"id": "MEDIA2", "mime_type": "audio/ogg"}},
    {"from": "919999999999", "id": "wamid.D", "type": "text", "text": {"body": "నా బిల్లు ఎందుకు ఎక్కువ?"}},
]}}]}]}


def test_webhook_parsing():
    parsed = parse_webhook(WEBHOOK)
    assert [p.kind for p in parsed] == ["image", "button_reply", "audio", "text"]
    assert parsed[0].media_ref == "MEDIA1" and parsed[1].reply_id == "why"


def test_user_key_never_contains_phone():
    key = user_key("919999999999")
    assert "9999999999" not in key and key.startswith("wa:")


def test_outbound_payloads():
    to = "919999999999"
    text = to_payload(to, TextOut(body="hi", language="te"), {})[0]
    assert text["type"] == "text" and text["text"]["body"] == "hi"
    buttons = to_payload(to, ButtonsOut(body="b", buttons=[Button(id="why", title="Why")], language="te"), {})[0]
    assert buttons["interactive"]["action"]["buttons"][0]["reply"]["id"] == "why"
    image = to_payload(to, ImageOut(media_id="m1", caption="c", language="te"), {"m1": "WA1"})[0]
    assert image["image"] == {"id": "WA1", "caption": "c"}
    audio = to_payload(to, AudioOut(media_ids=["a", "b"], transcript="t", language="te"), {"a": "1", "b": "2"})
    assert [a["audio"]["id"] for a in audio] == ["1", "2"]


def test_signature():
    body = json.dumps(WEBHOOK).encode()
    good = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert signature_valid("secret", body, good)
    assert not signature_valid("secret", body, "sha256=00")
    assert not signature_valid("secret", body, None)


def test_guard_accepts_engine_numbers_and_rejects_invented_ones():
    facts = analyse(OCT_2025, "guard-test").facts
    assert guard.check("మీరు 138 యూనిట్లు వాడారు, రూ. 1245 కట్టాలి.", facts).passed
    result = guard.check("You used 138 units and must pay Rs 702.40.", facts)
    assert not result.passed and result.unmatched == ["702.40"]
    assert guard.check("రూ. ౧౨౪౫", facts).passed  # Telugu digits are normalised


def test_api_surface(sign_in):
    with TestClient(app) as client:
        sign_in(client, "officer")
        health = client.get("/api/health").json()
        assert health["modes"]["vision"] == "off" and health["modes"]["whatsapp"] == "ready, not connected"
        assert client.get("/api/samples").status_code == 404
        assert [t["id"] for t in client.get("/api/tariffs").json()][0] == "TGERC-RST-2023-24"
        summary = client.get("/api/console/summary").json()
        assert {"bills_read", "complaints", "daily"} <= set(summary)
        page = client.get("/api/console/complaints?page=1&page_size=5").json()
        assert page["page"] == 1 and all("simulated" not in item for item in page["items"])
        assert client.get("/api/media/..%2F..%2Fetc%2Fpasswd").status_code == 404
        assert client.post("/api/whatsapp/webhook", json=WEBHOOK).status_code == 503
        lines = client.post("/api/web/messages", json={
            "kind": "text", "text": "hello", "language": "en"}).text
        events = [json.loads(line) for line in lines.splitlines()]
        assert events[-1] == {"kind": "done"}
        assert any(e["kind"] == "message" for e in events)
        upload = client.post("/api/web/upload", files={"file": ("x.txt", b"hello", "text/plain")})
        assert upload.status_code == 415


def test_retried_whatsapp_message_is_processed_once():
    from app.store import repos

    assert repos.first_delivery("wamid.retry-test")
    assert not repos.first_delivery("wamid.retry-test")
