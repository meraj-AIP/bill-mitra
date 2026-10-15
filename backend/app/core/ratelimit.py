"""Fixed-window request limits, in memory. One API process per deployment (SQLite already requires that);
a second worker would need a shared store such as Redis."""

import time
from collections.abc import Callable
from threading import Lock

from fastapi import HTTPException, Request

_hits: dict[str, tuple[float, int]] = {}
_lock = Lock()
_MAX_KEYS = 50_000  # bounds memory under a flood of distinct keys


def hit(key: str, limit: int, window_s: int) -> bool:
    now = time.monotonic()
    with _lock:
        if len(_hits) > _MAX_KEYS:
            _hits.clear()
        start, count = _hits.get(key, (now, 0))
        if now - start >= window_s:
            start, count = now, 0
        _hits[key] = (start, count + 1)
        return count + 1 <= limit


def per_ip(name: str, limit: int, window_s: int = 60) -> Callable[[Request], None]:
    def check(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        if not hit(f"{name}:{client}", limit, window_s):
            raise HTTPException(429, "Too many attempts. Please wait a minute and try again.")

    return check
