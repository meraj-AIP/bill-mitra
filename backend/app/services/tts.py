"""Telugu-first voice notes: Soniox first (app/services/soniox_tts.py), Sarvam Bulbul when Soniox is not set up, does
not speak the language, or fails. Audio is kept by provider, exact text and voice settings (app/store/voice_cache.py),
so a sentence already spoken is never paid for twice, by any worker."""

import base64
import hashlib
import logging
import re

import httpx

from app.config import get_settings
from app.core import retry
from app.domain.conversation.lang import VOICE_CODES
from app.services import soniox_tts
from app.store import media, voice_cache

log = logging.getLogger(__name__)
CHUNK_LIMIT = 1200  # characters; Bulbul v3 accepts 2500, shorter chunks start playing sooner
# Voice is optional: after this the explanation goes as text, so it gives up quickly.
VOICE = retry.Policy(attempts=2, base_s=1.0, max_s=4.0, budget_s=15.0)


def _cache_key(text: str, language: str) -> str:
    s = get_settings()
    raw = f"{s.sarvam_model}|{s.sarvam_speaker}|{s.sarvam_pace}|{language}|{text}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _soniox_key(text: str, language: str) -> str:
    s = get_settings()
    raw = f"soniox|{s.soniox_tts_model}|{s.soniox_tts_voice or 'auto:' + s.soniox_tts_accent}|{language}|{text}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _cached(key: str) -> list[str] | None:
    """The clips for this text, while their files are still on disk (the retention sweep removes old ones)."""
    ids = voice_cache.voice(key)
    return ids if ids and all(media.path_for(i) for i in ids) else None


def chunks(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?।۔])\s+", text.strip())
    out, current = [], ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > CHUNK_LIMIT:
            out.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        out.append(current)
    return out


def _audio_mime(data: bytes) -> str:
    return "audio/wav" if data[:4] == b"RIFF" else "audio/mpeg"


async def _synthesise(client: httpx.AsyncClient, text: str, code: str) -> bytes:
    s = get_settings()
    body = {"text": text, "target_language_code": code, "speaker": s.sarvam_speaker,
            "model": s.sarvam_model, "pace": s.sarvam_pace, "output_audio_codec": "mp3"}

    async def once() -> httpx.Response:
        response = await client.post("/text-to-speech", json=body)
        if response.status_code in (400, 422) and "target_language_code" in body:
            # Older and newer API revisions name the language field differently.
            body["language_code"] = body.pop("target_language_code")
            response = await client.post("/text-to-speech", json=body)
        return response.raise_for_status()

    response = await retry.call(once, "sarvam tts", VOICE)
    audios = response.json().get("audios")
    if not isinstance(audios, list) or not audios or not isinstance(audios[0], str):
        raise ValueError("no audio in the reply")
    # validate=True: a garbled reply must fail here, not be saved and cached as an empty voice note.
    audio = base64.b64decode(audios[0], validate=True)
    if not audio:
        raise ValueError("empty audio")
    return audio


FAILURES = (httpx.HTTPError, *retry.TRANSPORT, KeyError, IndexError, ValueError, TypeError, AttributeError)


def _save(clips: list[bytes]) -> list[str]:
    return [media.save(audio, _audio_mime(audio)) for audio in clips]


async def _by_soniox(text: str, language: str) -> list[str] | None:
    try:
        async with soniox_tts.client() as client:
            found = await soniox_tts.catalogue(client)
            code = soniox_tts.language_code(language)
            if found is None or code not in found.languages:
                return None
            return _save([await soniox_tts.synthesise(client, part, code, found.voice) for part in chunks(text)])
    except FAILURES as exc:
        log.warning("soniox tts failed: %s", type(exc).__name__)
        return None


async def _by_sarvam(text: str, language: str) -> list[str] | None:
    code = VOICE_CODES.get(language)
    if code is None:
        return None
    s = get_settings()
    try:
        async with httpx.AsyncClient(base_url=s.sarvam_base_url, headers={"api-subscription-key": s.sarvam_api_key},
                                     timeout=s.request_timeout_s) as client:
            return _save([await _synthesise(client, part, code) for part in chunks(text)])
    except FAILURES as exc:
        log.warning("sarvam tts failed: %s", type(exc).__name__)
        return None


async def speak(text: str, language: str) -> list[str] | None:
    """Media ids for the voice note, or None when no provider can speak this language right now."""
    s = get_settings()
    providers = [(key, make) for on, key, make in (
        (bool(s.soniox_api_key), _soniox_key(text, language), _by_soniox),
        (bool(s.sarvam_api_key) and VOICE_CODES.get(language) is not None, _cache_key(text, language), _by_sarvam),
    ) if on]
    # A clip either provider already made is used before any new call is paid for.
    for key, _ in providers:
        cached = _cached(key)
        if cached:
            return cached
    for key, make in providers:
        ids = await make(text, language)
        if ids:
            voice_cache.remember_voice(key, ids)
            return ids
    return None
