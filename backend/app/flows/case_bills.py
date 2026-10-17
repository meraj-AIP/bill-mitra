"""Supporting bills on a wrong reading case: the system asks for the months nobody has given us yet, bills the
consumer uploads for those months are attached, and a consumer without them can say so.

Every step here is automatic, so its audit entry has no actor (shown as System). Consumer text comes from the
language packs; what staff read in the thread is English.
"""

from dataclasses import dataclass

from app.domain.bill import ExtractedBill
from app.domain.conversation.composer import month_label
from app.domain.conversation.lang import text
from app.flows.turn import Turn
from app.services import notify
from app.store import accounts, complaints
from app.store import case_evidence as evidence_store
from app.store.complaints import Complaint

NO_BILLS_NOTE = "Consumer says they do not have the requested bills."


def month_name(language: str, month: str | None) -> str:
    return month_label(language, int(month[5:7]), int(month[:4])) if month else ""


def month_list(language: str, months: list[str]) -> str:
    names = [month_name(language, m) for m in months]
    if len(names) < 2:
        return "".join(names)
    return ", ".join(names[:-1]) + text(language, "join_last") + names[-1]


async def _deliver(complaint: Complaint, message: str, turn: Turn | None) -> str:
    """In the chat the turn answers, on its own channel; a web report is read in the app. Kept in the thread."""
    if turn is not None:
        await turn.say(message)
        delivery = "sent" if notify.reply_channel(complaint) == "whatsapp" else "stored"
        complaints.add_message(complaint.ticket, "system", None, message, delivery)
        return delivery
    outcome = await notify.send(complaint, message)
    complaints.add_message(complaint.ticket, "system", None, message, outcome.delivery, outcome.note)
    return outcome.delivery


async def request_months(complaint: Complaint, bill_month: str, months: list[str], turn: Turn | None) -> None:
    """Ask for a photo of each missing month, in the consumer's language, on their channel."""
    language = complaint.language or "te"
    evidence_store.add_month_request(complaint.ticket, months, "Earlier bills for " + ", ".join(months))
    message = text(language, "review_need_bills", month=month_name(language, bill_month),
                   months=month_list(language, months))
    delivery = await _deliver(complaint, message, turn)
    accounts.audit(None, "case.request", complaint.ticket, f"earlier bills for {', '.join(months)}, "
                   f"delivery {delivery}", unit_id=complaint.unit_id)


@dataclass(frozen=True)
class Attached:
    ticket: str
    month: str
    complete: bool


def attach_upload(user_id: str, bill_id: str, bill: ExtractedBill, media_id: str | None) -> list[Attached]:
    """File a fresh upload under every open case of this user that asked for its month on the same connection."""
    if not bill.service_number or not bill.bill_month:
        return []
    out = []
    for request in evidence_store.open_month_requests(user_id, bill.service_number):
        if bill.bill_month not in request["months"]:
            continue
        ticket = request["ticket"]
        if not evidence_store.attach(ticket, request["id"], bill.bill_month, bill_id):
            continue
        found = evidence_store.month_request(ticket)
        received = set(found["received"]) if found else set()
        complete = set(request["months"]) <= received
        complaints.add_message(ticket, "consumer", None, f"Bill for {bill.bill_month} sent for this check.", "stored",
                               media_id=media_id)
        if complete:
            evidence_store.answer(request["id"])
        complaint = complaints.get(ticket)
        accounts.audit(None, "case.attach", ticket, f"bill for {bill.bill_month}, {len(received)} of "
                       f"{len(request['months'])} received", unit_id=complaint.unit_id if complaint else None)
        out.append(Attached(ticket, bill.bill_month, complete))
    return out


async def tell_attached(turn: Turn, attached: list[Attached]) -> None:
    for item in attached:
        await turn.say_key("review_bill_received", month=month_name(turn.lang, item.month), ticket=item.ticket)
        if item.complete:
            await turn.say_key("review_bills_complete", ticket=item.ticket)


def no_bills(ticket: str, request_id: int) -> None:
    """The consumer does not have the months asked for: the request is answered with that note."""
    complaint = complaints.get(ticket)
    complaints.add_message(ticket, "consumer", None, NO_BILLS_NOTE, "stored")
    evidence_store.answer(request_id)
    accounts.audit(None, "case.no_bills", ticket, "request answered: consumer has no earlier bills",
                   unit_id=complaint.unit_id if complaint else None)


async def no_bills_from_chat(turn: Turn) -> bool:
    """True when the message answered an open request for earlier bills."""
    found = evidence_store.open_month_request_for_user(turn.state.user_id)
    if found is None:
        return False
    no_bills(found["ticket"], found["id"])
    await turn.say_key("review_no_bills", ticket=found["ticket"])
    return True
