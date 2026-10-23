"""Get my bill by service number in the chat. On WhatsApp the sender's number must match the mobile the DISCOM holds
for the connection; in the web chat a one-time code goes to that mobile. Either way the answer never says whether
the service number exists, and the bill then goes through the same checks and explanation as a photo.

Every prompt can be left: a Cancel button, the photo as the other way, and a message with no digits in it (a question)
leaves the prompt and is answered as usual instead of being taken as a wrong number or code."""

import re

from app.core.hashing import clean_service_number
from app.domain.conversation.intents import classify
from app.flows import bill as bill_flow
from app.flows import read_reply, usc
from app.flows.turn import Turn
from app.services import discom_bills
from app.store import chat_drafts

AWAIT_NUMBER = "usc:number"
AWAIT_CODE = "usc:code"
CANCEL = "usc_cancel"
DISCOMS = (("TGSPDCL", "btn_spdcl"), ("TGNPDCL", "btn_npdcl"))
START_REPLIES = {"no_code_needed": None, "sent": "usc_code_sent", "unavailable": "usc_unavailable",
                 "rate_limited": "usc_rate_limited"}
VERIFY_REPLIES = {"wrong": "usc_code_wrong", "locked": "usc_locked", "unavailable": "usc_unavailable",
                  "no_bill": "usc_no_bill"}
_DIGIT = re.compile(r"\d")


async def _prompt(turn: Turn, key: str, **values: object) -> None:
    """A prompt that waits for a number, with the ways out."""
    await turn.buttons(turn.t(key, **values), [(CANCEL, "btn_cancel"), (read_reply.NEW_PHOTO, "btn_send_bill")])


def _leave(turn: Turn) -> None:
    draft = chat_drafts.get(turn.state.user_id)
    if draft is not None and draft.get("flow") == "usc":  # a complaint being written stays
        chat_drafts.drop(turn.state.user_id)
    if turn.state.awaiting in (AWAIT_NUMBER, AWAIT_CODE):
        turn.state.awaiting = None


async def start(turn: Turn) -> None:
    ready = discom_bills.available() if turn.inbound.channel == "whatsapp" else usc.can_use_codes()
    if not ready:
        await turn.say_key("usc_unavailable")
        return
    chat_drafts.save(turn.state.user_id, {"flow": "usc"})
    turn.state.awaiting = None
    await turn.buttons(turn.t("usc_pick_discom"), [*((f"udis:{d}", key) for d, key in DISCOMS), (CANCEL, "btn_cancel")])


async def _explain(turn: Turn, discom: str, number: str) -> None:
    _leave(turn)
    found = await usc.fetch_for_chat(turn.state.user_id, discom, number)
    if found is None:
        await turn.say_key("usc_no_bill")
        return
    await bill_flow.handle_bill(turn, found, None, source="discom")


async def _whatsapp(turn: Turn, discom: str, number: str) -> None:
    if not usc.within_limits(turn.state.user_id, number):
        await turn.say_key("usc_rate_limited")
        return
    if not await usc.owns_by_whatsapp(turn.inbound.reply_to, discom, number):
        _leave(turn)
        usc.audit(turn.state.user_id, "usc.verify", discom, number, "number did not match")
        await turn.say_key("usc_not_mine")
        return
    usc.audit(turn.state.user_id, "usc.verify", discom, number, "number matched")
    await _explain(turn, discom, number)


async def _web(turn: Turn, discom: str, number: str) -> None:
    status = await usc.start(turn.state.user_id, discom, number, turn.lang)
    if status == "no_code_needed":
        await _explain(turn, discom, number)
        return
    if status == "sent":
        chat_drafts.save(turn.state.user_id, {"flow": "usc", "discom": discom, "usc": number})
        turn.state.awaiting = AWAIT_CODE
        await _prompt(turn, "usc_code_sent")
        return
    _leave(turn)
    await turn.say_key(START_REPLIES[status] or "usc_unavailable")


async def on_button(turn: Turn, reply_id: str) -> bool:
    if reply_id == CANCEL:
        _leave(turn)
        await turn.say_key("usc_cancelled")
        return True
    if not reply_id.startswith("udis:"):
        return False
    discom = reply_id.removeprefix("udis:")
    if discom not in dict(DISCOMS):
        await start(turn)
        return True
    chat_drafts.save(turn.state.user_id, {"flow": "usc", "discom": discom})
    turn.state.awaiting = AWAIT_NUMBER
    await _prompt(turn, "usc_ask")
    return True


async def _code(turn: Turn, discom: str, number: str, message: str) -> None:
    problem = usc.verify_code(turn.state.user_id, discom, number, message.strip())
    if problem is None:
        await _explain(turn, discom, number)
    elif problem == "wrong":
        await _prompt(turn, "usc_code_wrong_left", left=usc.attempts_left(turn.state.user_id, discom, number))
    else:
        _leave(turn)
        await turn.say_key(VERIFY_REPLIES[problem])


async def on_text(turn: Turn, message: str) -> bool:
    if turn.state.awaiting not in (AWAIT_NUMBER, AWAIT_CODE) or classify(message).intent == "stop":
        return False
    draft = chat_drafts.get(turn.state.user_id)
    if draft is None or draft.get("flow") != "usc" or not draft.get("discom") or not _DIGIT.search(message):
        _leave(turn)  # no digits: a question or a change of mind, answered as usual, never a wasted try
        return False
    discom = str(draft["discom"])
    if turn.state.awaiting == AWAIT_CODE:
        await _code(turn, discom, str(draft["usc"]), message)
        return True
    number = clean_service_number(message)
    if number is None:
        await _prompt(turn, "usc_invalid")
    elif turn.inbound.channel == "whatsapp":
        await _whatsapp(turn, discom, number)
    else:
        await _web(turn, discom, number)
    return True
