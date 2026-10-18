"""Maker-checker: the rules prepare routine actions, an officer approves them, and nothing happens without that.

Bills are real fixtures or labelled variants (tests/real.py, tests/test_misread.py). Logins and numbers are fake.
"""

import secrets
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.flows import proposals as flow
from app.main import app
from app.store import complaints, review
from app.store import proposals as store
from app.store.complaints import General, Intake, Placement
from app.store.db import DISCOM_UNITS, tx
from tests.real import OCT_2025, variant
from tests.review_kit import Tree, tree
from tests.test_complaints import OVERCHARGED, chat_complaint
from tests.test_misread import consumer, report, staff, synthetic, upload

LATER = datetime.now(UTC) + timedelta(hours=1)  # past the wait, so every new complaint is looked at


@pytest.fixture(autouse=True)
def every_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    # The test database is shared, so one pass must reach this test's complaints whatever came before.
    monkeypatch.setattr(get_settings(), "proposal_batch", 5000)


@pytest.fixture
def area() -> Tree:
    return tree()


def _proposals(ticket: str) -> list[dict]:
    with tx() as conn:
        return [dict(r) for r in conn.execute("SELECT id, kind, state, decided_by, note FROM proposals "
                                              "WHERE ticket = ? ORDER BY id", (ticket,))]


def _officer(sign_in, *scopes: str) -> TestClient:
    client = TestClient(app)
    sign_in(client, "officer", "TGSPDCL", scopes=list(scopes) or None)
    return client


def test_a_correct_bill_gets_its_explanation_proposed_and_sent_only_on_approval(reader, sign_in):
    ticket = chat_complaint(reader, "web", variant(OCT_2025, bill_month="2025-07"))
    flow.run(LATER)
    [made] = _proposals(ticket)
    assert made["kind"] == "explain_correct" and made["state"] == "pending"
    assert complaints.get(ticket).status == "Open"  # proposing changes nothing

    officer = _officer(sign_in)
    listed = officer.get("/api/console/proposals", params={"kind": "explain_correct", "page_size": 100}).json()
    mine = next(p for p in listed["items"] if p["ticket"] == ticket)
    assert mine["why"] and listed["counts"]["explain_correct"] >= 1
    approved = officer.post(f"/api/console/proposals/{mine['id']}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "approved" and approved.json()["decided_by_name"]
    detail = officer.get(f"/api/console/complaints/{ticket}").json()
    assert detail["status"] == "Resolved" and any(m["author_kind"] == "officer" for m in detail["messages"])
    assert officer.post(f"/api/console/proposals/{mine['id']}/approve").status_code == 409


def test_an_overcharge_is_left_to_the_officer_and_a_fresh_complaint_waits(reader):
    over = chat_complaint(reader, "web", OVERCHARGED)
    young = chat_complaint(reader, "web", variant(OCT_2025, bill_month="2025-05"))
    flow.run(datetime.now(UTC))  # younger than the wait: the consumer may still be sending things
    assert _proposals(young) == []
    flow.run(LATER)
    assert _proposals(over) == [] and [p["kind"] for p in _proposals(young)] == ["explain_correct"]


def test_an_estimated_reading_gets_a_meter_photo_request_approved_in_a_batch(reader, sign_in):
    ticket = chat_complaint(reader, "web", variant(OCT_2025, bill_month="2025-04", present_status="02"))
    flow.run(LATER)
    [made] = _proposals(ticket)
    assert made["kind"] == "request_meter"
    officer = _officer(sign_in)
    result = officer.post("/api/console/proposals/approve", json={"ids": [made["id"], 987654321]}).json()
    assert result["done"] == [made["id"]] and result["skipped"][0]["id"] == 987654321
    assert [r["kind"] for r in review.requests(ticket)] == ["meter_photo"]
    assert complaints.get(ticket).status == "Open"  # asked, not decided


def test_a_bill_complaint_without_a_bill_gets_a_bill_request(sign_in):
    user = f"web:{secrets.token_hex(10)}"
    made_at = (datetime.now(UTC) - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    ticket = complaints.create_general(
        General(user_id=user, discom="TGSPDCL", issue="Bill too high", language="en", channel="web"),
        Placement(section_id=None, unit_id=DISCOM_UNITS["TGSPDCL"]),
        Intake(type="high_bill", priority="normal", due_at=made_at, source="consumer_web"), "My bill is too high",
        created_at=made_at)
    flow.run(datetime.now(UTC))
    assert [p["kind"] for p in _proposals(ticket)] == ["request_bill"]


def test_a_clear_reading_check_is_decided_correct_by_the_ae_who_approves(reader, sign_in, area):
    client = consumer(sign_in)
    bill = upload(client, reader, synthetic("2026-02", 1000.0, 1150.0, section=area.section_a.name, usual=150))
    ticket = report(client, bill["id"])
    flow.run(LATER)
    [made] = _proposals(ticket)
    assert made["kind"] == "decide_correct"
    # An officer without the case permission never sees it.
    officer = _officer(sign_in, area.section_a.id)
    assert officer.post(f"/api/console/proposals/{made['id']}/approve").status_code in (403, 404)
    ae = staff(sign_in, "section_ae", area.section_a.id)
    assert ae.post(f"/api/console/proposals/{made['id']}/approve").status_code == 200
    case = ae.get(f"/api/review/cases/{ticket}").json()
    assert case["decisions"][0]["kind"] == "correct" and complaints.get(ticket).status == "Resolved"


def test_a_proposal_the_complaint_outgrew_does_nothing(reader, sign_in):
    ticket = chat_complaint(reader, "web", variant(OCT_2025, bill_month="2025-03"))
    flow.run(LATER)
    [made] = _proposals(ticket)
    officer = _officer(sign_in)
    officer.post(f"/api/console/complaints/{ticket}/reply", json={"body": "We are looking at your bill now."})
    approved = officer.post(f"/api/console/proposals/{made['id']}/approve").json()
    assert approved["state"] == "stale" and "changed" in approved["note"]
    assert complaints.get(ticket).status == "Open"

    closed = chat_complaint(reader, "web", variant(OCT_2025, bill_month="2025-02"))
    flow.run(LATER)
    complaints.set_status(closed, "Resolved")
    flow.run(LATER)
    assert [p["state"] for p in _proposals(closed)] == ["stale"]


def test_a_rejected_proposal_is_never_offered_again(reader, sign_in):
    ticket = chat_complaint(reader, "web", variant(OCT_2025, bill_month="2025-01"))
    flow.run(LATER)
    [made] = _proposals(ticket)
    officer = _officer(sign_in)
    rejected = officer.post(f"/api/console/proposals/{made['id']}/reject", json={"note": "Caller wants a visit"})
    assert rejected.status_code == 200 and rejected.json()["state"] == "rejected"
    complaints.add_message(ticket, "consumer", None, "any update?", "stored")
    flow.run(LATER)
    assert [p["state"] for p in _proposals(ticket)] == ["rejected"]


def test_only_staff_in_scope_with_the_permission_see_or_act(reader, sign_in, area):
    ticket = chat_complaint(reader, "web", variant(OCT_2025, bill_month="2024-12"))
    flow.run(LATER)
    [made] = _proposals(ticket)
    north = TestClient(app)
    sign_in(north, "officer", "TGNPDCL")
    assert all(p["ticket"] != ticket for p in north.get("/api/console/proposals",
                                                        params={"page_size": 100}).json()["items"])
    assert north.post(f"/api/console/proposals/{made['id']}/approve").status_code == 404
    citizen = consumer(sign_in)
    assert citizen.get("/api/console/proposals").status_code == 403
    assert TestClient(app).get("/api/console/proposals").status_code == 401
    assert store.get(made["id"]).state == "pending"
