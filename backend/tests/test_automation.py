"""Scheduled jobs: reminders, lapses, overdue and escalation, the digest, auto applied and section patterns.

Every job runs with a fixed clock. Cases are opened through the real report route, then their timestamps are set
to a fixed past moment so the clock decides what is due. The DB is shared across tests, so assertions look at
this test's own cases; the second run of a job must do nothing at all.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.domain.conversation.facts import rs
from app.domain.conversation.lang import text
from app.flows import automation, case_bills
from app.main import app
from app.services import billing_records, scheduler
from app.services.billing_records import RecordMonth, Records
from app.store import case_evidence as evidence_store
from app.store import complaints as complaint_store
from app.store.db import tx
from tests.real import variant
from tests.review_kit import SPIKED, Tree, printed, tree
from tests.test_review import _case, _consumer, _decide, _staff

T0 = datetime(2030, 1, 1, 6, 0, tzinfo=UTC)  # when this test's cases and requests were raised
MONTHS = ["2025-07", "2025-08", "2025-09"]


def run(job: Callable[[datetime], Awaitable[int]], now: datetime) -> int:
    return asyncio.run(job(now))


def _at(ticket: str, moment: datetime = T0) -> None:
    """Test-only: the case and its requests were raised at `moment`."""
    stamp = moment.strftime("%Y-%m-%d %H:%M:%S")
    with tx() as conn:
        conn.execute("UPDATE complaints SET created_at = ? WHERE ticket = ?", (stamp, ticket))
        conn.execute("UPDATE case_requests SET created_at = ? WHERE ticket = ?", (stamp, ticket))


def _audits(ticket: str, action: str) -> list[dict]:
    with tx() as conn:
        rows = conn.execute("SELECT actor_id, detail FROM audit_log WHERE target = ? AND action = ?",
                            (ticket, action)).fetchall()
    return [dict(r) for r in rows]


def _alerts(dedupe_key: str) -> int:
    with tx() as conn:
        return conn.execute("SELECT COUNT(*) FROM alerts WHERE dedupe_key = ?", (dedupe_key,)).fetchone()[0]


@pytest.fixture
def area() -> Tree:
    return tree()


@pytest.fixture
def asked(sign_in, area) -> tuple[TestClient, str, int]:
    """A case in section A whose system request for three earlier months is still open, raised at T0."""
    ae, _ = _staff(sign_in, "section_ae", area.section_a.id)
    consumer, user = _consumer(sign_in)
    _, ticket = _case(consumer, printed(SPIKED, area.section_a.name), user)
    request_id = evidence_store.add_month_request(ticket, MONTHS, "Earlier bills for " + ", ".join(MONTHS))
    _at(ticket)
    return ae, ticket, request_id


def test_reminder_once_after_the_wait_in_the_consumer_language(asked):
    ae, ticket, _ = asked
    run(automation.run_reminders, T0 + timedelta(days=2))
    assert not _audits(ticket, "case.remind")  # not yet due

    assert run(automation.run_reminders, T0 + timedelta(days=3, minutes=1)) >= 1
    assert run(automation.run_reminders, T0 + timedelta(days=4)) == 0  # running again sends nothing more
    assert [a["actor_id"] for a in _audits(ticket, "case.remind")] == [None]
    expected = text("en", "request_reminder", ticket=ticket, month=case_bills.month_name("en", "2025-10"),
                    months=case_bills.month_list("en", MONTHS))
    bodies = [m["body"] for m in complaint_store.messages(ticket) if m["author_kind"] == "system"]
    assert bodies.count(expected) == 1 and "AE" not in expected
    timeline = ae.get(f"/api/review/cases/{ticket}").json()["timeline"]
    assert any(e["actor"]["kind"] == "system" and e["text"].startswith("Reminded the consumer") for e in timeline)
    assert ae.get("/api/alerts").json()["items"][0]["kind"] == "request_reminded"


def test_lapse_closes_the_request_and_tells_the_consumer(asked):
    ae, ticket, request_id = asked
    run(automation.run_lapses, T0 + timedelta(days=6))
    assert ae.get(f"/api/review/cases/{ticket}").json()["state"] == "info_requested"

    assert run(automation.run_lapses, T0 + timedelta(days=7, minutes=1)) >= 1
    assert run(automation.run_lapses, T0 + timedelta(days=8)) == 0
    detail = ae.get(f"/api/review/cases/{ticket}").json()
    request = next(r for r in detail["requests"] if r["id"] == request_id)
    assert request["status"] == "answered" and request["note"] == automation.LAPSE_NOTE
    assert detail["state"] == "awaiting_review"
    lapsed = text("en", "request_lapsed", ticket=ticket, month=case_bills.month_name("en", "2025-10"),
                  months=case_bills.month_list("en", MONTHS))
    assert [m["body"] for m in detail["messages"]].count(lapsed) == 1
    assert any(e["actor"]["name"] == "System" and e["text"].startswith("Closed the request")
               for e in detail["timeline"])
    # A lapsed request is never reminded afterwards.
    run(automation.run_reminders, T0 + timedelta(days=9))
    assert not _audits(ticket, "case.remind")


def test_overdue_then_escalation_to_the_division(sign_in, area):
    ae, _ = _staff(sign_in, "section_ae", area.section_a.id)
    officer, _ = _staff(sign_in, "officer", area.division.id)
    consumer, user = _consumer(sign_in)
    _, ticket = _case(consumer, printed(SPIKED, area.section_a.name), user)
    _, decided = _case(consumer, printed(variant(SPIKED, bill_month="2025-11"), area.section_a.name), user)
    assert _decide(ae, decided, kind="correct", reason_code="bill_correct").status_code == 200
    _at(ticket)
    _at(decided)

    run(automation.run_overdue, T0 + timedelta(days=3, hours=1))
    assert _alerts(f"case_overdue:{ticket}") == 0  # within the default 3 day target

    run(automation.run_overdue, T0 + timedelta(days=4, hours=1))
    assert _alerts(f"case_overdue:{ticket}") == 1 and _alerts(f"case_escalated:{ticket}") == 0
    assert _alerts(f"case_overdue:{decided}") == 0  # a decided case is never overdue
    assert ae.get("/api/alerts").json()["items"][0]["ticket"] == ticket
    assert ticket not in {a["ticket"] for a in officer.get("/api/alerts").json()["items"]}  # needs cases.decide

    run(automation.run_overdue, T0 + timedelta(days=7, hours=1))
    assert run(automation.run_overdue, T0 + timedelta(days=8)) == 0
    assert _alerts(f"case_overdue:{ticket}") == 1 and _alerts(f"case_escalated:{ticket}") == 1
    escalated = officer.get("/api/alerts").json()["items"][0]
    assert escalated["kind"] == "case_escalated" and escalated["unit_name"] == area.division.name
    assert "case_escalated" not in {a["kind"] for a in ae.get("/api/alerts").json()["items"]}
    with tx() as conn:
        assert conn.execute("SELECT escalated_at FROM complaints WHERE ticket = ?", (ticket,)).fetchone()[0]
    assert [a["actor_id"] for a in _audits(ticket, "case.escalate")] == [None]
    timeline = officer.get(f"/api/review/cases/{ticket}").json()["timeline"]
    assert any(e["text"].startswith(f"Escalated: to {area.division.name}") for e in timeline)
    assert officer.get(f"/api/review/cases/{ticket}").json()["state"] == "awaiting_review"  # never decided for them


def test_daily_digest_once_a_day_after_the_hour(sign_in, area):
    ae, ae_id = _staff(sign_in, "section_ae", area.section_a.id)
    consumer, user = _consumer(sign_in)
    _, ticket = _case(consumer, printed(SPIKED, area.section_a.name), user)
    _at(ticket, T0.replace(hour=0))
    day = T0 + timedelta(days=3)  # 3 days open: due today under the default 3 day target
    assert run(automation.run_digest, day.replace(hour=1)) == 0  # 06:30 IST, before 08:00

    assert run(automation.run_digest, day.replace(hour=3)) >= 1  # 08:30 IST
    assert run(automation.run_digest, day.replace(hour=10)) == 0  # same IST day
    digest = [a for a in ae.get("/api/alerts").json()["items"] if a["kind"] == "digest"]
    assert len(digest) == 1 and digest[0]["body"] == "Waiting for a decision: 1. Due today: 1. Overdue: 0."
    assert _alerts(f"digest:{ae_id}:{day.date()}") == 1


def test_auto_applied_only_on_a_matching_billed_amount(sign_in, area, monkeypatch):
    ae, _ = _staff(sign_in, "section_ae", area.section_a.id)
    consumer, user = _consumer(sign_in)
    _, ticket = _case(consumer, printed(SPIKED, area.section_a.name), user)
    decision = _decide(ae, ticket, kind="corrected_reading", corrected_present_reading=351).json()["decisions"][0]
    billed = {"amount": decision["revised_amount"] + 5}

    async def records(_service_number: str | None) -> Records:
        return Records("included", [RecordMonth(month="2025-10", units=138, billed_amount=billed["amount"])])

    monkeypatch.setattr(billing_records, "fetch", records)
    assert run(automation.run_auto_applied, T0) == 0  # connector not live: nothing is fetched
    settings = get_settings()
    monkeypatch.setattr(settings, "billing_records_url", "https://records.example.invalid")
    monkeypatch.setattr(settings, "billing_records_token", "test-token-not-real")

    run(automation.run_auto_applied, T0)
    assert ae.get(f"/api/review/cases/{ticket}").json()["state"] == "decided"  # Rs 5 off is not a match

    billed["amount"] = decision["revised_amount"] + 0.5
    run(automation.run_auto_applied, T0)
    assert run(automation.run_auto_applied, T0) == 0
    detail = ae.get(f"/api/review/cases/{ticket}").json()
    assert detail["state"] == "applied" and detail["decisions"][0]["billing_ref"] == "DISCOM records 2025-10"
    assert [a["actor_id"] for a in _audits(ticket, "revision.applied_auto")] == [None]
    assert any(e["actor"]["kind"] == "system" and "billing records" in e["text"] for e in detail["timeline"])
    told = text("en", "review_applied", ticket=ticket, month=case_bills.month_name("en", "2025-10"),
                revised=rs(decision["revised_amount"]))
    assert [m["body"] for m in detail["messages"]].count(told) == 1
    assert _alerts(f"applied_auto:{decision['id']}") == 1


def _approved_corrections(sign_in, area: Tree, count: int) -> None:
    ae, _ = _staff(sign_in, "section_ae", area.section_a.id)
    consumer, user = _consumer(sign_in)
    for month in ("2025-10", "2025-11", "2025-12")[:count]:
        _, ticket = _case(consumer, printed(variant(SPIKED, bill_month=month), area.section_a.name), user)
        assert _decide(ae, ticket, kind="corrected_reading", corrected_present_reading=351).status_code == 200
        with tx() as conn:  # test-only: decided at T0
            conn.execute("UPDATE review_decisions SET decided_at = ? WHERE ticket = ?",
                         (T0.strftime("%Y-%m-%d %H:%M:%S"), ticket))


def test_pattern_alert_to_the_division_once_a_month(sign_in, area):
    officer, _ = _staff(sign_in, "officer", area.division.id)
    _approved_corrections(sign_in, area, 2)
    run(automation.run_patterns, T0 + timedelta(days=1))
    assert _alerts(f"pattern_section:{area.section_a.id}:2030-01") == 0  # two are not a pattern

    _approved_corrections(sign_in, area, 1)
    run(automation.run_patterns, T0 + timedelta(days=1))
    assert run(automation.run_patterns, T0 + timedelta(days=2)) == 0
    alert = next(a for a in officer.get("/api/alerts").json()["items"] if a["kind"] == "pattern_section")
    assert alert["body"].startswith(f"{area.section_a.name}: 3 corrected readings")
    assert run(automation.run_patterns, T0 + timedelta(days=91)) == 0  # outside the window


def test_one_failing_job_never_stops_the_others(monkeypatch):
    ran: list[str] = []

    async def broken(_now: datetime) -> int:
        raise RuntimeError("synthetic failure")

    async def fine(_now: datetime) -> int:
        ran.append("fine")
        return 1

    monkeypatch.setattr(scheduler, "JOBS", (("broken", broken), ("fine", fine)))
    assert asyncio.run(scheduler.run_once(T0)) == {"fine": 1}
    assert ran == ["fine"]
    health = TestClient(app).get("/api/health").json()["automation"]
    assert health == {"enabled": False, "last_run_at": T0.isoformat(timespec="seconds"),
                      "last_error": "broken: RuntimeError"}


def test_scheduler_starts_only_when_enabled_and_stops_cleanly(monkeypatch):
    ran: list[datetime] = []

    async def job(now: datetime) -> int:
        ran.append(now)
        return 0

    monkeypatch.setattr(scheduler, "JOBS", (("job", job),))

    async def lifecycle() -> None:
        scheduler.start()
        assert scheduler._state.task is None  # disabled in tests
        monkeypatch.setattr(get_settings(), "automation_enabled", True)
        scheduler.start()
        task = scheduler._state.task
        assert task is not None
        for _ in range(3):
            await asyncio.sleep(0)  # yield to the loop, no wall clock wait
        await scheduler.stop()
        assert task.cancelled() and scheduler._state.task is None

    asyncio.run(lifecycle())
    assert len(ran) == 1


def test_record_month_billed_amount_is_optional_and_checked():
    assert RecordMonth(month="2025-10", units=138).billed_amount is None
    assert RecordMonth(month="2025-10", units=138, billed_amount=812.5).billed_amount == 812.5
    with pytest.raises(ValueError):
        RecordMonth(month="2025-10", units=138, billed_amount=-1)
