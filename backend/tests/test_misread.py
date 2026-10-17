"""Misread found from the next bill: the rule, the dashboard offer, the case suggestion with its audit line and
alert, and the chat offer that reports the earlier month.

Every bill here is synthetic: invented readings, a placeholder service number, charges priced by the engine.
"""

import asyncio
import io
import re
import secrets
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core import service
from app.core.messages import Inbound
from app.core.trace import Event
from app.domain.bill import ExtractedBill, LineItem, UsagePoint
from app.domain.conversation.lang import PACKS, text
from app.domain.pricing import price
from app.flows import misread
from app.main import app
from app.store import media, suggestions
from app.store.db import tx
from tests.real import reading
from tests.review_kit import Tree, tree
from tests.test_complaints import WA_NUMBER

SERVICE = "SYNTHETIC0002"
OTHER_SERVICE = "SYNTHETIC0003"


def synthetic(month: str, previous: float, present: float, section: str | None = None, service_number: str = SERVICE,
              usual: int | None = None) -> ExtractedBill:
    """An invented domestic bill whose charges are the engine's own, so it audits as verified. `usual` prints a
    three month usage table at that many units a month."""
    year, number = int(month[:4]), int(month[5:7])
    billed_on = date(year, number, 5)
    units = round(present - previous)
    history = []
    if usual is not None:
        for back in (3, 2, 1):
            m = (number - back - 1) % 12 + 1
            y = year - (1 if number - back < 1 else 0)
            history.append(UsagePoint(month=f"{y:04d}-{m:02d}", units=usual))
    bill = ExtractedBill(discom="TGSPDCL", service_number=service_number, section=section, category="1B(i) DOMESTIC",
                         bill_month=month, bill_date=billed_on.isoformat(),
                         previous_reading_date=(billed_on - timedelta(days=30)).isoformat(), billing_days=30,
                         previous_reading=previous, present_reading=present, units=units, load_kw=2.0,
                         gruha_jyothi_household=False, usage_history=history, confidence=0.95)
    comp = price(bill, units, units)
    lines = [LineItem(code=code, label=code.title(), amount=getattr(comp, code))
             for code in ("energy", "fixed", "customer", "duty")]
    amount = round(sum(line.amount for line in lines), 2)
    return bill.model_copy(update={"line_items": lines, "bill_amount": amount, "total_payable": amount})


def _jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(out, "JPEG")
    return out.getvalue()


PHOTO = {"file": ("bill.jpg", _jpeg(), "image/jpeg")}
# March read as 1400 where the meter showed about 1150; April starts from the true 1150.
MARCH = ("2026-03", 1000.0, 1400.0)
APRIL = ("2026-04", 1150.0, 1300.0)


def upload(client: TestClient, reader, bill: ExtractedBill) -> dict:
    reader(reading(bill))
    response = client.post("/api/bills", files=PHOTO, data={"language": "en"})
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "checked", response.json()["outcome_reason"]
    return response.json()


def staff(sign_in, role: str, *scopes: str) -> TestClient:
    client = TestClient(app)
    sign_in(client, role, scopes=list(scopes) or None)
    return client


def consumer(sign_in) -> TestClient:
    client = TestClient(app)
    sign_in(client)
    return client


def report(client: TestClient, bill_id: str) -> str:
    response = client.post(f"/api/bills/{bill_id}/review-request", params={"language": "en"}, json={})
    assert response.status_code == 200, response.text
    return response.json()["ticket"]


def audit_rows(ticket: str, action: str) -> list[dict]:
    with tx() as conn:
        return [dict(r) for r in conn.execute("SELECT actor_id, detail, unit_id FROM audit_log WHERE target = ? "
                                              "AND action = ?", (ticket, action))]


def alert_rows(ticket: str) -> list[dict]:
    with tx() as conn:
        return [dict(r) for r in conn.execute("SELECT kind, unit_id, perm, title, body FROM alerts WHERE ticket = ?",
                                              (ticket,))]


@pytest.fixture
def area() -> Tree:
    return tree()


def test_signal_needs_the_next_bill_to_start_inside_the_earlier_period():
    earlier = synthetic(*MARCH)
    assert misread.signal(earlier, synthetic(*APRIL))
    assert not misread.signal(earlier, synthetic("2026-04", 1400.0, 1500.0))  # consistent: starts where it ended
    assert not misread.signal(earlier, synthetic("2026-04", 900.0, 1000.0))  # below the earlier start: not a misread
    assert not misread.signal(earlier, synthetic("2026-04", 1500.0, 1600.0))
    assert not misread.signal(earlier.model_copy(update={"present_reading": None}), synthetic(*APRIL))


def test_dashboard_offers_the_earlier_month_until_it_is_reported(reader, sign_in, area):
    ae = staff(sign_in, "section_ae", area.section_a.id)
    client = consumer(sign_in)
    march = upload(client, reader, synthetic(*MARCH, section=area.section_a.name))
    assert march["misread"] is None
    april = upload(client, reader, synthetic(*APRIL, section=area.section_a.name))
    assert april["misread"] == {"earlier_bill_id": march["id"], "earlier_month": "2026-03",
                                "printed_present": 1400.0, "next_previous": 1150.0}
    assert client.get(f"/api/bills/{april['id']}").json()["misread"] == april["misread"]

    ticket = report(client, march["id"])
    assert client.get(f"/api/bills/{april['id']}").json()["misread"] is None  # a check is now open on March
    found = suggestions.get(ticket)
    assert found and found.corrected_present_reading == 1150 and found.source_bill_id == april["id"]
    lines = audit_rows(ticket, "case.suggestion")
    assert len(lines) == 1 and lines[0]["actor_id"] is None and "1150" in lines[0]["detail"]
    assert SERVICE not in lines[0]["detail"]
    alerts = [a for a in alert_rows(ticket) if a["kind"] != "case_assigned"]  # routing tells the AE separately
    assert [(a["kind"], a["unit_id"], a["perm"]) for a in alerts] == [("misread_found", area.section_a.id,
                                                                      "cases.decide")]
    assert SERVICE not in alerts[0]["title"] + alerts[0]["body"]
    timeline = ae.get(f"/api/review/cases/{ticket}").json()["timeline"]
    step = next(e for e in timeline if e["text"].startswith("Found a misread from the next bill"))
    assert step["actor"] == {"kind": "system", "name": "System"}


def test_next_bill_arriving_after_the_case_opens_adds_the_suggestion_once(reader, sign_in, area):
    client = consumer(sign_in)
    march = upload(client, reader, synthetic(*MARCH, section=area.section_a.name))
    ticket = report(client, march["id"])
    assert suggestions.get(ticket) is None
    april = upload(client, reader, synthetic(*APRIL, section=area.section_a.name))
    assert april["misread"] is None  # the case already exists, so the suggestion went there instead
    assert suggestions.get(ticket).source_bill_id == april["id"]
    upload(client, reader, synthetic(*APRIL, section=area.section_a.name))  # the same month sent again
    assert len(audit_rows(ticket, "case.suggestion")) == 1 and len(alert_rows(ticket)) == 1


@pytest.mark.parametrize("following", [
    synthetic("2026-04", 1400.0, 1550.0),  # readings consistent
    synthetic("2026-04", 1150.0, 1300.0, service_number=OTHER_SERVICE),  # another connection
    synthetic("2026-05", 1150.0, 1300.0),  # months not adjacent
], ids=["consistent", "other_service", "not_adjacent"])
def test_no_signal_means_no_offer_and_no_suggestion(reader, sign_in, area, following):
    client = consumer(sign_in)
    march = upload(client, reader, synthetic(*MARCH, section=area.section_a.name))
    ticket = report(client, march["id"])
    later = upload(client, reader, following.model_copy(update={"section": area.section_a.name}))
    assert later["misread"] is None and suggestions.get(ticket) is None
    assert audit_rows(ticket, "case.suggestion") == [] and alert_rows(ticket) == []


def test_another_consumers_bill_never_pairs(reader, sign_in, area):
    first, second = consumer(sign_in), consumer(sign_in)
    upload(first, reader, synthetic(*MARCH, section=area.section_a.name))
    assert upload(second, reader, synthetic(*APRIL, section=area.section_a.name))["misread"] is None


def test_chat_offers_to_report_the_earlier_month_and_files_it(reader, sign_in, area):
    officer = staff(sign_in, "officer", area.division.id)
    user = f"wa:{secrets.token_hex(10)}"
    sent: list[dict] = []

    async def keep(event: Event) -> None:
        if event.kind == "message" and event.message is not None:
            sent.append(event.message.model_dump())

    def say(**fields) -> None:
        asyncio.run(service.handle(Inbound(channel="whatsapp", user_id=user, reply_to=WA_NUMBER, **fields), keep,
                                   language="en"))

    def photo(bill: ExtractedBill) -> None:
        reader(reading(bill))
        say(kind="image", media_id=media.save(b"synthetic-photo", "image/jpeg"), mime_type="image/jpeg")

    photo(synthetic(*MARCH, section=area.section_a.name))
    assert not [m for m in sent if m["type"] == "buttons" and m["buttons"][0]["id"] == "report_misread"]
    photo(synthetic(*APRIL, section=area.section_a.name))
    offers = [m for m in sent if m["type"] == "buttons" and m["buttons"][0]["id"] == "report_misread"]
    assert len(offers) == 1 and "1400" in offers[0]["body"] and "1150" in offers[0]["body"]
    say(kind="button_reply", reply_id="report_misread")
    filed = next(m["body"] for m in sent if m["type"] == "text" and "report " in m["body"] and "TGSPDCL" in m["body"])
    ticket = filed.split("report ")[1].split(" ")[0]
    row = officer.get(f"/api/review/cases/{ticket}").json()
    assert row["bill_month"] == "2026-03"
    assert suggestions.get(ticket).corrected_present_reading == 1150


@pytest.mark.parametrize("language", sorted(PACKS))
def test_offer_copy_exists_in_every_language_and_never_names_staff(language):
    body = text(language, "misread_offer", month="March", printed="1400", next="1150", office="TGSPDCL")
    assert "1400" in body and "1150" in body and "TGSPDCL" in body
    assert "misread_offer" in PACKS[language].T and "btn_report_misread" in PACKS[language].T
    assert not re.search(r"\b(ae|officer|engineer|staff)\b", body, re.IGNORECASE)
    assert len(text(language, "btn_report_misread")) <= 20
