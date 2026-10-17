"""Deliver an officer's reply or a status change to the consumer, on the channel they complained from.

The result is recorded on the message, so the officer always sees whether the consumer actually got it.
"""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.channels.whatsapp import client
from app.config import get_settings
from app.domain.conversation.lang import text
from app.store.complaints import Complaint, Delivery, Status

log = logging.getLogger(__name__)

STATUS_KEYS: dict[str, str] = {"Open": "cstatus_open", "In progress": "cstatus_in_progress",
                               "Resolved": "cstatus_resolved", "Rejected": "cstatus_rejected"}
NOT_CONNECTED = "WhatsApp is not connected on this server, so the consumer has not received this."
NO_NUMBER = "No WhatsApp number is stored for this complaint, so the consumer has not received this."
REJECTED = ("WhatsApp did not accept the message, most likely because the consumer has not written in the last "
            "24 hours and no approved template is set. The consumer has not received this.")
TEMPLATE_REJECTED = "WhatsApp did not accept the message or the approved template. The consumer has not received this."
TEMPLATE_USED = "Sent as the approved template because the consumer has not written in the last 24 hours."


@dataclass(frozen=True)
class Outcome:
    delivery: Delivery
    note: str | None = None


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
    return await _deliver(complaint, message)


async def status(complaint: Complaint, new_status: Status) -> tuple[str, Outcome]:
    """The localised status line (stored in the thread as sent) and how it was delivered."""
    language = complaint.language or "te"
    line = text(language, "complaint_status", ticket=complaint.ticket, status=status_label(language, new_status))
    return line, await _deliver(complaint, line, new_status)


async def send(complaint: Complaint, message: str, template_status: str | None = None) -> Outcome:
    """Any other message for the consumer, such as a request for a photo or a retry of one that failed."""
    return await _deliver(complaint, message, template_status)


async def _deliver(complaint: Complaint, message: str, template_status: str | None = None) -> Outcome:
    if reply_channel(complaint) != "whatsapp":
        return Outcome("stored")
    settings = get_settings()
    if not settings.whatsapp_enabled:
        return Outcome("failed", NOT_CONNECTED)
    if not complaint.reply_to:
        return Outcome("failed", NO_NUMBER)
    base: dict[str, Any] = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": complaint.reply_to}
    try:
        await client.send(base | {"type": "text", "text": {"body": message[:4096], "preview_url": False}})
        return Outcome("sent")
    except httpx.HTTPError:
        log.warning("complaint %s: free text reply not accepted by WhatsApp", complaint.ticket)
    if not settings.whatsapp_complaint_template:
        return Outcome("failed", REJECTED)
    language = complaint.language or "te"
    label = status_label(language, template_status or complaint.status)
    params = [{"type": "text", "text": complaint.ticket}, {"type": "text", "text": label}]
    template = {"name": settings.whatsapp_complaint_template, "language": {"code": language},
                "components": [{"type": "body", "parameters": params}]}
    try:
        await client.send(base | {"type": "template", "template": template})
        return Outcome("sent", TEMPLATE_USED)
    except httpx.HTTPError:
        log.warning("complaint %s: template not accepted by WhatsApp", complaint.ticket)
        return Outcome("failed", TEMPLATE_REJECTED)



def can_send_code() -> bool:
    """One-time codes go out as an approved WhatsApp authentication template. No SMS provider is wired yet."""
    settings = get_settings()
    return settings.whatsapp_enabled and bool(settings.whatsapp_code_template)


async def send_code(mobile: str, code: str, language: str) -> bool:
    """Send a one-time code to a 10 digit Indian mobile. The number and the code are never logged."""
    if not can_send_code():
        return False
    params = [{"type": "text", "text": code}]
    template = {"name": get_settings().whatsapp_code_template, "language": {"code": language},
                "components": [{"type": "body", "parameters": params},
                               {"type": "button", "sub_type": "url", "index": "0", "parameters": params}]}
    try:
        await client.send({"messaging_product": "whatsapp", "recipient_type": "individual", "to": f"91{mobile}",
                           "type": "template", "template": template})
        return True
    except httpx.HTTPError:
        log.warning("one-time code template not accepted by WhatsApp")
        return False
