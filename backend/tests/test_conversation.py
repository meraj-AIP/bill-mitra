"""Drive the conversation the way a channel does, on the two real bills. Only the vision provider is scripted
(with what it actually returned for those bills); the gate, the engine, the history and the composer run for real."""

import asyncio
import secrets

import pytest

from app.core import service
from app.core.messages import Inbound
from app.core.trace import Event
from app.domain.conversation.lang import PACKS
from app.services.openai_client import ProviderError
from app.store import media
from tests.real import MAR_2024, OCT_2025, SOLAR_SEP_2026, reading, variant


def run(user: str, language: str = "en", **fields: object) -> list[Event]:
    events: list[Event] = []

    async def emit(event: Event) -> None:
        events.append(event)

    if fields.get("kind") == "image":
        fields = {"media_id": media.save(f"synthetic-photo-{secrets.token_hex(8)}".encode(), "image/jpeg"), "mime_type": "image/jpeg", **fields}
    inbound = Inbound(channel="web", user_id=user, **fields)  # type: ignore[arg-type]
    asyncio.run(service.handle(inbound, emit, language=language))
    return events


def messages(events: list[Event]) -> list:
    return [e.message for e in events if e.kind == "message"]


def bodies(events: list[Event]) -> str:
    return "\n".join(getattr(m, "body", "") or getattr(m, "caption", "") or "" for m in messages(events))


def new_user() -> str:
    return f"test-{secrets.token_hex(4)}"


def test_real_bills_are_verified_without_any_consent_prompt(reader):
    for real, payable in ((OCT_2025, "Rs 1,245"), (MAR_2024, "Rs 774")):
        reader(reading(real))
        events = run(new_user(), kind="image")
        text = bodies(events)
        assert "charges match the TGERC tariff" in text and payable in text
        assert "12 months" not in text
        trace = [e.trace for e in events if e.kind == "trace" and e.trace and e.trace.status == "done"]
        assert {t.mode for t in trace} >= {"ai", "rules", "channel"} and all(t.mode != "demo" for t in trace)


def test_overcharge_found_and_complaint_recorded_honestly(reader):
    user = new_user()
    reader(reading(variant(OCT_2025, charge=("energy", 140.0))))  # real bill, energy printed Rs 140 higher
    assert "Rs 140 more" in bodies(run(user, kind="image"))
    preview = bodies(run(user, kind="button_reply", reply_id="complain"))
    assert "Service number" in preview and "••••1111" in preview and "999900001111" not in preview
    filed = bodies(run(user, kind="button_reply", reply_id="complaint_send"))
    assert "BM-" in filed and "not connected to 1912" in filed


def test_other_document_is_refused(reader):
    reader(reading(None, kind="other_bill", reason="A shop receipt."))
    assert "does not look like an electricity bill" in bodies(run(new_user(), kind="image"))


def test_unreadable_photo_asks_again_then_accepts_typed_units(reader):
    user = new_user()
    reader(reading(None, quality="unreadable"))
    assert "could not read this photo clearly" in bodies(run(user, kind="image"))
    second = bodies(run(user, kind="text", text="214"))
    assert "calculated the bill for 214 units" in second and "Calculated" in second


def test_misread_customer_charge_is_never_trusted(reader):
    # What the live model returned for a tilted photo of the March 2024 slip: customer charge read as 9.42.
    reader(reading(variant(MAR_2024, line_items=[
        {**i.model_dump(), "amount": 9.42} if i.code == "customer" else i.model_dump() for i in MAR_2024.line_items])))
    text = bodies(run(new_user(), kind="image"))
    # The printed figures and the rules' gap are named; nothing is priced from a reading that does not add up.
    assert "add up to Rs 693.42, but the bill amount reads Rs 774, a gap of Rs 80.58" in text
    assert "charges in the middle of the slip" in text and "to pay" not in text


def test_blurred_units_are_not_guessed(reader):
    reader(reading(variant(OCT_2025, unreadable_fields=["units"], quality="poor")))
    assert "could not read the units" in bodies(run(new_user(), kind="image"))


def test_reading_off_without_a_key_says_so():
    assert "switched off" in bodies(run(new_user(), kind="image"))


def test_provider_failure_falls_back_to_typed_units(reader):
    reader(ProviderError("HTTPStatusError"))
    events = run(new_user(), kind="image")
    assert "type the units on your bill, for example: 214 units October 2025" in bodies(events)
    assert [b.id for b in messages(events)[-1].buttons] == ["retry_last", "type_units"]


def test_meter_photo_projects_from_the_last_real_bill(reader):
    user = new_user()
    reader(reading(OCT_2025))
    run(user, kind="image")
    reader(reading(variant(OCT_2025, document_type="meter", meter_reading=400.0), kind="meter"))
    assert "Meter reading 400" in bodies(run(user, kind="image"))


def test_earlier_upload_of_same_connection_becomes_history(reader):
    from app.flows.analysis import analyse

    user = new_user()
    reader(reading(MAR_2024))
    run(user, kind="image")
    history = analyse(OCT_2025, user).history
    assert [(h.month, h.units, h.source) for h in history] == [("2024-03", 157, "uploaded")]
    assert analyse(OCT_2025, new_user()).history == []  # another person's uploads never mix in


def test_non_domestic_bill_before_lt2_rates_is_not_audited(reader):
    reader(reading(variant(MAR_2024, is_domestic=False, category="LT-II Non-Domestic")))
    assert "not one I can check yet" in bodies(run(new_user(), kind="image"))


def test_solar_commercial_bill_is_checked_and_explained(reader):
    reader(reading(SOLAR_SEP_2026))
    said = bodies(run(new_user(), kind="image"))
    assert "commercial (LT-II)" in said and "sent 9 units to the grid" in said and "3092 net units" in said
    assert "Rs 545 from earlier bills is in your favour" in said and "-545" not in said


def test_sms_bill():
    sms = ("TGSPDCL: Dear Consumer, bill for USC 999900001111 for Oct-25: Units 138, "
           "Amt Rs 692.00, Due Dt 19-10-2025.")
    assert "Rs 692" in bodies(run(new_user(), kind="text", text=sms))


def test_off_topic_and_power_cut_get_fixed_replies():
    user = new_user()
    assert "only with your electricity bill" in bodies(run(user, kind="text", text="who will win the match"))
    assert "1912" in bodies(run(user, kind="text", text="power cut in my street"))


def test_question_without_bill_asks_for_bill():
    assert "send a photo of your bill first" in bodies(run(new_user(), kind="text", text="why so high"))


def test_what_if(reader):
    user = new_user()
    reader(reading(OCT_2025))
    run(user, kind="image")
    assert "At 230 units your bill would be about" in bodies(run(user, kind="text", text="what if 230 units"))


@pytest.mark.parametrize("word", ["STOP", "ఆపండి", "रोको", "بند کرو"])
def test_stop_forgets_in_every_language(reader, word):
    user = new_user()
    reader(reading(OCT_2025))
    run(user, kind="image")
    run(user, kind="text", text=word)
    assert "send a photo of your bill first" in bodies(run(user, kind="text", text="why so high"))


SCENARIOS = {
    "oct_2025": lambda: OCT_2025,
    "mar_2024": lambda: MAR_2024,
    "overcharged": lambda: variant(OCT_2025, charge=("energy", 140.0)),
    "non_domestic": lambda: variant(OCT_2025, is_domestic=False),
}


@pytest.mark.parametrize("language", sorted(PACKS))
@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_every_language_renders_every_scenario(reader, language, scenario):
    user = new_user()
    reader(reading(SCENARIOS[scenario]()))
    msgs = messages(run(user, language=language, kind="image"))
    assert msgs and all(m.language == language for m in msgs)
    for reply in ("why", "next", "save"):
        assert messages(run(user, language=language, kind="button_reply", reply_id=reply))


def test_buttons_fit_whatsapp_limits(reader):
    reader(reading(variant(OCT_2025, charge=("energy", 140.0))))
    for language in PACKS:
        for m in messages(run(new_user(), language=language, kind="image")):
            if m.type == "buttons":
                assert len(m.buttons) <= 3 and all(len(b.title) <= 20 for b in m.buttons)
                assert len(m.body) <= 1024
