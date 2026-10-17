"""The hand-off journey: routing to the section AE, handing over with a note, sending back, the alerts that follow,
the inbox filters, and the consumer answering a request with a photo. Logins, notes and photos are synthetic."""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.domain.review import Policy
from app.main import app
from app.store import complaints as store
from app.store import policy as policy_store
from app.store.db import DISCOM_UNITS, tx
from tests.review_kit import SPIKED, Tree, printed, tree
from tests.test_complaint_intake import STAFF_BODY
from tests.test_review import _case, _decide, south_policy  # noqa: F401  (a fixture, used by name)

NOTE = "Line fault on the feeder, please check on site."
BACK = "Supply restored here, nothing more for the section."
JPEG = b"\xff\xd8\xff\xe0" + b"synthetic meter photo"


@pytest.fixture
def area() -> Tree:
    return tree()


def staff(sign_in, role: str, *scopes: str):
    client = TestClient(app)
    return client, sign_in(client, role, scopes=list(scopes) or None)


def alerts(client: TestClient, ticket: str, kind: str) -> list[dict]:
    items = client.get("/api/alerts", params={"page_size": 100}).json()["items"]
    return [a for a in items if a["ticket"] == ticket and a["kind"] == kind]


def raised(client: TestClient, section_id: str) -> dict:
    made = client.post("/api/console/complaints", json={**STAFF_BODY, "section_id": section_id})
    assert made.status_code == 201, made.text
    return made.json()


def test_a_section_complaint_goes_to_its_ae_with_a_timeline_line_and_one_alert(sign_in, area):
    agent, _ = staff(sign_in, "call_centre", area.section_a.id)
    ae, ae_account = staff(sign_in, "section_ae", area.section_a.id)
    made = raised(agent, area.section_a.id)
    assert made["assignee"] == {"id": ae_account.id, "name": ae_account.name}
    assert made["handoff"] == {"by": None, "note": None, "at": None} and made["waiting_on"] == "staff"
    assert any(e["text"] == f"Routed to {ae_account.name}" and e["actor"]["kind"] == "system"
               for e in made["timeline"])
    assert [a["href"] for a in alerts(ae, made["ticket"], "complaint_assigned")] == \
        [f"/console/complaints/{made['ticket']}"]


def test_hand_over_follows_the_rules_per_role_and_sends_back_to_the_giver(sign_in, area):
    agent, cc = staff(sign_in, "call_centre", area.section_a.id)
    ae, first = staff(sign_in, "section_ae", area.section_a.id)
    other, second = staff(sign_in, "section_ae", area.subdivision.id)
    lead, officer = staff(sign_in, "officer", area.division.id)
    watcher, _ = staff(sign_in, "auditor", area.division.id)
    ticket = raised(agent, area.section_a.id)["ticket"]
    url = f"/api/console/complaints/{ticket}"

    offered = {p["id"] for p in agent.get(url).json()["assignable"]}
    assert second.id in offered and not offered & {officer.id, cc.id, first.id}  # desk staff hand to an AE only
    assert agent.post(f"{url}/assign", json={"account_id": officer.id, "note": NOTE}).status_code == 400
    assert agent.post(f"{url}/assign", json={"account_id": second.id, "note": "too short"}).status_code == 422
    assert watcher.post(f"{url}/assign", json={"account_id": second.id, "note": NOTE}).status_code == 403
    done = agent.post(f"{url}/assign", json={"account_id": second.id, "note": NOTE}).json()
    assert done["assignee"]["id"] == second.id and done["can_return"] is False
    assert done["handoff"]["by"] == {"id": cc.id, "name": cc.name} and done["handoff"]["note"] == NOTE
    assert done["timeline"][-1] == {"at": done["timeline"][-1]["at"], "actor": {"kind": "staff", "name": cc.name},
                                    "text": f"Handed to {second.name}: {NOTE}"}

    held = other.get(url).json()
    assert held["can_return"] is True and {officer.id, cc.id, first.id} <= {p["id"] for p in held["assignable"]}
    assert lead.post(f"{url}/return", json={"note": BACK}).status_code == 409  # only the holder sends it back
    back = other.post(f"{url}/return", json={"note": BACK}).json()
    assert back["assignee"]["id"] == cc.id and back["handoff"]["by"]["id"] == second.id
    assert back["timeline"][-1]["text"] == f"Sent back to {cc.name}: {BACK}"
    assert len(alerts(other, ticket, "complaint_assigned")) == 1
    assert [a["title"] for a in alerts(agent, ticket, "complaint_assigned")] == ["Complaint sent back to you"]

    admin, _ = staff(sign_in, "admin")
    moved = admin.post(f"{url}/assign", json={"account_id": officer.id, "note": NOTE})
    assert moved.status_code == 200 and moved.json()["assignee"]["id"] == officer.id  # admin: anyone in scope
    store.set_status(ticket, "Resolved")
    assert lead.post(f"{url}/assign", json={"account_id": second.id, "note": NOTE}).status_code == 409


def test_with_me_and_waiting_on_me_filters(sign_in, area):
    agent, _ = staff(sign_in, "call_centre", area.section_a.id)
    ae, ae_account = staff(sign_in, "section_ae", area.section_a.id)
    lead, _ = staff(sign_in, "officer", area.division.id)
    ticket = raised(agent, area.section_a.id)["ticket"]

    def listed(client: TestClient, **query: object) -> list[str]:
        return [r["ticket"] for r in client.get("/api/console/complaints", params={"page_size": 50, **query})
                .json()["items"]]

    assert ticket in listed(ae, with_me=True) and ticket in listed(ae, waiting_on_me=True)
    row = next(r for r in lead.get("/api/console/complaints", params={"page_size": 50}).json()["items"]
               if r["ticket"] == ticket)
    assert row["assignee_name"] == ae_account.name and row["waiting_on"] == "staff"
    assert ticket not in listed(lead, with_me=True) and ticket in listed(lead)
    asked = ae.post(f"/api/console/complaints/{ticket}/request", json={"kind": "details"}).json()
    assert asked["waiting_on"] == "consumer" and asked["requests"][0]["answer"] is None
    assert ticket in listed(ae, with_me=True) and ticket not in listed(ae, waiting_on_me=True)
    assert ae.get("/api/console/complaints", params={"with_me": "maybe"}).status_code == 422


def photo(client: TestClient, ticket: str, name: str = "m.jpg", data: bytes = JPEG, mime: str = "image/jpeg"):
    return client.post(f"/api/complaints/{ticket}/photo", params={"language": "en"},
                       files={"file": (name, data, mime)})


def asked(sign_in) -> tuple[TestClient, TestClient, str]:
    """A consumer's web complaint, handed by an officer to an AE who asked for a meter photo."""
    consumer, _ = staff(sign_in, "consumer")
    lead, _ = staff(sign_in, "officer")
    ae, ae_account = staff(sign_in, "section_ae", DISCOM_UNITS["TGSPDCL"])
    ticket = consumer.post("/api/complaints", json={"type": "high_bill", "discom": "TGSPDCL",
                                                    "description": "Bill doubled this month."}).json()["ticket"]
    assert photo(consumer, ticket).status_code == 409  # nothing asked yet
    lead.post(f"/api/console/complaints/{ticket}/assign", json={"account_id": ae_account.id, "note": NOTE})
    ae.post(f"/api/console/complaints/{ticket}/request", json={"kind": "meter_photo"})
    return consumer, ae, ticket


def test_consumer_photo_answers_the_request_and_only_the_right_people_open_it(sign_in):
    consumer, ae, ticket = asked(sign_in)
    stranger, _ = staff(sign_in, "consumer")
    north, _ = staff(sign_in, "officer", DISCOM_UNITS["TGNPDCL"])
    url = f"/api/console/complaints/{ticket}"
    sent = photo(consumer, ticket)
    assert sent.status_code == 200, sent.text
    mine = sent.json()["messages"][-1]
    assert mine["from"] == "you" and mine["body"] == "Photo sent" and mine["media_type"] == "image/jpeg"
    assert consumer.get(mine["media_url"]).content == JPEG
    assert stranger.get(mine["media_url"]).status_code == 404

    seen = ae.get(url).json()
    request, last = seen["requests"][0], seen["messages"][-1]
    assert request["status"] == "answered" and request["answer"]["body"] is None and seen["waiting_on"] == "staff"
    assert request["answer"]["message_id"] == last["id"] and request["answer"]["media_url"] == last["media_url"]
    assert last["media_url"].startswith(f"{url}/media/") and ae.get(last["media_url"]).content == JPEG
    assert north.get(last["media_url"]).status_code == 404  # out of scope
    assert consumer.get(last["media_url"]).status_code == 403  # a staff route
    assert ae.get(f"{url}/media/{'0' * 24}.jpg").status_code == 404
    assert store.add_message(ticket, "consumer", None, "One more thing.", "stored") is not None
    replied = alerts(ae, ticket, "consumer_replied")  # once per staff turn, opening the complaint
    assert [a["href"] for a in replied] == [f"/console/complaints/{ticket}"]


def test_photo_upload_is_checked_and_nothing_reaches_a_closed_complaint(sign_in, monkeypatch):
    consumer, ae, ticket = asked(sign_in)
    assert photo(consumer, ticket, "x.gif", b"GIF89a-synthetic", "image/gif").status_code == 415
    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)
    assert photo(consumer, ticket).status_code == 413
    ae.post(f"/api/console/complaints/{ticket}/status", json={"status": "Resolved"})
    assert store.add_message(ticket, "consumer", None, "Late reply.", "stored") is None
    assert consumer.post(f"/api/complaints/{ticket}/reply", json={"body": "Late reply."}).status_code == 409
    with tx() as conn:
        late = conn.execute("SELECT COUNT(*) FROM complaint_messages WHERE ticket = ? AND body = 'Late reply.'",
                            (ticket,)).fetchone()[0]
    assert late == 0


@pytest.mark.usefixtures("south_policy")
def test_review_cases_alert_on_routing_reassignment_reply_and_a_returned_decision(sign_in, area):
    ae, first = staff(sign_in, "section_ae", area.section_a.id)
    other, second = staff(sign_in, "section_ae", area.section_a.id)
    lead, _ = staff(sign_in, "officer", area.division.id)
    approver, _ = staff(sign_in, "billing_approver", area.division.id)
    consumer, owner = staff(sign_in, "consumer")
    _, ticket = _case(consumer, printed(SPIKED, area.section_a.name), owner.user_id)
    holder = lead.get(f"/api/review/cases/{ticket}").json()["assignee"]["id"]
    deciders = {first.id: ae, second.id: other}
    spare_id = next(i for i in deciders if i != holder)
    spare = deciders[spare_id]
    assert [a["title"] for a in alerts(deciders[holder], ticket, "case_assigned")] == ["New case for you"]

    lead.post(f"/api/review/cases/{ticket}/assign", json={"account_id": spare_id})
    assert len(alerts(spare, ticket, "case_assigned")) == 1
    store.add_message(ticket, "consumer", None, "The meter shows a lower number.", "stored")
    assert [a["href"] for a in alerts(spare, ticket, "consumer_replied")] == [f"/review/{ticket}"]

    policy_store.save(Policy(discom="TGSPDCL", ae_limit=10))
    held = _decide(spare, ticket, kind="corrected_reading", corrected_present_reading=351).json()
    approver.post(f"/api/review/decisions/{held['decisions'][0]['id']}/reject", json={"note": "Ask for a meter photo"})
    assert [a["kind"] for a in alerts(spare, ticket, "decision_returned")] == ["decision_returned"]


def test_a_complaint_in_the_discom_queue_can_be_handed_to_a_section_ae_which_places_it(sign_in, area):
    consumer = TestClient(app)
    sign_in(consumer, "consumer")
    made = consumer.post("/api/complaints?language=en", json={"type": "high_bill", "discom": area.discom,
                                                              "description": "Bill doubled this month, please check."})
    assert made.status_code == 201, made.text
    ticket = made.json()["ticket"]
    lead, _ = staff(sign_in, "officer", DISCOM_UNITS[area.discom])
    ae, ae_account = staff(sign_in, "section_ae", area.section_a.id)
    url = f"/api/console/complaints/{ticket}"
    offered = {p["id"]: p["name"] for p in lead.get(url).json()["assignable"]}
    assert ae_account.id in offered and area.section_a.name in offered[ae_account.id]
    done = lead.post(f"{url}/assign", json={"account_id": ae_account.id, "note": NOTE})
    assert done.status_code == 200, done.text
    assert done.json()["assignee"]["id"] == ae_account.id and done.json()["section"] == area.section_a.name
    assert ae.get(url).status_code == 200  # the AE's scope now covers it
    assert alerts(ae, ticket, "complaint_assigned")


def test_a_consumer_answer_keeps_their_complaint_in_progress(sign_in, area):
    consumer = TestClient(app)
    sign_in(consumer, "consumer")
    ticket = consumer.post("/api/complaints?language=en", json={"type": "high_bill", "discom": area.discom,
                                                                "description": "Bill doubled this month."}).json()["ticket"]
    assert consumer.get(f"/api/complaints/{ticket}").json()["status"] == "received"
    lead, _ = staff(sign_in, "officer", DISCOM_UNITS[area.discom])
    assert lead.post(f"/api/console/complaints/{ticket}/request", json={"kind": "meter_photo"}).status_code == 200
    assert consumer.get(f"/api/complaints/{ticket}").json()["status"] == "waiting_for_you"
    sent = consumer.post(f"/api/complaints/{ticket}/photo", files={"file": ("meter.jpg", JPEG, "image/jpeg")})
    assert sent.status_code in (200, 201), sent.text
    assert consumer.get(f"/api/complaints/{ticket}").json()["status"] == "in_progress"
