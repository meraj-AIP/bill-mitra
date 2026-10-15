"""Speech to text with Soniox async transcription. Voice notes are short, so polling is quick."""

import asyncio
import logging
from collections import Counter

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)
POLL_SECONDS = 0.6
MAX_WAIT_SECONDS = 40
LANGUAGE_HINTS = ["te", "hi", "en", "ur"]


async def _cleanup(client: httpx.AsyncClient, transcription_id: str | None, file_id: str | None) -> None:
    for path in (f"/v1/transcriptions/{transcription_id}" if transcription_id else None,
                 f"/v1/files/{file_id}" if file_id else None):
        if path:
            try:
                await client.delete(path)
            except httpx.HTTPError:
                log.info("soniox cleanup skipped for %s", path.split("/")[2])


async def transcribe(audio: bytes, mime: str) -> tuple[str, str | None] | None:
    """Return (text, detected language) or None if unavailable or failed."""
    s = get_settings()
    if not s.soniox_api_key:
        return None
    headers = {"Authorization": f"Bearer {s.soniox_api_key}"}
    transcription_id = file_id = None
    async with httpx.AsyncClient(base_url=s.soniox_base_url, headers=headers, timeout=s.request_timeout_s) as client:
        try:
            upload = await client.post("/v1/files", files={"file": ("voice", audio, mime)})
            upload.raise_for_status()
            file_id = upload.json()["id"]
            created = await client.post("/v1/transcriptions", json={
                "model": s.soniox_model, "file_id": file_id, "language_hints": LANGUAGE_HINTS,
                "enable_language_identification": True,
            })
            created.raise_for_status()
            transcription_id = created.json()["id"]
            waited = 0.0
            while waited < MAX_WAIT_SECONDS:
                status = (await client.get(f"/v1/transcriptions/{transcription_id}")).json()
                if status.get("status") == "completed":
                    break
                if status.get("status") == "error":
                    raise ValueError(status.get("error_message", "transcription error"))
                await asyncio.sleep(POLL_SECONDS)
                waited += POLL_SECONDS
            transcript = (await client.get(f"/v1/transcriptions/{transcription_id}/transcript")).json()
            tokens = transcript.get("tokens", [])
            text = "".join(t.get("text", "") for t in tokens).strip()
            languages = Counter(t.get("language") for t in tokens if t.get("language"))
            language = languages.most_common(1)[0][0] if languages else None
            return (text, language) if text else None
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            log.warning("soniox stt failed: %s", type(exc).__name__)
            return None
        finally:
            await _cleanup(client, transcription_id, file_id)
