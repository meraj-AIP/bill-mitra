"""Deliver an officer's reply or a status change to the consumer, on the channel they complained from.

The result is recorded on the message, so the officer always sees whether the consumer actually got it.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from app.channels.whatsapp.mapper import user_key
from app.config import get_settings
from app.core.messages import TextOut
from app.domain.conversation.lang import text
from app.services import delivery
from app.store import chat, outbox
from app.store import complaints as complaint_store
from app.store.complaints import Complaint, Delivery, Status

log = logging.getLogger(__name__)

STATUS_KEYS: dict[str, str] = {"Open": "cstatus_open", "In progress": "cstatus_in_progress",
                               "Resolved": "cstatus_resolved", "Rejected": "cstatus_rejected"}
NOT_CONNECTED = "WhatsApp is not connected on this server, so the consumer has not received this."
NO_NUMBER = delivery.NO_NUMBER
REJECTED = delivery.REJECTED
TEMPLATE_USED = delivery.TEMPLATE_USED
FAILED_LATER = "WhatsApp accepted the message but could not deliver it. The consumer has not received this."
# Meta reports a message sent outside the 24 hour window in a later status, with this error code.
OUTSIDE_WINDOW = 131047
CODE_LIFETIME = timedelta(minutes=5)  # matches the code's own expiry in app/flows/usc.py


@dataclass(frozen=True)
class Outcome:
    delivery: Delivery
    note: str | None = None
    wamid: str | None = None  # Meta's id for the sent message, so its later delivery status can be matched
    outbox_id: int | None = None  # pass to add_message, so a queued send updates the thread when it goes


def reply_channel(complaint: Complaint) -> str:
    # Complaints recorded before the channel column existed: a hashed WhatsApp key still means WhatsApp.
    if complaint.channel:
        return complaint.channel
    return "whatsapp" if complaint.user_id.startswith("wa:") else "web"


def status_label(language: str, status: str) -> str:
    return text(language, STATUS_KEYS[status])


async def reply(complaint: Complaint, body: str) -> Outcome:
    language = complaint.language or "te"
    message = text(language, "complaint_update", ticket=complaint.ticket) + "\n" + body
    return await _deliver(complaint, message, None, "staff")


async def status(complaint: Complaint, new_status: Status) -> tuple[str, Outcome]:
    """The localised status line (stored in the thread as sent) and how it was delivered."""
    language = complaint.language or "te"
    line = text(language, "complaint_status", ticket=complaint.ticket, status=status_label(language, new_status))
    return line, await _deliver(complaint, line, new_status, "status")


async def send(complaint: Complaint, message: str, template_status: str | None = None,
               kind: str = "notice") -> Outcome:
    """Any other message for the consumer, such as a request for a photo or a retry of one that failed."""
    return await _deliver(complaint, message, template_status, kind)


def _template(complaint: Complaint, template_status: str | None) -> dict[str, Any] | None:
    """The approved template, for a consumer outside the 24 hour window. It carries the ticket and status only."""
    name = get_settings().whatsapp_complaint_template
    if not name:
        return None
    language = complaint.language or "te"
    label = status_label(language, template_status or complaint.status)
    return {"name": name, "language": language, "params": [complaint.ticket, label]}


def _outcome(row: outbox.Row) -> Outcome:
    return Outcome(delivery.DELIVERY[row.state], row.note, row.wamid, row.id)


def _to_web_chat(complaint: Complaint, message: str) -> Outcome:
    """A complaint raised in the web app has no phone to send to. The update lands in the person's web chat, as it
    would on WhatsApp, so the chat preview behaves like the real channel. A complaint with no account behind it
    (logged by staff for a caller with no mobile) can only be kept on the complaint."""
    if not complaint.user_id.startswith("acct:"):
        return Outcome("stored")
    chat.record_out(complaint.user_id, TextOut(body=message[:4096], language=complaint.language or "te").model_dump())
    return Outcome("sent")


async def _deliver(complaint: Complaint, message: str, template_status: str | None, kind: str) -> Outcome:
    if reply_channel(complaint) != "whatsapp":
        return _to_web_chat(complaint, message)
    if not get_settings().whatsapp_enabled:
        return Outcome("failed", NOT_CONNECTED)
    if not complaint.reply_to:
        return Outcome("failed", NO_NUMBER)
    language = complaint.language or "te"
    row = await delivery.deliver(outbox.NewItem(
        dedupe_key=f"{kind}:{complaint.ticket}:{uuid.uuid4().hex}", kind=kind, recipient=complaint.user_id,
        address=complaint.reply_to, message=TextOut(body=message[:4096], language=language).model_dump(),
        template=_template(complaint, template_status), ticket=complaint.ticket))
    return _outcome(row)


async def delivery_failed(wamid: str, error_code: int | None) -> None:
    """Meta reported a message as failed after accepting it. Outside the 24 hour window the approved template goes
    instead; anything else is marked not delivered, so the officer sees it and can send again."""
    found = complaint_store.by_wamid(wamid)
    if found is None or found["author_kind"] == "consumer":
        return
    complaint = complaint_store.get(found["ticket"])
    if complaint is None:
        return
    template = _template(complaint, None)
    if error_code == OUTSIDE_WINDOW and template is None:
        complaint_store.set_delivery(found["id"], "failed", REJECTED)
        return
    if error_code == OUTSIDE_WINDOW and complaint.reply_to:
        row = await delivery.deliver(outbox.NewItem(
            dedupe_key=f"window:{wamid}", kind="status", recipient=complaint.user_id, address=complaint.reply_to,
            message=None, template=template, ticket=complaint.ticket, message_id=found["id"]))
        outcome = _outcome(row)
        note = TEMPLATE_USED if outcome.delivery == "sent" else outcome.note
        complaint_store.set_delivery(found["id"], outcome.delivery, note, outcome.wamid)
        return
    complaint_store.set_delivery(found["id"], "failed", FAILED_LATER)


def can_send_code() -> bool:
    """One-time codes go out as an approved WhatsApp authentication template. No SMS provider is wired yet."""
    settings = get_settings()
    return settings.whatsapp_enabled and bool(settings.whatsapp_code_template)


async def send_code(mobile: str, code: str, language: str) -> bool:
    """Send a one-time code to a 10 digit Indian mobile. The number and the code are never logged, and the number is
    not stored: the outbox row keeps neither the number nor the code, so a code that fails inline is not retried."""
    if not can_send_code():
        return False
    address = f"91{mobile}"
    template = {"name": get_settings().whatsapp_code_template, "language": language, "params": [code], "button": True}
    row = await delivery.deliver(outbox.NewItem(
        dedupe_key=f"code:{uuid.uuid4().hex}", kind="code", recipient=user_key(address), address=None, message=None,
        lifetime=CODE_LIFETIME), address=address, template=template)
    if row.state != "sent":
        log.warning("one-time code template not accepted by WhatsApp")
    return row.state == "sent"
