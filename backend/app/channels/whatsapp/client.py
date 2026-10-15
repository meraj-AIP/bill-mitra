"""WhatsApp Cloud API calls: download inbound media, upload outbound media, send messages."""

import asyncio
import logging
import shutil
from typing import Any

import httpx

from app.config import get_settings
from app.store import media

log = logging.getLogger(__name__)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_settings().whatsapp_token}"}


async def download(media_ref: str) -> tuple[bytes, str]:
    s = get_settings()
    async with httpx.AsyncClient(timeout=s.request_timeout_s, headers=_headers()) as client:
        meta = (await client.get(f"{s.whatsapp_graph_url}/{media_ref}")).raise_for_status().json()
        data = (await client.get(meta["url"])).raise_for_status().content
    return data, meta.get("mime_type", "application/octet-stream").split(";")[0]


async def _to_voice_note(data: bytes) -> tuple[bytes, str]:
    """WhatsApp shows audio as a voice note only for OGG/Opus. Convert when ffmpeg is available."""
    if shutil.which("ffmpeg") is None:
        return data, "audio/mpeg"
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-c:a", "libopus", "-b:a", "32k", "-f", "ogg", "pipe:1",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
    out, _ = await proc.communicate(data)
    return (out, "audio/ogg") if proc.returncode == 0 and out else (data, "audio/mpeg")


async def upload(media_id: str) -> str:
    s = get_settings()
    data = media.load(media_id) or b""
    mime = media.mime_for(media_id)
    if mime.startswith("audio/"):
        data, mime = await _to_voice_note(data)
    files = {"file": (media_id, data, mime)}
    form = {"messaging_product": "whatsapp", "type": mime}
    async with httpx.AsyncClient(timeout=s.request_timeout_s, headers=_headers()) as client:
        response = await client.post(f"{s.whatsapp_graph_url}/{s.whatsapp_phone_number_id}/media",
                                     data=form, files=files)
        response.raise_for_status()
        uploaded: str = response.json()["id"]
        return uploaded


async def send(payload: dict[str, Any]) -> None:
    s = get_settings()
    async with httpx.AsyncClient(timeout=s.request_timeout_s, headers=_headers()) as client:
        response = await client.post(f"{s.whatsapp_graph_url}/{s.whatsapp_phone_number_id}/messages", json=payload)
        if response.is_error:
            log.warning("whatsapp send failed: %s", response.status_code)
        response.raise_for_status()


async def mark_read(message_id: str) -> None:
    payload = {"messaging_product": "whatsapp", "status": "read", "message_id": message_id}
    try:
        await send(payload)
    except httpx.HTTPError:
        log.info("could not mark message read")
