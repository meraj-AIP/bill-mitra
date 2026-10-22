"""Raising a complaint of a given type, from any surface: the consumer web page, the chat, or a staff member logging a
call or a walk-in. One place decides placement, priority, due date and ownership, so the surfaces never disagree.

Consumers never learn who handles a complaint; nothing returned here names a person.
"""

from dataclasses import dataclass

from app.core.hashing import service_hash
from app.domain import complaint_types
from app.domain.bill import ExtractedBill, mask
from app.domain.complaint_reply import request_text, triage
from app.flows import cases
from app.flows.analysis import analyse
from app.services import notify
from app.store import accounts, complaints, repos
from app.store.complaints import General, Placement

WRONG_READING = complaint_types.WRONG_READING


@dataclass(frozen=True)
class Raise:
    """One complaint as the raiser described it. `service_number` is the plain number: hashed and masked here."""

    user_id: str
    type: str
    discom: str
    description: str
    language: str
    channel: str | None
    source: str
    service_number: str | None = None
    bill_id: str | None = None
    reply_to: str | None = None
    raised_by: str | None = None
    contact_hash: str | None = None
    placement: Placement | None = None
    in_chat: bool = False  # the chat says follow-up questions itself, so nothing is sent separately


def issue_text(type_code: str, description: str) -> str:
    """What staff read in the inbox, in English: the type, then the raiser's own words."""
    return f"{complaint_types.get(type_code).label}. {description}"


def _bill_for(item: Raise) -> tuple[str | None, ExtractedBill | None]:
    """The linked bill, only when the raiser owns it (the consumer) or the complaint owner does (staff)."""
    if not item.bill_id:
        return None, None
    stored = repos.get_own_bill(item.user_id, item.bill_id)
    return (stored.id, stored.bill) if stored else (None, None)


def _checked(bill: ExtractedBill | None, user_id: str) -> dict[str, object]:
    """What the bill check found, for a complaint that links a bill: its triage and any overcharge."""
    if bill is None:
        return {}
    audit = analyse(bill, user_id).audit
    return {"triage": triage(audit), "amount": audit.overcharge}


def _ownership(bill: ExtractedBill | None, service_number: str | None) -> str:
    if bill is not None:
        return "verified"
    return "unverified" if service_number else "not_needed"


def open_duplicate(user_id: str, type_code: str, service_number: str | None, *, number_asked: bool = True) -> str | None:
    """An open complaint of this type the consumer already has, for the same service number when it is known. Before
    the number is asked, an unknown number matches only a complaint that has none."""
    return complaints.open_of_type(user_id, type_code, service_hash(service_number) if service_number else None,
                                   unknown_is_any=number_asked)


def add_to_open(ticket: str, words: str, source: str) -> None:
    """A repeat of an open complaint joins its thread instead of opening a second ticket."""
    complaints.add_message(ticket, "consumer", None, words, "stored")
    accounts.audit(None, "complaint.merge", ticket, f"source {source}")


def bill_request(ticket: str, language: str) -> str:
    return request_text("bill_photo", language, ticket)


async def _ask_for_bill(ticket: str, in_chat: bool) -> None:
    """A reading complaint without a bill: ask for the photo straight away, as an officer's request would."""
    complaint = complaints.get(ticket)
    assert complaint is not None
    message = bill_request(ticket, complaint.language or "te")
    if in_chat:
        complaints.add_message(ticket, "system", None, message, "sent")
        return
    outcome = await notify.send(complaint, message, kind="request")
    complaints.add_message(ticket, "system", None, message, outcome.delivery, outcome.note, wamid=outcome.wamid, outbox_id=outcome.outbox_id)
    repos.set_awaiting(complaint.user_id, "info:" + ticket)


async def submit(item: Raise) -> str:
    """Record the complaint and return its ticket. A reading complaint with a bill opens the review case instead."""
    bill_id, bill = _bill_for(item)
    if item.type == WRONG_READING and bill_id and bill is not None:
        return await cases.report(item.user_id, bill_id, analyse(bill, item.user_id), item.language,
                                  item.channel or "web", item.reply_to, item.description)
    service_number = (bill.service_number if bill else None) or item.service_number
    discom = bill.discom if bill else item.discom
    placement = item.placement or cases.place_general(discom, bill.section if bill else None)
    intake = complaints.intake_for(
        item.type, item.source, discom, raised_by=item.raised_by, contact_hash=item.contact_hash,
        service_number_hash=service_hash(service_number) if service_number else None,
        description=item.description, ownership=_ownership(bill, service_number))
    record = General(user_id=item.user_id, discom=discom, issue=issue_text(item.type, item.description),
                     language=item.language, channel=item.channel, reply_to=item.reply_to, bill_id=bill_id,
                     service_masked=mask(service_number), bill_month=bill.bill_month if bill else None,
                     **_checked(bill, item.user_id),
                     section_name=bill.section if bill else None)
    staff = item.raised_by is not None
    ticket = complaints.create_general(record, placement, intake, item.description,
                                       "officer" if staff else "consumer", item.raised_by)
    accounts.audit(item.raised_by, "complaint.create", ticket, f"type {item.type}, source {item.source}",
                   unit_id=placement.unit_id)
    if item.type == WRONG_READING and bill is None:
        await _ask_for_bill(ticket, item.in_chat)
    return ticket
