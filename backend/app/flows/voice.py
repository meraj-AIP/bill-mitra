"""Runs voice jobs (app/store/voice_jobs.py): a voice note the turn did not wait for, delivered once it is made.

The clip the turn started usually finished in the meantime and is in the cache, so most jobs only deliver it. On
WhatsApp the note goes through the outbox, which keeps one copy per job; in the web chat it is stored in the person's
chat, where the open page picks it up. Nothing is sent when the last try fails: the consumer already has the words.
"""

import logging
from datetime import datetime

from app.core.messages import AudioOut
from app.services import delivery, notify, tts
from app.store import voice_jobs
from app.store.voice_jobs import Job

log = logging.getLogger(__name__)


async def run_due(now: datetime | None = None) -> int:
    """Every job whose time has come. Returns how many notes were delivered."""
    sent = 0
    for job in voice_jobs.claim_due(now):
        try:
            ids = tts.cached(job.script, job.language) or await tts.speak(job.script, job.language)
            if not ids:
                raise RuntimeError("no voice yet")
            await _deliver(job, AudioOut(media_ids=ids, transcript=job.script, language=job.language))
        except Exception as exc:  # Soniox is still failing, or anything else: tried again, then parked
            log.warning("voice job not delivered yet: %s", type(exc).__name__)
            voice_jobs.later(job.id, type(exc).__name__, now)
            continue
        voice_jobs.done(job.id, now)
        sent += 1
    return sent


async def _deliver(job: Job, note: AudioOut) -> None:
    if job.channel == "whatsapp" and job.address:
        await delivery.send_reply(note, job.user_id, job.address, f"voice:{job.id}")
    else:
        notify.to_web_chat(job.user_id, note)
