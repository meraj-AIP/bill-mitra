"""Telugu-first voice notes with Sarvam Bulbul. Audio is cached on disk by text, so a rehearsed
demo replays without the network and a repeated sentence never costs twice."""

import base64
import hashlib
import json
import logging
import re
import threading

import httpx

from app.config import get_settings
from app.core import retry
from app.domain.conversation.lang import VOICE_CODES
from app.store import media

log = logging.getLogger(__name__)
_lock = threading.Lock()
CHUNK_LIMIT = 1200  # characters; Bulbul v3 accepts 2500, shorter chunks start playing sooner
# Voice is optional: after this the explanation goes as text, so it gives up quickly.
VOICE = retry.Policy(attempts=2, base_s=1.0, max_s=4.0, budget_s=15.0)


def _index_path():  # type: ignore[no-untyped-def]
    return get_settings().data_dir / "tts_index.json"


def _cache_key(text: str, language: str) -> str:
    s = get_settings()
    raw = f"{s.sarvam_model}|{s.sarvam_speaker}|{s.sarvam_pace}|{language}|{text}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _cached(key: str) -> list[str] | None:
    path = _index_path()
    if not path.exists():
        return None
    ids = json.loads(path.read_text()).get(key)
    if ids and all(media.path_for(i) for i in ids):
        return list(ids)
    return None


def _remember(key: str, ids: list[str]) -> None:
    with _lock:
        path = _index_path()
        index = json.loads(path.read_text()) if path.exists() else {}
        index[key] = ids
        path.write_text(json.dumps(index))


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
    return base64.b64decode(response.json()["audios"][0])


async def speak(text: str, language: str) -> list[str] | None:
    """Return media ids for the voice note, or None when voice is unavailable for this language."""
    code = VOICE_CODES.get(language)
    if code is None:
        return None
    key = _cache_key(text, language)
    cached = _cached(key)
    if cached:
        return cached
    s = get_settings()
    if not s.sarvam_api_key:
        return None
    headers = {"api-subscription-key": s.sarvam_api_key}
    try:
        async with httpx.AsyncClient(base_url=s.sarvam_base_url, headers=headers,
                                     timeout=s.request_timeout_s) as client:
            ids = []
            for part in chunks(text):
                audio = await _synthesise(client, part, code)
                ids.append(media.save(audio, _audio_mime(audio)))
    except (httpx.HTTPError, *retry.TRANSPORT, KeyError, IndexError, ValueError) as exc:
        log.warning("sarvam tts failed: %s", type(exc).__name__)
        return None
    _remember(key, ids)
    return ids
