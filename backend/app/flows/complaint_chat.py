"""Raise a complaint in the chat without a bill: category (three buttons), type (a list), DISCOM (two buttons),
service number (typed, or Skip), a short description, then preview and send. With a checked bill in the chat, the
bill fills the DISCOM and service number and is linked. WhatsApp and the web chat share this flow.

The draft lives in chat_drafts until it is sent or cancelled. Consumer copy never names who handles a complaint.
"""

from app.core.hashing import clean_service_number
from app.core.messages import Button, ButtonsOut, ListOut, ListRow
from app.domain import complaint_types
from app.domain.bill import mask
from app.domain.conversation.intents import classify
from app.flows import cases, intake, usc_chat
from app.flows.analysis import analyse
from app.flows.turn import Turn
from app.store import chat_drafts, policy, repos

AWAIT_USC = "cdraft:usc"
AWAIT_DESC = "cdraft:desc"
DISCOMS = (("TGSPDCL", "btn_spdcl"), ("TGNPDCL", "btn_npdcl"))
MIN_DESCRIPTION = 3
MAX_DESCRIPTION = 1000


def _source(turn: Turn) -> str:
    return "whatsapp" if turn.inbound.channel == "whatsapp" else "consumer_chat"


async def start(turn: Turn) -> None:
    """The three categories as buttons. Any half-finished draft is replaced."""
    chat_drafts.save(turn.state.user_id, {"flow": "complaint"})
    turn.state.awaiting = None
    await turn.buttons(turn.t("cflow_pick_category"),
                       [(f"ccat:{c}", f"ccat_{c}") for c in complaint_types.CATEGORIES])


async def _types(turn: Turn, category: str) -> None:
    rows = [ListRow(id=f"ctype:{t.code}", title=turn.t(t.short_key), description=turn.t(t.label_key)[:72])
            for t in complaint_types.in_category(category)]
    await turn.tracer.message(ListOut(body=turn.t("cflow_pick_type"), button_label=turn.t("cflow_list_button"),
                                      rows=rows, language=turn.lang))


def _own_bill(turn: Turn) -> repos.StoredBill | None:
    bill_id = turn.state.current_bill_id
    return repos.get_own_bill(turn.state.user_id, bill_id) if bill_id else None


async def _after_type(turn: Turn, draft: dict[str, object]) -> None:
    """A checked bill in the chat answers DISCOM and service number; otherwise ask for them."""
    stored = _own_bill(turn)
    if stored is not None and draft["type"] == complaint_types.WRONG_READING:
        chat_drafts.drop(turn.state.user_id)  # a reading complaint on a bill is the review case flow
        await cases.report_from_chat(turn, analyse(stored.bill, turn.state.user_id), stored.id)
        return
    if stored is not None and stored.bill.discom in dict(DISCOMS):
        draft |= {"discom": stored.bill.discom, "bill_id": stored.id}
        chat_drafts.save(turn.state.user_id, draft)
        await _ask_description(turn)
        return
    chat_drafts.save(turn.state.user_id, draft)
    await turn.buttons(turn.t("cflow_pick_discom"), [(f"cdis:{d}", key) for d, key in DISCOMS])


async def _ask_usc(turn: Turn) -> None:
    turn.state.awaiting = AWAIT_USC
    await turn.buttons(turn.t("cflow_ask_usc"), [("cusc_skip", "btn_skip")])


async def _ask_description(turn: Turn) -> None:
    turn.state.awaiting = AWAIT_DESC
    await turn.say_key("cflow_ask_desc")


async def _preview(turn: Turn, draft: dict[str, object]) -> None:
    turn.state.awaiting = None
    stored = _own_bill(turn) if draft.get("bill_id") else None
    service = (stored.bill.masked_service_number() if stored else mask(str(draft.get("usc") or ""))) or \
        turn.t("cflow_no_usc")
    body = turn.t("cflow_preview", type=turn.t(f"ctype_{draft['type']}"), discom=draft["discom"], service=service,
                  description=str(draft["description"])[:600])[:1024]
    buttons = [Button(id="cdraft_send", title=turn.t("btn_send")), Button(id="cdraft_cancel", title=turn.t("btn_cancel"))]
    await turn.tracer.message(ButtonsOut(body=body, buttons=buttons, language=turn.lang))


async def _send(turn: Turn, draft: dict[str, object]) -> None:
    type_code = str(draft["type"])
    ticket = await intake.submit(intake.Raise(
        user_id=turn.state.user_id, type=type_code, discom=str(draft["discom"]),
        description=str(draft["description"]), language=turn.lang, channel=turn.inbound.channel,
        source=_source(turn), service_number=str(draft["usc"]) if draft.get("usc") else None,
        bill_id=str(draft["bill_id"]) if draft.get("bill_id") else None, reply_to=turn.inbound.reply_to,
        in_chat=True))
    chat_drafts.drop(turn.state.user_id)
    days = complaint_types.get(type_code).target_days or policy.get(str(draft["discom"])).decision_sla_days
    await turn.say_key("cflow_filed", ticket=ticket, days=days)
    if type_code == complaint_types.WRONG_READING and not draft.get("bill_id"):
        turn.state.awaiting = "info:" + ticket
        await turn.say(intake.bill_request(ticket, turn.lang))
    repos.log_event(turn.inbound.channel, "complaint", language=turn.lang, discom=str(draft["discom"]))


async def on_intent(turn: Turn, intent: str) -> bool:
    """Complaints without a bill start here; with a bill the one-tap tariff complaint still comes first."""
    if intent == "fetch_bill":
        await usc_chat.start(turn)
        return True
    if intent == "complain" and _own_bill(turn) is None:
        await start(turn)
        return True
    return False


async def on_button(turn: Turn, reply_id: str) -> bool:
    """True when the button belongs to this flow. A stale button with no draft starts again."""
    if reply_id == "cnew":
        await start(turn)
        return True
    if not reply_id.startswith(("ccat:", "ctype:", "cdis:", "cusc_skip", "cdraft_")):
        return False
    draft = chat_drafts.get(turn.state.user_id)
    if draft is None or draft.get("flow") != "complaint":
        await start(turn)
        return True
    kind, _, value = reply_id.partition(":")
    if kind == "ccat" and value in complaint_types.CATEGORIES:
        await _types(turn, value)
    elif kind == "ctype" and value in complaint_types.BY_CODE:
        await _after_type(turn, {"flow": "complaint", "type": value})
    elif kind == "cdis" and value in dict(DISCOMS) and draft.get("type"):
        chat_drafts.save(turn.state.user_id, draft | {"discom": value})
        await _ask_usc(turn)
    elif reply_id == "cusc_skip" and draft.get("discom"):
        await _ask_description(turn)
    elif reply_id == "cdraft_send" and draft.get("description"):
        await _send(turn, draft)
    elif reply_id == "cdraft_cancel":
        chat_drafts.drop(turn.state.user_id)
        turn.state.awaiting = None
        await turn.say_key("complaint_cancel")
    else:
        await start(turn)
    return True


async def on_text(turn: Turn, message: str) -> bool:
    """Typed answers while the flow waits for the service number or the description."""
    if turn.state.awaiting not in (AWAIT_USC, AWAIT_DESC) or classify(message).intent == "stop":
        return False
    draft = chat_drafts.get(turn.state.user_id)
    if draft is None or draft.get("flow") != "complaint":
        turn.state.awaiting = None
        return False
    if turn.state.awaiting == AWAIT_USC:
        usc = clean_service_number(message)
        if usc is None:
            await turn.buttons(turn.t("cflow_usc_invalid"), [("cusc_skip", "btn_skip")])
            return True
        chat_drafts.save(turn.state.user_id, draft | {"usc": usc})
        await _ask_description(turn)
        return True
    words = message.strip()
    if len(words) < MIN_DESCRIPTION:
        await turn.say_key("cflow_desc_short")
        return True
    draft |= {"description": words[:MAX_DESCRIPTION]}
    chat_drafts.save(turn.state.user_id, draft)
    await _preview(turn, draft)
    return True
