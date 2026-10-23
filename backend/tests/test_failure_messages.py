"""Every failed read says what happened, which part, and what to do next (docs/errors-contract.md section 1). Only the
vision provider is scripted, with the real bills or one printed figure changed; the checks and the engine run."""

import asyncio
import io
import secrets
from datetime import date

import pytest
from PIL import Image

from app.core import service
from app.core.messages import Inbound
from app.core.trace import Event, TraceStep, public
from app.domain.conversation import composer
from app.domain.conversation.facts import rs
from app.domain.conversation.intents import parse_units
from app.domain.conversation.lang import PACKS
from app.flows import question
from app.flows.analysis import analyse
from app.services import llm, sms_parser, vision
from app.services.openai_client import ProviderError
from app.store import media, repos
from tests.real import OCT_2025, SOLAR_SEP_2026, reading, variant
from tests.test_conversation import bodies, messages, new_user, run


def buttons(events: list[Event]) -> list[tuple[str, str]]:
    last = [m for m in messages(events) if m.type == "buttons"][-1]
    return [(b.id, b.title) for b in last.buttons]


RETAKE = [("new_photo", "New photo"), ("type_units", "Type units")]
CHECKS = {
    "readings": (variant(OCT_2025, units=150),
                 "meter readings 213 to 351, which makes 138 units, but it says 150 units.",
                 [("units_pick:138", "138 units"), ("units_pick:150", "150 units"), ("new_photo", "New photo")]),
    "energy_units": (variant(OCT_2025, units=148, present_reading=361.0),
                     "The energy charge on your bill, Rs 518.20, matches 138 units, but I read the units as 148.",
                     [("units_pick:138", "138 units"), ("units_pick:148", "148 units"), ("new_photo", "New photo")]),
    "charges_sum": (variant(OCT_2025, bill_amount=792.0),
                    "add up to Rs 692, but the bill amount reads Rs 792, a gap of Rs 100. One of them is probably "
                    "misread. Please send a sharper photo of the charges in the middle of the slip.", RETAKE),
    "total": (variant(OCT_2025, total_payable=1345.0),
              "Bill amount Rs 692 plus arrears Rs 553 makes Rs 1,245, but the total due reads Rs 1,345. Please send "
              "a sharper photo of the total at the bottom of the slip.", RETAKE),
    "net_units": (variant(SOLAR_SEP_2026, billed_units=3000),
                  "Units from the grid (3101) minus units exported (9) make 3092, but I read the billed units as 3000.",
                  RETAKE),
    "export_readings": (variant(SOLAR_SEP_2026, billed_units=None, export_previous_reading=100.0,
                                export_present_reading=105.0),
                        "The solar export readings 100 to 105 make 5 units, but I read the units exported as 9.",
                        RETAKE),
}


@pytest.mark.parametrize("check", sorted(CHECKS))
def test_each_failed_check_names_the_printed_figures_and_offers_the_way_forward(reader, check):
    bill, said, expected = CHECKS[check]
    reader(reading(bill))
    user = new_user()
    events = run(user, kind="image")
    assert said in bodies(events) and buttons(events) == expected
    assert "to pay" not in bodies(events) and repos.get_user(user, "web").current_bill_id is None


def test_a_picked_unit_count_is_marked_as_the_consumers_and_priced_by_the_engine(reader):
    reader(reading(variant(OCT_2025, units=150)))
    user = new_user()
    run(user, kind="image")
    said = bodies(run(user, kind="button_reply", reply_id="units_pick:150"))
    assert "checked the bill with 150 units, as you confirmed" in said and "Units: 150" in said
    state = repos.get_user(user, "web")
    stored = repos.get_bill(state.current_bill_id or "")
    assert stored is not None
    bill = stored[0]
    assert (bill.units, bill.confirmed_by_consumer) == (150, ["units"])
    assert (bill.previous_reading, bill.present_reading) == (None, None)  # they gave 138, so one was misread
    a = analyse(bill, user)
    assert a.comp.units == 150 and f"Rs {rs(a.facts.total_payable)}" in said
    # The same tap again, or a count we never offered, prices nothing.
    assert "no longer open" in bodies(run(user, kind="button_reply", reply_id="units_pick:150"))


def test_a_count_that_was_not_offered_is_refused(reader):
    reader(reading(variant(OCT_2025, units=150)))
    user = new_user()
    run(user, kind="image")
    assert "no longer open" in bodies(run(user, kind="button_reply", reply_id="units_pick:999"))
    said = bodies(run(user, kind="button_reply", reply_id="units_pick:138"))
    stored = repos.get_bill(repos.get_user(user, "web").current_bill_id or "")
    assert "as you confirmed" in said and stored is not None and stored[0].previous_reading == 213.0


def test_a_model_cannot_claim_the_consumer_confirmed_anything():
    from app.domain.bill_normalise import to_bill

    assert to_bill({**OCT_2025.model_dump(), "confirmed_by_consumer": ["units"]}).confirmed_by_consumer == []


@pytest.mark.parametrize(("seen_discom", "bill_discom"), [("OTHER", "TGSPDCL"), ("TGSPDCL", "OTHER")])
def test_a_bill_from_outside_telangana_is_never_priced(reader, seen_discom, bill_discom):
    found = reading(variant(OCT_2025, discom=bill_discom))
    found.classification = found.classification.model_copy(update={"discom": seen_discom})
    reader(found)
    user = new_user()
    events = run(user, kind="image")
    assert "only TGSPDCL and TGNPDCL bills" in bodies(events) and "Rs" not in bodies(events)
    assert buttons(events) == [("new_photo", "Send my bill"), ("show_help", "Help")]
    assert repos.get_user(user, "web").current_bill_id is None


def _jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (40, 60), "white").save(out, format="JPEG")
    return out.getvalue()


def test_the_reader_stops_at_the_first_look_for_another_states_bill(monkeypatch):
    async def first_look(_jpeg: bytes) -> vision.Classification:
        return vision.Classification(document_type="electricity_bill", discom="OTHER")

    async def never(*_: object, **__: object) -> None:
        raise AssertionError("an outside bill is never read further")

    monkeypatch.setattr(vision, "classify", first_look)
    monkeypatch.setattr(vision, "extract", never)
    found = asyncio.run(vision.read_document(_jpeg(), "image/jpeg"))
    assert found.bill is None and found.classification.discom == "OTHER"


def test_a_file_that_will_not_open_says_so_with_what_works(reader):
    assert asyncio.run(vision.read_document(b"%PDF-1.4 broken", "application/pdf")).problem == "unopenable"
    reader(vision.Reading(vision.UNOPENABLE, None, problem="unopenable"))
    events = run(new_user(), kind="image")
    assert "could not open this file" in bodies(events) and "under 12 MB" in bodies(events)
    assert "does not look like" not in bodies(events)
    reader(vision.Reading(vision.UNOPENABLE, None, problem="too_long"))
    assert "could not find the bill in its first 3 pages" in bodies(run(new_user(), kind="image"))


def test_not_a_bill_offers_three_ways_forward(reader):
    reader(reading(None, kind="other", reason="A photo of logos."))
    events = run(new_user(), kind="image")
    assert buttons(events) == [("new_photo", "Send my bill"), ("type_units", "Type units"), ("show_help", "Help")]


def test_meter_photos_get_meter_words_and_a_kept_reading_waits_for_the_bill(reader):
    reader(reading(None, kind="meter"))
    said = bodies(run(new_user(), kind="image"))
    assert "meter display" in said and "flat" not in said
    user = new_user()
    reader(reading(variant(OCT_2025, document_type="meter", meter_reading=400.0), kind="meter"))
    assert "I read your meter: 400. I have kept it." in bodies(run(user, kind="image"))
    reader(reading(OCT_2025))
    assert "Meter reading 400" in bodies(run(user, kind="image"))  # projected once the bill arrived
    assert "Meter reading 400" not in bodies(run(user, kind="image"))  # and only once


@pytest.mark.parametrize(("units_field", "said"), [
    ("units", "could not read the units on this photo. They are near the top of the slip"),
    ("energy", "could not read the energy charge on this photo. It is in the middle of the slip"),
    ("bill_amount", "could not read the bill amount on this photo. It is near the bottom of the slip"),
])
def test_an_unreadable_figure_is_named_with_where_it_is(reader, units_field, said):
    reader(reading(variant(OCT_2025, unreadable_fields=[units_field])))
    events = run(new_user(), kind="image")
    assert said in bodies(events) and buttons(events) == RETAKE


def test_a_lost_upload_says_it_did_not_reach_us():
    said = bodies(run(new_user(), kind="image", media_id="0" * 24 + ".jpg", mime_type="image/jpeg"))
    assert "did not reach us" in said and "send a photo of your bill first" not in said


def test_every_typed_units_example_parses_in_its_own_language():
    for language, pack in PACKS.items():
        example = pack.T["read_failed"].rsplit(": ", 1)[1].rstrip(".।۔")
        assert parse_units(example) == 214, language
        assert sms_parser.typed_month(example) == "2025-10", language


def test_a_month_without_a_year_is_the_latest_such_month():
    today = date(2026, 3, 10)
    assert sms_parser.typed_month("214 units October", today) == "2025-10"
    assert sms_parser.typed_month("214 units march", today) == "2026-03"
    assert sms_parser.typed_month("214 యూనిట్లు అక్టోబర్", today) == "2025-10"
    assert sms_parser.typed_month("214", today) is None


def test_a_month_with_no_tariff_in_force_says_the_nearest_was_used(reader, monkeypatch):
    old = variant(OCT_2025, bill_month="2022-10")
    a = analyse(old, new_user())
    assert a.facts.tariff_nearest and not analyse(OCT_2025, new_user()).facts.tariff_nearest
    note = PACKS["en"].T["tariff_nearest"]
    assert note in composer.explain(a.facts, "en")

    async def written(*_: object, **__: object) -> str:
        return "Your bill is explained here."  # no figure, so the number guard passes it

    reader(reading(old))
    monkeypatch.setattr(llm, "explain", written)
    assert f"Your bill is explained here. {note}" in bodies(run(new_user(), kind="image"))


def test_the_generic_failure_has_a_reference_and_try_again_runs_the_same_message(monkeypatch):
    real = question.handle_text

    async def broken(*_: object, **__: object) -> None:
        raise RuntimeError("secret detail 9999999999")

    user = new_user()
    monkeypatch.setattr(question, "handle_text", broken)
    events = run(user, kind="text", text="who will win the match")
    sorry = messages(events)[-1]
    assert "something went wrong on our side" in sorry.body and "Reference " in sorry.body
    assert [b.id for b in sorry.buttons] == ["retry_last"]
    assert "secret detail" not in "".join(e.model_dump_json() for e in events)
    monkeypatch.setattr(question, "handle_text", real)
    assert "only with your electricity bill" in bodies(run(user, kind="button_reply", reply_id="retry_last"))
    assert "nothing waiting to try again" in bodies(run(user, kind="button_reply", reply_id="retry_last"))


def test_try_again_after_a_failed_read_reads_the_same_photo_again(reader):
    user = new_user()
    reader(ProviderError("HTTPStatusError"))
    run(user, kind="image")
    reader(reading(OCT_2025))
    assert "charges match the TGERC tariff" in bodies(run(user, kind="button_reply", reply_id="retry_last"))


def details(events: list[Event]) -> str:
    return " ".join(e.trace.detail or "" for e in events if e.kind == "trace" and e.trace)


def test_reading_off_is_said_without_naming_the_setting():
    off = details(run(new_user(), kind="image"))
    assert "switched off" in off and "OPENAI" not in off and "KEY" not in off


def test_the_web_chat_trace_never_carries_settings_models_or_raw_errors(reader, monkeypatch):
    reader(ProviderError("HTTPStatusError: 500 from api.openai.com"))
    failed = details(run(new_user(), kind="image"))
    assert "HTTPStatusError" not in failed and "openai" not in failed.lower()
    reader(reading(OCT_2025))
    monkeypatch.setattr(vision.get_settings(), "openai_vision_model", "model-name-not-shown")
    assert "model-name-not-shown" not in details(run(new_user(), kind="image"))
    step = TraceStep(id="s1", label="Speak", status="skipped", mode="ai",
                     detail="Voice unavailable: Sarvam key not set, Sarvam failed. SARVAM_API_KEY missing.")
    assert "key not set" not in (public(step).detail or "") and "SARVAM_API_KEY" not in (public(step).detail or "")


def test_a_failed_step_never_shows_the_error(monkeypatch):
    async def broken(*_: object, **__: object) -> None:
        raise RuntimeError("secret detail")

    events: list[Event] = []

    async def emit(event: Event) -> None:
        events.append(event)

    monkeypatch.setattr(service.stt, "transcribe", broken)
    data = media.save(b"synthetic-voice-" + secrets.token_bytes(4), "audio/ogg")
    asyncio.run(service.handle(Inbound(channel="web", user_id=new_user(), kind="audio", media_id=data,
                                       mime_type="audio/ogg"), emit, language="en"))
    failed = [e.trace for e in events if e.kind == "trace" and e.trace and e.trace.status == "failed"]
    assert failed and all(t.detail == "This step did not finish" for t in failed)
