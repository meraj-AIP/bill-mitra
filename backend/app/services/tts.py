"""Telugu-first voice notes with Soniox (app/services/soniox_tts.py). Audio is kept by its exact text and voice
settings (app/store/voice_cache.py), so a sentence already spoken is never paid for twice, by any worker. When Soniox
cannot speak, the caller sends the words as text.

Soniox takes about as long to make a clip as the clip plays, so one long request for a whole explanation took 46 s.
The text is cut into short parts, made PARALLEL at a time, and joined into one clip: one voice note on WhatsApp."""

import asyncio
import hashlib
import logging
import re

import httpx

from app.config import get_settings
from app.core import retry
from app.services import soniox_tts
from app.store import media, voice_cache

log = logging.getLogger(__name__)
PART_LIMIT = 220  # characters in one request; a part this long takes Soniox a few seconds
PARALLEL = 3  # Soniox's limit on requests at once for one key; a fourth comes back without audio
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
        if current and len(current) + len(sentence) + 1 > PART_LIMIT:
            out.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        out.append(current)
    return out


def _without_tag(clip: bytes) -> bytes:
    """The clip without its leading ID3 tag. MP3 frames play back to back, but a tag in the middle breaks decoding."""
    if len(clip) < 10 or clip[:3] != b"ID3":
        return clip
    size = (clip[6] & 0x7F) << 21 | (clip[7] & 0x7F) << 14 | (clip[8] & 0x7F) << 7 | (clip[9] & 0x7F)
    return clip[10 + size + (10 if clip[5] & 0x10 else 0):]


def join(clips: list[bytes]) -> bytes:
    return clips[0] + b"".join(_without_tag(c) for c in clips[1:]) if clips else b""


def available() -> bool:
    return bool(get_settings().soniox_api_key)


def cached(text: str, language: str) -> list[str] | None:
    """The voice note for these exact words, when one was made before and its file is still kept."""
    return _cached(_cache_key(text, language)) if available() else None


async def speak(text: str, language: str) -> list[str] | None:
    """Media ids for the voice note, or None when there is no voice for this language right now."""
    if not available():
        return None
    key = _cache_key(text, language)
    found_ids = _cached(key)
    if found_ids:
        return found_ids
    try:
        async with soniox_tts.client() as client:
            found = await soniox_tts.catalogue(client)
            code = soniox_tts.language_code(language)
            if found is None or code not in found.languages:
                return None
            gate = asyncio.Semaphore(PARALLEL)

            async def part(words: str) -> bytes:
                async with gate:
                    return await soniox_tts.synthesise(client, words, code, found.voice)

            clips = await asyncio.gather(*(part(p) for p in chunks(text)))
    except FAILURES as exc:
        log.warning("soniox tts failed: %s", type(exc).__name__)
        return None
    ids = [media.save(join(list(clips)), "audio/mpeg")]
    voice_cache.remember_voice(key, ids)
    return ids


_making: set[asyncio.Task[list[str] | None]] = set()  # held so a clip the turn stopped waiting for is still made


def start(text: str, language: str) -> asyncio.Task[list[str] | None]:
    """Make the clip in its own task. A turn that stops waiting leaves it running, and it lands in the cache."""
    task = asyncio.get_running_loop().create_task(speak(text, language))
    _making.add(task)
    task.add_done_callback(_making.discard)
    return task
