"""Understanding a consumer's free text: the rules, then the model when one is configured, then one decision.

Rules and model agree, or one is sure and the other silent: act. They disagree about a complaint, or both are unsure:
ask the consumer one question with buttons. The model only ever picks from fixed lists, and nothing it says is copied
into a reply; its details can only pre-answer a follow-up question with a fixed value.
"""

from dataclasses import dataclass, field

from app.domain.complaint_types import BY_CODE
from app.domain.conversation.intents import COMPLAINT_INTENTS, DISPUTE_TYPES, INTENTS, Classified, Intent, classify
from app.flows import complaint_chat
from app.flows.turn import Turn
from app.services import llm
from app.services.llm import Reading
from app.store import chat_drafts

SURE = 0.8
CONFIRM = "uconf:"
SAID_MAX = 1000
_NOT_A_QUESTION = COMPLAINT_INTENTS | {"off_topic", "stop"}


@dataclass(frozen=True)
class Decision:
    intent: Intent
    complaint_type: str | None = None
    units: int | None = None
    details: dict[str, object] = field(default_factory=dict)
    ask_about: str | None = None  # a complaint type to confirm with the consumer before acting
    question: Intent | None = None  # what to answer if they say it was just a question
    by: str = "rules"
    said: str | None = None

    @property
    def label(self) -> str:
        return f"confirm:{self.ask_about}" if self.ask_about else self.complaint_type or self.intent


def _complaint_intent(code: str) -> Intent:
    return "dispute" if code in DISPUTE_TYPES else "complain"


def _rules(r: Classified, by: str = "rules", details: dict[str, object] | None = None) -> Decision:
    return Decision(r.intent, r.complaint_type, r.units, details or {}, by=by)


def _model(m: Reading) -> Decision:
    details = m.details.model_dump(exclude_none=True)
    code = m.complaint_type or ("power_outage" if m.intent == "power_cut" else None)
    return Decision(_complaint_intent(code) if code else m.intent, code, None, details, by="model")


def _question(r: Classified, m: Reading) -> Intent | None:
    return next((i for i in (r.intent, m.intent) if i not in _NOT_A_QUESTION), None)


def reconcile(r: Classified, m: Reading | None) -> Decision:
    if m is None or r.intent == "stop":
        return _rules(r)
    if m.label == r.label:
        return _rules(r, "both", m.details.model_dump(exclude_none=True))
    sure = m.confidence >= SURE
    silent = not r.matched and not r.negated
    if not sure:
        if silent and m.complaint_type:
            return Decision(r.intent, ask_about=m.complaint_type, question=_question(r, m), by="both")
        return _rules(r)  # an unsure model is as good as silent next to a rule that matched
    if r.label == "complain" and m.complaint_type:
        # "I have a complaint" says nothing about the type, so the consumer picks it; when the words do point at
        # one, the model's guess is put to them as a question rather than acted on.
        if not r.evidence:
            return _rules(r)
        return Decision(r.intent, ask_about=m.complaint_type, by="both")
    if silent:
        return _model(m)  # the model fills a silence
    if r.complaint_type and m.is_complaint and not m.complaint_type:
        return _rules(r, "both")
    ask_about = m.complaint_type or r.complaint_type
    if ask_about:
        return Decision(r.intent, r.complaint_type, r.units, ask_about=ask_about, question=_question(r, m), by="both")
    return _rules(r)  # two different bill questions: the rules' answer is the checked one


def _note(r: Classified, m: Reading | None, d: Decision) -> str:
    said = f"Rules: '{r.label}'" + (" (said it is not a complaint)" if r.negated else "")
    said += f"; model: '{m.label}', confidence {m.confidence:.2f}" if m else "; model off or its answer was unusable"
    if d.ask_about:
        return said + f". They differ, so we ask the consumer about '{d.ask_about}'"
    return said + f". Acting on '{d.label}' ({d.by})"


async def read(turn: Turn, message: str) -> Decision:
    async with turn.tracer.step("Understand the message", "rules") as step:
        r = classify(message)
        m = await llm.classify(message)
        decision = reconcile(r, m)
        step.note(_note(r, m, decision), "ai" if m else None)
    return decision


async def ask(turn: Turn, decision: Decision, message: str) -> None:
    """One question with three buttons. The draft keeps their words so the complaint does not need them again."""
    code = str(decision.ask_about)
    chat_drafts.save(turn.state.user_id, {"flow": "confirm", "type": code, "said": message.strip()[:SAID_MAX],
                                          "question": decision.question})
    turn.state.awaiting = None
    await turn.buttons(turn.t("uconf_ask", type=turn.t(BY_CODE[code].label_key)),
                       [(CONFIRM + "yes", "btn_uconf_yes"), (CONFIRM + "other", "btn_uconf_other"),
                        (CONFIRM + "question", "btn_uconf_question")])


async def on_confirm(turn: Turn, reply_id: str) -> Decision | None:
    """The consumer's answer to the question. Returns what to act on, or None when it is handled here."""
    draft = chat_drafts.get(turn.state.user_id)
    if draft is None or draft.get("flow") != "confirm":
        await complaint_chat.start(turn)
        return None
    said = str(draft.get("said") or "")
    code = draft.get("type")
    choice = reply_id.removeprefix(CONFIRM)
    if choice == "yes" and isinstance(code, str) and code in BY_CODE:
        chat_drafts.drop(turn.state.user_id)
        return Decision(_complaint_intent(code), code, by="consumer", said=said)
    if choice == "other":
        await complaint_chat.start(turn, said)
        return None
    chat_drafts.drop(turn.state.user_id)
    question = draft.get("question")
    if question in INTENTS and question not in _NOT_A_QUESTION:
        return Decision(question, by="consumer")  # type: ignore[arg-type]
    await turn.say_key("uconf_type_question")
    return None
