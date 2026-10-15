"""The conversation is kept with the account, reads back in order, and is erased on request."""

import asyncio
import json

from fastapi.testclient import TestClient

from app.core import service
from app.core.messages import Inbound
from app.main import app
from app.store import chat


def say(client: TestClient, text: str) -> None:
    lines = client.post("/api/web/messages", json={"kind": "text", "text": text, "language": "en"}).text
    assert json.loads(lines.splitlines()[-1]) == {"kind": "done"}


def test_history_reads_back_in_order_and_pages(sign_in):
    with TestClient(app) as client:
        sign_in(client)
        say(client, "hello")
        say(client, "power cut in my street")
        latest = client.get("/api/web/history?limit=2").json()
        assert latest["has_more"] and [i["sender"] for i in latest["items"]] == ["user", "bot"]
        assert latest["items"][0]["body"] == {"kind": "text", "text": "power cut in my street"}
        assert "1912" in latest["items"][1]["body"]["body"]
        earlier = client.get(f"/api/web/history?limit=2&before={latest['items'][0]['id']}").json()
        assert earlier["items"][0]["body"]["text"] == "hello" and not earlier["has_more"]


def test_history_is_private_and_reset_erases_it(sign_in):
    with TestClient(app) as owner, TestClient(app) as other:
        sign_in(owner)
        sign_in(other)
        say(owner, "hello")
        assert other.get("/api/web/history").json()["items"] == []
        assert owner.post("/api/web/reset").status_code == 204
        assert owner.get("/api/web/history").json()["items"] == []
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/web/history").status_code == 401


def test_whatsapp_number_is_never_stored_in_history():
    async def ignore(_event: object) -> None:
        return None

    inbound = Inbound(channel="whatsapp", user_id="wa:test-history", kind="text", text="hello",
                      reply_to="test-wa-address-1")
    asyncio.run(service.handle(inbound, ignore))
    stored = chat.page("wa:test-history", None, 10)
    assert stored.items and all("test-wa-address-1" not in json.dumps(i.body) for i in stored.items)
