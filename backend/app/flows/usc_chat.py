"""Get my bill by service number in the chat. On WhatsApp the sender's number must match the mobile the DISCOM holds
for the connection; in the web chat a one-time code goes to that mobile. Either way the answer never says whether
the service number exists, and the bill then goes through the same checks and explanation as a photo."""

from app.core.hashing import clean_service_number
from app.domain.conversation.intents import classify
from app.flows import bill as bill_flow
from app.flows import usc
from app.flows.turn import Turn
from app.services import discom_bills
from app.store import chat_drafts

AWAIT_NUMBER = "usc:number"
AWAIT_CODE = "usc:code"
DISCOMS = (("TGSPDCL", "btn_spdcl"), ("TGNPDCL", "btn_npdcl"))
START_REPLIES = {"no_code_needed": None, "sent": "usc_code_sent", "unavailable": "usc_unavailable",
                 "rate_limited": "usc_rate_limited"}
VERIFY_REPLIES = {"wrong": "usc_code_wrong", "locked": "usc_locked", "unavailable": "usc_unavailable",
                  "no_bill": "usc_no_bill"}


async def start(turn: Turn) -> None:
    ready = discom_bills.available() if turn.inbound.channel == "whatsapp" else usc.can_use_codes()
    if not ready:
        await turn.say_key("usc_unavailable")
        return
    chat_drafts.save(turn.state.user_id, {"flow": "usc"})
    turn.state.awaiting = None
    await turn.buttons(turn.t("usc_pick_discom"), [(f"udis:{d}", key) for d, key in DISCOMS])


async def _explain(turn: Turn, discom: str, number: str) -> None:
    chat_drafts.drop(turn.state.user_id)
    turn.state.awaiting = None
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
        chat_drafts.drop(turn.state.user_id)
        turn.state.awaiting = None
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
    else:
        chat_drafts.drop(turn.state.user_id)
        turn.state.awaiting = None
    await turn.say_key(START_REPLIES[status] or "usc_unavailable")


async def on_button(turn: Turn, reply_id: str) -> bool:
    if not reply_id.startswith("udis:"):
        return False
    discom = reply_id.removeprefix("udis:")
    if discom not in dict(DISCOMS):
        await start(turn)
        return True
    chat_drafts.save(turn.state.user_id, {"flow": "usc", "discom": discom})
    turn.state.awaiting = AWAIT_NUMBER
    await turn.say_key("usc_ask")
    return True


async def on_text(turn: Turn, message: str) -> bool:
    if turn.state.awaiting not in (AWAIT_NUMBER, AWAIT_CODE) or classify(message).intent == "stop":
        return False
    draft = chat_drafts.get(turn.state.user_id)
    if draft is None or draft.get("flow") != "usc" or not draft.get("discom"):
        turn.state.awaiting = None
        return False
    discom = str(draft["discom"])
    if turn.state.awaiting == AWAIT_NUMBER:
        number = clean_service_number(message)
        if number is None:
            await turn.say_key("usc_invalid")
        elif turn.inbound.channel == "whatsapp":
            await _whatsapp(turn, discom, number)
        else:
            await _web(turn, discom, number)
        return True
    problem = usc.verify_code(turn.state.user_id, discom, str(draft["usc"]), message.strip())
    if problem is None:
        await _explain(turn, discom, str(draft["usc"]))
        return True
    if problem != "wrong":
        chat_drafts.drop(turn.state.user_id)
        turn.state.awaiting = None
    await turn.say_key(VERIFY_REPLIES[problem])
    return True
