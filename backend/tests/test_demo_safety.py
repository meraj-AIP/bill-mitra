"""Inputs that used to break a demo step now get the normal answer: impossible dates on a blurred photo, a model
reply in the wrong shape, a strange voice provider reply, an iPhone photo, a provider that hangs. Nothing leaves the
machine: every provider is faked."""

import asyncio
import io
import secrets
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pillow_heif import register_heif_opener
from pydantic import ValidationError

from app.config import get_settings
from app.core import retry, service, uploads
from app.core.messages import Inbound
from app.core.trace import Event
from app.domain.bill import ExtractedBill, UsagePoint, real_date, real_month
from app.main import app
from app.services import soniox_tts, stt, tts, vision
from app.services.openai_client import ProviderError
from app.store import media
from app.store.db import tx
from tests.real import OCT_2025, reading, variant
from tests.test_bills_api import PHOTO

register_heif_opener()


def _jpeg(width: int = 600, height: int = 800) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, "JPEG")
    return out.getvalue()


# Impossible dates from a blurred photo


@pytest.mark.parametrize(("value", "ok"), [("2025-02-28", True), ("2024-02-29", True), ("2025-02-30", False),
                                           ("2025-13-01", False), ("30/02/2025", False), (None, False)])
def test_real_date(value, ok):
    assert real_date(value) is ok


@pytest.mark.parametrize(("value", "ok"), [("2025-12", True), ("2025-13", False), ("2025-00", False), ("Oct-25", False)])
def test_real_month(value, ok):
    assert real_month(value) is ok


@pytest.mark.parametrize(("field", "value"), [("bill_month", "2025-13"), ("previous_reading_date", "2025-02-30"),
                                              ("disconnection_date", "2025-11-31"), ("last_paid_date", "2025-13-01")])
def test_the_bill_refuses_a_date_the_calendar_does_not_have(field, value):
    with pytest.raises(ValidationError):
        variant(OCT_2025, **{field: value})
    with pytest.raises(ValidationError):
        UsagePoint(month="2025-13", units=10)


def test_the_reader_drops_impossible_dates_and_keeps_the_rest_of_the_bill():
    raw = vision._clean({"units": 138, "bill_month": "2025-13", "previous_reading_date": "2025-02-30",
                         "billing_days": 31, "disconnection_date": "2025-11-04",
                         "usage_history": [{"month": "2025-13", "units": 5}, {"month": "2025-09", "units": 140}]})
    bill = ExtractedBill.model_validate(raw)
    assert bill.units == 138 and bill.bill_month is None and bill.previous_reading_date is None
    assert bill.disconnection_date == "2025-11-04" and [p.month for p in bill.usage_history] == ["2025-09"]
    assert bill.period() == 1.0  # no start date left, so the bill is priced as a plain month, not an error


# A model reply in the wrong shape


@pytest.mark.parametrize("shape", [{"line_items": 5}, {"line_items": {"energy": 518.2}}, {"usage_history": "none"},
                                   {"unreadable_fields": 7}, {"bill_month": 202510}])
def test_a_reply_in_the_wrong_shape_is_cleaned_not_a_crash(shape):
    bill = ExtractedBill.model_validate(vision._clean({"units": 138, **shape}))
    assert bill.units == 138 and bill.line_items == [] and bill.usage_history == []


def test_an_unreadable_reply_is_a_provider_error_the_caller_already_handles(monkeypatch):
    async def model(*_: object, **__: object) -> dict:
        return {"units": {"value": 138}, "line_items": 5}

    monkeypatch.setattr(vision, "chat_json", model)
    with pytest.raises(ProviderError):
        asyncio.run(vision.extract(_jpeg(), reading(OCT_2025).classification))


# Strange replies from the voice providers


def _fake_provider(monkeypatch: pytest.MonkeyPatch, module: object, body: object) -> None:
    real = httpx.AsyncClient

    def client(**kwargs: object) -> httpx.AsyncClient:
        return real(transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=body)), **kwargs)

    monkeypatch.setattr(module.httpx, "AsyncClient", client)  # type: ignore[attr-defined]


@pytest.mark.parametrize("body", [{"models": None}, {"models": []}, {"models": [5]}, [1, 2], "text"])
def test_a_strange_voice_reply_means_no_voice_note(monkeypatch, body):
    monkeypatch.setattr(get_settings(), "soniox_api_key", "test-key-not-real")
    soniox_tts.forget()
    _fake_provider(monkeypatch, soniox_tts, body)
    assert asyncio.run(tts.speak(f"Your bill is checked {secrets.token_hex(4)}.", "te")) is None


@pytest.mark.parametrize("body", [[1, 2], "text", 5])
def test_a_strange_transcription_reply_means_typed_questions(monkeypatch, body):
    monkeypatch.setattr(get_settings(), "soniox_api_key", "test-key-not-real")
    _fake_provider(monkeypatch, stt, body)
    assert asyncio.run(stt.transcribe(b"OggS-voice", "audio/ogg")) is None


def test_a_voice_failure_sends_the_explanation_as_text(reader, monkeypatch):
    async def broken(*_: object) -> list[str]:
        raise RuntimeError("anything at all")

    monkeypatch.setattr(tts, "speak", broken)
    reader(reading(variant(OCT_2025, bill_month="2025-07")))
    events: list[Event] = []

    async def emit(event: Event) -> None:
        events.append(event)

    inbound = Inbound(channel="web", user_id=f"web:{secrets.token_hex(10)}", kind="image",
                      media_id=media.save(_jpeg(), "image/jpeg"), mime_type="image/jpeg")
    asyncio.run(service.handle(inbound, emit, language="en"))
    sent = [e.message.type for e in events if e.kind == "message" and e.message]
    spoke = [e.trace for e in events if e.trace and e.trace.label == "Speak in the consumer's language"]
    assert "text" in sent and "buttons" in sent and "audio" not in sent
    assert spoke and spoke[-1].status == "skipped"


# iPhone photos


def test_an_iphone_photo_is_kept_as_a_jpeg_the_browser_can_show():
    out = io.BytesIO()
    Image.new("RGB", (64, 48), "white").save(out, format="HEIF")
    data, mime = asyncio.run(uploads.displayable(out.getvalue(), "image/heic"))
    assert mime == "image/jpeg" and data.startswith(b"\xff\xd8\xff")
    assert Image.open(io.BytesIO(data)).size == (64, 48)


def test_a_broken_iphone_photo_stays_as_it_came_for_the_reader_to_refuse():
    data, mime = asyncio.run(uploads.displayable(b"\x00\x00\x00\x18ftypheic-broken", "image/heic"))
    assert mime == "image/heic" and data.endswith(b"broken")


# A provider that hangs


def test_one_hanging_attempt_cannot_outlast_the_retry_budget():
    async def hangs() -> None:
        await asyncio.sleep(30)

    started = time.monotonic()
    with pytest.raises(TimeoutError):
        asyncio.run(retry.call(hangs, "test", retry.Policy(attempts=2, base_s=0.01, max_s=0.01, budget_s=0.05,
                                                           min_attempt_s=0.01)))
    assert time.monotonic() - started < 2


def test_an_attempt_near_the_end_of_the_budget_still_gets_its_floor(monkeypatch):
    # The floor, not what is left of the budget, decides how long a late attempt may run, so a WhatsApp send is not
    # cut off after Meta has taken it (the outbox would then send it again).
    given: list[float] = []
    real_wait_for = asyncio.wait_for

    async def wait_for(awaitable, timeout):  # noqa: ANN001
        given.append(timeout)
        return await real_wait_for(awaitable, timeout)

    calls = iter([httpx.ConnectError("down"), "ok"])

    async def flaky() -> str:
        result = next(calls)
        if isinstance(result, Exception):
            raise result
        return result

    ticks = iter([0.0, 0.0, 19.0, 19.0, 19.0])
    monkeypatch.setattr(retry, "clock", lambda: next(ticks, 19.0))
    monkeypatch.setattr(retry.asyncio, "wait_for", wait_for)

    async def no_wait(_s: float) -> None:
        return None

    monkeypatch.setattr(retry, "sleep", no_wait)
    policy = retry.Policy(attempts=3, base_s=0.1, max_s=0.1, budget_s=20.0, min_attempt_s=10.0)
    assert asyncio.run(retry.call(flaky, "test", policy)) == "ok"
    assert given == [20.0, 10.0]


def test_whatsapp_policies_give_each_attempt_a_real_floor():
    from app.channels.whatsapp import client

    assert client.SEND.min_attempt_s >= 10 and client.MEDIA.min_attempt_s >= 10
    assert client.ONCE.budget_s >= 10


def test_a_slow_read_hands_the_upload_to_a_job_instead_of_hanging(reader, sign_in, monkeypatch):
    reader(reading(OCT_2025))

    async def slow(_data: bytes, _mime: str) -> vision.Reading:
        await asyncio.sleep(30)
        return reading(OCT_2025)

    monkeypatch.setattr(vision, "read_document", slow)
    monkeypatch.setattr(get_settings(), "upload_read_deadline_s", 0.05)
    with TestClient(app) as client:
        sign_in(client)
        started = time.monotonic()
        answer = client.post("/api/bills", files=PHOTO, data={"language": "en"})
    job = answer.json()
    with tx() as conn:  # the queue tests count due jobs, so this one must not outlive the test
        conn.execute("DELETE FROM extract_jobs WHERE id = ?", (job["job_id"],))
    assert answer.status_code == 202 and job["status"] == "queued"
    assert time.monotonic() - started < 5
