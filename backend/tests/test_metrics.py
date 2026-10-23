"""Console metrics, the complaints CSV and ticket numbers. The database is shared across tests, so counts are
compared before and after. Bills are the real fixtures; identifiers are synthetic."""

import asyncio
import csv
import io
import re
import secrets
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core import service
from app.core.messages import Inbound
from app.core.trace import Event
from app.main import app
from app.services import llm, vision
from app.store import complaints as store
from app.store import console, media
from app.store.db import tx
from tests.real import OCT_2025, reading, variant

FAKE_WA = "test-wa-address-3"  # obviously synthetic WhatsApp address


@pytest.fixture(autouse=True)
def live_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests read the summary before and after a change, so each read is fresh."""
    monkeypatch.setattr(console, "CACHE_SECONDS", 0)


def test_the_summary_is_shared_for_a_minute(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(console, "CACHE_SECONDS", 60)
    first = console.summary(days=3)
    _complaint("TGSPDCL")
    assert console.summary(days=3) is first
    console.forget_cached()
    assert console.summary(days=3) is not first


def _photo_in_chat(channel: str = "web") -> None:
    async def emit(_: Event) -> None:
        return None

    inbound = Inbound(channel=channel, user_id=f"test-{secrets.token_hex(4)}", kind="image",  # type: ignore[arg-type]
                      media_id=media.save(f"synthetic-photo-{secrets.token_hex(8)}".encode(), "image/jpeg"), mime_type="image/jpeg")
    asyncio.run(service.handle(inbound, emit, language="en"))


def _complaint(discom: str, issue: str = "Energy charge above tariff.") -> str:
    ticket = store.create(f"test-{secrets.token_hex(4)}", None, variant(OCT_2025, discom=discom), issue, 140.0, "en",
                          "whatsapp", FAKE_WA, "Energy charge looks too high.")
    assert ticket
    return ticket


def test_chat_read_and_explanation_are_counted(reader):
    before = console.summary()
    reader(reading(OCT_2025))
    _photo_in_chat()
    rescued = reading(OCT_2025)
    reader(vision.Reading(rescued.classification, rescued.bill, reread="Charges do not add up"))
    _photo_in_chat()
    reader(reading(None, kind="other_bill", reason="A shop receipt."))
    _photo_in_chat()
    after = console.summary()
    reads, was = after["reads"], before["reads"]
    assert reads["total"] - was["total"] == 3
    assert reads["trusted_first_time"] - was["trusted_first_time"] == 1
    assert reads["reread_rescued"] - was["reread_rescued"] == 1
    assert reads["not_a_bill"] - was["not_a_bill"] == 1
    assert reads["median_ms"] is not None and reads["p90_ms"] >= reads["median_ms"] >= 0
    assert after["explanations"]["template"] - before["explanations"]["template"] == 2


def test_number_guard_rejection_is_counted_as_fallback(reader, monkeypatch: pytest.MonkeyPatch):
    async def invents(*_: object) -> str:
        return "Your bill is Rs 98,765."

    async def plain(*_: object) -> str:
        return "Your bill matches the tariff."

    reader(reading(OCT_2025))
    before = console.summary()["explanations"]
    monkeypatch.setattr(llm, "explain", invents)
    _photo_in_chat()
    monkeypatch.setattr(llm, "explain", plain)
    _photo_in_chat()
    after = console.summary()["explanations"]
    assert after["llm_fallback"] - before["llm_fallback"] == 1 and after["llm_pass"] - before["llm_pass"] == 1


def test_dashboard_reads_are_counted_with_their_outcome(reader, sign_in):
    reader(reading(None, quality="unreadable"))
    before = console.summary()["reads"]
    with TestClient(app) as client:
        sign_in(client)
        photo = {"file": ("bill.pdf", b"%PDF-1.4 synthetic", "application/pdf")}
        assert client.post("/api/bills", files=photo).json()["outcome"] == "retake"
    assert console.summary()["reads"]["retake"] - before["retake"] == 1


def test_complaint_status_overdue_and_discom_filter():
    before_n, before_s = console.summary(discom="TGNPDCL"), console.summary(discom="TGSPDCL")
    ticket = _complaint("TGNPDCL")
    with tx() as conn:  # test-only backdating
        conn.execute("UPDATE complaints SET created_at = datetime('now', '-10 days') WHERE ticket = ?", (ticket,))
    after_n, after_s = console.summary(discom="TGNPDCL"), console.summary(discom="TGSPDCL")
    assert after_n["complaints_by_status"]["Open"] - before_n["complaints_by_status"]["Open"] == 1
    assert after_n["complaints_overdue"] - before_n["complaints_overdue"] == 1
    assert after_s["complaints_overdue"] == before_s["complaints_overdue"]
    assert console.summary(days=5, discom="TGNPDCL")["complaints_by_status"]["Open"] < \
        after_n["complaints_by_status"]["Open"]


def test_summary_params_and_officer_scope(sign_in):
    with TestClient(app) as client:
        sign_in(client, "officer", "TGNPDCL")
        scoped = client.get("/api/console/summary", params={"discom": "TGSPDCL", "days": 7}).json()
        assert scoped["discom"] == "TGNPDCL" and scoped["days"] == 7
        assert {"bills_read", "daily", "audit", "reads", "explanations", "complaints_by_status"} <= set(scoped)
        assert client.get("/api/console/summary", params={"days": 0}).status_code == 422
        assert client.get("/api/console/summary", params={"days": 366}).status_code == 422


def test_complaints_csv_is_scoped_and_safe_in_a_spreadsheet(sign_in):
    south = _complaint("TGSPDCL", "=HYPERLINK(\"http://example.com\")")
    north = _complaint("TGNPDCL")
    with TestClient(app) as client:
        sign_in(client, "officer", "TGSPDCL")
        response = client.get("/api/console/complaints.csv", params={"q": south[-5:]})
        everything = client.get("/api/console/complaints.csv").text
        assert client.get("/api/console/complaints.csv", params={"discom": "TGNPDCL"}).text.count("\n") == 1
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/csv")
    assert f"bill-mitra-complaints-{datetime.now(UTC):%Y%m%d}.csv" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert list(rows[0]) == ["ticket", "created_at", "updated_at", "status", "discom", "bill_month", "service_masked",
                             "issue", "amount", "channel", "days_open"]
    row = next(r for r in rows if r["ticket"] == south)
    assert row["issue"].startswith("'=") and row["days_open"] == "0"
    assert FAKE_WA not in response.text and north not in everything


def test_consumer_cannot_export(sign_in):
    with TestClient(app) as client:
        assert client.get("/api/console/complaints.csv").status_code == 401
        sign_in(client)
        assert client.get("/api/console/complaints.csv").status_code == 403


def test_ticket_numbers_are_random_and_collisions_retry(monkeypatch: pytest.MonkeyPatch):
    assert re.fullmatch(r"BM-\d{6}-[A-Z0-9]{5}", _complaint("TGSPDCL"))
    monkeypatch.setattr(store.secrets, "choice", lambda _: "Q")
    assert _complaint("TGSPDCL").endswith("-QQQQQ")
    with pytest.raises(RuntimeError):
        _complaint("TGSPDCL")
