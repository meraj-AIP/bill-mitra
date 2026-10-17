"""One retry policy for every call that leaves the server (docs/reliability-contract.md section 1).

Exponential backoff with full jitter, Retry-After honoured, bounded by an attempt count and a total time budget,
whichever comes first. Only transient failures are retried; a 400, 401, 403, 404 or 422 is surfaced at once.
`sleep` and `clock` are module attributes so tests replace them and never wait.
"""

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TypeVar

import httpcore
import httpx

log = logging.getLogger(__name__)
T = TypeVar("T")

TRANSIENT_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
# A pooled connection the far end already closed fails with a read, protocol or connect error; a fresh connection
# usually works, so these are transient. httpx normally wraps the httpcore ones, but not on every code path.
TRANSPORT: tuple[type[BaseException], ...] = (
    httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError,
    httpcore.TimeoutException, httpcore.NetworkError, httpcore.RemoteProtocolError,
    TimeoutError, ConnectionError)

sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
clock: Callable[[], float] = time.monotonic


@dataclass(frozen=True)
class Policy:
    attempts: int
    base_s: float
    max_s: float  # cap on one jittered wait; a Retry-After hint is bounded by the budget instead
    budget_s: float


def status_of(exc: BaseException) -> int | None:
    return exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None


def transient(exc: BaseException) -> bool:
    status = status_of(exc)
    if status is not None:
        return status in TRANSIENT_STATUS
    return isinstance(exc, TRANSPORT)


def retry_after(exc: BaseException) -> float | None:
    """Seconds the provider asked us to wait, from a number or an HTTP date; None when it did not say."""
    if not isinstance(exc, httpx.HTTPStatusError):
        return None
    value = exc.response.headers.get("retry-after", "").strip()
    if not value:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max((when - datetime.now(UTC)).total_seconds(), 0.0)


async def call(op: Callable[[], Awaitable[T]], name: str, policy: Policy,
               retry_on: Callable[[BaseException], bool] = transient) -> T:
    """Run `op` until it succeeds, a failure is not worth retrying, or attempts or budget run out. The last failure
    is raised as is, so callers keep their own handling."""
    started = clock()
    for attempt in range(1, policy.attempts + 1):
        try:
            return await op()
        except Exception as exc:
            if attempt == policy.attempts or not retry_on(exc):
                raise
            wait = retry_after(exc)
            if wait is None:
                wait = random.uniform(0, min(policy.max_s, policy.base_s * 2 ** (attempt - 1)))
            if clock() - started + wait > policy.budget_s:
                raise
            log.info("retry %s: attempt %d failed (%s), next in %.1fs", name, attempt,
                     status_of(exc) or type(exc).__name__, wait)
            await sleep(wait)
    raise AssertionError("unreachable")
