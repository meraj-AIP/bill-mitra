"""Runs the automation jobs (app/flows/automation.py) every AUTOMATION_INTERVAL_SECONDS, and the queue recovery jobs
(app/flows/recovery.py) every QUEUE_INTERVAL_SECONDS, each in one asyncio task of the one worker holding the lock.

A failing job is logged by name and exception type only (never its data) and the other jobs still run.
"""

import asyncio
import contextlib
import fcntl
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from app.config import get_settings
from app.flows import recovery
from app.flows.automation import JOBS

Jobs = tuple[tuple[str, Callable[[datetime], Awaitable[int]]], ...]

log = logging.getLogger(__name__)


class AutomationHealth(BaseModel):
    enabled: bool
    last_run_at: str | None
    last_error: str | None  # "job: ExceptionType", no personal data


@dataclass
class _State:
    task: asyncio.Task[None] | None = None  # automation
    queue_task: asyncio.Task[None] | None = None  # queue recovery
    lock_file: Any = None  # held open while this process is the one that runs the jobs
    last_run_at: str | None = None
    last_error: str | None = None


_state = _State()


async def _run(jobs: Jobs, now: datetime) -> tuple[dict[str, int], list[str]]:
    done: dict[str, int] = {}
    errors: list[str] = []
    for name, job in jobs:
        try:
            done[name] = await job(now)
        except Exception as exc:  # one job must never stop the others
            # No traceback: its message can carry what the job was working on.
            log.error("automation job %s failed: %s", name, type(exc).__name__)
            errors.append(f"{name}: {type(exc).__name__}")
    return done, errors


async def run_once(now: datetime) -> dict[str, int]:
    """Every automation job once with the same clock. Returns how many things each job did."""
    done, errors = await _run(JOBS, now)
    _state.last_run_at = now.isoformat(timespec="seconds")
    _state.last_error = "; ".join(errors) or None
    if any(done.values()):
        log.info("automation run: %s", done)
    return done


async def run_queues(now: datetime) -> dict[str, int]:
    done, _ = await _run(recovery.JOBS, now)
    if any(done.values()):
        log.info("queue recovery run: %s", done)
    return done


async def _loop(run: Callable[[datetime], Awaitable[dict[str, int]]], interval: int) -> None:
    while True:
        await run(datetime.now(UTC))
        await asyncio.sleep(interval)


def _claim() -> bool:
    """With several uvicorn workers each would run every job. The first to take this file lock runs them; the lock
    goes with the process, so if it dies another worker takes over at its next start."""
    if _state.lock_file is not None:
        return True
    handle = open(get_settings().data_dir / "automation.lock", "w")  # noqa: SIM115 (kept open on purpose)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return False
    _state.lock_file = handle
    return True


def start() -> None:
    settings = get_settings()
    if settings.automation_enabled and _state.task is None and _claim():
        _state.task = asyncio.create_task(_loop(run_once, settings.automation_interval_seconds), name="automation")
    if settings.queue_retry_enabled and _state.queue_task is None and _claim():
        _state.queue_task = asyncio.create_task(_loop(run_queues, settings.queue_interval_seconds),
                                                name="queue-recovery")


async def stop() -> None:
    tasks = (_state.task, _state.queue_task)
    _state.task = _state.queue_task = None
    for task in tasks:
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


def health() -> AutomationHealth:
    return AutomationHealth(enabled=get_settings().automation_enabled, last_run_at=_state.last_run_at,
                            last_error=_state.last_error)
