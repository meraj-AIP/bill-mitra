"""Complaint types, staff raising complaints for consumers, the consumer's own complaints on the web, the chat flow
without a bill, and the development demo seed. Numbers, logins and service numbers are obviously synthetic."""

import asyncio
import json
import secrets

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.core import service
from app.core.hashing import service_hash
from app.core.messages import Inbound, ListOut
from app.core.trace import Event
from app.domain import complaint_types, rbac
from app.domain.conversation.lang import PACKS
from app.main import app
from app.store import complaints as store
from app.store import db, repos
from app.tools import demo_complaints
from tests.review_kit import tree


def fake_usc() -> str:
    return "99" + str(secrets.randbelow(10**10)).zfill(10)


def run(user: str, channel: str = "web", **fields: object) -> list[Event]:
    events: list[Event] = []

    async def emit(event: Event) -> None:
        events.append(event)

    reply_to = "919999999001" if channel == "whatsapp" else None
    inbound = Inbound(channel=channel, user_id=user, reply_to=reply_to, **fields)  # type: ignore[arg-type]
    asyncio.run(service.handle(inbound, emit, language="en"))
    return events


def sent(events: list[Event]) -> list:
    return [e.message for e in events if e.kind == "message" and e.message is not None]


# Catalogue


def test_catalogue_has_three_categories_and_twelve_types_with_labels_everywhere():
    assert complaint_types.CATEGORIES == ("billing", "meter", "supply")
    assert len(complaint_types.TYPES) == 12
    assert {t.route for t in complaint_types.TYPES} == {"section", "review"}
    assert complaint_types.get("wrong_reading").target_days is None
    for pack in PACKS.values():
        for t in complaint_types.TYPES:
            assert t.label_key in pack.T and len(pack.T[t.short_key]) <= 24, (pack.CODE, t.code)


def test_types_route_is_public_and_labelled_in_the_language_asked():
    with TestClient(app) as client:
        english = client.get("/api/complaint-types").json()
        telugu = client.get("/api/complaint-types", params={"language": "te"}).json()
        assert client.get("/api/complaint-types", params={"language": "xx"}).status_code == 422
    assert [t["code"] for t in english][:2] == ["high_bill", "wrong_reading"]
    assert english[0]["label"] == "Bill is too high" and english[0]["category_label"] == "Billing"
    assert telugu[0]["label"] != english[0]["label"] and telugu[0]["label_key"] == "ctype_high_bill"


def test_migration_backfills_old_rows_and_grants_create_once(data_dir):
    """An older database: complaints without the type columns, an officer role without complaints.create."""
    path = data_dir / "billmitra.db"
    with TestClient(app) as client:
        assert client.get("/api/complaint-types").status_code == 200
    conn = db.connection()
    old_perms = '["console.view", "complaints.view"]'
    conn.execute("UPDATE roles SET permissions = ? WHERE slug = 'officer'", (old_perms,))
    conn.commit()
    ticket = f"BM-OLD-{secrets.token_hex(3)}"
    conn.execute("INSERT INTO complaints (ticket, user_id, issue, status, kind) VALUES (?, 'web:x', 'old', 'Open', "
                 "'general')", (ticket,))
    conn.execute("UPDATE complaints SET type = NULL, priority = NULL, due_at = NULL, source = NULL WHERE ticket = ?",
                 (ticket,))
    conn.commit()
    db._migrate(conn)  # a second run backfills the row; the grant only happens with the first type column
    row = conn.execute("SELECT type, priority, due_at, source FROM complaints WHERE ticket = ?", (ticket,)).fetchone()
    assert tuple(row)[:2] == ("high_bill", "normal") and row["due_at"] and row["source"] == "consumer_chat"
    assert conn.execute("SELECT permissions FROM roles WHERE slug = 'officer'").fetchone()[0] == old_perms
    db._grant(conn, "complaints.create", db._CREATE_GRANTED_TO)
    assert "complaints.create" in conn.execute("SELECT permissions FROM roles WHERE slug = 'officer'").fetchone()[0]
    conn.execute("UPDATE roles SET permissions = ? WHERE slug = 'officer'",
                 (json.dumps(rbac.default_permissions("officer")),))
    conn.commit()
    assert path.exists()


# Staff raise

STAFF_BODY = {"type": "power_outage", "discom": "TGSPDCL", "description": "Caller says no power since morning.",
              "source": "call_centre"}


@pytest.mark.parametrize("role", ["admin", "auditor", "billing_approver", "consumer"])
def test_roles_without_create_cannot_raise(sign_in, role):
    with TestClient(app) as client:
        sign_in(client, role)
        assert client.post("/api/console/complaints", json=STAFF_BODY).status_code == 403


@pytest.mark.parametrize("role", ["call_centre", "officer", "section_ae"])
def test_staff_raise_in_scope_with_a_caller_mobile(sign_in, role):
    t = tree()
    usc = fake_usc()
    with TestClient(app) as client:
        account = sign_in(client, role, scopes=[t.section_a.id])
        body = {**STAFF_BODY, "section_id": t.section_a.id, "service_number": usc, "contact_mobile": "9999999123"}
        made = client.post("/api/console/complaints", json=body)
        assert made.status_code == 201, made.text
        detail = made.json()
        ticket = detail["ticket"]
        assert detail["type"] == "power_outage" and detail["priority"] == "urgent" and detail["source"] == "call_centre"
        assert detail["raised_by"] == account.name and detail["ownership"] == "unverified" and detail["due_at"]
        assert detail["service_masked"].endswith(usc[-4:]) and usc not in made.text and "9999999123" not in made.text
        listed = client.get("/api/console/complaints", params={"type": "power_outage", "priority": "urgent",
                                                               "source": "call_centre"}).json()
        assert ticket in [r["ticket"] for r in listed["items"]]
        assert client.get("/api/console/complaints", params={"source": "nowhere"}).status_code == 422
    complaint = store.get(ticket)
    assert complaint and complaint.reply_to == "919999999123" and complaint.section_id == t.section_a.id
    row = db.connection().execute("SELECT service_number_hash, contact_hash FROM complaints WHERE ticket = ?",
                                  (ticket,)).fetchone()
    assert row["service_number_hash"] == service_hash(usc) and row["contact_hash"]
    audit = db.connection().execute("SELECT detail FROM audit_log WHERE action = 'complaint.create' AND target = ?",
                                    (ticket,)).fetchone()[0]
    assert audit == "type power_outage, source call_centre"


def test_staff_raise_refuses_a_section_out_of_scope(sign_in):
    t = tree()
    with TestClient(app) as client:
        sign_in(client, "section_ae", scopes=[t.section_a.id])
        out = client.post("/api/console/complaints", json={**STAFF_BODY, "section_id": t.section_b.id})
        queue = client.post("/api/console/complaints", json=STAFF_BODY)  # the DISCOM queue is above their section
        bad_mobile = client.post("/api/console/complaints", json={**STAFF_BODY, "section_id": t.section_a.id,
                                                                   "contact_mobile": "12345"})
    assert out.status_code == 403 and queue.status_code == 403 and bad_mobile.status_code == 422


# Consumer web


def test_consumer_raises_lists_and_reads_only_their_own(sign_in):
    with TestClient(app) as mine, TestClient(app) as theirs:
        sign_in(mine, "consumer")
        sign_in(theirs, "consumer")
        usc = fake_usc()
        made = mine.post("/api/complaints", json={"type": "voltage_fluctuation", "discom": "TGNPDCL",
                                                  "service_number": usc, "description": "Fans run slow at night."})
        assert made.status_code == 201, made.text
        ticket = made.json()["ticket"]
        assert made.json()["status"] == "received" and made.json()["service_masked"].endswith(usc[-4:])
        assert usc not in made.text
        assert mine.get("/api/complaints").json()["items"][0]["ticket"] == ticket
        assert mine.get(f"/api/complaints/{ticket}").json()["messages"][0]["from"] == "you"
        assert theirs.get(f"/api/complaints/{ticket}").status_code == 404
        assert theirs.post(f"/api/complaints/{ticket}/reply", json={"body": "hello there"}).status_code == 404
        assert ticket not in theirs.get("/api/complaints").text
        assert mine.post(f"/api/complaints/{ticket}/reply", json={"body": "Any news?"}).status_code == 409
        assert mine.post("/api/complaints", json={"type": "voltage_fluctuation", "discom": "TGNPDCL",
                                                  "bill_id": "b_notmine", "description": "x y z"}).status_code == 404


def test_consumer_view_never_names_staff(sign_in):
    with TestClient(app) as consumer, TestClient(app) as officer:
        sign_in(consumer, "consumer")
        made = consumer.post("/api/complaints", json={"type": "wrong_reading", "discom": "TGSPDCL",
                                                      "description": "Reading looks higher than my meter."}).json()
        ticket = made["ticket"]
        # A reading complaint without a bill asks for the photo at once, so the consumer is the one awaited.
        assert made["status"] == "waiting_for_you" and made["messages"][-1]["from"] == "bill_mitra"
        staff = sign_in(officer, "officer")
        reply = officer.post(f"/api/console/complaints/{ticket}/reply", json={"body": "Please send the bill photo."})
        assert reply.status_code == 200, reply.text
        assert reply.json()["messages"][-1]["author_name"] == staff.name
        view = consumer.get(f"/api/complaints/{ticket}")
        assert staff.name not in view.text and "author" not in view.text and "assigned" not in view.text
        assert {m["from"] for m in view.json()["messages"]} == {"you", "bill_mitra"}
        answered = consumer.post(f"/api/complaints/{ticket}/reply", json={"body": "Sending it in the chat."})
        assert answered.status_code == 200 and answered.json()["status"] == "in_progress"  # staff have acted, so it is under way


# Chat without a bill


def test_chat_complaint_without_a_bill_end_to_end():
    user = f"wa:{secrets.token_hex(10)}"
    usc = fake_usc()
    first = sent(run(user, "whatsapp", kind="text", text="I want to raise a complaint"))
    assert [b.id for b in first[-1].buttons] == ["ccat:billing", "ccat:meter", "ccat:supply"]
    listed = sent(run(user, "whatsapp", kind="button_reply", reply_id="ccat:supply"))[-1]
    assert isinstance(listed, ListOut) and [r.id for r in listed.rows] == [
        "ctype:power_outage", "ctype:voltage_fluctuation", "ctype:supply_other"]
    discoms = sent(run(user, "whatsapp", kind="button_reply", reply_id="ctype:power_outage"))[-1]
    assert [b.id for b in discoms.buttons] == ["cdis:TGSPDCL", "cdis:TGNPDCL"]
    run(user, "whatsapp", kind="button_reply", reply_id="cdis:TGNPDCL")
    assert "does not look like a service number" in sent(run(user, "whatsapp", kind="text", text="12ab"))[-1].body
    run(user, "whatsapp", kind="text", text=usc)
    asked = sent(run(user, "whatsapp", kind="text", text="No power since the morning, only our house."))[-1]
    assert "Since when" in asked.body and [b.id for b in asked.buttons] == ["cfq_skip"]
    run(user, "whatsapp", kind="button_reply", reply_id="cfq_skip")
    preview = sent(run(user, "whatsapp", kind="button_reply", reply_id="cfq_skip"))[-1]
    assert usc not in preview.body and usc[-4:] in preview.body and "No power at my home" in preview.body
    filed = sent(run(user, "whatsapp", kind="button_reply", reply_id="cdraft_send"))[-1]
    assert "BM-" in filed.body
    page = store.page(1, 5, owner=user)
    assert page.total == 1
    row = page.items[0]
    assert (row["type"], row["priority"], row["source"], row["discom"]) == ("power_outage", "urgent", "whatsapp",
                                                                            "TGNPDCL")
    assert "officer" not in filed.body.lower() and " AE" not in filed.body
    assert repos.get_user(user, "whatsapp").awaiting is None


def test_chat_draft_can_be_skipped_and_cancelled():
    user = f"web:{secrets.token_hex(10)}"
    run(user, kind="button_reply", reply_id="ccat:billing")  # a stale button with no draft starts again
    run(user, kind="button_reply", reply_id="ctype:arrears_dispute")
    run(user, kind="button_reply", reply_id="cdis:TGSPDCL")
    run(user, kind="button_reply", reply_id="cusc_skip")
    run(user, kind="text", text="Old dues added again.")
    preview = sent(run(user, kind="button_reply", reply_id="cfq_skip"))[-1]
    assert "not given" in preview.body
    assert "not sent" in sent(run(user, kind="button_reply", reply_id="cdraft_cancel"))[-1].body
    assert store.page(1, 5, owner=user).total == 0


# Demo seed


def test_demo_seed_refuses_in_production(monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "production")
    assert demo_complaints.main(["seed"]) == 2


def test_demo_seed_and_remove_touch_only_demo_rows(sign_in):
    with TestClient(app) as client:
        sign_in(client, "consumer")
        real = client.post("/api/complaints", json={"type": "high_bill", "discom": "TGSPDCL",
                                                    "description": "A real one."}).json()["ticket"]
    assert demo_complaints.main(["seed"]) == 0
    conn = db.connection()
    counts = dict(conn.execute("SELECT type, COUNT(*) FROM complaints WHERE demo = 1 AND kind = 'general' "
                               "GROUP BY type").fetchall())
    assert sum(counts.values()) == len(demo_complaints.SPECS) and counts["power_outage"] == 1
    assert counts.get("high_bill", 0) + counts.get("wrong_reading", 0) >= 6
    assert conn.execute("SELECT COUNT(*) FROM complaints WHERE demo = 1 AND escalated_at IS NOT NULL").fetchone()[0] == 2
    db.purge_mock_data()  # the startup purge keeps them
    assert conn.execute("SELECT COUNT(*) FROM complaints WHERE demo = 1 AND kind = 'general'").fetchone()[0] == \
        len(demo_complaints.SPECS)
    assert demo_complaints.main(["remove"]) == 0
    assert conn.execute("SELECT COUNT(*) FROM complaints WHERE demo = 1").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM bills WHERE source = 'demo'").fetchone()[0] == 0
    assert store.get(real) is not None


# Settings and roles


def test_production_refuses_to_start_without_the_ownership_check():
    with pytest.raises(ValueError, match="OWNERSHIP_CHECK"):
        Settings(app_env="production", ownership_check=False, hash_pepper="test-pepper-not-real")
    with pytest.raises(ValueError, match="HASH_PEPPER"):
        Settings(app_env="production", ownership_check=True)
    assert Settings(app_env="development", ownership_check=False).dev_bills


def test_create_permission_follows_the_contract():
    holders = {r.slug for r in rbac.BUILTIN_ROLES if "complaints.create" in r.permissions}
    assert holders == {"call_centre", "officer", "section_ae"}
    assert rbac.BUILTIN["call_centre"].permissions == {"console.view", "complaints.view", "complaints.create",
                                                       "complaints.reply", "complaints.assign"}


# Console detail, assignee and hand-off: tests/test_handoff.py


def test_consumer_list_filters_by_neutral_status(sign_in):
    with TestClient(app) as client:
        sign_in(client, "consumer")
        client.post("/api/complaints", json={"type": "high_bill", "discom": "TGSPDCL", "description": "Too high."})
        client.post("/api/complaints", json={"type": "wrong_reading", "discom": "TGSPDCL",
                                             "description": "Reading looks wrong."})
        waiting = client.get("/api/complaints", params={"status": "waiting_for_you"}).json()
        received = client.get("/api/complaints", params={"status": "received", "language": "en"}).json()
        assert client.get("/api/complaints", params={"status": "Open"}).status_code == 422
    assert waiting["total"] == 1 and waiting["items"][0]["type"] == "wrong_reading"
    assert received["total"] == 1 and received["items"][0]["status_label"] == "Received"
