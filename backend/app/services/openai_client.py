"""Minimal OpenAI chat client over httpx, so the provider can be swapped by base URL (Azure, gateway)."""

import json
import logging
from typing import Any

import httpx

from app.config import get_settings
from app.core import retry
from app.services.http import shared

log = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    def __init__(self, message: str, transient: bool = False) -> None:
        super().__init__(message)
        self.transient = transient  # provider down, timed out or rate limited: worth trying again later


# Wording and classify have a rules fallback, so they give up fast; the bill reader passes its own policy.
TEXT = retry.Policy(attempts=2, base_s=1.0, max_s=5.0, budget_s=15.0)


async def _post(client: httpx.AsyncClient, body: dict[str, Any], headers: dict[str, str],
                policy: retry.Policy) -> httpx.Response:
    async def once() -> httpx.Response:
        return (await client.post("/chat/completions", json=body, headers=headers)).raise_for_status()

    return await retry.call(once, "openai", policy)


async def chat_json(model: str, system: str, user_content: Any, temperature: float = 0.1,
                    max_tokens: int = 800, policy: retry.Policy = TEXT) -> dict[str, Any]:
    """Return the model's JSON object reply. Raises ProviderError on any failure."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise ProviderError("no OpenAI key configured")
    body = {
        "model": model,
        "temperature": temperature,
        # Azure reserves rate-limit quota for the full output budget up front, so keep it tight.
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_content}],
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    try:
        client = shared(f"openai:{settings.openai_base_url}", base_url=settings.openai_base_url,
                        timeout=settings.request_timeout_s)
        response = await _post(client, body, headers, policy)
        content = response.json()["choices"][0]["message"]["content"]
        if not isinstance(content, str):  # a refusal comes back with no content at all
            raise ProviderError("no content")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ProviderError("reply was not a JSON object")
        return parsed
    except (httpx.HTTPError, *retry.TRANSPORT, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        log.warning("openai call failed: %s %s", type(exc).__name__, status or "")
        raise ProviderError(type(exc).__name__, retry.transient(exc)) from exc
