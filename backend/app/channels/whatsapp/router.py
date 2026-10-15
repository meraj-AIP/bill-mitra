"""WhatsApp Cloud API webhook. Switches on when WHATSAPP_* settings are present."""

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.channels.whatsapp import client
from app.channels.whatsapp.mapper import IncomingWhatsApp, media_ids, parse_webhook, to_payload, user_key
from app.config import get_settings
from app.core import service
from app.core.messages import Inbound
from app.core.trace import Event
from app.store import media, repos

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp channel"])


def signature_valid(secret: str, body: bytes, header: str | None) -> bool:
    if not secret:
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


@router.get("/webhook", response_class=PlainTextResponse)
async def verify(mode: str = Query(alias="hub.mode"), token: str = Query(alias="hub.verify_token"),
                 challenge: str = Query(alias="hub.challenge")) -> str:
    settings = get_settings()
    if mode == "subscribe" and settings.whatsapp_verify_token and hmac.compare_digest(
            token, settings.whatsapp_verify_token):
        return challenge
    raise HTTPException(403, "verification failed")


async def _process(incoming: IncomingWhatsApp) -> None:
    await client.mark_read(incoming.message_id)
    media_id = mime = None
    if incoming.media_ref:
        data, mime = await client.download(incoming.media_ref)
        media_id = media.save(data, mime)
    inbound = Inbound(channel="whatsapp", user_id=user_key(incoming.wa_id), kind=incoming.kind,  # type: ignore[arg-type]
                      text=incoming.text, reply_id=incoming.reply_id, media_id=media_id, mime_type=mime,
                      reply_to=incoming.wa_id)

    async def emit(event: Event) -> None:
        if event.kind != "message" or event.message is None:
            return
        uploaded = {mid: await client.upload(mid) for mid in media_ids(event.message)}
        for payload in to_payload(incoming.wa_id, event.message, uploaded):
            await client.send(payload)

    await service.handle(inbound, emit)


@router.post("/webhook")
async def receive(request: Request, tasks: BackgroundTasks) -> dict[str, str]:
    settings = get_settings()
    if not settings.whatsapp_enabled:
        raise HTTPException(503, "WhatsApp channel is not configured")
    body = await request.body()
    if not signature_valid(settings.whatsapp_app_secret, body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(401, "bad signature")
    for incoming in parse_webhook(json.loads(body or b"{}")):
        if repos.first_delivery(incoming.message_id):
            tasks.add_task(_process, incoming)
    return {"status": "received"}
