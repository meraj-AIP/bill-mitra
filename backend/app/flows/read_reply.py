"""The chat side of a read that did not end in a checked bill: the message for the problem, with buttons for every way
forward, and what those buttons need kept until they are tapped (app/store/pending_reads.py)."""

from app.core.messages import Button, ButtonsOut
from app.domain import capture
from app.domain.bill import ExtractedBill
from app.flows import read_problem
from app.flows.turn import Turn
from app.store import pending_reads

RETRY = "retry_last"
PICK = "units_pick:"
NEW_PHOTO = "new_photo"
HELP = "show_help"
TYPE_UNITS = ("type_units", "btn_type_units")
# Buttons per problem, as (reply id, title key). Anything not listed is a photo to take again.
BUTTONS: dict[str, list[tuple[str, str]]] = {
    "read_failed": [(RETRY, "btn_try_again"), TYPE_UNITS],
    "reading_off": [TYPE_UNITS],
    "not_a_bill": [(NEW_PHOTO, "btn_send_bill"), TYPE_UNITS, (HELP, "btn_help")],
    "other_discom": [(NEW_PHOTO, "btn_send_bill"), (HELP, "btn_help")],
    "file_unopenable": [(NEW_PHOTO, "btn_send_bill"), TYPE_UNITS],
    "file_too_long": [(NEW_PHOTO, "btn_send_bill"), TYPE_UNITS],
    "file_unsupported": [(NEW_PHOTO, "btn_send_bill"), TYPE_UNITS],
}
RETAKE = [(NEW_PHOTO, "btn_new_photo"), TYPE_UNITS]
# What a retried message may carry; the channel and address come from the tap, not from storage.
RETRY_FIELDS = {"kind", "text", "reply_id", "media_id", "mime_type"}


async def send(turn: Turn, body: str, buttons: list[tuple[str, str]]) -> None:
    """Buttons whose titles are already written, for titles that carry a figure."""
    await turn.tracer.message(ButtonsOut(body=body, buttons=[Button(id=bid, title=title) for bid, title in buttons],
                                         language=turn.lang))


def keep_for_retry(turn: Turn) -> None:
    """Try again re-runs this very message, so nothing has to be sent twice."""
    pending_reads.put(turn.state.user_id, "retry", turn.inbound.model_dump(include=RETRY_FIELDS))


async def tell(turn: Turn, code: str, report: capture.CaptureReport | None, bill: ExtractedBill | None,
               media_id: str | None) -> None:
    body = turn.t(code, **read_problem.values(code, report))
    options = read_problem.choices(code, report)
    if options and bill is not None:
        pending_reads.put(turn.state.user_id, "choice",
                          {"bill": bill.model_dump(mode="json"), "options": options, "media_id": media_id})
        turn.state.awaiting = "units"
        picks = [(f"{PICK}{n}", turn.t("btn_units_choice", units=n)) for n in options]
        await send(turn, f"{body}\n{turn.t('chk_which')}", [*picks, (NEW_PHOTO, turn.t("btn_new_photo"))])
        return
    if code == "read_failed":
        keep_for_retry(turn)
    if code != "other_discom":  # typed units would be priced on the Telangana tariff
        turn.state.awaiting = "units"
    await send(turn, body, [(bid, turn.t(key)) for bid, key in BUTTONS.get(code, RETAKE)])


async def on_button(turn: Turn, reply_id: str) -> bool:
    if reply_id == NEW_PHOTO:
        await turn.say_key("new_photo_tip")
        return True
    if reply_id == HELP:
        await turn.say_key("help")
        return True
    return False
