"""A voice note never holds up the answer and is never lost: when it is not ready in time the words go at once and the
note follows from a voice job, a bill already explained plays its note at once, and the same photo is not read twice.
Soniox and the bill reader are faked; nothing leaves the machine."""

import asyncio
import secrets
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.config import get_settings
from app.domain.conversation.composer import plain
from app.flows import turn
from app.flows import voice as voice_flow
from app.services import soniox_tts, tts, vision
from app.store import voice_jobs
from app.store.db import tx
from tests.real import OCT_2025, reading
from tests.test_web_chat_parity import Device

LATER = timedelta(seconds=voice_jobs.FIRST_WAIT_S + 1)


@pytest.fixture
def voice(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Voice on. Set "slow" to make the next clips take longer than a turn waits, "fail" to make them fail."""
    monkeypatch.setattr(get_settings(), "soniox_api_key", "test-key-not-real")
    monkeypatch.setattr(turn, "WAIT_S", 0.05)
    with tx() as conn:  # each test makes its own notes; an earlier test's note for the same bill would play at once
        conn.execute("DELETE FROM tts_cache")
    state: dict[str, object] = {"slow": False, "fail": False, "spoken": [], "busy": 0, "most": 0}

    async def catalogue(_client: object) -> soniox_tts.Catalogue:
        return soniox_tts.Catalogue("Arjun", frozenset({"te", "en"}))

    async def fake(_client: object, text: str, _code: str, _voice: str) -> bytes:
        state["busy"] += 1  # type: ignore[operator]
        state["most"] = max(state["most"], state["busy"])  # type: ignore[call-overload]
        try:
            await asyncio.sleep(0.3 if state["slow"] else 0.01)
            if state["fail"]:
                raise httpx.ConnectError("synthetic failure")
            state["spoken"].append(text)  # type: ignore[union-attr]
            return b"ID3\x04\x00\x00\x00\x00\x00\x02ab" + secrets.token_bytes(64)
        finally:
            state["busy"] -= 1  # type: ignore[operator]

    monkeypatch.setattr(soniox_tts, "catalogue", catalogue)
    monkeypatch.setattr(soniox_tts, "synthesise", fake)
    return state


def _messages(events: list[dict]) -> list[dict]:
    return [e["message"] for e in events if e["kind"] == "message"]


def _run_voice(after: timedelta = LATER) -> int:
    return asyncio.run(voice_flow.run_due(datetime.now(UTC) + after))


def test_a_slow_voice_note_follows_the_words_and_the_same_bill_then_plays_at_once(sign_in, reader, voice):
    consumer = Device(sign_in)
    reader(reading(OCT_2025), reading(OCT_2025))
    voice["slow"] = True
    first = _messages(consumer.photo())
    assert not any(m["type"] == "audio" for m in first)
    explained = next(m["body"] for m in first if m["type"] == "text")  # the words went at once
    consumer.new_in_chat()
    voice["slow"] = False
    assert _run_voice() == 1
    [note] = [m for m in consumer.new_in_chat() if m["type"] == "audio"]
    assert note["transcript"] == plain(explained) and len(note["media_ids"]) == 1
    assert _run_voice(timedelta(hours=1)) == 0  # delivered once

    made = len(voice["spoken"])  # type: ignore[arg-type]
    again = _messages(consumer.photo())  # a new photo of the same bill: same explanation, same note
    assert any(m["type"] == "audio" for m in again) and len(voice["spoken"]) == made  # type: ignore[arg-type]


def test_the_same_photo_sent_again_is_not_read_again(sign_in, reader, monkeypatch, voice):
    consumer = Device(sign_in)
    reader(reading(OCT_2025))
    name, data, mime = b"bill.jpg", b"\xff\xd8\xff synthetic-photo-" + secrets.token_bytes(8), "image/jpeg"
    uploaded = consumer.client.post("/api/web/upload", files={"file": (name.decode(), data, mime)}).json()
    consumer.say(kind="image", media_id=uploaded["media_id"], mime_type=mime)
    reads: list[bytes] = []

    async def counted(photo: bytes, _mime: str) -> vision.Reading:
        reads.append(photo)
        raise AssertionError("read again")

    monkeypatch.setattr(vision, "read_document", counted)
    again = _messages(consumer.say(kind="image", media_id=uploaded["media_id"], mime_type=mime))
    assert reads == [] and any(m["type"] == "buttons" and "Bill checked" in m["body"] for m in again)


def test_a_voice_job_that_keeps_failing_is_parked_and_sends_nothing(sign_in, reader, voice):
    consumer = Device(sign_in)
    reader(reading(OCT_2025))
    voice["slow"] = voice["fail"] = True
    consumer.photo()
    consumer.new_in_chat()
    voice["slow"] = False
    for minutes in (1, 3, 9, 30):
        _run_voice(timedelta(minutes=minutes))
    assert not any(m["type"] == "audio" for m in consumer.new_in_chat())
    with tx() as conn:
        row = conn.execute("SELECT state, address FROM voice_jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                           (f"acct:{consumer.account.id}",)).fetchone()
    assert (row[0], row[1]) == ("failed", None)


def test_a_long_text_is_made_three_parts_at_a_time_and_joined_into_one_clip(voice):
    text = " ".join(f"Sentence {i} of the explanation, {secrets.token_hex(40)}." for i in range(8))
    [clip] = asyncio.run(tts.speak(text, "en"))
    assert len(voice["spoken"]) == len(tts.chunks(text)) > tts.PARALLEL and voice["most"] == tts.PARALLEL  # type: ignore[arg-type]
    first, second = b"ID3\x04\x00\x00\x00\x00\x00\x02ab" + b"one", b"ID3\x04\x00\x00\x00\x00\x00\x02cd" + b"two"
    assert tts.join([first, second]) == first + b"two"  # a tag in the middle would break decoding


def test_a_reply_without_audio_is_tried_again(monkeypatch: pytest.MonkeyPatch):
    replies = [httpx.Response(200, headers={"content-type": "application/json"}, content=b'{"error": "busy"}'),
               httpx.Response(200, headers={"content-type": "audio/mpeg"}, content=b"ID3" + secrets.token_bytes(96))]
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: replies.pop(0)))
    monkeypatch.setattr(get_settings(), "soniox_tts_url", "https://tts-rt.soniox.invalid/tts")
    assert asyncio.run(soniox_tts.synthesise(client, "Your bill is checked.", "en", "Arjun"))[:3] == b"ID3"
    assert replies == []
