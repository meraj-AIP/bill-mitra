"""The conversation engine. Channels hand it an Inbound and an emit function; it does the rest.

This module knows nothing about HTTP, WhatsApp or the web page.
"""

import logging

from app.config import get_settings
from app.core.errors import current_ref, log_failure, new_ref
from app.core.messages import Button, ButtonsOut, Inbound, TextOut
from app.core.trace import Emit, Event, Tracer
from app.domain.conversation.lang import text
from app.flows import bill as bill_flow
from app.flows import complaint as complaint_flow
from app.flows import complaint_chat, question, read_reply, usc_chat
from app.flows.turn import Turn
from app.services import stt
from app.store import chat, media, pending_reads, repos

log = logging.getLogger(__name__)


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
        await turn.say_key("file_lost")
        return
    async with turn.tracer.step("Listen to the voice note", "ai") as step:
        result = await stt.transcribe(data, inbound.mime_type or "audio/webm")
        if result is None:
            step.skip("Speech to text is switched off on this server; asked the consumer to type")
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


async def _retry(turn: Turn) -> None:
    """Try again: the message that failed, run once more as if just sent. A kept tap on Try again is never kept."""
    kept = pending_reads.take(turn.state.user_id, "retry")
    if not kept or kept.get("reply_id") == read_reply.RETRY:
        await turn.say_key("retry_gone")
        return
    turn.inbound = turn.inbound.model_copy(update=kept)
    await _dispatch(turn, turn.inbound)


async def _button(turn: Turn, reply_id: str) -> None:
    if reply_id == read_reply.RETRY:
        await _retry(turn)
    elif not (await complaint_chat.on_button(turn, reply_id) or await usc_chat.on_button(turn, reply_id) or
              await bill_flow.on_units_pick(turn, reply_id) or await read_reply.on_button(turn, reply_id)):
        await question.handle_button(turn, reply_id)


async def _dispatch(turn: Turn, inbound: Inbound) -> None:
    if await complaint_flow.capture_info(turn):
        return
    if inbound.kind in ("image", "document"):
        data = media.load(inbound.media_id or "")
        if not data:
            await turn.say_key("file_lost")
            return
        await bill_flow.handle_document(turn, data, inbound.mime_type or "image/jpeg", inbound.media_id)
    elif inbound.kind == "audio":
        await _voice(turn, inbound)
    elif inbound.kind == "button_reply" and inbound.reply_id:
        await _button(turn, inbound.reply_id)
    elif inbound.text and (await complaint_chat.on_text(turn, inbound.text) or
                           await usc_chat.on_text(turn, inbound.text)):
        return
    elif inbound.text:
        detected = detect_language(inbound.text)
        if detected and inbound.channel == "whatsapp":
            turn.state.language = detected
        await question.handle_text(turn, inbound.text)


def _recording(emit: Emit, inbound: Inbound, record_in: bool = True) -> tuple[Emit, int | None]:
    """Keep the conversation as the person saw it, so it reads back on any device after sign in. A retried turn or a
    queued bill read does not store the person's message a second time. Returns the wrapped emit and the stored id
    of the person's message."""
    asked = chat.record_in(inbound) if record_in else None

    async def recorded(event: Event) -> None:
        if event.kind == "message" and event.message is not None:
            stored = chat.record_out(inbound.user_id, event.message.model_dump(exclude_none=True))
            event = event.model_copy(update={"chat_id": stored})
        elif event.kind == "transcript" and event.text and asked:
            chat.add_transcript(asked, event.text)
        await emit(event)

    return recorded, asked


def _kept(turn: Turn) -> bool:
    try:
        read_reply.keep_for_retry(turn)
    except Exception:  # the store may be what failed: the apology still goes out, without the button
        return False
    return True


async def _sorry(turn: Turn, language: str, exc: Exception) -> None:
    """The generic failure: a reference support can find in the log, and Try again for the same message."""
    ref = current_ref() or new_ref()
    log_failure(log, "conversation turn failed", exc, ref)
    body = text(language, "error_generic", ref=ref)
    if turn.inbound.reply_id == read_reply.RETRY or not _kept(turn):
        await turn.tracer.message(TextOut(body=body, language=language))
        return
    await turn.tracer.message(ButtonsOut(body=body, language=language,
                                         buttons=[Button(id=read_reply.RETRY, title=text(language, "btn_try_again"))]))


async def handle(inbound: Inbound, emit: Emit, language: str | None = None, *, retryable: bool = False,
                 first_try: bool = True) -> None:
    """`retryable`: the caller queues the turn again on failure (the WhatsApp inbox), so an error is raised instead of
    answered, and the state is left as it was before the turn."""
    state = repos.get_user(inbound.user_id, inbound.channel)
    if language:
        state.language = language
    recorded, asked = _recording(emit, inbound, record_in=first_try)
    turn = Turn(inbound=inbound, state=state, tracer=Tracer(recorded))
    try:
        if asked is not None:
            await emit(Event(kind="state", chat_id=asked))
        if state.created and inbound.channel == "whatsapp":
            await _privacy_notice(turn, inbound)
        await _dispatch(turn, inbound)
    except Exception as exc:
        if retryable:
            raise
        await _sorry(turn, state.language, exc)  # a failed Try again keeps the message it was retrying
    repos.save_user(turn.state)


async def resume_document(inbound: Inbound, emit: Emit, last_try: bool) -> str:
    """A bill read that failed for a passing reason, run again by its extract job (app/flows/extract.py). Before the
    last try a provider failure is raised, so the job is retried; on the last try the consumer is offered Try again
    and typed units, as on any failed read. Returns the read's outcome."""
    state = repos.get_user(inbound.user_id, inbound.channel)
    turn = Turn(inbound=inbound, state=state, tracer=Tracer(_recording(emit, inbound, record_in=False)[0]),
                read_failure="fallback" if last_try else "raise")
    data = media.load(inbound.media_id or "")
    if not data:
        await turn.say_key("file_lost")
        result = "reading_failed"
    else:
        result = await bill_flow.handle_document(turn, data, inbound.mime_type or "image/jpeg", inbound.media_id)
    repos.save_user(turn.state)
    return result
