"""Reading consumer messages: the rules on the labelled set, the hard cases, the model at its boundary (agree,
disagree, invalid JSON, low confidence), the one-question confirm, dedupe into an open complaint, and the follow-up
questions on WhatsApp and the web chat. Every message, number and service number is synthetic."""

import asyncio
import json
import secrets
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from app.config import get_settings
from app.core import service
from app.core.messages import ButtonsOut, Inbound
from app.core.trace import Event
from app.domain import complaint_types
from app.domain.complaint_options import STAFF_WORDS
from app.domain.conversation.intents import INTENTS, classify
from app.domain.conversation.lang import PACKS
from app.flows.understand import reconcile
from app.services import llm
from app.services.openai_client import ProviderError
from app.store import complaints as store

DATA = Path(__file__).parent / "data" / "messages.jsonl"
# Rules alone reach 214 of 233 (91.8%) on the set: 192 of 193 on the messages the rules were written against, 22 of
# 40 on the batch marked "untuned". Four of those 22 were fixed later on purpose (cuts that come and go, "when will
# the power come"), so the untouched rate is nearer 18 of 36. The floor sits a little below.
RULES_FLOOR = 0.90
LABELS = set(INTENTS) | set(complaint_types.BY_CODE)


def rows() -> list[dict[str, str]]:
    return [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(user: str, channel: str = "web", language: str = "en", **fields: object) -> list[Any]:
    events: list[Event] = []

    async def emit(event: Event) -> None:
        events.append(event)

    reply_to = "919999999002" if channel == "whatsapp" else None
    inbound = Inbound(channel=channel, user_id=user, reply_to=reply_to, **fields)  # type: ignore[arg-type]
    asyncio.run(service.handle(inbound, emit, language=language))
    return [e.message for e in events if e.kind == "message" and e.message is not None]


def text(user: str, said: str, channel: str = "web") -> list[Any]:
    return run(user, channel, kind="text", text=said)


def tap(user: str, reply_id: str, channel: str = "web") -> list[Any]:
    return run(user, channel, kind="button_reply", reply_id=reply_id)


def ids(message: Any) -> list[str]:
    return [b.id for b in message.buttons] if isinstance(message, ButtonsOut) else []


def new_user(channel: str = "web") -> str:
    return f"{'wa' if channel == 'whatsapp' else 'web'}:{secrets.token_hex(8)}"


def reading(intent: str = "complain", complaint_type: str | None = None, confidence: float = 0.9,
            **details: object) -> dict[str, object]:
    is_complaint = intent in ("complain", "dispute", "power_cut")
    return {"intent": intent, "is_complaint": is_complaint, "complaint_type": complaint_type, "details": details,
            "confidence": confidence}


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """The provider call scripted: each call takes the next reply; an exception is raised as the client would."""
    monkeypatch.setattr(get_settings(), "openai_api_key", "test-key-not-real")
    replies: list[object] = []

    async def fake(_model: str, _system: str, content: str, **_: object) -> object:
        assert "999" not in content  # long numbers are masked before anything leaves
        reply = replies.pop(0) if len(replies) > 1 else replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(llm, "chat_json", fake)
    return replies


# The labelled set


def test_labelled_set_is_big_varied_and_valid():
    data = rows()
    assert len(data) >= 150
    assert {r["label"] for r in data} <= LABELS
    assert set(complaint_types.BY_CODE) <= {r["label"] for r in data}
    assert {"en", "te", "te_rom", "hi", "ur", "mixed"} <= {r["lang"] for r in data}
    assert sum("negation" in r.get("note", "") for r in data) >= 10


def test_rules_alone_reach_the_accuracy_floor():
    data = rows()
    right = Counter(r["label"] for r in data if classify(r["text"]).label == r["label"])
    accuracy = sum(right.values()) / len(data)
    assert accuracy >= RULES_FLOOR, f"rules-only accuracy {accuracy:.3f}"


# Hard cases for the rules


@pytest.mark.parametrize(("message", "label"), [
    ("I don't want to complain, just tell me why the bill is high", "why_high"),
    ("No complaint, thanks", "thanks"),
    ("ఫిర్యాదు వద్దు, బిల్లు ఎందుకు ఎక్కువ వచ్చిందో చెప్పండి", "why_high"),
    ("शिकायत नहीं करनी, बस बिल समझना है", "off_topic"),
    ("کوئی شکایت نہیں، شکریہ", "thanks"),
    ("The meter is not burnt, but it is running fast", "meter_issue"),
    ("मीटर जला नहीं है पर तेज़ चल रहा है", "meter_issue"),
    ("No power cut today, all good", "off_topic"),
    ("I have not paid yet, when is the due date?", "due"),
])
def test_negation(message, label):
    assert classify(message).label == label


@pytest.mark.parametrize(("message", "label"), [
    ("Why is my bill so high?", "why_high"),
    ("My bill is too high this month, please check it", "high_bill"),
    ("బిల్లు ఎందుకు ఇంత ఎక్కువ వచ్చింది?", "why_high"),
    ("ఈ నెల బిల్లు చాలా ఎక్కువ వచ్చింది, చెక్ చేయండి", "high_bill"),
    ("बिल इतना ज़्यादा क्यों आया?", "why_high"),
    ("इस बार बिल बहुत ज़्यादा आया है, कृपया जाँच करें", "high_bill"),
    ("بل اتنا زیادہ کیوں آیا؟", "why_high"),
    ("اس مہینے بل بہت زیادہ آیا ہے، براہ کرم چیک کریں", "high_bill"),
    ("Why is there no power?", "power_outage"),  # a question in form, a report in fact
])
def test_questions_and_reports(message, label):
    assert classify(message).label == label


@pytest.mark.parametrize(("message", "label"), [
    ("What is the fixed charge?", "explain_fixed"),
    ("My meter got fixed yesterday, thanks", "thanks"),
    ("Problem is fixed now, thank you", "thanks"),
    ("The prefixed amount on the bill, what does it mean", "off_topic"),
    ("Is the highway open today?", "off_topic"),
])
def test_words_inside_other_words(message, label):
    assert classify(message).label == label


@pytest.mark.parametrize(("message", "label"), [
    ("I paid through PhonePe but the payment is not updated", "payment_not_updated"),
    ("paid via gpay yesterday, not reflecting", "payment_not_updated"),
    ("paytm lo kattanu, inka pending ani chupistundi", "payment_not_updated"),
    ("मैंने फोनपे से भुगतान कर दिया, पर अपडेट नहीं हुआ", "payment_not_updated"),
    ("Can I pay my bill with Google Pay?", "due"),
    ("How can I pay through Paytm?", "due"),
])
def test_payment_app_names(message, label):
    assert classify(message).label == label


@pytest.mark.parametrize(("message", "label"), [
    ("Frequent power cuts in our area every day", "supply_other"),
    ("current malli malli potundi", "supply_other"),
    ("కరెంటు వస్తూ పోతూ ఉంది", "supply_other"),
    ("दिन में बार बार बिजली जाती है", "supply_other"),
    ("light aati jaati rehti hai poore din", "supply_other"),
    ("روز شام بجلی چلی جاتی ہے", "supply_other"),
    ("current pothundi roju sayantram", "supply_other"),
    ("No power at my house since morning", "power_outage"),
    ("बिजली कब आएगी? 4 घंटे हो गए", "power_outage"),
    ("bijli kab aayegi, 4 ghante ho gaye", "power_outage"),
    ("صبح سے بجلی نہیں ہے", "power_outage"),
])
def test_cuts_that_come_and_go_against_no_power_now(message, label):
    assert classify(message).label == label


def test_a_generic_complaint_records_whether_its_words_point_at_a_type():
    assert not classify("I have a complaint").evidence
    assert not classify("ఫిర్యాదు చేయాలి").evidence and not classify("مجھے شکایت درج کرنی ہے").evidence
    found = classify("I have a complaint about the meter")
    assert (found.label, found.evidence) == ("complain", True)


def test_stop_only_when_it_is_the_whole_message():
    assert classify("STOP").intent == "stop" and classify("ఆపండి").intent == "stop"
    assert classify("please don't stop the supply").intent != "stop"


# Reconcile, pure


def _read(**fields: object) -> llm.Reading:
    return llm.Reading.model_validate(reading(**fields))  # type: ignore[arg-type]


def test_reconcile_acts_when_they_agree_or_one_is_silent():
    rules = classify("No power at my house since morning")
    agreed = reconcile(rules, _read(complaint_type="power_outage", whole_area=False))
    assert (agreed.complaint_type, agreed.by, agreed.ask_about) == ("power_outage", "both", None)
    assert agreed.details == {"whole_area": False}
    silent = classify("the thing outside our gate is sparking")
    assert not silent.matched
    filled = reconcile(silent, _read(complaint_type="meter_burnt"))
    assert (filled.intent, filled.complaint_type, filled.by) == ("complain", "meter_burnt", "model")
    assert reconcile(rules, None).complaint_type == "power_outage"


def test_reconcile_asks_when_they_disagree_or_both_are_unsure():
    question = classify("Why is my bill so high?")
    differ = reconcile(question, _read(intent="dispute", complaint_type="high_bill"))
    assert differ.ask_about == "high_bill" and differ.question == "why_high"
    unsure = reconcile(classify("the thing outside our gate is sparking"), _read(complaint_type="meter_burnt",
                                                                                   confidence=0.5))
    assert unsure.ask_about == "meter_burnt"
    # An unsure model next to a rule that matched is as good as silent.
    kept = reconcile(classify("My meter is burnt"), _read(intent="why_high", confidence=0.4))
    assert (kept.complaint_type, kept.ask_about) == ("meter_burnt", None)
    # A bare complaint says nothing about its type: the model's guess is not taken, the consumer picks.
    for bare in ("I have a complaint", "ఫిర్యాదు చేయాలి", "مجھے شکایت درج کرنی ہے"):
        kept = reconcile(classify(bare), _read(complaint_type="supply_other"))
        assert (kept.intent, kept.complaint_type, kept.ask_about) == ("complain", None, None), bare
    # The words point at a type the rules could not name: the model's guess becomes the question.
    asked = reconcile(classify("I have a complaint about the meter"), _read(complaint_type="meter_issue"))
    assert asked.ask_about == "meter_issue" and asked.complaint_type is None


# The model at its boundary


@pytest.mark.parametrize("reply", [
    ProviderError("JSONDecodeError"),
    ["not", "an", "object"],
    reading() | {"intent": "book_a_flight"},
    reading(complaint_type="meter_melted"),
    reading(confidence=1.5),
    reading() | {"units": 3},  # no keys outside the contract
    reading("why_high") | {"is_complaint": True},  # a question cannot be a complaint
    reading("why_high", "high_bill"),  # a type needs is_complaint
    reading(complaint_type="power_outage", since="since 3 days"),  # details only from the fixed lists
    reading() | {"confidence": "0.9"},
])
def test_model_answers_outside_the_lists_are_dropped(model, reply):
    model.append(reply)
    assert asyncio.run(llm.classify("No power at my house since morning")) is None


def test_model_masks_numbers_and_reads_valid_answers(model):
    model.append(reading("dispute", "wrong_reading", 0.85))
    found = asyncio.run(llm.classify("reading wrong for USC 999988887777"))
    assert found is not None and found.label == "wrong_reading"


def test_chat_with_an_agreeing_model_skips_what_it_already_knows(model):
    model.append(reading(complaint_type="power_outage", whole_area=True))
    user = new_user()
    said = text(user, "No power at my house since morning")
    assert "1912" in said[0].body and ids(said[-1]) == ["cdis:TGSPDCL", "cdis:TGNPDCL"]
    tap(user, "cdis:TGSPDCL")
    asked = tap(user, "cusc_skip")[-1]
    assert "Since when" in asked.body
    preview = text(user, "since morning")[-1]
    assert ids(preview) == ["cdraft_send", "cdraft_cancel"] and "Where: Whole street" in preview.body


def test_chat_with_a_disagreeing_model_asks_one_question(model):
    model.append(reading("dispute", "high_bill"))
    user = new_user()
    asked = text(user, "Why is my bill so high?")[-1]
    assert ids(asked) == ["uconf:yes", "uconf:other", "uconf:question"] and "Bill is too high" in asked.body
    assert all(len(b.title) <= 20 for b in asked.buttons)
    assert "send a photo of your bill first" in tap(user, "uconf:question")[-1].body
    text(user, "Why is my bill so high?")
    assert ids(tap(user, "uconf:yes")[-1]) == ["cdis:TGSPDCL", "cdis:TGNPDCL"]
    text(user, "Why is my bill so high?")
    assert ids(tap(user, "uconf:other")[-1]) == ["ccat:billing", "ccat:meter", "ccat:supply"]
    tap(user, "ccat:billing")
    tap(user, "ctype:high_bill")
    tap(user, "cdis:TGNPDCL")
    asked = tap(user, "cusc_skip")[-1]
    assert "Since which month" in asked.body  # their first words are the description, so it is not asked again


def test_chat_with_a_bare_complaint_shows_the_categories_whatever_the_model_says(model):
    model.append(reading(complaint_type="supply_other"))
    for bare in ("I have a complaint", "ఫిర్యాదు చేయాలి", "مجھے شکایت درج کرنی ہے"):
        assert ids(text(new_user(), bare)[-1]) == ["ccat:billing", "ccat:meter", "ccat:supply"], bare
    model[0] = reading(complaint_type="meter_issue")
    asked = text(new_user(), "I have a complaint about the meter")[-1]
    assert ids(asked) == ["uconf:yes", "uconf:other", "uconf:question"] and "Meter not working" in asked.body


def test_model_prompt_defines_every_type():
    assert set(llm.TYPE_MEANINGS) == set(complaint_types.BY_CODE)
    assert all(meaning in llm._system() for meaning in llm.TYPE_MEANINGS.values())


def test_chat_with_invalid_model_json_falls_back_to_the_rules(model):
    model.append(ProviderError("JSONDecodeError"))
    assert ids(text(new_user(), "మా ఇంట్లో కరెంటు లేదు")[-1]) == ["cdis:TGSPDCL", "cdis:TGNPDCL"]


def test_chat_with_a_low_confidence_model_and_silent_rules_asks(model):
    model.append(reading(complaint_type="meter_burnt", confidence=0.5))
    asked = text(new_user(), "the thing outside our gate is sparking")[-1]
    assert ids(asked) == ["uconf:yes", "uconf:other", "uconf:question"]
    model[0] = reading("thanks", confidence=0.4)
    user = new_user()
    assert "Happy to help" in text(user, "thank you")[-1].body


# Dedupe and follow-ups


def _raise_outage(user: str, channel: str, usc: str | None = None) -> None:
    text(user, "No power at my house since morning", channel)
    tap(user, "cdis:TGNPDCL", channel)
    if usc:
        text(user, usc, channel)
    else:
        tap(user, "cusc_skip", channel)
    tap(user, "cfq_skip", channel)
    tap(user, "cfq_skip", channel)
    tap(user, "cdraft_send", channel)


def test_a_repeat_joins_the_open_complaint_and_says_so():
    user = new_user()
    _raise_outage(user, "web")
    first = store.page(1, 5, owner=user)
    assert first.total == 1
    ticket = first.items[0]["ticket"]
    said = text(user, "still no power, please send someone")[-1].body
    assert ticket in said and "added your message" in said and not STAFF_WORDS.search(said)
    assert store.page(1, 5, owner=user).total == 1
    assert store.messages(ticket)[-1]["body"] == "still no power, please send someone"
    # A different type is a new complaint.
    text(user, "My meter is not working")
    assert ids(tap(user, "cdis:TGNPDCL")[-1]) == ["cusc_skip"]


def test_a_repeat_with_another_service_number_is_a_new_complaint():
    user = new_user()
    _raise_outage(user, "web", "999911112222")
    text(user, "No power at my house since morning")
    tap(user, "cdis:TGNPDCL")
    text(user, "999933334444")
    tap(user, "cfq_skip")
    tap(user, "cfq_skip")
    assert "BM-" in tap(user, "cdraft_send")[-1].body
    assert store.page(1, 5, owner=user).total == 2


def _payment_flow(channel: str) -> tuple[list[tuple[str, list[str]]], str]:
    user = new_user(channel)
    steps = [("text", "I paid through PhonePe but the payment is not updated"), ("tap", "cdis:TGSPDCL"),
             ("tap", "cusc_skip"), ("text", "yesterday evening"), ("tap", "cfq:upi_app"), ("tap", "cfq:no")]
    seen = []
    for kind, value in steps:
        out = (text if kind == "text" else tap)(user, value, channel)[-1]
        seen.append((out.body, ids(out)))
    filed = tap(user, "cdraft_send", channel)[-1].body
    ticket = store.page(1, 5, owner=user).items[0]["ticket"]
    assert ticket in filed
    return seen, str(store.row(ticket)["description"])


def test_follow_ups_are_the_same_on_whatsapp_and_the_web_chat():
    web, web_description = _payment_flow("web")
    whatsapp, whatsapp_description = _payment_flow("whatsapp")
    assert web == whatsapp and web_description == whatsapp_description
    assert [b for _, b in web][2:] == [["cfq_skip"], ["cfq:upi_app", "cfq:counter", "cfq_skip"],
                                       ["cfq:yes", "cfq:no", "cfq_skip"], ["cdraft_send", "cdraft_cancel"]]
    assert "Paid by: UPI or payment app" in web[-1][0]
    assert web_description == ("I paid through PhonePe but the payment is not updated\nPaid on: yesterday evening\n"
                               "Paid by: UPI or payment app\nHas a receipt or UTR: No")


@pytest.mark.parametrize("language", sorted(PACKS))
def test_follow_ups_in_every_language_fit_whatsapp(language):
    user = new_user()
    run(user, language=language, kind="text", text="My meter is burnt")
    run(user, language=language, kind="button_reply", reply_id="cdis:TGSPDCL")
    asked = run(user, language=language, kind="button_reply", reply_id="cusc_skip")[-1]
    assert ids(asked) == ["cfq:yes", "cfq:no", "cfq_skip"] and all(len(b.title) <= 20 for b in asked.buttons)
    run(user, language=language, kind="button_reply", reply_id="cfq:yes")
    preview = run(user, language=language, kind="button_reply", reply_id="cfq_skip")[-1]
    assert ids(preview) == ["cdraft_send", "cdraft_cancel"] and len(preview.body) <= 1024
    assert all(m.language == language for m in [asked, preview])


def test_new_copy_is_in_every_language_and_never_names_staff():
    keys = [k for k in PACKS["en"].T if k.startswith(("uconf_", "btn_uconf_", "cflow_urgent", "cflow_added",
                                                      "cfq_", "fq_", "fqv_"))]
    assert len(keys) == 54
    for pack in PACKS.values():
        for key in keys:
            assert key in pack.T, (pack.CODE, key)
            assert not STAFF_WORDS.search(pack.T[key]), (pack.CODE, key)
            assert "\u2013" not in pack.T[key] and "\u2014" not in pack.T[key]
            if key.startswith(("btn_", "fqv_")):
                assert len(pack.T[key]) <= 20, (pack.CODE, key)
