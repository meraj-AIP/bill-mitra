"""One inbound message and everything needed to answer it."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Literal

from app.core.messages import AudioOut, Button, ButtonsOut, ImageOut, Inbound, TextOut
from app.core.trace import Tracer
from app.domain.conversation.composer import plain
from app.domain.conversation.lang import text
from app.services import tts
from app.store import voice_jobs
from app.store.repos import UserState

log = logging.getLogger(__name__)
WAIT_S = 20.0  # how long a turn waits for a new voice note; after this the words go now and the note follows
Voice = Literal["sent", "later", "none"]


@dataclass
class Turn:
    inbound: Inbound
    state: UserState
    tracer: Tracer
    voice_reply: bool = False  # answer with a voice note too (bill explanations, voice questions)
    # What a bill read that fails for a passing reason does: queue an extract job (WhatsApp), raise so the job is
    # retried, or ask for the units as before (web chat, a job's last try).
    read_failure: Literal["defer", "raise", "fallback"] = "defer"

    @property
    def lang(self) -> str:
        return self.state.language

    def t(self, key: str, **values: object) -> str:
        return text(self.lang, key, **values)

    async def say(self, body: str) -> None:
        await self.tracer.message(TextOut(body=body, language=self.lang))

    async def say_key(self, key: str, **values: object) -> None:
        await self.say(self.t(key, **values))

    async def buttons(self, body: str, options: list[tuple[str, str]]) -> None:
        buttons = [Button(id=bid, title=self.t(key)) for bid, key in options[:3]]
        await self.tracer.message(ButtonsOut(body=body, buttons=buttons, language=self.lang))

    async def image(self, media_id: str, caption: str | None) -> None:
        await self.tracer.message(ImageOut(media_id=media_id, caption=caption, language=self.lang))

    async def speak(self, spoken: str) -> Voice:
        """Send a voice note: "sent", or "later" when it is still being made and a voice job will deliver it, or "none"
        when there is no voice for this language right now. Either way but "sent", the caller sends the words as text."""
        script = plain(spoken)
        async with self.tracer.step("Speak in the consumer's language", "ai") as step:
            ids = tts.cached(script, self.lang)
            if ids:
                step.note("Same words as before: the voice note already made is reused")
            elif tts.available():
                making = tts.start(script, self.lang)
                try:
                    ids = await asyncio.wait_for(asyncio.shield(making), WAIT_S)
                except TimeoutError:
                    self._follow_up(script)
                    step.note("The voice note is still being made: the words go now and the note follows")
                    return "later"
                except Exception as exc:  # voice is optional: any failure here sends the text, never ends the turn
                    log.warning("voice note failed: %s", type(exc).__name__)
            if not ids:
                step.skip("Voice unavailable: Soniox key not set, Soniox failed, or no voice for this language. "
                          "Sent as text.")
                return "none"
            step.note(f"Soniox voice, {len(script)} characters, {len(ids)} clip(s)")
        await self.tracer.message(AudioOut(media_ids=ids, transcript=script, language=self.lang))
        return "sent"

    def _follow_up(self, script: str) -> None:
        """Queue the note for the chat this turn came from. A web chat with nobody signed in has nowhere to send it."""
        whatsapp = self.inbound.channel == "whatsapp"
        if (whatsapp and not self.inbound.reply_to) or (not whatsapp and not self.state.user_id.startswith("acct:")):
            return
        voice_jobs.create(self.state.user_id, "whatsapp" if whatsapp else "web", self.inbound.reply_to, self.lang, script)
