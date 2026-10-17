"""Runs extract jobs (app/store/extract_jobs.py): bills whose read failed for a passing reason, read again later.

On WhatsApp the normal report goes out through the outbox when the read succeeds; on the last try a failed read asks
the consumer to type the units, as any failed read does. On the dashboard the report is kept on the job for the page
that polls it, and a checked bill lands in My bills.
"""

import itertools
import logging
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.core import service
from app.core.messages import Inbound
from app.core.trace import Event
from app.flows import report
from app.services import delivery, vision
from app.services.openai_client import ProviderError
from app.store import extract_jobs, media
from app.store.extract_jobs import Job

log = logging.getLogger(__name__)

QUEUED_DETAIL = ("The bill reader is busy right now. We kept your bill and will read it again in a few minutes; it "
                 "will appear in My bills.")
Finished = tuple[Literal["done", "failed"], str | None, dict[str, object] | None]


class ReadJob(BaseModel):
    """The dashboard's view of a queued read: the 202 body and what GET /api/bills/jobs/{job_id} returns."""

    job_id: str
    status: Literal["queued", "running", "done", "failed"]
    bill_id: str | None  # set when done and the bill was saved
    detail: str | None


def view(job: Job) -> ReadJob:
    status: Literal["queued", "running", "done", "failed"] = "failed" if job.state == "dismissed" else job.state
    detail = QUEUED_DETAIL if job.state in ("queued", "running") else None
    if job.result:
        detail = str(job.result.get("outcome_reason") or "") or None
    return ReadJob(job_id=job.id, status=status, bill_id=job.bill_id, detail=detail)


async def run_due(now: datetime | None = None) -> int:
    """Every job whose retry time has come. Returns how many finished with a read."""
    done = 0
    for job in extract_jobs.claim_due(now):
        done += await _run(job, now)
    return done


async def _run(job: Job, now: datetime | None) -> bool:
    try:
        state, bill_id, result = await (_whatsapp(job) if job.channel == "whatsapp" else _dashboard(job))
    except Exception as exc:  # the provider is still down, or anything else: tried again, then parked
        error = str(exc) if isinstance(exc, ProviderError) else type(exc).__name__
        log.warning("extract job not read yet: %s", error)
        if job.last_try:
            gave_up = _report(job, None).model_dump(mode="json") if job.channel == "dashboard" else None
            extract_jobs.finish(job.id, "failed", None, gave_up, error, now)
        else:
            extract_jobs.later(job.id, error, now)
        return False
    extract_jobs.finish(job.id, state, bill_id, result, None, now)
    return state == "done"


async def _whatsapp(job: Job) -> Finished:
    address = job.address or ""
    inbound = Inbound(channel="whatsapp", user_id=job.user_id, media_id=job.media_id, mime_type=job.mime,
                      kind="document" if job.mime == "application/pdf" else "image", reply_to=address)
    seq = itertools.count()

    async def emit(event: Event) -> None:
        if event.kind == "message" and event.message is not None and address:
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
