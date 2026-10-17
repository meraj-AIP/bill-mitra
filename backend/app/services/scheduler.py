"""Runs the automation jobs (app/flows/automation.py) every AUTOMATION_INTERVAL_SECONDS in one asyncio task.

A failing job is logged by name and exception type only (never its data) and the other jobs still run.
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel

from app.config import get_settings
from app.flows.automation import JOBS

log = logging.getLogger(__name__)


class AutomationHealth(BaseModel):
    enabled: bool
    last_run_at: str | None
    last_error: str | None  # "job: ExceptionType", no personal data


@dataclass
class _State:
    task: asyncio.Task[None] | None = None
    last_run_at: str | None = None
    last_error: str | None = None


_state = _State()


async def run_once(now: datetime) -> dict[str, int]:
    """Every job once with the same clock. Returns how many things each job did."""
    done: dict[str, int] = {}
    errors: list[str] = []
    for name, job in JOBS:
        try:
            done[name] = await job(now)
        except Exception as exc:  # one job must never stop the others
            # No traceback: its message can carry what the job was working on.
            log.error("automation job %s failed: %s", name, type(exc).__name__)
            errors.append(f"{name}: {type(exc).__name__}")
    _state.last_run_at = now.isoformat(timespec="seconds")
    _state.last_error = "; ".join(errors) or None
    if any(done.values()):
        log.info("automation run: %s", done)
    return done


async def _loop(interval: int) -> None:
    while True:
        await run_once(datetime.now(UTC))
        await asyncio.sleep(interval)


def start() -> None:
    settings = get_settings()
    if settings.automation_enabled and _state.task is None:
        _state.task = asyncio.create_task(_loop(settings.automation_interval_seconds), name="automation")


async def stop() -> None:
    task, _state.task = _state.task, None
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def health() -> AutomationHealth:
    return AutomationHealth(enabled=get_settings().automation_enabled, last_run_at=_state.last_run_at,
                            last_error=_state.last_error)
