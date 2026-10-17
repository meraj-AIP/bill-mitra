"""One-tap complaint, recorded in Bill Mitra with the audit finding and the bill photo for the section officer.

There is no 1912 integration yet, so the consumer is told plainly to also call 1912 with the reference."""

from dataclasses import dataclass

from app.config import get_settings
from app.domain import complaint_reply
from app.domain.complaint_reply import RequestKind, Triage
from app.domain.conversation import guard
from app.domain.conversation.composer import month_label
from app.domain.conversation.facts import rs
from app.domain.conversation.intents import classify
from app.flows import cases
from app.flows.analysis import Analysis, analyse
from app.flows.turn import Turn
from app.services import llm, notify
from app.store import complaints, repos
from app.store import review as review_store
from app.store.complaints import OPEN_STATUSES, Complaint

LABEL_EN = {"energy": "Energy charge", "fixed": "Fixed charge", "customer": "Customer charge",
            "duty": "Electricity duty", "fsa": "FSA", "total": "Bill amount"}


def issue_for_discom(a: Analysis) -> str:
    """The complaint text the section officer reads in the console, in English."""
    over = [line for line in a.audit.lines if line.status == "over"]
    if not over:
        return ("Consumer asked for a review. Every tariff charge matches, so please check the meter reading and "
                "the other lines on the bill.")
    parts = [f"{LABEL_EN.get(line.code, line.code)} Rs {rs(line.difference)} above TGERC tariff "
             f"(printed Rs {rs(line.printed)}, expected Rs {rs(line.expected)})" for line in over]
    return "; ".join(parts)


def _issue_for_consumer(turn: Turn, a: Analysis) -> str:
    if a.audit.overcharge:
        return turn.t("status_mismatch", over=rs(a.audit.overcharge)).replace("*", "")
    return turn.t("reason_ok")


async def preview(turn: Turn, a: Analysis) -> None:
    turn.state.awaiting = "complaint"
    service = a.bill.masked_service_number() or "-"
    month = month_label(turn.lang, a.facts.month_number, a.facts.year)
    body = turn.t("complaint_preview", service=service, month=month, issue=_issue_for_consumer(turn, a))
    await turn.buttons(body, [("complaint_send", "btn_send"), ("complaint_cancel", "btn_cancel"),
                              ("cnew", "btn_other_problem")])


async def submit(turn: Turn, a: Analysis) -> None:
    async with turn.tracer.step("Record the complaint", "channel") as step:
        issue = issue_for_discom(a)
        ticket = complaints.create(turn.state.user_id, turn.state.current_bill_id, a.bill, issue,
                                   a.audit.overcharge, turn.lang, turn.inbound.channel, turn.inbound.reply_to, issue,
                                   complaint_reply.triage(a.audit),
                                   placement=cases.place_general(a.bill.discom, a.bill.section))
        step.note(f"Reference {ticket}; bill photo and audit lines attached for the console. Not sent to 1912")
    turn.state.awaiting = None
    days = get_settings().complaint_reply_days
    await turn.say(turn.t("complaint_filed", ticket=ticket) + "\n" + turn.t("complaint_next", days=days))
    repos.log_event(turn.inbound.channel, "complaint", language=turn.lang, amount=a.audit.overcharge,
                    discom=a.bill.discom)


INFO_PREFIX = "info:"
PHOTO_NOTE = "Photo from the consumer, sent after the officer asked."


@dataclass(frozen=True)
class Suggestion:
    text: str
    triage: Triage
    worded_by: str  # "ai" when the model reworded the checked draft and the guard passed it, else "rules"


async def suggest_reply(complaint: Complaint) -> Suggestion | None:
    """A reply the officer can send as is, in the consumer's language. None when the bill is gone."""
    found = repos.get_bill(complaint.bill_id) if complaint.bill_id else None
    if not found:
        return None
    a = analyse(found[0], complaint.user_id)
    language = complaint.language or "te"
    checked = complaint_reply.draft(a.facts, a.audit, language)
    kind = complaint_reply.triage(a.audit)
    worded = await llm.polish_reply(checked, language)
    if worded and guard.check(worded, a.facts, guard.numbers_in(checked)).passed:
        return Suggestion(worded, kind, "ai")
    return Suggestion(checked, kind, "rules")


def checked_reply(complaint: Complaint) -> str | None:
    """The rules-only draft, for bulk sends where nobody reads each reply first."""
    found = repos.get_bill(complaint.bill_id) if complaint.bill_id else None
    if not found:
        return None
    a = analyse(found[0], complaint.user_id)
    return complaint_reply.draft(a.facts, a.audit, complaint.language or "te")


async def ask(complaint: Complaint, kind: RequestKind, account_id: str, note: str | None = None) -> notify.Outcome:
    """Ask the consumer for something on their channel. Their next photo or message is filed under the complaint."""
    message = complaint_reply.request_text(kind, complaint.language or "te", complaint.ticket)
    if note:
        message += "\n" + note
    outcome = await notify.send(complaint, message)
    complaints.add_message(complaint.ticket, "officer", account_id, message, outcome.delivery, outcome.note)
    repos.set_awaiting(complaint.user_id, INFO_PREFIX + complaint.ticket)
    return outcome


async def capture_info(turn: Turn) -> bool:
    """After an officer asks for something, the consumer's next photo or message goes to that complaint."""
    awaiting = turn.state.awaiting or ""
    inbound = turn.inbound
    if not awaiting.startswith(INFO_PREFIX) or inbound.kind not in ("image", "document", "text"):
        return False
    if inbound.kind == "text" and (not inbound.text or classify(inbound.text).intent == "stop"):
        return False
    turn.state.awaiting = None
    complaint = complaints.get(awaiting.removeprefix(INFO_PREFIX))
    if complaint is None or complaint.user_id != turn.state.user_id or complaint.status not in OPEN_STATUSES:
        return False
    body = inbound.text if inbound.kind == "text" and inbound.text else PHOTO_NOTE
    media_id = inbound.media_id if inbound.kind != "text" else None
    complaints.add_message(complaint.ticket, "consumer", None, body, "stored", media_id=media_id)
    review_store.answer_requests(complaint.ticket)
    key = "review_info_received" if complaint.kind == cases.KIND else "complaint_info_received"
    await turn.say_key(key, ticket=complaint.ticket)
    return True
