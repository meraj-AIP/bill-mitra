"""Text, voice and button replies. Answers come from a fixed intent set over the engine's facts."""

from app.domain.conversation import composer
from app.domain.conversation.facts import rs
from app.domain.conversation.intents import Intent, classify, parse_units, says_no_bills
from app.domain.conversation.lang import text
from app.domain.tariff.engine import compute
from app.flows import bill as bill_flow
from app.flows import case_bills, cases, complaint
from app.flows.analysis import Analysis, analyse, gruha_jyothi_eligible
from app.flows.turn import Turn
from app.services import llm, sms_parser
from app.store import repos

NO_BILL_NEEDED = {"greeting": "greeting", "thanks": "thanks", "power_cut": "power_cut",
                  "new_connection": "new_connection", "help": "help", "off_topic": "off_topic"}
BUTTON_INTENTS: dict[str, Intent] = {"why": "why_high", "next": "next_bill", "save": "save", "complain": "complain"}


def _current(turn: Turn) -> Analysis | None:
    if not turn.state.current_bill_id:
        return None
    stored = repos.get_bill(turn.state.current_bill_id)
    # A revised bill is answered with its revised figures, which the facts carry for the number guard.
    return cases.with_final(analyse(stored[0], turn.state.user_id), turn.state.current_bill_id) if stored else None


def _answer(intent: Intent, a: Analysis, lang: str, units: int | None) -> str:
    f = a.facts
    if intent == "why_high":
        return composer.why_high(f, lang)
    if intent == "next_bill":
        return composer.next_bill(f, lang)
    if intent == "save":
        return composer.save_advice(f, lang)
    if intent == "gruha_jyothi":
        return composer.gruha_jyothi(f, lang)
    if intent == "due":
        return composer.due(f, lang)
    if intent.startswith("explain_"):
        return composer.explain_charge(f, lang, intent.removeprefix("explain_"))
    if intent == "what_if" and units is not None:
        amount = compute(units, a.bill.month_date(), a.bill.load_kw or 1.0, gruha_jyothi_eligible(a.bill),
                         category=a.comp.category).net
        return text(lang, "what_if", units=units, amount=rs(amount))
    return composer.why_high(f, lang)


async def _classify(turn: Turn, message: str) -> tuple[Intent, int | None]:
    async with turn.tracer.step("Understand the question", "rules") as step:
        found = classify(message)
        intent, units = found.intent, found.units
        if intent == "off_topic":
            by_model = await llm.classify(message)
            if by_model:
                intent, units = by_model
                step.note(f"Intent '{intent}' (language model, constrained to the fixed list)", "ai")
                return intent, units
        step.note(f"Intent '{intent}' from the fixed list" + (f", units {units}" if units else ""))
    return intent, units


async def _reply(turn: Turn, body: str) -> None:
    if turn.voice_reply:
        await turn.speak(body)
    await turn.say(body)


# Exact words only, so "don't stop the supply" is not read as a request to delete data.
STOP_WORDS = {"stop", "ఆపండి", "ఆపు", "रोको", "बंद करो", "بند کرو", "روکو"}


async def handle_text(turn: Turn, message: str) -> None:
    lowered = message.strip().lower()
    if lowered.strip(" .!") in STOP_WORDS:
        repos.forget_user(turn.state.user_id)
        turn.state.current_bill_id = None
        await turn.say_key("stop")
        return
    units = parse_units(message)
    if units is not None and (turn.state.awaiting == "units" or not turn.state.current_bill_id):
        await turn.say_key("units_read", units=units)
        await bill_flow.handle_bill(turn, sms_parser.manual(units, message), None)
        return
    if sms_parser.looks_like_sms(message):
        parsed = sms_parser.parse(message)
        if parsed is None:
            await turn.say_key("sms_failed")
            return
        await bill_flow.handle_bill(turn, parsed, None)
        return
    if says_no_bills(message) and await case_bills.no_bills_from_chat(turn):
        return
    intent, what_if_units = await _classify(turn, message)
    await answer_intent(turn, intent, what_if_units)


async def answer_intent(turn: Turn, intent: Intent, units: int | None = None) -> None:
    repos.log_event(turn.inbound.channel, "question", language=turn.lang, intent=intent)
    if intent in NO_BILL_NEEDED:
        await _reply(turn, turn.t(NO_BILL_NEEDED[intent]))
        return
    a = _current(turn)
    if a is None:
        await turn.say_key("need_bill")
        return
    if intent == "complain":
        await complaint.preview(turn, a)
        return
    if intent == "dispute":
        await cases.report_from_chat(turn, a)
        return
    async with turn.tracer.step("Answer from the engine's figures", "rules") as step:
        body = _answer(intent, a, turn.lang, units)
        step.note(f"Template '{intent}' filled with computed values; no free-form generation")
    await _reply(turn, body)


async def handle_button(turn: Turn, reply_id: str) -> None:
    if reply_id in BUTTON_INTENTS:
        await answer_intent(turn, BUTTON_INTENTS[reply_id])
        return
    if reply_id == "type_units":
        turn.state.awaiting = "units"
        await turn.say_key("ask_units")
        return
    a = _current(turn)
    if a is None:
        await turn.say_key("need_bill")
        return
    if reply_id == "complaint_send":
        await complaint.submit(turn, a)
    elif reply_id == "report_bill":
        await cases.report_from_chat(turn, a)
    elif reply_id == "report_misread":
        await cases.report_misread(turn)
    elif reply_id == "complaint_cancel":
        turn.state.awaiting = None
        await turn.say_key("complaint_cancel")

