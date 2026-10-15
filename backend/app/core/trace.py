"""The reasoning trace: what each step did, how long it took, and whether AI or rules did it."""

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
        await self.emit(Event(kind="trace", trace=step.model_copy()))
        started = time.perf_counter()
        handle = StepHandle(step)
        try:
            yield handle
        except Exception as exc:
            step.status = "failed"
            step.detail = step.detail or type(exc).__name__
            step.ms = int((time.perf_counter() - started) * 1000)
            await self.emit(Event(kind="trace", trace=step))
            raise
        if step.status == "running":
            step.status = "done"
        step.ms = int((time.perf_counter() - started) * 1000)
        await self.emit(Event(kind="trace", trace=step))
