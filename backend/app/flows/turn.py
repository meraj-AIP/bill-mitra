"""One inbound message and everything needed to answer it."""

import logging
from dataclasses import dataclass
from typing import Literal

from app.core.messages import AudioOut, Button, ButtonsOut, ImageOut, Inbound, TextOut
from app.core.trace import Tracer
from app.domain.conversation.composer import plain
from app.domain.conversation.lang import text
from app.services import tts
from app.store.repos import UserState

log = logging.getLogger(__name__)


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

    async def speak(self, spoken: str) -> bool:
        """Send a voice note. Returns False when voice is not available, so the caller sends text."""
        script = plain(spoken)
        async with self.tracer.step("Speak in the consumer's language", "ai") as step:
            try:
                ids = await tts.speak(script, self.lang)
            except Exception as exc:  # voice is optional: any failure here sends the text, never ends the turn
                log.warning("voice note failed: %s", type(exc).__name__)
                ids = None
            if not ids:
                step.skip("Voice unavailable: Sarvam key not set, Sarvam failed, or language without a voice. "
                          "Sent as text.")
                return False
            step.note(f"Sarvam Bulbul voice, {len(script)} characters, {len(ids)} clip(s)")
        await self.tracer.message(AudioOut(media_ids=ids, transcript=script, language=self.lang))
        return True
