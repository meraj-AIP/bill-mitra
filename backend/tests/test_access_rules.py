"""Rules from the end to end audit: a reading check closes only through its case, closed cases cannot change,
complaints only go to people who can answer them, and closed work leaves everyone's queue."""

from fastapi.testclient import TestClient

from app.domain.review import Policy
from app.main import app
from app.store import policy as policy_store
from app.store.db import tx
from tests.review_kit import SPIKED, printed, tree
from tests.test_complaint_intake import STAFF_BODY
from tests.test_review import _case, _decide

NOTE = "Line fault on the feeder, please check on site."


def staff(sign_in, role, *scopes):
    client = TestClient(app)
    return client, sign_in(client, role, scopes=list(scopes) or None)


def consumer(sign_in):
    client = TestClient(app)
    return client, sign_in(client).user_id


def raised(client, section_id):
    response = client.post("/api/console/complaints", json={**STAFF_BODY, "section_id": section_id})
    assert response.status_code == 201, response.text
    return response.json()["ticket"]


def test_reading_check_is_never_closed_or_asked_from_the_console(sign_in):
    area = tree()
    officer, _ = staff(sign_in, "officer", area.section_a.id)
    desk, _ = staff(sign_in, "call_centre", area.section_a.id)
    cons, user = consumer(sign_in)
    _, ticket = _case(cons, printed(SPIKED, area.section_a.name), user)
    for client in (officer, desk):
        assert client.post(f"/api/console/complaints/{ticket}/status", json={"status": "Resolved"}).status_code == 409
    assert desk.post(f"/api/console/complaints/{ticket}/request", json={"kind": "meter_photo"}).status_code == 403
    skipped = officer.post("/api/console/complaints/bulk", json={"tickets": [ticket], "status": "Resolved"}).json()
    assert skipped["done"] == [] and "review case" in skipped["skipped"][0]["reason"]
    assert officer.get(f"/api/review/cases/{ticket}").json()["state"] != "applied"


def test_closed_case_decisions_cannot_change_and_closed_cases_are_not_overdue(sign_in):
    area = tree()
    ae, _ = staff(sign_in, "section_ae", area.section_a.id)
    approver, _ = staff(sign_in, "billing_approver", area.section_a.id)
    cons, user = consumer(sign_in)
    _, ticket = _case(cons, printed(SPIKED, area.section_a.name), user)
    policy_store.save(Policy(discom="TGSPDCL", ae_limit=1))
    try:
        held = _decide(ae, ticket, kind="corrected_reading", corrected_present_reading=351).json()
        decision = held["decisions"][0]["id"]
        with tx() as conn:  # a case closed some other way, 30 days old
            conn.execute("UPDATE complaints SET status = 'Rejected', created_at = datetime('now', '-30 days') "
                         "WHERE ticket = ?", (ticket,))
        case = approver.get(f"/api/review/cases/{ticket}").json()
        assert case["can"]["approve"] is False and case["overdue"] is False
        assert approver.post(f"/api/review/decisions/{decision}/approve", json={}).status_code == 409
        assert approver.post(f"/api/review/decisions/{decision}/withdraw").status_code == 409
        overdue = approver.get("/api/review/cases", params={"overdue": True, "page_size": 50}).json()
        assert ticket not in [row["ticket"] for row in overdue["items"]]
    finally:
        policy_store.save(Policy(discom="TGSPDCL"))


def test_complaints_go_only_to_people_who_can_answer_them(sign_in):
    area = tree()
    desk, _ = staff(sign_in, "call_centre", area.section_a.id)
    _, auditor = staff(sign_in, "auditor", area.section_a.id)
    admin, _ = staff(sign_in, "admin")
    ticket = raised(desk, area.section_a.id)
    url = f"/api/console/complaints/{ticket}"
    assert auditor.id not in [p["id"] for p in admin.get(url).json()["assignable"]]
    assert admin.post(f"{url}/assign", json={"account_id": auditor.id, "note": NOTE}).status_code == 400


def test_with_me_lists_open_work_only(sign_in):
    area = tree()
    desk, _ = staff(sign_in, "call_centre", area.section_a.id)
    ae, ae_account = staff(sign_in, "section_ae", area.section_a.id)
    ticket = raised(desk, area.section_a.id)
    url = f"/api/console/complaints/{ticket}"
    # A complaint raised in a section is routed to its AE, so the AE already holds it.
    assert ae.get(url).json()["assignee"]["id"] == ae_account.id
    mine = lambda: [r["ticket"] for r in ae.get("/api/console/complaints", params={"with_me": True, "page_size": 50}).json()["items"]]  # noqa: E731
    assert ticket in mine()
    ae.post(f"{url}/status", json={"status": "Resolved"})
    assert ticket not in mine()
