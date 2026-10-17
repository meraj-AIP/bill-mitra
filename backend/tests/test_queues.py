"""Durable queues (docs/reliability-contract.md sections 2 to 5): inbound turns retried, every outbound message kept
in the outbox until WhatsApp takes it, bill reads queued while the reader is down, the stuck sweep, and the admin
Operations routes. Faults are injected at the HTTP boundary (the fake Graph API) or the vision provider; time moves
by passing a later `now`, never by sleeping."""

import asyncio
import secrets
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.channels.whatsapp import client as wa_client
from app.channels.whatsapp.mapper import IncomingWhatsApp, user_key
from app.config import get_settings
from app.core.messages import TextOut
from app.domain.conversation.lang import PACKS
from app.flows import recovery
from app.main import app
from app.services import delivery, notify
from app.services.openai_client import ProviderError
from app.store import extract_jobs, outbox, wa_queue
from app.store.db import tx
from tests.real import OCT_2025, reading
from tests.test_bills_api import PHOTO
from tests.test_whatsapp_readiness import whatsapp_complaint
from tests.whatsapp_kit import api, bodies, graph, ids, image, number, say, text  # noqa: F401

NEUTRAL = PACKS["te"].T["working_on_it"]
READING_LATER = PACKS["te"].T["reading_later"]
DOWN = ProviderError("HTTPStatusError", transient=True)


def later(seconds: int) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=seconds)


def run(job, seconds: int) -> int:  # type: ignore[no-untyped-def]
    return asyncio.run(job(later(seconds)))


def parked_turn(sender: str) -> int | None:
    with tx() as conn:
        row = conn.execute("SELECT id FROM wa_turns WHERE sender = ? AND state = 'failed'", (sender,)).fetchone()
    return row[0] if row else None


def test_a_turn_failing_twice_then_working_says_the_neutral_line_once_and_replies_once(api, graph, reader):  # noqa: F811
    reader(reading(OCT_2025))
    sender = number()
    say(api, graph, text(sender, "hi"))
    start = len(graph.messages())
    graph.media_down = 2 * wa_client.MEDIA.attempts  # Meta's media endpoint is down for two whole tries
    assert bodies(say(api, graph, image(sender))) == [NEUTRAL]
    run(recovery.retry_inbox, 61)  # the second try fails too, quietly
    assert len(graph.messages()) == start + 1
    run(recovery.retry_inbox, 61 + 301)  # the third works
    after = graph.messages()[start:]
    assert bodies(after).count(NEUTRAL) == 1 and ids(after).count("why") == 1
    assert graph.media_down == 0 and parked_turn(sender) is None  # both failed tries really reached Meta


def test_a_turn_that_keeps_failing_is_parked_with_one_alert_and_later_messages_go_ahead(api, graph, reader):  # noqa: F811
    reader(reading(OCT_2025))
    sender = number()
    say(api, graph, text(sender, "hi"))
    graph.media_down = 10**6
    say(api, graph, image(sender))
    for seconds in (61, 400, 1400, 2400):
        run(recovery.retry_inbox, seconds)
    turn_id = parked_turn(sender)
    assert turn_id is not None
    with tx() as conn:
        alerts = conn.execute("SELECT kind, body FROM alerts WHERE dedupe_key = ?", (f"inbound_failed:{turn_id}",)).fetchall()
    assert len(alerts) == 1 and alerts[0]["kind"] == "inbound_failed" and "hi" not in alerts[0]["body"]
    graph.media_down = 0
    reply = say(api, graph, text(sender, "why is my bill high"))
    assert reply and NEUTRAL not in bodies(reply)
    assert bodies(graph.messages()).count(NEUTRAL) == 1


def _item(to: str, body: str) -> outbox.NewItem:
    return outbox.NewItem(dedupe_key=f"test:{secrets.token_hex(6)}", kind="reply", recipient=user_key(to), address=to,
                          message=TextOut(body=body, language="en").model_dump())


def test_a_message_meta_accepted_is_never_sent_again(graph):  # noqa: F811
    item = _item(number(), "Synthetic once.")
    first = asyncio.run(delivery.deliver(item))
    again = asyncio.run(delivery.deliver(item))  # a retried turn queues the same logical message
    stray = asyncio.run(delivery.attempt(first.id))  # and a stray worker tries the row again
    assert first.state == "sent" and first.wamid and again.id == stray.id == first.id
    assert [m["text"]["body"] for m in graph.messages()].count("Synthetic once.") == 1
    assert outbox.get(first.id).address is None  # type: ignore[union-attr]  # the number goes once it is sent


def test_a_send_that_fails_for_now_waits_and_later_messages_keep_their_order(graph):  # noqa: F811
    to = number()
    graph.send_down = wa_client.SEND.attempts
    first = asyncio.run(delivery.deliver(_item(to, "Synthetic first.")))
    second = asyncio.run(delivery.deliver(_item(to, "Synthetic second.")))
    assert first.state == second.state == "queued" and first.note == delivery.QUEUED
    assert run(delivery.run_due, 61) == 2
    sent = [m["text"]["body"] for m in graph.messages() if m["to"] == to]
    assert sent == ["Synthetic first.", "Synthetic second."]


def _staff_reply(api, ticket: str, body: str) -> dict:  # noqa: F811
    return api.post(f"/api/console/complaints/{ticket}/reply", json={"body": body}).json()["messages"][-1]


def test_a_queued_staff_reply_shows_on_the_thread_and_alerts_the_holder_when_it_gives_up(api, graph, reader,  # noqa: F811
                                                                                         sign_in):
    ticket, _ = whatsapp_complaint(api, graph, reader)
    sign_in(api, "admin")
    graph.send_down = 10**6
    sent = _staff_reply(api, ticket, "We are checking.")
    assert sent["delivery"] == "queued" and sent["delivery_note"] == delivery.QUEUED
    for hours in range(1, 30):  # the backoff then every 3 hours, past the 24 hour lifetime
        run(delivery.run_due, hours * 3600)
    thread = api.get(f"/api/console/complaints/{ticket}").json()["messages"]
    after = next(m for m in thread if m["id"] == sent["id"])
    assert after["delivery"] == "failed" and after["delivery_note"] == delivery.GAVE_UP
    with tx() as conn:
        assert conn.execute("SELECT COUNT(*) FROM alerts WHERE kind = 'delivery_failed' AND ticket = ?",
                            (ticket,)).fetchone()[0] == 1


def test_a_queued_staff_reply_goes_when_whatsapp_is_back(api, graph, reader, sign_in):  # noqa: F811
    ticket, _ = whatsapp_complaint(api, graph, reader)
    sign_in(api, "admin")
    graph.send_down = wa_client.SEND.attempts
    sent = _staff_reply(api, ticket, "Synthetic update.")
    assert sent["delivery"] == "queued"
    run(delivery.run_due, 61)
    after = next(m for m in api.get(f"/api/console/complaints/{ticket}").json()["messages"] if m["id"] == sent["id"])
    assert after["delivery"] == "sent" and after["delivery_note"] is None


def test_after_24_hours_of_silence_the_template_goes_instead_of_free_text(api, graph, reader, sign_in,  # noqa: F811
                                                                          monkeypatch):
    monkeypatch.setattr(get_settings(), "whatsapp_complaint_template", "complaint_update")
    ticket, sender = whatsapp_complaint(api, graph, reader)
    with tx() as conn:
        conn.execute("UPDATE chat_messages SET ts = datetime('now', '-25 hours') WHERE user_id = ?", (user_key(sender),))
    sign_in(api, "admin")
    sent = _staff_reply(api, ticket, "Synthetic late update.")
    assert sent["delivery"] == "sent" and sent["delivery_note"] == notify.TEMPLATE_USED
    last = graph.messages()[-1]
    assert last["type"] == "template" and last["template"]["components"][0]["parameters"][0]["text"] == ticket


def test_a_bill_read_that_fails_for_now_is_read_later_and_the_report_sent(api, graph, reader):  # noqa: F811
    reader(DOWN, DOWN, reading(OCT_2025))
    sender = number()
    say(api, graph, text(sender, "hi"))
    first = say(api, graph, image(sender))
    assert bodies(first) == [READING_LATER]
    assert run(recovery.run_extracts, 61) == 0  # still down: tried again in 5 minutes
    start = len(graph.messages())
    assert run(recovery.run_extracts, 61 + 301) == 1
    report = graph.messages()[start:]
    assert ids(report).count("why") == 1 and READING_LATER not in bodies(report)


def test_web_upload_while_the_reader_is_down_is_a_202_then_a_poll_then_my_bills(reader, sign_in):
    reader(DOWN, reading(OCT_2025))
    with TestClient(app) as client:
        sign_in(client)
        queued = client.post("/api/bills", files=PHOTO, data={"language": "en"})
        assert queued.status_code == 202
        job = queued.json()
        assert job["status"] == "queued" and job["bill_id"] is None and job["detail"]
        assert set(job) == {"job_id", "status", "bill_id", "detail"}
        assert client.get(f"/api/bills/jobs/{job['job_id']}").json()["status"] == "queued"
        run(recovery.run_extracts, 61)
        done = client.get(f"/api/bills/jobs/{job['job_id']}").json()
        assert done["status"] == "done" and done["bill_id"]
        assert done["bill_id"] in [b["id"] for b in client.get("/api/bills").json()["items"]]
        assert client.get(f"/api/bills/{done['bill_id']}").json()["outcome"] == "checked"
        sign_in(client)  # someone else
        assert client.get(f"/api/bills/jobs/{job['job_id']}").status_code == 404


def test_sweep_requeues_work_whose_worker_died():
    sender = number()
    wa_queue.add(IncomingWhatsApp(sender, "wamid." + secrets.token_hex(6), "text", text="synthetic"))
    turn = wa_queue.claim(sender)
    row = outbox.put(_item(number(), "Synthetic stuck."))
    outbox.claim(row.id)
    job = extract_jobs.create("wa:synthetic", "dashboard", "media-synthetic", "image/jpeg", "en", None, "Timeout")
    extract_jobs.claim_due(later(61))
    with tx() as conn:
        conn.execute("UPDATE wa_turns SET claimed_at = datetime('now', '-10 minutes') WHERE id = ?", (turn.id,))  # type: ignore[union-attr]
    assert run(recovery.sweep_stuck, 3600) >= 3
    with tx() as conn:
        assert conn.execute("SELECT claimed_at FROM wa_turns WHERE id = ?", (turn.id,)).fetchone()[0] is None  # type: ignore[union-attr]
        assert conn.execute("SELECT state FROM outbox WHERE id = ?", (row.id,)).fetchone()[0] == "queued"
        assert conn.execute("SELECT state FROM extract_jobs WHERE id = ?", (job.id,)).fetchone()[0] == "queued"
        audited = {r[0] for r in conn.execute("SELECT target FROM audit_log WHERE action = 'queue.requeue' "
                                               "AND actor_id IS NULL")}
    assert {f"inbox:{turn.id}", f"outbox:{row.id}", f"extract:{job.id}"} <= audited  # type: ignore[union-attr]


def test_health_counts_the_queues():
    body = TestClient(app).get("/api/health").json()["queues"]
    assert set(body) == {"inbox", "outbox", "extract", "oldest_queued_s"}
    assert set(body["outbox"]) == {"queued", "failed"}


def _parked_outbound(ticket: str) -> int:
    row = outbox.put(outbox.NewItem(dedupe_key=f"test:{secrets.token_hex(6)}", kind="staff", recipient="wa:synthetic",
                                    address=number(), message={"type": "text", "body": "Synthetic.", "language": "en"},
                                    ticket=ticket))
    outbox.failed(row.id, "HTTPStatusError 400", delivery.REJECTED)
    return row.id


def test_operations_lists_parked_failures_by_permission_and_scope(api, graph, reader, sign_in):  # noqa: F811
    ticket, _ = whatsapp_complaint(api, graph, reader)
    row_id = _parked_outbound(ticket)
    target = f"/api/admin/operations/outbound/{row_id}"

    sign_in(api)  # a consumer
    assert api.get("/api/admin/operations").status_code == 403
    sign_in(api, "auditor", discom="TGNPDCL")  # the complaint is in the other DISCOM
    assert str(row_id) not in [i["id"] for i in api.get("/api/admin/operations", params={"kind": "outbound"}).json()["items"]]
    assert api.post(f"{target}/retry").status_code == 404
    sign_in(api, "auditor", discom="TGSPDCL")
    page = api.get("/api/admin/operations", params={"kind": "outbound", "page_size": 100}).json()
    assert set(page) == {"items", "total", "page", "page_size"}
    item = next(i for i in page["items"] if i["id"] == str(row_id))
    assert item == {"id": str(row_id), "kind": "outbound", "ticket": ticket, "attempts": 1,
                    "last_error": "HTTPStatusError 400", "created_at": item["created_at"], "failed_at": item["failed_at"]}

    assert api.post(f"{target}/retry").status_code == 204
    assert outbox.get(row_id).state == "queued"  # type: ignore[union-attr]
    outbox.failed(row_id, "HTTPStatusError 400", delivery.REJECTED)
    assert api.post(f"{target}/dismiss").status_code == 204
    dismissed = outbox.get(row_id)
    assert dismissed and dismissed.state == "dismissed" and dismissed.address is None and dismissed.message is None
    assert api.post(f"{target}/dismiss").status_code == 404
    with tx() as conn:
        actions = [r[0] for r in conn.execute("SELECT action FROM audit_log WHERE target = ? ORDER BY id",
                                              (f"outbound:{row_id}",))]
    assert actions == ["operations.retry", "operations.dismiss"]
