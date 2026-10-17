"""Demo review cases: seeded through the real report, upload and decision paths, safe to re-run, removed cleanly,
and refused on a production server. All bills are synthetic (99 service numbers, engine charges)."""

from typing import Any

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.store import db
from app.store import demo as demo_store
from app.tools import demo_complaints, demo_review

CASE_TABLES = ("complaint_messages", "case_requests", "review_decisions", "case_bills", "case_records",
               "case_suggestions", "alerts")


def _seed() -> dict[str, str]:
    counts, review = demo_complaints.seed()
    assert counts
    return {label: ticket for label, ticket in review}


def _case(client: TestClient, ticket: str) -> dict[str, Any]:
    response = client.get(f"/api/review/cases/{ticket}")
    assert response.status_code == 200, response.text
    return response.json()


def _rows(sql: str, *params: object) -> int:
    return int(db.connection().execute(sql, params).fetchone()[0])


def test_seeded_cases_read_as_the_flows_left_them(sign_in):
    tickets = _seed()
    with TestClient(app) as client:
        sign_in(client, "section_ae", "TGSPDCL")
        misread = _case(client, tickets["misread proven by the next bill"])
        assert misread["state"] == "awaiting_review" and misread["spike"]["flagged"]
        assert misread["spike"]["reason"] == "above_normal" and misread["section"] == "Isnapur"
        draft = client.get(f"/api/review/cases/{misread['ticket']}/draft").json()
        assert draft["kind"] == "corrected_reading" and draft["strength"] == "strong"
        assert draft["corrected_present_reading"] == 8592 and draft["preview"]["reduction"] > 0

        estimated = _case(client, tickets["estimated reading"])
        assert estimated["state"] == "awaiting_review" and estimated["bill"]["present_status"] == "05"
        pack = estimated["evidence_pack"]
        assert len(pack["requested_months"]) == 3 and len(pack["received_months"]) == 1
        assert client.get(f"/api/review/cases/{estimated['ticket']}/draft").json() is None

        charges = _case(client, tickets["charges conflict"])
        fixed = next(line for line in charges["audit_lines"] if line["code"] == "fixed")
        assert charges["state"] == "awaiting_review" and fixed["status"] == "over" and fixed["difference"] > 0
        assert charges["can"]["decide"]

        decided = _case(client, tickets["decided, pending update"])
        assert decided["state"] == "decided" and decided["decisions"][0]["revision"] == 1
        assert decided["decisions"][0]["proposed_by"]["name"] == demo_review.STAFF_NAME
        assert any(e["actor"]["name"] == demo_review.STAFF_NAME for e in decided["timeline"])
    with TestClient(app) as client:
        sign_in(client, "billing_approver", "TGSPDCL")
        assert _case(client, decided["ticket"])["can"]["mark_applied"]
    assert _rows("SELECT active FROM accounts WHERE login = ?", demo_review.LOGIN) == 0


def test_reseed_replaces_rather_than_adds():
    _seed()
    _seed()
    assert _rows("SELECT COUNT(*) FROM complaints WHERE demo = 1 AND kind = 'wrong_reading' AND bill_id IS NOT NULL") \
        == 4
    assert _rows("SELECT COUNT(*) FROM accounts WHERE login = ?", demo_review.LOGIN) == 1


def test_remove_leaves_no_demo_review_rows():
    tickets = list(_seed().values())
    assert demo_complaints.main(["remove"]) == 0
    for table in (*CASE_TABLES, "complaints"):
        marks = ", ".join("?" * len(tickets))
        assert _rows(f"SELECT COUNT(*) FROM {table} WHERE ticket IN ({marks})", *tickets) == 0, table
    assert _rows(f"SELECT COUNT(*) FROM audit_log WHERE target IN ({', '.join('?' * len(tickets))})", *tickets) == 0
    assert _rows("SELECT COUNT(*) FROM bills WHERE source = 'demo'") == 0
    assert _rows("SELECT COUNT(*) FROM accounts WHERE login = ?", demo_review.LOGIN) == 0
    assert _rows("SELECT COUNT(*) FROM audit_log WHERE action = ?", demo_store.STAFF_MARK) == 0


def test_review_seed_refused_in_production(monkeypatch):
    demo_complaints.main(["remove"])
    monkeypatch.setattr(get_settings(), "app_env", "production")
    assert demo_complaints.main(["seed"]) == 2
    assert demo_complaints.main(["remove"]) == 2
    assert _rows("SELECT COUNT(*) FROM complaints WHERE demo = 1") == 0
    assert _rows("SELECT COUNT(*) FROM accounts WHERE login = ?", demo_review.LOGIN) == 0
