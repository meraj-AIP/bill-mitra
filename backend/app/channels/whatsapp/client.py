"""WhatsApp Cloud API calls: download inbound media, upload outbound media, send messages."""

import asyncio
import logging
import shutil
from typing import Any

import httpx

from app.config import get_settings
from app.core import retry
from app.services.http import shared
from app.store import media

log = logging.getLogger(__name__)


def _graph() -> httpx.AsyncClient:
    # Headers go on each request, so a token changed in settings applies at once.
    return shared("whatsapp", timeout=get_settings().request_timeout_s)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_settings().whatsapp_token}"}


FFMPEG_TIMEOUT_S = 30
# Inline attempts. A send still failing after this waits in the outbox (store/outbox.py) for a later try.
SEND = retry.Policy(attempts=3, base_s=1.0, max_s=8.0, budget_s=20.0, min_attempt_s=10.0)
MEDIA = retry.Policy(attempts=3, base_s=1.0, max_s=8.0, budget_s=20.0, min_attempt_s=10.0)
# Read receipts are best effort: one try, but long enough for Meta to answer.
ONCE = retry.Policy(attempts=1, base_s=0.0, max_s=0.0, budget_s=10.0)


async def _get(url: str) -> httpx.Response:
    async def once() -> httpx.Response:
        return (await _graph().get(url, headers=_headers())).raise_for_status()

    return await retry.call(once, "whatsapp media download", MEDIA)


async def download(media_ref: str) -> tuple[bytes, str]:
    """Raises httpx.HTTPError, KeyError or ValueError (too large); the caller tells the consumer."""
    s = get_settings()
    limit = s.max_upload_mb * 1024 * 1024
    meta = (await _get(f"{s.whatsapp_graph_url}/{media_ref}")).json()
    if int(meta.get("file_size") or 0) > limit:
        raise ValueError("media too large")
    data = (await _get(meta["url"])).content
    if len(data) > limit:
        raise ValueError("media too large")
    return data, meta.get("mime_type", "application/octet-stream").split(";")[0]


async def _to_voice_note(data: bytes) -> tuple[bytes, str]:
    """WhatsApp shows audio as a voice note only for OGG/Opus. Convert when ffmpeg is available."""
    if shutil.which("ffmpeg") is None:
        return data, "audio/mpeg"
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-c:a", "libopus", "-b:a", "32k", "-f", "ogg", "pipe:1",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(data), FFMPEG_TIMEOUT_S)
    except TimeoutError:
        proc.kill()
        log.warning("ffmpeg took too long; sending the audio unconverted")
        return data, "audio/mpeg"
    return (out, "audio/ogg") if proc.returncode == 0 and out else (data, "audio/mpeg")


async def upload(media_id: str) -> str:
    s = get_settings()
    data = media.load(media_id) or b""
    mime = media.mime_for(media_id)
    if mime.startswith("audio/"):
        data, mime = await _to_voice_note(data)
    files = {"file": (media_id, data, mime)}
    form = {"messaging_product": "whatsapp", "type": mime}

    async def once() -> httpx.Response:
        return (await _graph().post(f"{s.whatsapp_graph_url}/{s.whatsapp_phone_number_id}/media",
                                    data=form, files=files, headers=_headers())).raise_for_status()

    uploaded: str = (await retry.call(once, "whatsapp media upload", MEDIA)).json()["id"]
    return uploaded


async def _post_message(payload: dict[str, Any]) -> httpx.Response:
    s = get_settings()
    response = await _graph().post(f"{s.whatsapp_graph_url}/{s.whatsapp_phone_number_id}/messages", json=payload,
                                   headers=_headers())
    if response.is_error:
        # Meta's own error code says why (expired token, outside 24 hours, bad template); never the body.
        is_json = "json" in response.headers.get("content-type", "")
        code = (response.json().get("error") or {}).get("code") if is_json else None
        log.warning("whatsapp send failed: %s, Meta code %s", response.status_code, code)
    return response.raise_for_status()


async def send(payload: dict[str, Any], policy: retry.Policy = SEND) -> str | None:
    """Meta's id for the sent message, used to match the delivery status it reports later. Raises httpx errors
    (and httpcore transport errors) once the inline attempts are used up."""
    response = await retry.call(lambda: _post_message(payload), "whatsapp send", policy)
    is_json = "json" in response.headers.get("content-type", "")
    messages = (response.json().get("messages") if is_json else None) or [{}]
    found = messages[0].get("id")
    return found if isinstance(found, str) else None


async def mark_read(message_id: str) -> None:
    payload = {"messaging_product": "whatsapp", "status": "read", "message_id": message_id}
    try:
        await send(payload, ONCE)
    except (httpx.HTTPError, *retry.TRANSPORT):
        log.info("could not mark message read")
