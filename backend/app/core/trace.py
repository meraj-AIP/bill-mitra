"""The reasoning trace: what each step did, how long it took, and whether AI or rules did it."""

import re
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, Literal

from pydantic import BaseModel

from app.core.messages import Outbound

Mode = Literal["ai", "rules", "demo", "channel"]
StepStatus = Literal["running", "done", "failed", "skipped"]


class TraceStep(BaseModel):
    id: str
    label: str
    status: StepStatus
    mode: Mode
    detail: str | None = None
    ms: int | None = None


class Event(BaseModel):
    kind: Literal["trace", "message", "transcript", "state"]
    trace: TraceStep | None = None
    message: Outbound | None = None
    text: str | None = None
    data: dict[str, Any] | None = None


Emit = Callable[[Event], Awaitable[None]]
# Step notes reach the web chat, so a setting's name ("OPENAI_API_KEY", "Sarvam key not set") never does.
_CONFIG = re.compile(r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b|(?i:\b[\w-]+ (?:api )?key(?: is)? not set,? ?)")


def public(step: TraceStep) -> TraceStep:
    if not step.detail:
        return step.model_copy()
    return step.model_copy(update={"detail": re.sub(r"\s{2,}", " ", _CONFIG.sub("", step.detail)).strip()})


class StepHandle:
    def __init__(self, step: TraceStep) -> None:
        self.step = step

    def note(self, detail: str, mode: Mode | None = None) -> None:
        self.step.detail = detail
        if mode:
            self.step.mode = mode

    def skip(self, detail: str) -> None:
        self.step.status = "skipped"
        self.step.detail = detail


class Tracer:
    def __init__(self, emit: Emit) -> None:
        self.emit = emit
        self._count = 0

    async def message(self, message: Outbound) -> None:
        await self.emit(Event(kind="message", message=message))

    @asynccontextmanager
    async def step(self, label: str, mode: Mode):  # type: ignore[no-untyped-def]
        self._count += 1
        step = TraceStep(id=f"s{self._count}", label=label, status="running", mode=mode)
        await self.emit(Event(kind="trace", trace=public(step)))
        started = time.perf_counter()
        handle = StepHandle(step)
        try:
            yield handle
        except Exception:
            step.status = "failed"
            step.detail = step.detail or "This step did not finish"  # never the error itself
            step.ms = int((time.perf_counter() - started) * 1000)
            await self.emit(Event(kind="trace", trace=public(step)))
            raise
        if step.status == "running":
            step.status = "done"
        step.ms = int((time.perf_counter() - started) * 1000)
        await self.emit(Event(kind="trace", trace=public(step)))
