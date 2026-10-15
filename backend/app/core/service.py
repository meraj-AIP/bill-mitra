"""The conversation engine. Channels hand it an Inbound and an emit function; it does the rest.

This module knows nothing about HTTP, WhatsApp or the web page.
"""

import logging

from app.config import get_settings
from app.core.messages import Inbound, TextOut
from app.core.trace import Emit, Event, Tracer
from app.flows import bill as bill_flow
from app.flows import complaint as complaint_flow
from app.flows import question
from app.flows.turn import Turn
from app.services import stt
from app.store import chat, media, repos

log = logging.getLogger(__name__)

ERROR_TEXT = {
    "te": "క్షమించండి, మా వైపు సమస్య వచ్చింది. దయచేసి మళ్లీ ప్రయత్నించండి.",
    "en": "Sorry, something went wrong on our side. Please try again.",
    "hi": "माफ़ कीजिए, हमारी तरफ़ से कुछ गड़बड़ हुई। कृपया दोबारा कोशिश करें।",
    "ur": "معذرت، ہماری طرف سے کچھ خرابی ہوئی۔ براہ کرم دوبارہ کوشش کریں۔",
}


def detect_language(message: str) -> str | None:
    for char in message:
        code = ord(char)
        if 0x0C00 <= code <= 0x0C7F:
            return "te"
        if 0x0900 <= code <= 0x097F:
            return "hi"
        if 0x0600 <= code <= 0x06FF:
            return "ur"
    return None


async def _voice(turn: Turn, inbound: Inbound) -> None:
    data = media.load(inbound.media_id or "")
    if data is None:
        await turn.say_key("need_bill")
        return
    async with turn.tracer.step("Listen to the voice note", "ai") as step:
        result = await stt.transcribe(data, inbound.mime_type or "audio/webm")
        if result is None:
            step.skip("Speech-to-text unavailable (Soniox key not set); asked the consumer to type")
        else:
            step.note(f"Soniox: \"{result[0][:80]}\"" + (f" ({result[1]})" if result[1] else ""))
    if result is None:
        await turn.say_key("help")
        return
    spoken, language = result
    await turn.tracer.emit(Event(kind="transcript", text=spoken))
    if language in ("te", "hi", "ur", "en"):
        turn.state.language = language
    turn.voice_reply = True
    await question.handle_text(turn, spoken)


async def _privacy_notice(turn: Turn, inbound: Inbound) -> None:
    """WhatsApp has no sign up screen, so the first message from a number gets the DPDP notice first."""
    detected = detect_language(inbound.text or "")
    if detected:
        turn.state.language = detected
    settings = get_settings()
    body = turn.t("privacy_notice", days=settings.retention_days)
    if settings.privacy_contact:
        body += "\n" + turn.t("privacy_contact", contact=settings.privacy_contact)
    await turn.say(body)


async def _dispatch(turn: Turn, inbound: Inbound) -> None:
    if await complaint_flow.capture_info(turn):
        return
    if inbound.kind in ("image", "document"):
        data = media.load(inbound.media_id or "")
        if not data:
            await turn.say_key("need_bill")
            return
        await bill_flow.handle_document(turn, data, inbound.mime_type or "image/jpeg", inbound.media_id)
    elif inbound.kind == "audio":
        await _voice(turn, inbound)
    elif inbound.kind == "button_reply" and inbound.reply_id:
        await question.handle_button(turn, inbound.reply_id)
    elif inbound.text:
        detected = detect_language(inbound.text)
        if detected and inbound.channel == "whatsapp":
            turn.state.language = detected
        await question.handle_text(turn, inbound.text)


def _recording(emit: Emit, inbound: Inbound) -> Emit:
    """Keep the conversation as the person saw it, so it reads back on any device after sign in."""
    asked = chat.record_in(inbound)

    async def recorded(event: Event) -> None:
        if event.kind == "message" and event.message is not None:
            chat.record_out(inbound.user_id, event.message.model_dump(exclude_none=True))
        elif event.kind == "transcript" and event.text:
            chat.add_transcript(asked, event.text)
        await emit(event)

    return recorded


async def handle(inbound: Inbound, emit: Emit, language: str | None = None) -> None:
    state = repos.get_user(inbound.user_id, inbound.channel)
    if language:
        state.language = language
    turn = Turn(inbound=inbound, state=state, tracer=Tracer(_recording(emit, inbound)))
    try:
        if state.created and inbound.channel == "whatsapp":
            await _privacy_notice(turn, inbound)
        await _dispatch(turn, inbound)
    except Exception:
        log.exception("conversation turn failed")
        await turn.tracer.message(TextOut(body=ERROR_TEXT.get(state.language, ERROR_TEXT["en"]),
                                          language=state.language))
    finally:
        repos.save_user(turn.state)
