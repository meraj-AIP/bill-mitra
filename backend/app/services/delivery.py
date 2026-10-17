"""Sends outbox rows (app/store/outbox.py) on WhatsApp: a few quick tries inline, then the queue.

Free text inside the 24 hour window; outside it, or when Meta refuses free text, the row's approved template if it has
one. Each outcome lands on the complaint thread message the row delivers, and a complaint message that finally fails
raises a `delivery_failed` alert for whoever holds the complaint.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import TypeAdapter

from app.channels.whatsapp import client
from app.channels.whatsapp.mapper import media_ids, to_payload
from app.core import retry
from app.core.messages import Outbound
from app.store import chat, outbox
from app.store import complaints as complaint_store
from app.store.alerts import raise_alert
from app.store.complaints import Delivery
from app.store.db import ts

log = logging.getLogger(__name__)

QUEUED = "WhatsApp did not answer. We keep trying for up to 24 hours, and this updates once it is delivered."
GAVE_UP = "WhatsApp did not answer for 24 hours. The consumer has not received this; use Send again."
NO_NUMBER = "No WhatsApp number is stored for this complaint, so the consumer has not received this."
REJECTED = ("WhatsApp did not accept the message, most likely because the consumer has not written in the last "
            "24 hours and no approved template is set. The consumer has not received this.")
TEMPLATE_REJECTED = "WhatsApp did not accept the message or the approved template. The consumer has not received this."
TEMPLATE_USED = "Sent as the approved template because the consumer has not written in the last 24 hours."
CREDENTIALS = "WhatsApp refused our access token or number. An admin needs to check the WhatsApp settings."
NO_ANSWER = "WhatsApp did not answer in time. The consumer has not received this; use Send again."
WINDOW = timedelta(hours=24)
DELIVERY: dict[str, Delivery] = {"queued": "queued", "sending": "queued", "sent": "sent", "failed": "failed",
                                 "dismissed": "failed"}
_OUTBOUND: TypeAdapter[Any] = TypeAdapter(Outbound)
_SEND_ERRORS = (httpx.HTTPError, *retry.TRANSPORT, KeyError, ValueError)


def window_open(recipient: str, now: datetime | None = None) -> bool:
    last = chat.last_inbound(recipient)
    return bool(last) and str(last) > ts((now or datetime.now(UTC)) - WINDOW)


async def deliver(item: outbox.NewItem, now: datetime | None = None, address: str | None = None,
                  template: dict[str, Any] | None = None) -> outbox.Row:
    """Queue the message once per dedupe key and try it now. `address` and `template` are used for this try only and
    never stored: a registered mobile, or a template that carries a one-time code."""
    row = outbox.put(item, now)
    if row.state != "queued":  # already sent, being sent, or parked: never a second copy
        return row
    return await attempt(row.id, now, address=address, template=template, inline=True)


async def attempt(row_id: int, now: datetime | None = None, *, address: str | None = None,
                  template: dict[str, Any] | None = None, inline: bool = False) -> outbox.Row:
    row = outbox.claim(row_id, now)
    if row is None:  # someone else is sending it, or an earlier message to this person is still waiting
        found = outbox.get(row_id)
        assert found is not None
        return found
    to = address or row.address
    if not to:
        return _synced(outbox.failed(row.id, "NoAddress", NO_NUMBER, now))
    try:
        wamid, note = await _send(row, to, template or row.template, now)
    except _SEND_ERRORS as exc:
        updated = _synced(_after_failure(row, exc, now))
        if updated.state == "failed" and not inline:
            _alert(updated)
        return updated
    return _synced(outbox.sent(row.id, wamid, note, now))


async def run_due(now: datetime | None = None) -> int:
    """The scheduler's pass over queued rows whose time has come. Returns how many went out."""
    sent = 0
    for row_id in outbox.due(now):
        sent += (await attempt(row_id, now)).state == "sent"
    return sent


def _after_failure(row: outbox.Row, exc: BaseException, now: datetime | None) -> outbox.Row:
    status = retry.status_of(exc)
    error = f"{type(exc).__name__} {status}" if status else type(exc).__name__
    if retry.transient(exc) and row.address:
        return outbox.later(row.id, error, QUEUED, GAVE_UP, now)
    if status in (401, 403):
        note = CREDENTIALS
    elif status:
        note = TEMPLATE_REJECTED if row.template else REJECTED
    else:
        note = NO_ANSWER
    return outbox.failed(row.id, error, note, now)


async def _send(row: outbox.Row, to: str, template: dict[str, Any] | None,
                now: datetime | None) -> tuple[str | None, str | None]:
    use_template = template is not None and (row.message is None or not window_open(row.recipient, now))
    if not use_template and row.message is not None:
        try:
            return await _send_message(row.message, to), None
        except httpx.HTTPStatusError as exc:
            if template is None or retry.transient(exc) or exc.response.status_code in (401, 403):
                raise
            log.info("outbox %s: free text refused (%s), trying the template", row.id, exc.response.status_code)
    if template is None:
        raise ValueError("nothing to send")
    wamid = await client.send(_template_payload(to, template))
    return wamid, TEMPLATE_USED if row.message is not None else None


async def _send_message(message: dict[str, Any], to: str) -> str | None:
    out = _OUTBOUND.validate_python(message)
    uploaded = {mid: await client.upload(mid) for mid in media_ids(out)}
    wamid = None
    for payload in to_payload(to, out, uploaded):
        wamid = await client.send(payload)
    return wamid


def _template_payload(to: str, template: dict[str, Any]) -> dict[str, Any]:
    params = [{"type": "text", "text": str(p)} for p in template["params"]]
    components: list[dict[str, Any]] = [{"type": "body", "parameters": params}]
    if template.get("button"):
        components.append({"type": "button", "sub_type": "url", "index": "0", "parameters": params})
    return {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, "type": "template",
            "template": {"name": template["name"], "language": {"code": template["language"]},
                         "components": components}}


def _synced(row: outbox.Row) -> outbox.Row:
    """The complaint thread shows the delivery as it changes."""
    if row.message_id:
        complaint_store.set_delivery(row.message_id, DELIVERY[row.state], row.note, row.wamid)
    return row


def _alert(row: outbox.Row) -> None:
    complaint = complaint_store.get(row.ticket) if row.ticket else None
    if complaint is None:
        return
    raise_alert("delivery_failed", complaint.section_id or complaint.unit_id, "Message not delivered",
                f"Complaint {complaint.ticket}: WhatsApp did not take a message for the consumer after "
                f"{row.attempts + 1} tries. Open the thread and use Send again.", "complaints.reply",
                f"delivery_failed:{row.id}", ticket=complaint.ticket, account_id=complaint.assigned_to)


async def send_reply(message: Outbound, recipient: str, address: str, dedupe_key: str) -> outbox.Row:
    """A bot message in a WhatsApp conversation. The dedupe key is stable across retries of the same turn or job."""
    return await deliver(outbox.NewItem(dedupe_key=dedupe_key, kind="reply", recipient=recipient, address=address,
                                        message=message.model_dump(exclude_none=True)))
