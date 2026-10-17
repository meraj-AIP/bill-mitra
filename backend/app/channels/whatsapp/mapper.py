"""Pure mapping between WhatsApp Cloud API payloads and the engine's messages. No I/O here."""

import hashlib
from dataclasses import dataclass
from typing import Any

from app.core.messages import AudioOut, ButtonsOut, ImageOut, ListOut, Outbound, TextOut


@dataclass(frozen=True)
class IncomingWhatsApp:
    wa_id: str  # the sender's number; never logged, stored only on a complaint so an officer can answer
    message_id: str
    kind: str  # text | image | document | audio | button_reply
    text: str | None = None
    reply_id: str | None = None
    media_ref: str | None = None  # WhatsApp media id, downloaded by the client
    mime_type: str | None = None


def user_key(wa_id: str) -> str:
    """Stable pseudonymous id, so the database never holds a phone number."""
    return "wa:" + hashlib.sha256(wa_id.encode()).hexdigest()[:20]


@dataclass(frozen=True)
class DeliveryFailure:
    wamid: str
    error_code: int | None


def parse_failures(payload: dict[str, Any]) -> list[DeliveryFailure]:
    """Messages Meta accepted but later could not deliver. Sent, delivered and read statuses need no action."""
    out: list[DeliveryFailure] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for st in change.get("value", {}).get("statuses", []):
                if st.get("status") == "failed" and isinstance(st.get("id"), str):
                    code = next((e.get("code") for e in st.get("errors") or [] if isinstance(e.get("code"), int)), None)
                    out.append(DeliveryFailure(st["id"], code))
    return out


def parse_webhook(payload: dict[str, Any]) -> list[IncomingWhatsApp]:
    out: list[IncomingWhatsApp] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                parsed = _parse_message(msg)
                if parsed:
                    out.append(parsed)
    return out


def _parse_message(msg: dict[str, Any]) -> IncomingWhatsApp | None:
    kind, sender, mid = msg.get("type"), msg.get("from", ""), msg.get("id", "")
    if kind == "text":
        return IncomingWhatsApp(sender, mid, "text", text=msg.get("text", {}).get("body", ""))
    if kind in ("image", "document", "audio"):
        body = msg.get(kind, {})
        mapped = "audio" if kind == "audio" else "image" if kind == "image" else "document"
        return IncomingWhatsApp(sender, mid, mapped, media_ref=body.get("id"), mime_type=body.get("mime_type"))
    if kind == "interactive":
        inter = msg.get("interactive", {})
        reply = inter.get("button_reply") or inter.get("list_reply") or {}
        return IncomingWhatsApp(sender, mid, "button_reply", reply_id=reply.get("id"))
    if kind == "button":
        return IncomingWhatsApp(sender, mid, "button_reply", reply_id=msg.get("button", {}).get("payload"))
    if sender and mid and kind not in ("reaction", "system"):
        # Video, sticker, location, contacts: answered with what Bill Mitra can take, never left unanswered.
        return IncomingWhatsApp(sender, mid, "unsupported")
    return None


def to_payload(to: str, message: Outbound, uploaded: dict[str, str]) -> list[dict[str, Any]]:
    """Graph API /messages bodies for one outbound message. `uploaded` maps our media ids to WhatsApp ids."""
    base = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to}
    if isinstance(message, TextOut):
        return [base | {"type": "text", "text": {"body": message.body, "preview_url": False}}]
    if isinstance(message, ImageOut):
        image: dict[str, Any] = {"id": uploaded[message.media_id]}
        if message.caption:
            image["caption"] = message.caption
        return [base | {"type": "image", "image": image}]
    if isinstance(message, AudioOut):
        return [base | {"type": "audio", "audio": {"id": uploaded[mid]}} for mid in message.media_ids]
    if isinstance(message, ButtonsOut):
        buttons = [{"type": "reply", "reply": {"id": b.id, "title": b.title}} for b in message.buttons]
        return [base | {"type": "interactive", "interactive": {
            "type": "button", "body": {"text": message.body}, "action": {"buttons": buttons}}}]
    if isinstance(message, ListOut):
        rows = [{"id": r.id, "title": r.title, **({"description": r.description} if r.description else {})}
                for r in message.rows]
        return [base | {"type": "interactive", "interactive": {
            "type": "list", "body": {"text": message.body},
            "action": {"button": message.button_label, "sections": [{"title": message.button_label, "rows": rows}]}}}]
    return []


def media_ids(message: Outbound) -> list[str]:
    if isinstance(message, ImageOut):
        return [message.media_id]
    if isinstance(message, AudioOut):
        return list(message.media_ids)
    return []
