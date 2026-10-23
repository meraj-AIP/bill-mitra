"""Runs extract jobs (app/store/extract_jobs.py): bills whose read failed for a passing reason, read again later.

On WhatsApp the normal report goes out through the outbox when the read succeeds; in the web chat it is stored in the
person's chat, where the open page picks it up. On the last try a failed read asks the consumer to type the units, as
any failed read does. On the dashboard the report is kept on the job for the page that polls it, and a checked bill
lands in My bills.
"""

import itertools
import logging
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.core import service
from app.core.messages import Inbound, TextOut
from app.core.trace import Event
from app.domain.conversation.lang import text
from app.flows import report
from app.services import delivery, notify, vision
from app.services.openai_client import ProviderError
from app.store import extract_jobs, media
from app.store.extract_jobs import Job

log = logging.getLogger(__name__)

Finished = tuple[Literal["done", "failed"], str | None, dict[str, object] | None]


class ReadJob(BaseModel):
    """The dashboard's view of a queued read: the 202 body and what GET /api/bills/jobs/{job_id} returns. A finished
    read always says how it ended: `outcome` is "checked" with a bill_id, or the reason there is none (retake,
    not_a_bill, reading_failed), with `detail` saying it in the uploader's language."""

    job_id: str
    status: Literal["queued", "running", "done", "failed"]
    bill_id: str | None  # set when done and the bill was saved
    outcome: str | None = None  # set once the job has finished
    problem: str | None = None  # the lang key of what went wrong, when the frontend wants its own words
    detail: str | None


def view(job: Job) -> ReadJob:
    status: Literal["queued", "running", "done", "failed"] = "failed" if job.state == "dismissed" else job.state
    if job.state in ("queued", "running"):
        return ReadJob(job_id=job.id, status=status, bill_id=None, detail=text(job.language, "dash_queued"))
    result = job.result or {}
    outcome = "checked" if job.bill_id else str(result.get("outcome") or "reading_failed")
    detail = result.get("outcome_reason") or (None if job.bill_id else text(job.language, "dash_read_failed"))
    return ReadJob(job_id=job.id, status=status, bill_id=job.bill_id, outcome=outcome,
                   problem=result.get("problem") or (None if job.bill_id else "read_failed"),
                   detail=str(detail) if detail else None)


async def run_due(now: datetime | None = None) -> int:
    """Every job whose retry time has come. Returns how many finished with a read."""
    done = 0
    for job in extract_jobs.claim_due(now):
        done += await _run(job, now)
    return done


async def _run(job: Job, now: datetime | None) -> bool:
    try:
        state, bill_id, result = await (_dashboard(job) if job.channel == "dashboard" else _chat(job))
    except Exception as exc:  # the provider is still down, or anything else: tried again, then parked
        error = str(exc) if isinstance(exc, ProviderError) else type(exc).__name__
        log.warning("extract job not read yet: %s", error)
        if job.last_try:
            gave_up = _report(job, None).model_dump(mode="json") if job.channel == "dashboard" else None
            extract_jobs.finish(job.id, "failed", None, gave_up, error, now)
            await _tell_gave_up(job)
        else:
            extract_jobs.later(job.id, error, now)
        return False
    extract_jobs.finish(job.id, state, bill_id, result, None, now)
    return state == "done"


async def _tell_gave_up(job: Job) -> None:
    """The chat was told the result would follow, so the last failed try says so and what to do next. Once: the
    outbox drops a second copy with the same key, and a job finishes only once."""
    message = TextOut(body=text(job.language, "read_gave_up"), language=job.language)
    if job.channel == "whatsapp" and job.address:
        await delivery.send_reply(message, job.user_id, job.address, f"extract:{job.id}:gave_up")
    elif job.channel == "web":
        notify.to_web_chat(job.user_id, message)


async def _chat(job: Job) -> Finished:
    """WhatsApp sends each message of the report; the web chat already has them, stored as the read records them."""
    address = job.address or ""
    channel = "whatsapp" if job.channel == "whatsapp" else "web"
    inbound = Inbound(channel=channel, user_id=job.user_id, media_id=job.media_id, mime_type=job.mime,
                      kind="document" if job.mime == "application/pdf" else "image", reply_to=address or None)
    seq = itertools.count()

    async def emit(event: Event) -> None:
        if event.kind == "message" and event.message is not None and channel == "whatsapp" and address:
            await delivery.send_reply(event.message, job.user_id, address, f"extract:{job.id}:{next(seq)}")

    result = await service.resume_document(inbound, emit, job.last_try)
    return ("failed" if result == "reading_failed" else "done"), None, None


def _report(job: Job, reading: vision.Reading | None) -> report.BillReport:
    return report.finish_upload(job.user_id, reading, job.mime, job.media_id, job.language, None)


async def _dashboard(job: Job) -> Finished:
    data = media.load(job.media_id)
    reading = await report.read(data, job.mime) if data else None
    found = _report(job, reading)
    if found.id:
        return "done", found.id, None
    return ("failed" if found.outcome == "reading_failed" else "done"), None, found.model_dump(mode="json")
