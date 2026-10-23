"""Soniox voice notes (https://soniox.com/docs/tts). app/services/tts.py caches what this makes.

The languages and voices come from Soniox's own lists, read once and kept for a day, so a language or voice they add
needs no release here. The voice is the configured one, else the first shared voice with the configured accent
(Indian by default), else a voice whose description names that accent, else the first voice the model offers.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import get_settings
from app.core import retry

log = logging.getLogger(__name__)
LIST_TTL_S = 24 * 3600
# The lists are small and quick, so they give up quickly.
LISTS = retry.Policy(attempts=2, base_s=1.0, max_s=4.0, budget_s=12.0)
# Soniox speaks about as fast as the clip plays, so one part takes a few seconds and a long one ten or more. Each try
# gets that time in full; the turn decides how long it waits (app/flows/turn.py), and a background job has no hurry.
VOICE = retry.Policy(attempts=3, base_s=1.0, max_s=4.0, budget_s=60.0, min_attempt_s=30.0)


class NoAudio(ValueError):
    """A 200 without audio in it, which is how Soniox answers a request over its limit on requests at once."""


def _worth_retrying(exc: BaseException) -> bool:
    return retry.transient(exc) or isinstance(exc, NoAudio)


@dataclass(frozen=True)
class Catalogue:
    voice: str
    languages: frozenset[str]


_kept: tuple[float, Catalogue] | None = None


def language_code(language: str) -> str:
    """Soniox names languages by their two letter code: te-IN and te are both te."""
    return language.split("-")[0].strip().lower()


def choose_voice(shared: list[dict[str, Any]], listed: list[dict[str, Any]], accent: str) -> str | None:
    wanted = accent.strip().lower()
    for v in shared:
        if wanted and str(v.get("accent") or "").lower() == wanted and v.get("id"):
            return str(v["id"])
    for v in listed:
        if wanted and wanted in str(v.get("description") or "").lower() and v.get("id"):
            return str(v["id"])
    return next((str(v["id"]) for v in listed if v.get("id")), None)


def _model(body: Any, model_id: str) -> dict[str, Any] | None:
    models = body.get("models") if isinstance(body, dict) else None
    for m in models if isinstance(models, list) else []:
        if isinstance(m, dict) and model_id in (m.get("id"), m.get("aliased_model_id")):
            return m
    return None


async def _get(client: httpx.AsyncClient, path: str, params: dict[str, str] | None = None) -> Any:
    async def once() -> httpx.Response:
        return (await client.get(path, params=params)).raise_for_status()

    return (await retry.call(once, "soniox tts list", LISTS)).json()


async def catalogue(client: httpx.AsyncClient) -> Catalogue | None:
    """The voice and the languages for the configured model, or None when Soniox cannot say."""
    global _kept
    if _kept and time.monotonic() - _kept[0] < LIST_TTL_S:
        return _kept[1]
    s = get_settings()
    model = _model(await _get(client, "/v1/tts-models"), s.soniox_tts_model)
    if model is None:
        log.warning("soniox tts model %s is not offered", s.soniox_tts_model)
        return None
    listed = [v for v in model.get("voices") or [] if isinstance(v, dict)]
    shared: list[dict[str, Any]] = []
    if not s.soniox_tts_voice and s.soniox_tts_accent:
        try:
            found = await _get(client, "/v1/shared-voices", {"model": s.soniox_tts_model, "accent": s.soniox_tts_accent.lower()})
            shared = [v for v in (found.get("voices") or []) if isinstance(v, dict)] if isinstance(found, dict) else []
        except (httpx.HTTPError, *retry.TRANSPORT, ValueError):
            shared = []  # the accent filter is a preference; the model's own list still has voices
    voice = s.soniox_tts_voice or choose_voice(shared, listed, s.soniox_tts_accent)
    languages = frozenset(str(lang["code"]).lower() for lang in model.get("languages") or [] if isinstance(lang, dict) and lang.get("code"))
    if not voice or not languages:
        return None
    _kept = (time.monotonic(), Catalogue(voice, languages))
    log.info("soniox tts voice %s, %d languages", voice, len(languages))
    return _kept[1]


async def synthesise(client: httpx.AsyncClient, text: str, language: str, voice: str) -> bytes:
    s = get_settings()
    body = {"model": s.soniox_tts_model, "language": language, "voice": voice, "audio_format": "mp3", "text": text}

    async def once() -> bytes:
        response = (await client.post(s.soniox_tts_url, json=body)).raise_for_status()
        # The body is the audio itself. An error that starts after streaming can only show as a short or empty body.
        if not response.headers.get("content-type", "").startswith("audio/") or len(response.content) < 64:
            raise NoAudio("no audio in the reply")
        return response.content

    return await retry.call(once, "soniox tts", VOICE, _worth_retrying)


def client() -> httpx.AsyncClient:
    s = get_settings()
    return httpx.AsyncClient(base_url=s.soniox_base_url, headers={"Authorization": f"Bearer {s.soniox_api_key}"},
                             timeout=s.request_timeout_s)


def forget() -> None:
    """Tests, and a settings change, start from a fresh list."""
    global _kept
    _kept = None
