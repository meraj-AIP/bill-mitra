"""Self-healing passes, run by the scheduler every QUEUE_INTERVAL_SECONDS (docs/reliability-contract.md section 5):
release work whose worker died, retry inbound turns, send queued messages, read queued bills.

Each job takes the clock as `now` and returns how many things it did, like the automation jobs.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from pydantic import BaseModel

from app.channels.whatsapp import router
from app.flows import extract
from app.services import delivery
from app.store import accounts, extract_jobs, outbox, wa_queue


class QueueCounts(BaseModel):
    queued: int
    failed: int


class QueueHealth(BaseModel):
    inbox: QueueCounts
    outbox: QueueCounts
    extract: QueueCounts
    oldest_queued_s: int | None  # age of the oldest item still waiting in any queue


async def sweep_stuck(now: datetime) -> int:
    """Claims and sends whose worker died are put back, each audited with no actor."""
    requeued = ([f"inbox:{i}" for i in wa_queue.requeue_expired()] +
                [f"outbox:{i}" for i in outbox.requeue_stuck(now)] +
                [f"extract:{i}" for i in extract_jobs.requeue_stuck(now)])
    for target in requeued:
        accounts.audit(None, "queue.requeue", target, "lease expired, back in the queue")
    return len(requeued)


async def retry_inbox(now: datetime) -> int:
    senders = wa_queue.due_senders(now)
    for sender in senders:
        await router.drain(sender, now)
    return len(senders)


async def send_outbox(now: datetime) -> int:
    return await delivery.run_due(now)


async def run_extracts(now: datetime) -> int:
    return await extract.run_due(now)


# The sweep first, so what it releases is picked up in the same run.
JOBS: tuple[tuple[str, Callable[[datetime], Awaitable[int]]], ...] = (
    ("sweep_stuck", sweep_stuck), ("inbox", retry_inbox), ("outbox", send_outbox), ("extract", run_extracts))


def health(now: datetime | None = None) -> QueueHealth:
    found = {"inbox": wa_queue.counts(), "outbox": outbox.counts(), "extract": extract_jobs.counts()}
    oldest = min((c[2] for c in found.values() if c[2]), default=None)
    age = None
    if oldest:
        started = datetime.strptime(oldest, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        age = max(int(((now or datetime.now(UTC)) - started).total_seconds()), 0)
    return QueueHealth(**{k: QueueCounts(queued=c[0], failed=c[1]) for k, c in found.items()}, oldest_queued_s=age)
