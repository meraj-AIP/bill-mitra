"""Rate limits are retried with Azure's own back-off hint, a bounded number of times."""

import asyncio
import json

import httpx
import pytest

from app.config import get_settings
from app.services import openai_client


def _patch(monkeypatch: pytest.MonkeyPatch, statuses: list[int], waits: list[float]) -> list[float]:
    """`waits` is the shared retry_waits fixture: retries move a fake clock and never sleep."""
    monkeypatch.setattr(get_settings(), "openai_api_key", "test-key-not-real")

    def handler(_request: httpx.Request) -> httpx.Response:
        status = statuses.pop(0)
        if status != 200:
            return httpx.Response(status, headers={"retry-after": "3"})
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"ok": True})}}]})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(openai_client.httpx, "AsyncClient",
                        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    return waits


def test_rate_limit_is_retried_with_the_hint(monkeypatch, retry_waits):
    waits = _patch(monkeypatch, [429, 200], retry_waits)
    assert asyncio.run(openai_client.chat_json("m", "s", "u")) == {"ok": True}
    assert waits == [3.0]


def test_retries_are_bounded(monkeypatch, retry_waits):
    _patch(monkeypatch, [429, 429, 429], retry_waits)
    with pytest.raises(openai_client.ProviderError) as raised:
        asyncio.run(openai_client.chat_json("m", "s", "u"))
    assert raised.value.transient  # so a bill read is queued instead of answered as unreadable


def test_client_errors_are_not_retried(monkeypatch, retry_waits):
    waits = _patch(monkeypatch, [400], retry_waits)
    with pytest.raises(openai_client.ProviderError) as raised:
        asyncio.run(openai_client.chat_json("m", "s", "u"))
    assert waits == [] and not raised.value.transient
