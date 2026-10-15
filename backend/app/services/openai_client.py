"""Minimal OpenAI chat client over httpx, so the provider can be swapped by base URL (Azure, gateway)."""

import asyncio
import json
import logging
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    pass


ATTEMPTS = 3
MAX_WAIT_S = 20.0
RETRYABLE = {408, 429, 500, 502, 503, 504}


def _wait(response: httpx.Response, attempt: int) -> float:
    """Azure says how long to back off on a rate limit; otherwise back off exponentially."""
    try:
        hinted = float(response.headers.get("retry-after", ""))
    except ValueError:
        hinted = 2.0 * 2**attempt
    return min(max(hinted, 1.0), MAX_WAIT_S)


async def _post(client: httpx.AsyncClient, body: dict[str, Any], headers: dict[str, str]) -> httpx.Response:
    for attempt in range(ATTEMPTS):
        response = await client.post("/chat/completions", json=body, headers=headers)
        if response.status_code not in RETRYABLE or attempt == ATTEMPTS - 1:
            return response
        wait = _wait(response, attempt)
        log.info("openai %s, retrying in %.0fs", response.status_code, wait)
        await asyncio.sleep(wait)
    raise AssertionError("unreachable")


async def chat_json(model: str, system: str, user_content: Any, temperature: float = 0.1,
                    max_tokens: int = 800) -> dict[str, Any]:
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
        async with httpx.AsyncClient(base_url=settings.openai_base_url, timeout=settings.request_timeout_s) as client:
            response = await _post(client, body, headers)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed: dict[str, Any] = json.loads(content)
            return parsed
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        log.warning("openai call failed: %s %s", type(exc).__name__, status or "")
        raise ProviderError(type(exc).__name__) from exc
