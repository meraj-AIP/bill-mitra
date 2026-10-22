"""WhatsApp Cloud API webhook. Switches on when WHATSAPP_* settings are present."""

import asyncio
import hashlib
import hmac
import itertools
import json
import logging
from contextvars import ContextVar
from datetime import datetime

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.channels.whatsapp import client
from app.channels.whatsapp.mapper import IncomingWhatsApp, parse_failures, parse_webhook, user_key
from app.config import get_settings
from app.core import retry, service
from app.core.messages import Inbound, TextOut
from app.core.trace import Event
from app.core.uploads import displayable
from app.domain.conversation.lang import text
from app.services import delivery, notify
from app.store import media, repos, wa_queue
from app.store.alerts import raise_alert

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp channel"])


def signature_valid(secret: str, body: bytes, header: str | None) -> bool:
    # Without the app secret nothing can be verified, so nothing is accepted.
    if not secret:
        return False
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


async def _say(incoming: IncomingWhatsApp, key: str, language: str | None = None) -> None:
    """A fixed line outside the conversation engine, through the outbox like every other message."""
    language = language or repos.get_user(user_key(incoming.wa_id), "whatsapp").language
    message = TextOut(body=text(language, key), language=language)
    await delivery.send_reply(message, user_key(incoming.wa_id), incoming.wa_id, f"turn:{incoming.message_id}:{key}")


# The semaphore caps how many turns run at once in this worker. Order per sender comes from the shared queue.
_slots: dict[asyncio.AbstractEventLoop, asyncio.Semaphore] = {}


def _slot() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    if loop not in _slots:
        _slots.clear()
        _slots[loop] = asyncio.Semaphore(get_settings().whatsapp_turn_concurrency)
    return _slots[loop]


# Whether the turn running now has failed before, so a retry does not store the person's message twice.
_retrying: ContextVar[bool] = ContextVar("whatsapp_retrying", default=False)


async def drain(sender: str, now: datetime | None = None) -> None:
    """Handle this sender's waiting messages in order, as long as no other worker is on one of theirs. Whoever
    finishes a turn looks for the next, so a message that arrived at a busy moment is never left behind. A failed
    turn waits for its retry and holds the sender's later messages behind it; a parked one lets them go."""
    while (claimed := wa_queue.claim(sender, now)) is not None:
        token = _retrying.set(claimed.attempts > 0)
        try:
            async with _slot():
                await _turn(claimed.incoming)
        except Exception as exc:
            log.exception("whatsapp turn failed")
            await _failed(claimed, type(exc).__name__, now)
            continue
        finally:
            _retrying.reset(token)
        wa_queue.done(claimed.id)


async def _failed(claimed: wa_queue.Claimed, error: str, now: datetime | None) -> None:
    attempts, parked = wa_queue.fail(claimed.id, error, now)
    if attempts == 1:
        # Once, whatever happens next; the dedupe key keeps a second copy out of the outbox.
        language = repos.language_of(user_key(claimed.incoming.wa_id)) or "te"
        await _say(claimed.incoming, "working_on_it", language)
    if parked:
        # No message text: staff see it in Operations by its attempts and error class.
        raise_alert("inbound_failed", None, "WhatsApp message not answered",
                    f"A consumer's WhatsApp message failed {attempts} times and is parked. Retry or dismiss it on "
                    "the Operations page.", "audit.view", f"inbound_failed:{claimed.id}")


def resume() -> None:
    """At start: turns that were waiting when the server stopped are handled now instead of being lost."""
    for sender in wa_queue.waiting_senders():
        asyncio.get_running_loop().create_task(drain(sender))


async def _turn(incoming: IncomingWhatsApp) -> None:
    await client.mark_read(incoming.message_id)
    if incoming.kind == "unsupported":
        await _say(incoming, "unsupported_message")
        return
    media_id = mime = None
    if incoming.media_ref:
        try:
            data, mime = await client.download(incoming.media_ref)
        except (httpx.HTTPError, *retry.TRANSPORT, KeyError, ValueError) as exc:
            if retry.transient(exc):
                raise  # Meta is down for now: the inbox tries the whole turn again
            log.warning("whatsapp media could not be downloaded")
            await _say(incoming, "media_failed")
            return
        data, mime = await displayable(data, mime)
        media_id = media.save(data, mime)
    inbound = Inbound(channel="whatsapp", user_id=user_key(incoming.wa_id), kind=incoming.kind,  # type: ignore[arg-type]
                      text=incoming.text, reply_id=incoming.reply_id, media_id=media_id, mime_type=mime,
                      reply_to=incoming.wa_id)

    seq = itertools.count()

    async def emit(event: Event) -> None:
        # Numbered in the order the turn says them, so a retried turn finds what already went and sends only the rest.
        if event.kind == "message" and event.message is not None:
            await delivery.send_reply(event.message, inbound.user_id, incoming.wa_id,
                                      f"turn:{incoming.message_id}:{next(seq)}")

    await service.handle(inbound, emit, retryable=True, first_try=not _retrying.get())


@router.post("/webhook")
async def receive(request: Request, tasks: BackgroundTasks) -> dict[str, str]:
    settings = get_settings()
    if not settings.whatsapp_enabled:
        raise HTTPException(503, "WhatsApp channel is not configured")
    if not settings.whatsapp_app_secret:
        raise HTTPException(503, "Set WHATSAPP_APP_SECRET so incoming messages can be verified")
    body = await request.body()
    if not signature_valid(settings.whatsapp_app_secret, body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(401, "bad signature")
    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "body is not JSON") from exc
    for incoming in parse_webhook(payload):
        if repos.first_delivery(incoming.message_id):
            wa_queue.add(incoming)
            tasks.add_task(drain, incoming.wa_id)
    for failure in parse_failures(payload):
        tasks.add_task(notify.delivery_failed, failure.wamid, failure.error_code)
    return {"status": "received"}
