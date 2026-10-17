"""What has to hold once real Meta credentials are added: verified posts only, every message answered, delivery
failures Meta reports later handled, STOP starting afresh, and a model refusal falling back to the template."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.channels.whatsapp.mapper import user_key
from app.config import get_settings
from app.domain.conversation.lang import PACKS
from app.main import app
from app.services import notify
from app.services.openai_client import ProviderError, chat_json
from app.store import complaints as store
from app.store.db import tx
from tests.real import OCT_2025, reading
from tests.whatsapp_kit import api, bodies, envelope, graph, ids, image, mid, number, post, say, tap, text  # noqa: F401


def whatsapp_complaint(api, graph, reader) -> tuple[str, str]:  # noqa: F811
    reader(reading(OCT_2025))
    sender = number()
    say(api, graph, text(sender, "hi"))
    say(api, graph, image(sender))
    out = say(api, graph, tap(sender, "complain"))
    assert "complaint_send" in ids(out), out
    say(api, graph, tap(sender, "complaint_send"))
    page = store.page(1, 50, owner=user_key(sender))
    assert page.total == 1
    return page.items[0]["ticket"], sender


def wamid_of(message_id: int) -> str:
    with tx() as conn:
        found = conn.execute("SELECT wa_message_id FROM complaint_messages WHERE id = ?", (message_id,)).fetchone()[0]
    assert found, "the sent message keeps Meta's id"
    return found


def test_without_the_app_secret_nothing_is_accepted(api, monkeypatch):  # noqa: F811
    monkeypatch.setattr(get_settings(), "whatsapp_app_secret", "")
    assert post(api, envelope(text(number(), "hi")), signature=None).status_code == 503


def test_a_signed_body_that_is_not_json_is_a_400(api):  # noqa: F811
    from tests.whatsapp_kit import sign
    body = b"not json"
    response = api.post("/api/whatsapp/webhook", content=body, headers={"X-Hub-Signature-256": sign(body)})
    assert response.status_code == 400


def test_video_sticker_and_location_get_an_answer(api, graph):  # noqa: F811
    sender = number()
    say(api, graph, text(sender, "hi"))
    for kind, body in (("video", {"id": "V1"}), ("sticker", {"id": "S1"}), ("location", {"latitude": 17.3})):
        out = say(api, graph, {"from": sender, "id": mid(), "type": kind, kind: body})
        assert out and out[0]["type"] == "text", kind


def test_a_photo_that_cannot_be_downloaded_is_answered(api, graph, reader):  # noqa: F811
    sender = number()
    say(api, graph, text(sender, "hi"))
    graph.fail_media = True
    out = say(api, graph, image(sender))
    assert out and out[0]["text"]["body"] == PACKS["te"].T["media_failed"]


@pytest.mark.parametrize(("template", "note"), [("complaint_update", notify.TEMPLATE_USED), ("", notify.REJECTED)])
def test_late_outside_window_failure_falls_back_to_the_template(api, graph, reader, sign_in, monkeypatch,  # noqa: F811
                                                               template, note):
    monkeypatch.setattr(get_settings(), "whatsapp_complaint_template", template)
    ticket, sender = whatsapp_complaint(api, graph, reader)
    sign_in(api, "admin")
    sent = api.post(f"/api/console/complaints/{ticket}/reply", json={"body": "We are checking."}).json()["messages"][-1]
    assert sent["delivery"] == "sent"
    failure = {"id": wamid_of(sent["id"]), "status": "failed", "recipient_id": sender, "errors": [{"code": notify.OUTSIDE_WINDOW}]}
    assert post(api, envelope(statuses=[failure])).status_code == 200
    after = next(m for m in api.get(f"/api/console/complaints/{ticket}").json()["messages"] if m["id"] == sent["id"])
    assert after["delivery_note"] == note
    assert (graph.messages()[-1]["type"] == "template") == bool(template)


def test_any_other_late_failure_is_marked_not_delivered(api, graph, reader, sign_in):  # noqa: F811
    ticket, sender = whatsapp_complaint(api, graph, reader)
    sign_in(api, "admin")
    sent = api.post(f"/api/console/complaints/{ticket}/reply", json={"body": "Update."}).json()["messages"][-1]
    failure = {"id": wamid_of(sent["id"]), "status": "failed", "errors": [{"code": 131026}]}
    post(api, envelope(statuses=[failure]))
    after = next(m for m in api.get(f"/api/console/complaints/{ticket}").json()["messages"] if m["id"] == sent["id"])
    assert after["delivery"] == "failed" and after["delivery_note"] == notify.FAILED_LATER


def test_after_stop_the_next_message_gets_the_privacy_notice_again(api, graph):  # noqa: F811
    sender = number()
    notice = PACKS["te"].T["privacy_notice"].split("{")[0]
    assert bodies(say(api, graph, text(sender, "hi")))[0].startswith(notice)
    say(api, graph, text(sender, "STOP"))
    assert bodies(say(api, graph, text(sender, "hello")))[0].startswith(notice)


@pytest.mark.parametrize("content", [None, "[1, 2]", '"just text"'])
def test_a_refusal_or_odd_reply_is_a_provider_error(monkeypatch, content):
    import asyncio

    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "test-key-not-real")
    real = httpx.AsyncClient
    reply = {"choices": [{"message": {"content": content, "refusal": "no" if content is None else None}}]}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=reply))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: real(*a, **{**k, "transport": transport}))
    with pytest.raises(ProviderError):
        asyncio.run(chat_json("any-model", "system", "user"))


def test_webhook_app_is_importable_with_a_raising_client():
    with TestClient(app) as client:
        assert client.get("/api/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "x",
                                                            "hub.challenge": "1"}).status_code == 403
