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

from app.config import get_settings
from app.core import retry
from app.flows import recovery
from app.store import complaints, db, outbox, wa_queue

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


sqlite_only = pytest.mark.skipif(db.is_postgres(), reason="SQLite's write lock; Postgres has row locks")


@pytest.fixture
def held_write_lock():  # type: ignore[no-untyped-def]
    """Another worker holds the write lock, and our connection will not wait for it, so any attempt to take it fails
    at once instead of slowing the test."""
    shared = db.connection()
    other = sqlite3.connect(get_settings().data_dir / "billmitra.db", isolation_level=None)
    other.execute("BEGIN IMMEDIATE")
    shared.execute("PRAGMA busy_timeout=0")
    try:
        yield
    finally:
        shared.execute(f"PRAGMA busy_timeout={db.BUSY_TIMEOUT_MS}")
        other.execute("ROLLBACK")
        other.close()


@sqlite_only
def test_read_paths_never_take_the_write_lock(held_write_lock):
    """The load test: BEGIN IMMEDIATE on every transaction made the console and the webhook queue behind writers."""
    assert complaints.page(1, 10).total >= 0
    assert recovery.health().inbox.queued >= 0
    assert wa_queue.due_senders() is not None and outbox.due() is not None
    with db.tx() as conn:
        conn.execute("SELECT COUNT(*) FROM alerts").fetchone()
        assert not conn.in_transaction
    with pytest.raises(sqlite3.OperationalError, match="locked"), db.tx(immediate=True):
        pass  # a claim does need the lock, which proves the lock really is held


@sqlite_only
def test_only_claims_take_the_write_lock_up_front():
    with db.tx(immediate=True) as conn:
        assert conn.in_transaction
    with db.tx() as conn:
        conn.execute("SELECT 1").fetchone()
        assert not conn.in_transaction


def test_workers_starting_together_on_a_fresh_database_take_turns(tmp_path):
    """Four uvicorn workers on a new database used to race: first in the migration, then a finished worker's startup
    writes against another's migration. Each process here runs the app's real startup, scheduler included."""
    backend = Path(__file__).resolve().parent.parent
    env = {**os.environ, "DATA_DIR": str(tmp_path), "AUTOMATION_ENABLED": "true", "QUEUE_RETRY_ENABLED": "true"}
    code = ("from fastapi.testclient import TestClient\nfrom app.main import app\n"
            "with TestClient(app) as client:\n    assert client.get('/api/health').status_code == 200\n")
    workers = [subprocess.Popen([sys.executable, "-c", code], cwd=backend, env=env, stderr=subprocess.PIPE)
               for _ in range(4)]
    results = [(w.wait(timeout=120), (w.stderr.read() if w.stderr else b"").decode()[-300:]) for w in workers]
    assert all(code == 0 for code, _ in results), results
    if db.is_postgres():
        return  # the shared test database already had the schema; the four startups only had to take turns
    with sqlite3.connect(tmp_path / "billmitra.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name IN ('outbox', 'extract_jobs')").fetchone()[0] == 2


@pytest.mark.skipif(not db.is_postgres(), reason="Postgres claim lock")
def test_claims_take_turns_on_postgres_and_reads_do_not_wait():
    """tx(immediate=True) is SQLite's BEGIN IMMEDIATE on Postgres: while one claim runs, no other claim may start,
    and reads go on."""
    import psycopg

    from app.store import pg

    with db.tx(immediate=True), psycopg.connect(get_settings().database_url, autocommit=True) as other:
        taken = other.execute("SELECT pg_try_advisory_lock(%s)", (pg.CLAIM_LOCK,)).fetchone()
        assert taken is not None and taken[0] is False
        assert complaints.page(1, 10).total >= 0
    with psycopg.connect(get_settings().database_url, autocommit=True) as other:
        taken = other.execute("SELECT pg_try_advisory_lock(%s)", (pg.CLAIM_LOCK,)).fetchone()
        assert taken is not None and taken[0] is True
