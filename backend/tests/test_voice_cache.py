"""Paid calls are made once: a sentence already spoken is never sent to Sarvam again, and the same bill sent again
reuses its checked explanation, so neither the language model nor Sarvam is paid twice. Nothing leaves the machine:
both providers are faked here."""

import asyncio
import json
import secrets

import pytest

from app.config import get_settings
from app.services import llm, tts
from app.store import media, voice_cache
from app.store.db import tx
from tests.real import OCT_2025, reading, variant
from tests.test_complaints import chat


@pytest.fixture
def sarvam(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Voice on with a fake Sarvam that records every text it is asked to speak."""
    monkeypatch.setattr(get_settings(), "sarvam_api_key", "test-key-not-real")
    spoken: list[str] = []

    async def fake(_client: object, text: str, _code: str) -> bytes:
        spoken.append(text)
        return b"ID3" + secrets.token_bytes(64)  # distinct bytes, so each clip is its own file

    monkeypatch.setattr(tts, "_synthesise", fake)
    return spoken


def test_a_sentence_already_spoken_is_not_paid_for_again(sarvam):
    text = f"Your bill is checked {secrets.token_hex(4)}."
    first = asyncio.run(tts.speak(text, "te"))
    again = asyncio.run(tts.speak(text, "te"))
    assert first and again == first and sarvam == [text]
    assert asyncio.run(tts.speak(text, "en")) != first and len(sarvam) == 2  # another language is another voice


def test_a_clip_the_retention_sweep_removed_is_made_again(sarvam):
    text = f"Due date passed {secrets.token_hex(4)}."
    [clip] = asyncio.run(tts.speak(text, "te"))
    path = media.path_for(clip)
    assert path is not None
    path.unlink()
    remade = asyncio.run(tts.speak(text, "te"))
    assert remade and remade != [clip] and sarvam == [text, text]
    assert asyncio.run(tts.speak(text, "te")) == remade and len(sarvam) == 2


def test_the_same_bill_sent_again_reuses_its_explanation_and_voice(reader, sarvam, monkeypatch):
    written: list[int] = []

    async def model(_facts: object, _language: str) -> str:
        written.append(1)
        return "Every charge on your bill matches the tariff."

    monkeypatch.setattr(llm, "explain", model)
    user = f"web:{secrets.token_hex(10)}"
    reader_bill = variant(OCT_2025, bill_month="2025-08")
    for _ in range(2):
        reader(reading(reader_bill))
        chat(user, "web", kind="image")
    assert len(written) == 1
    assert sarvam.count("Every charge on your bill matches the tariff.") == 1

    other = f"web:{secrets.token_hex(10)}"
    reader(reading(reader_bill))
    chat(other, "web", kind="image")
    assert len(written) == 2  # another consumer gets their own explanation, never someone else's


def test_erasing_an_account_removes_its_explanations():
    user = f"web:{secrets.token_hex(10)}"
    voice_cache.remember_explanation("k-" + secrets.token_hex(8), user, "Your bill is fine.")
    with tx() as conn:
        voice_cache.erase(conn, user)
        assert conn.execute("SELECT COUNT(*) FROM explain_cache WHERE user_id = ?", (user,)).fetchone()[0] == 0


def test_the_old_cache_file_moves_into_the_database(sarvam):
    key, clip = secrets.token_hex(16), media.save(b"ID3" + secrets.token_bytes(32), "audio/mpeg")
    legacy = get_settings().data_dir / "tts_index.json"
    legacy.write_text(json.dumps({key: [clip]}))
    with tx() as conn:
        voice_cache.ensure(conn)
    assert not legacy.exists() and voice_cache.voice(key) == [clip]
