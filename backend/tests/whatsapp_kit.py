"""A fake WhatsApp Cloud API for tests. Only HTTP itself is faked (the httpx transport), so client.py builds and sends
the real Graph requests, and the fake rejects anything over a published Cloud API limit. Numbers are synthetic."""

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from tests.real import OCT_2025, variant

PHONE_ID = "100000000000001"
SECRET = "audit-app-secret-not-real"
VERIFY = "audit-verify-not-real"
GRAPH = "graph.facebook.com"
OVERCHARGED = variant(OCT_2025, charge=("energy", 140.0))
REAL_ASYNC_CLIENT = httpx.AsyncClient


def number() -> str:
    return "9199999" + str(secrets.randbelow(10**5)).zfill(5)


@dataclass
class Graph:
    sent: list[dict] = field(default_factory=list)
    uploads: list[dict] = field(default_factory=list)
    downloads: list[str] = field(default_factory=list)
    auth_headers: list[str] = field(default_factory=list)
    fail_text: bool = False
    fail_template: bool = False
    fail_media: bool = False
    media_down: int = 0  # how many media requests answer 503 before Meta is back
    send_down: int = 0  # how many message sends answer 503 before Meta is back
    tts_calls: int = 0
    tts_audio: bytes = b"ID3fake-mp3"

    def handle(self, request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if host == GRAPH:
            self.auth_headers.append(request.headers.get("authorization", ""))
        if host == GRAPH and path.endswith(f"/{PHONE_ID}/messages"):
            body = json.loads(request.content)
            if body.get("status") == "read":
                self.sent.append(body)
                return httpx.Response(200, json={"success": True})
            if self.send_down > 0:
                self.send_down -= 1
                return httpx.Response(503, json={"error": {"code": 2}})
            if (body.get("type") == "text" and self.fail_text) or (body.get("type") == "template" and self.fail_template):
                return httpx.Response(400, json={"error": {"code": 131047, "message": "Re-engagement message"}})
            problems = cloud_api_problems(body)
            if problems:
                return httpx.Response(400, json={"error": {"code": 100, "message": "; ".join(problems)}})
            self.sent.append(body)
            return httpx.Response(200, json={"messaging_product": "whatsapp", "messages": [{"id": f"wamid.{secrets.token_hex(8)}"}]})
        if host == GRAPH and path.endswith(f"/{PHONE_ID}/media"):
            raw = request.content
            self.uploads.append({"has_product": b'name="messaging_product"' in raw,
                                 "has_type": b'name="type"' in raw,
                                 "ogg": b"audio/ogg" in raw, "mpeg": b"audio/mpeg" in raw, "png": b"image/png" in raw})
            return httpx.Response(200, json={"id": f"WAMEDIA{len(self.uploads)}"})
        if host == GRAPH and request.method == "GET":
            self.downloads.append(path)
            if self.media_down > 0:  # Meta down for now: the turn is retried
                self.media_down -= 1
                return httpx.Response(503, json={"error": {"code": 2}})
            if self.fail_media:  # the media is gone for good
                return httpx.Response(404, json={"error": {"code": 100}})
            mime = "audio/ogg; codecs=opus" if "AUDIO" in path else "image/jpeg"
            return httpx.Response(200, json={"url": "https://lookaside.fbsbx.com/whatsapp_business/x?mid=1",
                                             "mime_type": mime, "id": path.rsplit("/", 1)[-1]})
        if host == "lookaside.fbsbx.com":
            self.auth_headers.append(request.headers.get("authorization", ""))
            self.downloads.append("lookaside")
            # A JPEG signature, so the upload type check lets the synthetic photo through.
            return httpx.Response(200, content=b"\xff\xd8\xff synthetic-photo-bytes")
        if host == "api.sarvam.ai":
            self.tts_calls += 1
            return httpx.Response(200, json={"audios": [base64.b64encode(self.tts_audio).decode()]})
        return httpx.Response(599, json={"unexpected_host": host})

    def messages(self) -> list[dict]:
        return [m for m in self.sent if m.get("status") != "read"]


def cloud_api_problems(p: dict) -> list[str]:
    """What the Cloud API would reject, from the published limits."""
    out = []
    if p.get("messaging_product") != "whatsapp" or not p.get("to"):
        out.append("missing messaging_product/to")
    kind = p.get("type")
    if kind == "text":
        body = p["text"].get("body", "")
        if not body.strip() or len(body) > 4096:
            out.append(f"text body length {len(body)}")
    elif kind == "interactive":
        inter = p["interactive"]
        body = inter.get("body", {}).get("text", "")
        if not body.strip() or len(body) > 1024:
            out.append(f"interactive body length {len(body)}")
        if inter["type"] == "button":
            buttons = inter["action"]["buttons"]
            titles = [b["reply"]["title"] for b in buttons]
            ids = [b["reply"]["id"] for b in buttons]
            if not 1 <= len(buttons) <= 3:
                out.append(f"{len(buttons)} buttons")
            if any(len(t) > 20 or not t.strip() for t in titles):
                out.append(f"button title too long {titles}")
            if len(set(titles)) != len(titles) or len(set(ids)) != len(ids):
                out.append(f"duplicate button title or id {titles}")
            if any(len(i) > 256 for i in ids):
                out.append("button id > 256")
        elif inter["type"] == "list":
            action = inter["action"]
            rows = [r for s in action["sections"] for r in s["rows"]]
            if len(action["button"]) > 20 or len(rows) > 10:
                out.append("list button/rows over limit")
            if any(len(s.get("title", "")) > 24 for s in action["sections"]):
                out.append("section title > 24")
            if any(len(r["title"]) > 24 or len(r.get("description", "")) > 72 or len(r["id"]) > 200 for r in rows):
                out.append("row over limit")
    elif kind in ("image", "audio"):
        if not p[kind].get("id"):
            out.append(f"{kind} without id")
        if kind == "image" and len(p[kind].get("caption", "")) > 1024:
            out.append("caption > 1024")
    elif kind == "template":
        t = p["template"]
        if not t.get("name") or not t.get("language", {}).get("code"):
            out.append("template without name/language")
    else:
        out.append(f"unknown type {kind}")
    return out


@pytest.fixture
def graph(monkeypatch: pytest.MonkeyPatch) -> Graph:
    s = get_settings()
    for name, value in (("whatsapp_token", "audit-token-not-real"), ("whatsapp_phone_number_id", PHONE_ID),
                        ("whatsapp_verify_token", VERIFY), ("whatsapp_app_secret", SECRET)):
        monkeypatch.setattr(s, name, value)
    fake = Graph()
    transport = httpx.MockTransport(fake.handle)

    def factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs["transport"] = transport
        return REAL_ASYNC_CLIENT(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    return fake


@pytest.fixture
def api(graph):  # type: ignore[no-untyped-def]
    with TestClient(app) as client:
        yield client


def envelope(*messages: dict, statuses: list | None = None) -> dict:
    value: dict = {"messaging_product": "whatsapp",
                   "metadata": {"display_phone_number": "910000000000", "phone_number_id": PHONE_ID}}
    if messages:
        value["contacts"] = [{"profile": {"name": "Synthetic"}, "wa_id": messages[0]["from"]}]
        value["messages"] = list(messages)
    if statuses:
        value["statuses"] = statuses
    return {"object": "whatsapp_business_account", "entry": [{"id": "WABA", "changes": [{"field": "messages",
                                                                                        "value": value}]}]}


def sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def post(client: TestClient, payload: dict, signature: str | None = "auto") -> httpx.Response:
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if signature == "auto":
        headers["X-Hub-Signature-256"] = sign(body)
    elif signature:
        headers["X-Hub-Signature-256"] = signature
    return client.post("/api/whatsapp/webhook", content=body, headers=headers)


def mid() -> str:
    return "wamid." + secrets.token_hex(8)


def text(sender: str, body: str) -> dict:
    return {"from": sender, "id": mid(), "timestamp": "1760000000", "type": "text", "text": {"body": body}}


def image(sender: str, media: str = "MEDIA1") -> dict:
    return {"from": sender, "id": mid(), "timestamp": "1760000000", "type": "image",
            "image": {"id": media, "mime_type": "image/jpeg", "sha256": "x"}}


def tap(sender: str, reply_id: str, kind: str = "button_reply") -> dict:
    return {"from": sender, "id": mid(), "timestamp": "1760000000", "type": "interactive",
            "interactive": {"type": kind, kind: {"id": reply_id, "title": "t"}}}


def say(client: TestClient, graph: Graph, msg: dict) -> list[dict]:
    before = len(graph.messages())
    assert post(client, envelope(msg)).status_code == 200
    return graph.messages()[before:]


def bodies(sent: list[dict]) -> list[str]:
    out = []
    for m in sent:
        if m["type"] == "text":
            out.append(m["text"]["body"])
        elif m["type"] == "interactive":
            out.append(m["interactive"]["body"]["text"])
    return out


def ids(sent: list[dict]) -> list[str]:
    return [b["reply"]["id"] for m in sent if m["type"] == "interactive" and m["interactive"]["type"] == "button"
            for b in m["interactive"]["action"]["buttons"]]


