"""Guards that keep one server light: one automation runner per host, and a console summary that never makes a
request wait for the full count once it has been built."""

import fcntl
import threading

import pytest

from app.config import get_settings
from app.services import scheduler
from app.store import console


def test_only_one_process_runs_the_automation(monkeypatch: pytest.MonkeyPatch, tmp_path):
    # Its own folder: the app started by other tests already holds the shared lock, as it should.
    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    monkeypatch.setattr(scheduler, "_state", scheduler._State())
    assert scheduler._claim() is True
    try:
        with open(get_settings().data_dir / "automation.lock", "w") as other, pytest.raises(OSError):
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)  # a second worker on the same host
    finally:
        scheduler._state.lock_file.close()


def test_a_stale_summary_is_served_while_a_fresh_one_is_built(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(console, "CACHE_SECONDS", 60)
    console.forget_cached()
    clock = iter([0.0, 120.0, 121.0, 122.0])
    monkeypatch.setattr(console.time, "monotonic", lambda: next(clock))
    started = threading.Event()
    release = threading.Event()
    calls = []

    def build() -> dict:
        calls.append(1)
        if len(calls) > 1:
            started.set()
            release.wait(5)
        return {"n": len(calls)}

    assert console._cached(("k",), build) == {"n": 1}
    assert console._cached(("k",), build) == {"n": 1}  # stale, answered at once
    assert started.wait(5)
    release.set()
    for t in threading.enumerate():
        if t.name == "summary-refresh":
            t.join(5)
    assert console._cached(("k",), build) == {"n": 2}
