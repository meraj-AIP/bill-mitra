"""Raise a complaint in the chat without a bill: category (three buttons), type (a list), DISCOM (two buttons),
service number (typed, or Skip), a short description, the type's follow-up questions, then preview and send. A message
the understanding step reads as a complaint of a known type starts at the DISCOM, with its words as the description.
With a checked bill in the chat, the bill fills the DISCOM and service number and is linked. WhatsApp and the web chat
share this flow.

An open complaint of the same type gets the new words added instead of a second ticket. The draft lives in chat_drafts
until it is sent or cancelled. Consumer copy never names who handles a complaint.
"""

from typing import Any

from app.core.hashing import clean_service_number
from app.core.messages import Button, ButtonsOut, ListOut, ListRow
from app.domain import complaint_followups as followups
from app.domain import complaint_types
from app.domain.bill import mask
from app.domain.conversation.intents import DISPUTE_TYPES, classify
from app.flows import cases, intake, usc_chat
from app.flows.analysis import analyse
from app.flows.turn import Turn
from app.store import chat_drafts, policy, repos

AWAIT_USC = "cdraft:usc"
AWAIT_DESC = "cdraft:desc"
AWAIT_FOLLOWUP = "cdraft:fq"
DISCOMS = (("TGSPDCL", "btn_spdcl"), ("TGNPDCL", "btn_npdcl"))
MIN_DESCRIPTION = 3
MAX_DESCRIPTION = 1000
PREVIEW_WORDS = 600

Draft = dict[str, Any]


def _source(turn: Turn) -> str:
    return "whatsapp" if turn.inbound.channel == "whatsapp" else "consumer_chat"


async def start(turn: Turn, said: str = "") -> None:
    """The three categories as buttons. Any half-finished draft is replaced; words already given are kept."""
    draft: Draft = {"flow": "complaint"}
    if len(said.strip()) >= MIN_DESCRIPTION:
        draft["description"] = said.strip()[:MAX_DESCRIPTION]
    chat_drafts.save(turn.state.user_id, draft)
    turn.state.awaiting = None
    await turn.buttons(turn.t("cflow_pick_category"),
                       [(f"ccat:{c}", f"ccat_{c}") for c in complaint_types.CATEGORIES])


async def begin(turn: Turn, code: str, said: str, details: dict[str, object]) -> None:
    """A complaint of a known type, from the consumer's own message."""
    stored = _own_bill(turn)
    if await _joined_open(turn, code, stored.bill.service_number if stored else None, said, number_asked=False):
        return
    if complaint_types.get(code).priority == "urgent":
        await turn.say_key("cflow_urgent")
    draft: Draft = {"flow": "complaint", "type": code, "answers": followups.from_details(code, details)}
    if len(said.strip()) >= MIN_DESCRIPTION:
        draft["description"] = said.strip()[:MAX_DESCRIPTION]
    await _after_type(turn, draft)


async def _joined_open(turn: Turn, code: str, service_number: str | None, words: str, *,
                       number_asked: bool = True) -> bool:
    ticket = intake.open_duplicate(turn.state.user_id, code, service_number, number_asked=number_asked)
    if ticket is None:
        return False
    if words.strip():
        intake.add_to_open(ticket, words.strip()[:MAX_DESCRIPTION], _source(turn))
    chat_drafts.drop(turn.state.user_id)
    turn.state.awaiting = None
    await turn.say_key("cflow_added_existing", ticket=ticket)
    return True


async def _types(turn: Turn, category: str) -> None:
    rows = [ListRow(id=f"ctype:{t.code}", title=turn.t(t.short_key), description=turn.t(t.label_key)[:72])
            for t in complaint_types.in_category(category)]
    await turn.tracer.message(ListOut(body=turn.t("cflow_pick_type"), button_label=turn.t("cflow_list_button"),
                                      rows=rows, language=turn.lang))


def _own_bill(turn: Turn) -> repos.StoredBill | None:
    bill_id = turn.state.current_bill_id
    return repos.get_own_bill(turn.state.user_id, bill_id) if bill_id else None


async def _after_type(turn: Turn, draft: Draft) -> None:
    """A checked bill in the chat answers DISCOM and service number; otherwise ask for them."""
    stored = _own_bill(turn)
    if stored is not None and draft["type"] == complaint_types.WRONG_READING:
        chat_drafts.drop(turn.state.user_id)  # a reading complaint on a bill is the review case flow
        await cases.report_from_chat(turn, analyse(stored.bill, turn.state.user_id), stored.id)
        return
    if stored is not None and stored.bill.discom in dict(DISCOMS):
        await _next(turn, draft | {"discom": stored.bill.discom, "bill_id": stored.id})
        return
    chat_drafts.save(turn.state.user_id, draft)
    await turn.buttons(turn.t("cflow_pick_discom"), [(f"cdis:{d}", key) for d, key in DISCOMS])


def _pending(draft: Draft) -> followups.FollowUp | None:
    answers = draft.get("answers") or {}
    return next((q for q in followups.for_type(str(draft.get("type"))) if q.key not in answers), None)


async def _next(turn: Turn, draft: Draft) -> None:
    """Ask for whatever the draft still lacks, one thing at a time; the preview once nothing is missing."""
    chat_drafts.save(turn.state.user_id, draft)
    question = _pending(draft)
    if not draft.get("description"):
        turn.state.awaiting = AWAIT_DESC
        await turn.say_key("cflow_ask_desc")
    elif question is not None:
        turn.state.awaiting = AWAIT_FOLLOWUP
        body = turn.t(f"fq_ask_{question.key}") + "\n" + turn.t("cfq_skip_hint")
        await turn.buttons(body, [(f"cfq:{v}", f"fqv_{v}") for v in question.options] + [("cfq_skip", "btn_skip")])
    else:
        await _preview(turn, draft)


def _answered(draft: Draft, value: str) -> Draft:
    question = _pending(draft)
    if question is None:
        return draft
    return draft | {"answers": (draft.get("answers") or {}) | {question.key: value}}


async def _ask_usc(turn: Turn) -> None:
    turn.state.awaiting = AWAIT_USC
    await turn.buttons(turn.t("cflow_ask_usc"), [("cusc_skip", "btn_skip")])


def _answer_lines(turn: Turn, draft: Draft) -> list[str]:
    answers = draft.get("answers") or {}
    return [f"{turn.t(f'fq_label_{q.key}')}: {turn.t(f'fqv_{v}') if v in followups.VALUE_EN else v}"
            for q in followups.for_type(str(draft["type"])) if (v := answers.get(q.key))]


async def _preview(turn: Turn, draft: Draft) -> None:
    turn.state.awaiting = None
    stored = _own_bill(turn) if draft.get("bill_id") else None
    service = (stored.bill.masked_service_number() if stored else mask(str(draft.get("usc") or ""))) or \
        turn.t("cflow_no_usc")
    body = turn.t("cflow_preview", type=turn.t(f"ctype_{draft['type']}"), discom=draft["discom"], service=service,
                  description=str(draft["description"])[:PREVIEW_WORDS])
    body = "\n".join([body, *_answer_lines(turn, draft)])[:1024]
    buttons = [Button(id="cdraft_send", title=turn.t("btn_send")), Button(id="cdraft_cancel", title=turn.t("btn_cancel"))]
    await turn.tracer.message(ButtonsOut(body=body, buttons=buttons, language=turn.lang))


def _description(draft: Draft) -> str:
    """The consumer's words, then the follow-up answers as labelled lines, within the column's limit."""
    lines = "\n".join(followups.staff_lines(str(draft["type"]), draft.get("answers") or {}))
    words = str(draft["description"])
    return f"{words[:MAX_DESCRIPTION - len(lines) - 1]}\n{lines}" if lines else words[:MAX_DESCRIPTION]


async def _send(turn: Turn, draft: Draft) -> None:
    type_code = str(draft["type"])
    description = _description(draft)
    stored = _own_bill(turn) if draft.get("bill_id") else None
    usc = str(draft["usc"]) if draft.get("usc") else (stored.bill.service_number if stored else None)
    if await _joined_open(turn, type_code, usc, description):
        return
    ticket = await intake.submit(intake.Raise(
        user_id=turn.state.user_id, type=type_code, discom=str(draft["discom"]), description=description,
        language=turn.lang, channel=turn.inbound.channel, source=_source(turn),
        service_number=str(draft["usc"]) if draft.get("usc") else None,
        bill_id=str(draft["bill_id"]) if draft.get("bill_id") else None, reply_to=turn.inbound.reply_to,
        in_chat=True))
    chat_drafts.drop(turn.state.user_id)
    days = complaint_types.get(type_code).target_days or policy.get(str(draft["discom"])).decision_sla_days
    await turn.say_key("cflow_filed", ticket=ticket, days=days)
    if type_code == complaint_types.WRONG_READING and not draft.get("bill_id"):
        turn.state.awaiting = "info:" + ticket
        await turn.say(intake.bill_request(ticket, turn.lang))
    repos.log_event(turn.inbound.channel, "complaint", language=turn.lang, discom=str(draft["discom"]))


async def on_intent(turn: Turn, intent: str, complaint_type: str | None = None, said: str | None = None,
                    details: dict[str, object] | None = None) -> bool:
    """Complaints without a bill start here; with a bill the one-tap tariff complaint and the bill check still come
    first."""
    if intent == "fetch_bill":
        await usc_chat.start(turn)
        return True
    if complaint_type in complaint_types.BY_CODE:
        if complaint_type in DISPUTE_TYPES and _own_bill(turn) is not None:
            return False
        await begin(turn, complaint_type, said or "", details or {})
        return True
    if intent == "complain" and _own_bill(turn) is None:
        await start(turn)  # "I want to complain" says nothing about the problem, so it is not the description
        return True
    return False


async def _on_draft_button(turn: Turn, reply_id: str, draft: Draft) -> None:
    kind, _, value = reply_id.partition(":")
    question = _pending(draft) if draft.get("description") and draft.get("discom") else None
    if kind == "ccat" and value in complaint_types.CATEGORIES:
        await _types(turn, value)
    elif kind == "ctype" and value in complaint_types.BY_CODE:
        kept = {"description": draft["description"]} if draft.get("description") else {}
        await _after_type(turn, {"flow": "complaint", "type": value, "answers": {}, **kept})
    elif kind == "cdis" and value in dict(DISCOMS) and draft.get("type"):
        chat_drafts.save(turn.state.user_id, draft | {"discom": value})
        await _ask_usc(turn)
    elif reply_id == "cusc_skip" and draft.get("discom"):
        await _next(turn, draft)
    elif question is not None and (reply_id == "cfq_skip" or value in question.options):
        await _next(turn, _answered(draft, "" if reply_id == "cfq_skip" else value))
    elif reply_id == "cdraft_send" and draft.get("description"):
        await _send(turn, draft)
    elif reply_id == "cdraft_cancel":
        chat_drafts.drop(turn.state.user_id)
        turn.state.awaiting = None
        await turn.say_key("complaint_cancel")
    else:
        await start(turn)


async def on_button(turn: Turn, reply_id: str) -> bool:
    """True when the button belongs to this flow. A stale button with no draft starts again."""
    if reply_id == "cnew":
        await start(turn)
        return True
    if not reply_id.startswith(("ccat:", "ctype:", "cdis:", "cusc_skip", "cdraft_", "cfq:", "cfq_skip")):
        return False
    draft = chat_drafts.get(turn.state.user_id)
    if draft is None or draft.get("flow") != "complaint":
        await start(turn)
        return True
    await _on_draft_button(turn, reply_id, draft)
    return True


async def on_text(turn: Turn, message: str) -> bool:
    """Typed answers while the flow waits for the service number, the description or a follow-up answer."""
    if turn.state.awaiting not in (AWAIT_USC, AWAIT_DESC, AWAIT_FOLLOWUP) or classify(message).intent == "stop":
        return False
    draft = chat_drafts.get(turn.state.user_id)
    if draft is None or draft.get("flow") != "complaint":
        turn.state.awaiting = None
        return False
    words = message.strip()
    if turn.state.awaiting == AWAIT_USC:
        usc = clean_service_number(message)
        if usc is None:
            await turn.buttons(turn.t("cflow_usc_invalid"), [("cusc_skip", "btn_skip")])
            return True
        await _next(turn, draft | {"usc": usc})
    elif turn.state.awaiting == AWAIT_FOLLOWUP:
        await _next(turn, _answered(draft, words[:followups.ANSWER_MAX]))
    elif len(words) < MIN_DESCRIPTION:
        await turn.say_key("cflow_desc_short")
    else:
        await _next(turn, draft | {"description": words[:MAX_DESCRIPTION]})
    return True
