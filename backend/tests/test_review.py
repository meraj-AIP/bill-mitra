"""AE bill review end to end: spike rules, routing, scope, decisions priced by the engine, approvals, revisions,
what the consumer sees, unmasking, the CSV and the audit trail.

Bills are real fixtures from tests/real.py or labelled variants of them (tests/review_kit.py). Logins are fake.
"""

import asyncio
import csv
import io
import secrets
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core import service
from app.core.messages import Inbound
from app.core.trace import Event
from app.domain import review
from app.domain.conversation.facts import rs
from app.domain.prediction import MonthUsage
from app.domain.pricing import price
from app.domain.review import Policy
from app.main import app
from app.store import complaints as complaint_store
from app.store import media, repos
from app.store import policy as policy_store
from app.store.db import tx
from tests.real import OCT_2025, PLACEHOLDER_USC, reading, variant
from tests.review_kit import NORMAL, SPIKED, Tree, printed, tree
from tests.test_complaints import WA_NUMBER

NOTE = "Meter photo shows 351, the reader keyed 693 by mistake."


def _history(bill) -> list[MonthUsage]:
    return [MonthUsage(month=p.month, units=p.units, amount=0.0) for p in bill.usage_history]


def test_spike_flags_a_jump_and_a_meter_going_back_but_not_a_normal_month():
    policy = Policy(discom="TGSPDCL")
    spiked = review.detect(SPIKED, price(SPIKED, SPIKED.net_units()), _history(SPIKED), policy)
    assert spiked.flagged and spiked.reason == "above_normal" and spiked.months_used == 4
    assert spiked.median_units == 136.5 and spiked.ratio == round(480 / 136.5, 2)
    assert spiked.usual_amount == price(SPIKED, 136).net or spiked.usual_amount == price(SPIKED, 137).net
    normal = review.detect(NORMAL, price(NORMAL, 138), _history(NORMAL), policy)
    assert not normal.flagged and normal.reason is None
    short = review.detect(SPIKED, price(SPIKED, 480), _history(SPIKED)[:2], policy)
    assert not short.flagged  # two months of history are not enough to call it unusual
    # Variant: present reading printed below the previous one.
    back = variant(OCT_2025, present_reading=200.0)
    assert review.detect(back, price(back, 138), [], policy).reason == "reading_went_back"


@pytest.fixture
def south_policy() -> Iterator[None]:
    """Tests that change the policy put the owner's defaults back."""
    yield
    policy_store.save(Policy(discom="TGSPDCL"))


def _case(client: TestClient, bill, user_id: str, language: str = "en") -> tuple[str, str]:
    bill_id = repos.save_bill(user_id, bill, media.save(b"synthetic-photo", "image/jpeg"), "mismatch", 0.0)
    response = client.post(f"/api/bills/{bill_id}/review-request", params={"language": language}, json={})
    assert response.status_code == 200, response.text
    return bill_id, response.json()["ticket"]


def _consumer(sign_in) -> tuple[TestClient, str]:
    client = TestClient(app)
    account = sign_in(client)
    return client, account.user_id


def _staff(sign_in, role: str, *scopes: str) -> tuple[TestClient, str]:
    client = TestClient(app)
    return client, sign_in(client, role, scopes=list(scopes) or None).id


def _decide(client: TestClient, ticket: str, **body) -> dict:
    detail = client.get(f"/api/review/cases/{ticket}").json()
    evidence = [{"kind": "message", "id": str(detail["messages"][0]["id"])}]
    payload = {"reason_code": "photo_misread", "note": NOTE, "evidence": evidence, **body}
    return client.post(f"/api/review/cases/{ticket}/decisions", json=payload)


@pytest.fixture
def area() -> Tree:
    return tree()


def test_routing_balances_aes_and_falls_back_to_the_division(sign_in, area):
    ae_one, ae_one_id = _staff(sign_in, "section_ae", area.section_a.id)
    _, ae_two_id = _staff(sign_in, "section_ae", area.section_a.id)
    division, _ = _staff(sign_in, "officer", area.division.id)
    consumer, user = _consumer(sign_in)
    _, first = _case(consumer, printed(SPIKED, area.section_a.name), user)
    _, second = _case(consumer, printed(variant(SPIKED, bill_month="2025-11"), area.section_a.name), user)
    _, orphan = _case(consumer, printed(variant(SPIKED, bill_month="2025-12"), area.section_b.name), user)
    assigned = {t: ae_one.get(f"/api/review/cases/{t}").json()["assignee"] for t in (first, second)}
    assert {assigned[first]["id"], assigned[second]["id"]} == {ae_one_id, ae_two_id}
    assert ae_one.get(f"/api/review/cases/{orphan}").status_code == 404  # section B is not theirs
    row = division.get(f"/api/review/cases/{orphan}").json()
    assert row["assignee"] is None and row["section"] == area.section_b.name and row["state"] == "awaiting_review"
    listed = division.get("/api/review/cases", params={"page_size": 50}).json()
    assert {first, second, orphan} <= {r["ticket"] for r in listed["items"]}
    mine = ae_one.get("/api/review/cases", params={"mine": True, "page_size": 50}).json()["items"]
    assert [r["assignee"]["id"] for r in mine] == [ae_one_id] * len(mine) and len(mine) == 1


def test_ero_approver_sees_only_sections_billed_by_the_ero(sign_in, area):
    approver, _ = _staff(sign_in, "billing_approver", area.ero.id)
    consumer, user = _consumer(sign_in)
    _, in_ero = _case(consumer, printed(SPIKED, area.section_a.name), user)
    _, outside = _case(consumer, printed(variant(SPIKED, bill_month="2025-11"), area.section_b.name), user)
    assert approver.get(f"/api/review/cases/{in_ero}").status_code == 200
    assert approver.get(f"/api/review/cases/{outside}").status_code == 404


def test_unmapped_section_case_moves_once_the_name_is_mapped(sign_in, area):
    _, ae_id = _staff(sign_in, "section_ae", area.section_b.id)
    admin, _ = _staff(sign_in, "super_admin")
    consumer, user = _consumer(sign_in)
    old_name = f"Gandhi Nagar {area.tag}"
    _, ticket = _case(consumer, printed(SPIKED, old_name), user)
    first = admin.get(f"/api/review/cases/{ticket}")
    assert first.status_code == 200, first.text
    assert first.json()["assignee"] is None
    assert old_name in {u["name"] for u in admin.get("/api/admin/units/unmapped").json()}
    admin.post("/api/admin/units/unmapped/map", json={"name": old_name, "discom": "TGSPDCL",
                                                      "section_id": area.section_b.id})
    assert admin.get(f"/api/review/cases/{ticket}").json()["assignee"]["id"] == ae_id


def test_corrected_reading_is_priced_by_the_engine_and_the_consumer_is_told(sign_in, area):
    ae, _ = _staff(sign_in, "section_ae", area.section_a.id)
    consumer, user = _consumer(sign_in)
    bill = printed(SPIKED, area.section_a.name)
    bill_id, ticket = _case(consumer, bill, user)
    # Correcting the misread reading back to the real 351 must give back the real printed bill, to the paisa:
    # only the tariff lines change, the Rs 25 surcharge and the other printed lines stay.
    expected = OCT_2025.bill_amount
    preview = ae.post(f"/api/review/cases/{ticket}/preview", json={"corrected_present_reading": 351}).json()
    assert preview == {"corrected_units": 138, "revised_amount": expected,
                       "reduction": round(bill.bill_amount - expected, 2), "needs_approval": False}
    assert ae.post(f"/api/review/cases/{ticket}/preview", json={"corrected_present_reading": 100}).status_code == 400

    short = _decide(ae, ticket, kind="corrected_reading", corrected_present_reading=351, note="too short")
    assert short.status_code == 422
    no_evidence = ae.post(f"/api/review/cases/{ticket}/decisions", json={
        "kind": "corrected_reading", "corrected_present_reading": 351, "reason_code": "photo_misread", "note": NOTE,
        "evidence": []})
    assert no_evidence.status_code == 422
    foreign = ae.post(f"/api/review/cases/{ticket}/decisions", json={
        "kind": "corrected_reading", "corrected_present_reading": 351, "reason_code": "photo_misread", "note": NOTE,
        "evidence": [{"kind": "message", "id": "999999"}]})
    assert foreign.status_code == 400

    detail = _decide(ae, ticket, kind="corrected_reading", corrected_present_reading=351).json()
    decision = detail["decisions"][0]
    assert decision["status"] == "approved" and decision["revision"] == 1 and decision["revised_amount"] == expected
    assert decision["evidence"][0]["label"].startswith("Consumer message")
    assert detail["state"] == "decided" and detail["messages"][-1]["author_kind"] == "system"
    assert "revision 1" in detail["messages"][-1]["body"]

    summary = consumer.get(f"/api/bills/{bill_id}", params={"language": "en"}).json()["review"]
    assert summary["state"] == "revised" and summary["revision"]["status"] == "pending_update"
    assert summary["revision"]["revised_amount"] == expected
    assert summary["revision"]["reason"] == "The meter photo was misread"
    assert consumer.post(f"/api/bills/{bill_id}/review-request", json={}).status_code == 409


def test_custom_reduction_and_policy_limits_force_approval(sign_in, area, south_policy):
    ae, ae_id = _staff(sign_in, "section_ae", area.section_a.id)
    approver, _ = _staff(sign_in, "billing_approver", area.division.id)
    consumer, user = _consumer(sign_in)
    _, custom = _case(consumer, printed(SPIKED, area.section_a.name), user)
    done = _decide(ae, custom, kind="custom", reduction=100).json()["decisions"][0]
    assert done["status"] == "approved" and done["revised_amount"] == SPIKED.bill_amount - 100
    _, too_much = _case(consumer, printed(variant(SPIKED, bill_month="2025-11"), area.section_a.name), user)
    assert _decide(ae, too_much, kind="custom", reduction=SPIKED.bill_amount + 1).status_code == 400

    policy_store.save(Policy(discom="TGSPDCL", ae_limit=10, custom_needs_approval=True))
    held = _decide(ae, too_much, kind="corrected_reading", corrected_present_reading=351).json()
    assert held["state"] == "awaiting_approval" and held["decisions"][0]["revision"] is None
    assert _decide(ae, too_much, kind="custom", reduction=5).status_code == 409  # one decision at a time
    decision_id = held["decisions"][0]["id"]
    rejected = approver.post(f"/api/review/decisions/{decision_id}/reject", json={"note": "Ask for a meter photo"})
    assert rejected.json()["state"] == "rejected"
    again = _decide(ae, too_much, kind="custom", reduction=5).json()
    assert again["state"] == "awaiting_approval"  # custom_needs_approval is on
    assert again["can"]["approve"] is False  # the AE cannot approve
    approved = approver.post(f"/api/review/decisions/{again['decisions'][0]['id']}/approve", json={}).json()
    assert approved["state"] == "decided" and approved["decisions"][0]["decided_by"]["id"] != ae_id


def test_nobody_approves_or_applies_their_own_decision(sign_in, area, south_policy):
    admin, _ = _staff(sign_in, "super_admin")
    both = admin.post("/api/admin/roles", json={"name": f"Decide and approve {area.tag}",
                                                "permissions": ["cases.view", "cases.decide", "cases.approve",
                                                                "cases.mark_applied"]}).json()
    one, _ = _staff(sign_in, both["slug"], area.section_a.id)
    consumer, user = _consumer(sign_in)
    _, ticket = _case(consumer, printed(SPIKED, area.section_a.name), user)
    policy_store.save(Policy(discom="TGSPDCL", ae_limit=1))
    held = _decide(one, ticket, kind="corrected_reading", corrected_present_reading=351).json()
    decision_id = held["decisions"][0]["id"]
    assert held["can"]["approve"] is False
    assert one.post(f"/api/review/decisions/{decision_id}/approve", json={}).status_code == 403
    # The super admin manages roles and never moves money.
    assert admin.post(f"/api/review/decisions/{decision_id}/approve", json={}).status_code == 403
    assert _decide(admin, ticket, kind="correct").status_code == 403


def test_withdraw_before_applied_then_revisions_count_up(sign_in, area):
    ae, _ = _staff(sign_in, "section_ae", area.section_a.id)
    approver, _ = _staff(sign_in, "billing_approver", area.section_a.id)
    consumer, user = _consumer(sign_in)
    bill = printed(SPIKED, area.section_a.name)
    bill_id, ticket = _case(consumer, bill, user)
    first = _decide(ae, ticket, kind="custom", reduction=50).json()["decisions"][0]
    withdrawn = ae.post(f"/api/review/decisions/{first['id']}/withdraw").json()
    assert withdrawn["state"] == "awaiting_review" and withdrawn["decisions"][0]["status"] == "withdrawn"

    second = _decide(ae, ticket, kind="custom", reduction=60).json()["decisions"][0]
    assert second["revision"] == 2  # numbers are never reused, even after a withdrawal
    assert ae.post(f"/api/review/decisions/{second['id']}/applied", json={"billing_ref": "X1"}).status_code == 403
    applied = approver.post(f"/api/review/decisions/{second['id']}/applied", json={"billing_ref": "=1+1"}).json()
    assert applied["state"] == "applied" and applied["decisions"][0]["billing_ref"] == "=1+1"
    assert ae.post(f"/api/review/decisions/{second['id']}/withdraw").status_code == 409
    # The printed amount less the Rs 60 the AE typed, told on the consumer's channel.
    assert f"Rs {rs(SPIKED.bill_amount - 60)}" in applied["messages"][-1]["body"]

    summary = consumer.get(f"/api/bills/{bill_id}", params={"language": "en"}).json()["review"]
    assert summary["state"] == "revised" and summary["revision"]["status"] == "applied"

    exporter, _ = _staff(sign_in, "billing_approver", area.section_a.id)
    sheet = exporter.get("/api/review/revisions.csv", params={"ero_id": area.ero.id})
    rows = [r for r in csv.DictReader(io.StringIO(sheet.text)) if r["ticket"] == ticket]
    assert rows and rows[0]["billing_ref"] == "'=1+1" and rows[0]["revision"] == "2"
    assert PLACEHOLDER_USC not in sheet.text
    assert exporter.get("/api/review/revisions.csv", params={"from": "2025/01/01"}).status_code == 422
    outsider, _ = _staff(sign_in, "billing_approver", area.section_b.id)
    assert ticket not in outsider.get("/api/review/revisions.csv").text


def test_unmask_needs_the_permission_and_is_audited(sign_in, area):
    ae, ae_id = _staff(sign_in, "section_ae", area.section_a.id)
    officer, _ = _staff(sign_in, "officer", area.division.id)
    auditor, _ = _staff(sign_in, "auditor", area.division.id)
    consumer, user = _consumer(sign_in)
    _, ticket = _case(consumer, printed(SPIKED, area.section_a.name), user)
    assert officer.post(f"/api/review/cases/{ticket}/unmask").status_code == 403
    assert ae.post(f"/api/review/cases/{ticket}/unmask").json() == {"service_number": PLACEHOLDER_USC}
    log = auditor.get("/api/admin/audit", params={"action": "case.unmask", "page_size": 50}).json()["items"]
    assert any(e["actor_id"] == ae_id and e["target"] == ticket for e in log)
    assert ae.get(f"/api/review/cases/{ticket}").json()["service_masked"].endswith("1111")


def test_info_request_reuses_the_complaint_thread(sign_in, area):
    ae, _ = _staff(sign_in, "section_ae", area.section_a.id)
    consumer, user = _consumer(sign_in)
    _, ticket = _case(consumer, printed(SPIKED, area.section_a.name), user)
    asked = ae.post(f"/api/review/cases/{ticket}/request", json={"kind": "earlier_bills", "note": "Two will do."})
    body = asked.json()
    assert body["state"] == "info_requested" and body["requests"][0]["status"] == "open"
    assert "last two or three bills" in body["messages"][-1]["body"]
    asyncio.run(service.handle(Inbound(channel="web", user_id=user, kind="text", text="Sent them by post"),
                               _ignore, language="en"))
    after = ae.get(f"/api/review/cases/{ticket}").json()
    assert after["state"] == "awaiting_review" and after["requests"][0]["status"] == "answered"
    assert after["messages"][-1]["body"] == "Sent them by post"
    note_evidence = [{"kind": "note", "id": str(after["requests"][0]["id"])}]
    decided = ae.post(f"/api/review/cases/{ticket}/decisions", json={
        "kind": "correct", "reason_code": "bill_correct", "note": "Earlier bills show the same use pattern.",
        "evidence": note_evidence}).json()
    assert decided["state"] == "decided" and complaint_store.get(ticket).status == "Resolved"
    assert "the reading is correct" in decided["messages"][-1]["body"]


async def _ignore(_: Event) -> None:
    return None


def test_flagged_bill_in_chat_offers_the_report_button(reader, area, sign_in):
    _, ae_id = _staff(sign_in, "section_ae", area.section_a.id)
    officer, _ = _staff(sign_in, "officer", area.division.id)
    user = f"wa:{secrets.token_hex(10)}"
    sent: list[dict] = []

    async def keep(event: Event) -> None:
        if event.kind == "message" and event.message is not None:
            sent.append(event.message.model_dump())

    def say(**fields) -> None:
        inbound = Inbound(channel="whatsapp", user_id=user, reply_to=WA_NUMBER, **fields)
        asyncio.run(service.handle(inbound, keep, language="en"))

    reader(reading(printed(SPIKED, area.section_a.name)))
    say(kind="image", media_id=media.save(b"synthetic-photo", "image/jpeg"), mime_type="image/jpeg")
    offers = [m for m in sent if m["type"] == "buttons" and m["buttons"][0]["id"] == "report_bill"]
    assert len(offers) == 1 and "480 units" in offers[0]["body"] and len(offers[0]["buttons"]) == 1
    assert len(offers[0]["buttons"][0]["title"]) <= 20
    say(kind="button_reply", reply_id="report_bill")
    filed = sent[-1]["body"]
    ticket = filed.split("report ")[1].split(" ")[0]
    row = officer.get(f"/api/review/cases/{ticket}").json()
    assert row["channel"] == "whatsapp" and row["assignee"]["id"] == ae_id and row["units"] == 480
    say(kind="button_reply", reply_id="report_bill")
    assert ticket in sent[-1]["body"] and "already being checked" in sent[-1]["body"]

    sent.clear()
    reader(reading(printed(NORMAL, area.section_a.name)))
    say(kind="image", media_id=media.save(b"synthetic-photo-2", "image/jpeg"), mime_type="image/jpeg")
    assert not [m for m in sent if m["type"] == "buttons" and m["buttons"][0]["id"] == "report_bill"]


def test_overdue_follows_the_policy_sla(sign_in, area):
    officer, _ = _staff(sign_in, "officer", area.division.id)
    consumer, user = _consumer(sign_in)
    _, ticket = _case(consumer, printed(SPIKED, area.section_a.name), user)
    assert officer.get(f"/api/review/cases/{ticket}").json()["overdue"] is False
    with tx() as conn:  # test-only backdating past the default 3 day SLA
        conn.execute("UPDATE complaints SET created_at = datetime('now', '-5 days') WHERE ticket = ?", (ticket,))
    row = officer.get(f"/api/review/cases/{ticket}").json()
    assert row["overdue"] is True and row["days_open"] == 5
    overdue = officer.get("/api/review/cases", params={"overdue": True, "page_size": 50}).json()["items"]
    assert ticket in {r["ticket"] for r in overdue}


def test_audit_details_never_hold_a_service_number_or_phone(sign_in):
    with tx() as conn:
        details = [r[0] or "" for r in conn.execute("SELECT detail FROM audit_log")]
    assert details and not any(PLACEHOLDER_USC in d or WA_NUMBER in d or WA_NUMBER[2:] in d for d in details)


def test_policy_is_per_discom_and_scoped(sign_in, south_policy):
    owner, _ = _staff(sign_in, "super_admin")
    policies = owner.get("/api/admin/policy").json()
    assert [p["discom"] for p in policies] == ["TGSPDCL", "TGNPDCL"]
    assert policies[0]["ae_limit"] is None and policies[0]["custom_needs_approval"] is False
    saved = owner.put("/api/admin/policy/TGSPDCL", json={"ae_limit": 2500, "decision_sla_days": 5}).json()
    assert saved["ae_limit"] == 2500 and saved["decision_sla_days"] == 5 and saved["spike_ratio"] == 2.0
    assert owner.put("/api/admin/policy/TGSPDCL", json={"spike_ratio": 0.5}).status_code == 422
    south_only, _ = _staff(sign_in, "super_admin", "u_tgspdcl")
    assert south_only.put("/api/admin/policy/TGNPDCL", json={}).status_code == 403
    officer, _ = _staff(sign_in, "officer")
    assert officer.get("/api/admin/policy").status_code == 403


def test_reassign_within_scope_only(sign_in, area):
    officer, _ = _staff(sign_in, "officer", area.division.id)
    _, ae_a = _staff(sign_in, "section_ae", area.section_a.id)
    _, ae_b = _staff(sign_in, "section_ae", area.section_b.id)
    consumer, user = _consumer(sign_in)
    _, ticket = _case(consumer, printed(SPIKED, area.section_b.name), user)
    detail = officer.get(f"/api/review/cases/{ticket}").json()
    assert {p["id"] for p in detail["assignable"]} >= {ae_b} and ae_a not in {p["id"] for p in detail["assignable"]}
    assert officer.post(f"/api/review/cases/{ticket}/assign", json={"account_id": ae_a}).status_code == 400
    moved = officer.post(f"/api/review/cases/{ticket}/assign", json={"account_id": ae_b}).json()
    assert moved["assignee"]["id"] == ae_b
    log = officer.get("/api/admin/audit").status_code
    assert log == 403  # officers do not read the audit log


def test_withdrawing_an_announced_revision_tells_the_consumer(sign_in, area):
    ae, _ = _staff(sign_in, "section_ae", area.section_a.id)
    consumer, user = _consumer(sign_in)
    _, ticket = _case(consumer, printed(SPIKED, area.section_a.name), user)
    decision = _decide(ae, ticket, kind="corrected_reading", corrected_present_reading=351).json()["decisions"][0]
    detail = ae.post(f"/api/review/decisions/{decision['id']}/withdraw").json()
    assert detail["state"] != "decided"
    assert "withdrawn" in detail["messages"][-1]["body"] and f"Rs {rs(SPIKED.bill_amount)}" in detail["messages"][-1]["body"]


def test_queue_counts_sections_and_the_consumer_bill_list(sign_in, area):
    ae, _ = _staff(sign_in, "section_ae", area.section_a.id)
    consumer, user = _consumer(sign_in)
    bill_id, ticket = _case(consumer, printed(SPIKED, area.section_a.name), user)
    queue = ae.get("/api/review/cases").json()
    assert queue["counts"]["awaiting_review"] >= 1 and "overdue" in queue["counts"]
    assert {"id": area.section_a.id, "name": area.section_a.name} in ae.get("/api/review/sections").json()
    assert ae.get(f"/api/review/cases/{ticket}").json()["bill_id"] == bill_id
    row = next(r for r in consumer.get("/api/bills").json()["items"] if r["id"] == bill_id)
    assert row["under_review"] is True and row["revised_amount"] is None
    _decide(ae, ticket, kind="corrected_reading", corrected_present_reading=351)
    row = next(r for r in consumer.get("/api/bills").json()["items"] if r["id"] == bill_id)
    assert row["revised_amount"] == OCT_2025.bill_amount
