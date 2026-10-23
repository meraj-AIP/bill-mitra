"""Soniox speaks first and Sarvam stands behind it. Soniox is faked at its HTTP boundary and Sarvam at its call, so
nothing leaves the machine; keys are obviously fake."""

import asyncio
import json
import secrets

import httpx
import pytest

from app.config import get_settings
from app.services import soniox_tts, tts

VOICES = [{"id": "Adrian", "description": "A calm voice with an American accent.", "gender": "male"},
          {"id": "Priya", "description": "A warm voice with an Indian accent.", "gender": "female"}]


def _models(languages: list[str]) -> dict[str, object]:
    return {"models": [{"id": "tts-rt-v2", "aliased_model_id": None, "name": "TTS v2",
                        "languages": [{"code": c, "name": c} for c in languages], "voices": VOICES}]}


@pytest.fixture
def soniox(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """A fake Soniox. Set "shared" for the accent filter's answer, "fail" to make speaking fail, "languages" for the list."""
    settings = get_settings()
    monkeypatch.setattr(settings, "soniox_api_key", "test-key-not-real")
    monkeypatch.setattr(settings, "soniox_tts_voice", "")
    state: dict[str, object] = {"shared": [], "fail": False, "languages": ["te", "en", "hi", "ur", "ta", "kn"], "spoken": []}

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/tts-models":
            return httpx.Response(200, json=_models(state["languages"]))  # type: ignore[arg-type]
        if request.url.path == "/v1/shared-voices":
            assert request.url.params["accent"] == "indian"
            return httpx.Response(200, json={"voices": state["shared"], "next_page_cursor": None})
        if request.url.path == "/tts":
            if state["fail"]:
                return httpx.Response(503, json={"error_type": "internal_error"})
            body = json.loads(request.content)
            state["spoken"].append((body["language"], body["voice"], body["text"]))  # type: ignore[union-attr]
            return httpx.Response(200, headers={"content-type": "audio/mpeg"}, content=b"ID3" + secrets.token_bytes(96))
        return httpx.Response(404)

    monkeypatch.setattr(soniox_tts, "client", lambda: httpx.AsyncClient(base_url="https://api.soniox.invalid",
                                                                        transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(get_settings(), "soniox_tts_url", "https://tts-rt.soniox.invalid/tts")
    soniox_tts.forget()
    yield state
    soniox_tts.forget()


@pytest.fixture
def sarvam(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    monkeypatch.setattr(get_settings(), "sarvam_api_key", "test-key-not-real")
    spoken: list[str] = []

    async def fake(_client: object, text: str, _code: str) -> bytes:
        spoken.append(text)
        return b"ID3" + secrets.token_bytes(64)

    monkeypatch.setattr(tts, "_synthesise", fake)
    return spoken


def _text() -> str:
    return f"Your bill is checked {secrets.token_hex(4)}."


def test_soniox_speaks_first_with_an_indian_voice(soniox, sarvam):
    soniox["shared"] = [{"id": "Arjun", "accent": "indian", "gender": "male"}]
    text = _text()
    assert asyncio.run(tts.speak(text, "te"))
    assert soniox["spoken"] == [("te", "Arjun", text)] and sarvam == []
    assert asyncio.run(tts.speak(text, "te")) and len(soniox["spoken"]) == 1  # kept, never paid for twice


def test_sarvam_takes_over_when_soniox_fails(soniox, sarvam):
    soniox["fail"] = True
    text = _text()
    assert asyncio.run(tts.speak(text, "hi")) and sarvam == [text]


def test_urdu_and_other_soniox_languages_get_a_voice_sarvam_lacks(soniox, sarvam):
    for language in ("ur", "ta"):
        assert asyncio.run(tts.speak(_text(), language))
    assert [s[0] for s in soniox["spoken"]] == ["ur", "ta"] and sarvam == []
    soniox["fail"] = True
    assert asyncio.run(tts.speak(_text(), "ur")) is None  # no Sarvam voice for Urdu, so text is sent


def test_a_language_soniox_does_not_list_goes_to_sarvam(soniox, sarvam):
    soniox["languages"] = ["en"]
    text = _text()
    assert asyncio.run(tts.speak(text, "te")) and sarvam == [text] and soniox["spoken"] == []


def test_the_voice_choice_prefers_the_accent_then_a_description_then_any():
    shared = [{"id": "Arjun", "accent": "indian"}]
    assert soniox_tts.choose_voice(shared, VOICES, "indian") == "Arjun"
    assert soniox_tts.choose_voice([], VOICES, "indian") == "Priya"
    assert soniox_tts.choose_voice([], VOICES[:1], "indian") == "Adrian"
    assert soniox_tts.choose_voice([], [], "indian") is None


def test_a_configured_voice_wins_and_no_accent_lookup_is_made(soniox, sarvam, monkeypatch):
    monkeypatch.setattr(get_settings(), "soniox_tts_voice", "Maya")
    soniox["shared"] = "not a list"  # would break the lookup if it were made
    assert asyncio.run(tts.speak(_text(), "en"))
    assert soniox["spoken"][0][1] == "Maya"


def test_a_reply_that_is_not_audio_is_not_kept_as_a_voice_note(soniox, sarvam, monkeypatch):
    async def bad(*_: object) -> bytes:
        raise ValueError("no audio in the reply")

    monkeypatch.setattr(soniox_tts, "synthesise", bad)
    text = _text()
    assert asyncio.run(tts.speak(text, "en")) and sarvam == [text]
