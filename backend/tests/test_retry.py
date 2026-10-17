"""The one retry policy (app/core/retry.py), the SQLite lock retry in tx(), and workers starting together on a fresh
database. Nothing sleeps: the retry_waits fixture moves a fake clock."""

import asyncio
import logging
import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

import httpcore
import httpx
import pytest

from app.core import retry
from app.store import db

POLICY = retry.Policy(attempts=4, base_s=1.0, max_s=8.0, budget_s=60.0)
URL = "https://provider.example.test/v1/thing"


def status(code: int, retry_after: str | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", URL)
    headers = {"retry-after": retry_after} if retry_after else {}
    return httpx.HTTPStatusError("synthetic", request=request, response=httpx.Response(code, headers=headers,
                                                                                       request=request))


class Flaky:
    """Fails with the given errors in turn, then succeeds."""

    def __init__(self, *failures: BaseException) -> None:
        self.failures = list(failures)
        self.calls = 0

    async def __call__(self) -> str:
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return "ok"


def run(op: Flaky, policy: retry.Policy = POLICY) -> str:
    return asyncio.run(retry.call(op, "synthetic op", policy))


@pytest.mark.parametrize("failure", [
    status(503), status(429), status(408), status(425), status(500), status(502), status(504),
    httpx.ReadTimeout("slow"), httpx.ConnectTimeout("slow"),
    # A pooled connection the far end closed: retried on a fresh one (seen in the load test).
    httpx.ReadError("closed"), httpx.RemoteProtocolError("closed"), httpx.ConnectError("refused"),
    httpcore.ReadError("closed"), httpcore.RemoteProtocolError("closed"), httpcore.ConnectError("refused"),
])
def test_a_transient_failure_is_retried_until_it_works(failure, retry_waits):
    op = Flaky(failure, failure)
    assert run(op) == "ok" and op.calls == 3 and len(retry_waits) == 2


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_a_permanent_failure_is_raised_at_once(code, retry_waits):
    op = Flaky(status(code))
    with pytest.raises(httpx.HTTPStatusError):
        run(op)
    assert op.calls == 1 and retry_waits == []


def test_other_errors_are_not_retried(retry_waits):
    op = Flaky(KeyError("choices"))
    with pytest.raises(KeyError):
        run(op)
    assert op.calls == 1 and retry_waits == []


def test_attempts_are_bounded(retry_waits):
    op = Flaky(*[status(503)] * 10)
    with pytest.raises(httpx.HTTPStatusError):
        run(op)
    assert op.calls == POLICY.attempts and len(retry_waits) == POLICY.attempts - 1


def test_backoff_is_full_jitter_under_the_cap(retry_waits):
    op = Flaky(*[status(503)] * 10)
    with pytest.raises(httpx.HTTPStatusError):
        run(op, retry.Policy(attempts=6, base_s=1.0, max_s=4.0, budget_s=1000.0))
    assert all(0 <= wait <= min(4.0, 2 ** n) for n, wait in enumerate(retry_waits))


def test_retry_after_is_honoured_in_seconds_and_as_a_date(retry_waits):
    assert run(Flaky(status(429, "7"))) == "ok"
    later = format_datetime(datetime.now(UTC) + timedelta(seconds=30), usegmt=True)
    assert run(Flaky(status(503, later))) == "ok"
    assert retry_waits[0] == 7.0 and 25 <= retry_waits[1] <= 30


def test_the_time_budget_stops_retries_before_the_attempts_run_out(retry_waits):
    op = Flaky(status(429, "40"), status(429, "40"), status(429, "40"))
    with pytest.raises(httpx.HTTPStatusError):
        run(op)  # 40 s fits the 60 s budget, a second 40 s does not
    assert op.calls == 2 and retry_waits == [40.0]


def test_each_retry_logs_one_line_without_the_url(caplog):
    caplog.set_level(logging.INFO, logger="app.core.retry")
    run(Flaky(status(503), httpx.ReadError("closed")))
    lines = [r.getMessage() for r in caplog.records if r.name == "app.core.retry"]
    assert len(lines) == 2 and "synthetic op" in lines[0] and "503" in lines[0] and "ReadError" in lines[1]
    assert URL not in caplog.text


class Locked:
    """The real connection, except that BEGIN IMMEDIATE meets another worker's lock a given number of times."""

    def __init__(self, times: int, message: str = "database is locked") -> None:
        self.real = db.connection()
        self.times, self.message = times, message

    def execute(self, sql: str, *args: object) -> sqlite3.Cursor:
        if sql == "BEGIN IMMEDIATE" and self.times:
            self.times -= 1
            raise sqlite3.OperationalError(self.message)
        return self.real.execute(sql, *args)

    def __getattr__(self, name: str) -> object:
        return getattr(self.real, name)


def test_tx_waits_out_a_locked_database(monkeypatch, retry_waits):
    locked = Locked(2)
    monkeypatch.setattr(db, "connection", lambda: locked)
    with db.tx() as conn:
        assert conn.execute("SELECT 1").fetchone()[0] == 1
    assert locked.times == 0 and len(retry_waits) == 2


def test_tx_does_not_retry_other_database_errors(monkeypatch, retry_waits):
    locked = Locked(1, "disk I/O error")
    monkeypatch.setattr(db, "connection", lambda: locked)
    with pytest.raises(sqlite3.OperationalError), db.tx():
        pass
    assert retry_waits == []


def test_workers_starting_together_on_a_fresh_database_take_turns(tmp_path):
    """Four uvicorn workers on a new database used to race in the migration and three died with 'locked'."""
    backend = Path(__file__).resolve().parent.parent
    env = {**os.environ, "DATA_DIR": str(tmp_path)}
    code = "from app.store.db import connection; connection()"
    workers = [subprocess.Popen([sys.executable, "-c", code], cwd=backend, env=env, stderr=subprocess.PIPE)
               for _ in range(4)]
    results = [(w.wait(timeout=120), (w.stderr.read() if w.stderr else b"").decode()[-300:]) for w in workers]
    assert all(code == 0 for code, _ in results), results
    with sqlite3.connect(tmp_path / "billmitra.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name IN ('outbox', 'extract_jobs')").fetchone()[0] == 2
