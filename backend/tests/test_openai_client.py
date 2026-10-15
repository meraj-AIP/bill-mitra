"""Rate limits are retried with Azure's own back-off hint, a bounded number of times."""

import asyncio
import json

import httpx
import pytest

from app.config import get_settings
from app.services import openai_client


def _patch(monkeypatch: pytest.MonkeyPatch, statuses: list[int]) -> list[float]:
    monkeypatch.setattr(get_settings(), "openai_api_key", "test-key-not-real")
    waits: list[float] = []

    async def no_sleep(seconds: float) -> None:
        waits.append(seconds)

    def handler(_request: httpx.Request) -> httpx.Response:
        status = statuses.pop(0)
        if status != 200:
            return httpx.Response(status, headers={"retry-after": "3"})
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"ok": True})}}]})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(openai_client.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(openai_client.httpx, "AsyncClient",
                        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    return waits


def test_rate_limit_is_retried_with_the_hint(monkeypatch):
    waits = _patch(monkeypatch, [429, 200])
    assert asyncio.run(openai_client.chat_json("m", "s", "u")) == {"ok": True}
    assert waits == [3.0]


def test_retries_are_bounded(monkeypatch):
    _patch(monkeypatch, [429, 429, 429])
    with pytest.raises(openai_client.ProviderError):
        asyncio.run(openai_client.chat_json("m", "s", "u"))


def test_client_errors_are_not_retried(monkeypatch):
    waits = _patch(monkeypatch, [400])
    with pytest.raises(openai_client.ProviderError):
        asyncio.run(openai_client.chat_json("m", "s", "u"))
    assert waits == []
