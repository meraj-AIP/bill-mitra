"""Telugu-first voice notes with Soniox (app/services/soniox_tts.py). Audio is kept by its exact text and voice
settings (app/store/voice_cache.py), so a sentence already spoken is never paid for twice, by any worker. When Soniox
cannot speak, the caller sends the words as text."""

import hashlib
import logging
import re

import httpx

from app.config import get_settings
from app.core import retry
from app.services import soniox_tts
from app.store import media, voice_cache

log = logging.getLogger(__name__)
CHUNK_LIMIT = 1200  # characters; shorter chunks start playing sooner
FAILURES = (httpx.HTTPError, *retry.TRANSPORT, KeyError, IndexError, ValueError, TypeError, AttributeError)


def _cache_key(text: str, language: str) -> str:
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


async def speak(text: str, language: str) -> list[str] | None:
    """Media ids for the voice note, or None when there is no voice for this language right now."""
    if not get_settings().soniox_api_key:
        return None
    key = _cache_key(text, language)
    cached = _cached(key)
    if cached:
        return cached
    try:
        async with soniox_tts.client() as client:
            found = await soniox_tts.catalogue(client)
            code = soniox_tts.language_code(language)
            if found is None or code not in found.languages:
                return None
            ids = [media.save(await soniox_tts.synthesise(client, part, code, found.voice), "audio/mpeg") for part in chunks(text)]
    except FAILURES as exc:
        log.warning("soniox tts failed: %s", type(exc).__name__)
        return None
    voice_cache.remember_voice(key, ids)
    return ids
