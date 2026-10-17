"""Wrong reading cases: spotting a suspicious bill, taking the consumer's report, routing it to the section AE,
building the evidence pack and telling the consumer what was decided. Every amount the consumer hears comes from
the engine, the printed bill or a stored decision.

Consumers never see who reviews. Their copy names the office (the DISCOM), never a person or a role.
"""

from typing import Any, Literal

from pydantic import BaseModel

from app.domain import review
from app.domain.conversation.facts import rs, with_revision
from app.domain.conversation.lang import text
from app.domain.review import Final, Spike
from app.flows import case_bills, misread
from app.flows.analysis import Analysis, analyse
from app.flows.turn import Turn
from app.services import billing_records, notify
from app.store import accounts, complaints, repos, units
from app.store import case_evidence as evidence_store
from app.store import policy as policy_store
from app.store import review as review_store
from app.store.complaints import Complaint, Placement
from app.store.db import DISCOM_UNITS
from app.store.units import Conflict

KIND = "wrong_reading"
FIRST_MESSAGE = "Consumer reported this bill as wrong."
ConsumerState = Literal["received", "waiting_for_you", "revised", "no_change"]


class Revision(BaseModel):
    original_amount: float
    revised_amount: float
    original_total: float | None
    revised_total: float | None
    reason: str  # in the consumer's language
    office: str
    decided_at: str
    status: Literal["pending_update", "applied"]


class ReviewSummary(BaseModel):
    """The consumer's view of a case: no names, no staff states."""

    ticket: str
    state: ConsumerState
    requested_months: list[str]
    received_months: list[str]
    revision: Revision | None


def spike_for(a: Analysis) -> Spike:
    return review.detect(a.bill, a.comp, a.history, policy_store.get(a.bill.discom))


def office(language: str, discom: str | None) -> str:
    return discom if discom in DISCOM_UNITS else text(language, "office_unknown")


def _section(discom: str | None, printed: str | None) -> str | None:
    """The matched section; a printed name nobody has mapped yet goes on the unmapped list."""
    found = units.match_section(discom, printed)
    if found is None and printed and units.norm(printed) and discom in DISCOM_UNITS:
        units.record_unmapped(discom, printed)
    return found


def place_general(discom: str | None, printed: str | None) -> Placement:
    """A general complaint sits on its section, or its DISCOM when the section is not known. Nobody is assigned."""
    section_id = _section(discom, printed)
    return Placement(section_id=section_id, unit_id=section_id or DISCOM_UNITS.get(discom or ""))


def route(discom: str | None, printed: str | None) -> Placement:
    """To the section's least busy AE; with no AE, unassigned at the section's division; unmapped, at the DISCOM."""
    section_id = _section(discom, printed)
    if section_id is None:
        return Placement(section_id=None, unit_id=DISCOM_UNITS.get(discom or ""))
    assignee = review_store.least_busy_decider(section_id)
    if assignee:
        return Placement(section_id=section_id, unit_id=section_id, assigned_to=assignee)
    division = next((u.id for u in units.ancestors(section_id) if u.kind == "division"), section_id)
    return Placement(section_id=section_id, unit_id=division)


def _audit_route(ticket: str, placement: Placement) -> None:
    """Names, not ids, because the staff timeline reads this line as written. Staff names only, no consumer data."""
    section = units.get(placement.section_id) if placement.section_id else None
    person = accounts.get(placement.assigned_to) if placement.assigned_to else None
    accounts.audit(None, "case.route", ticket, f"section {section.name if section else 'unmapped'}, "
                   f"assignee {person.name if person else 'none'}", unit_id=placement.unit_id)


def _issue(spike: Spike) -> str:
    """What the AE reads in the case list, in English."""
    if spike.reason == "reading_went_back":
        return "Consumer reported the bill as wrong. The present reading is lower than the previous reading."
    if spike.reason == "above_normal" and spike.median_units:
        return (f"Consumer reported the bill as wrong. {spike.units} units against a usual "
                f"{spike.median_units:g} over {spike.months_used} months.")
    return "Consumer reported the bill as wrong."


def open_case(user_id: str, bill_id: str, a: Analysis, language: str, channel: str, reply_to: str | None,
              note: str | None) -> str:
    """Create the case and route it. Raises Conflict when a check is already open for the bill."""
    spike = spike_for(a)
    facts = {"units": spike.units, "median_units": spike.median_units, "printed_amount": a.bill.bill_amount,
             "usual_amount": spike.usual_amount, "reason": spike.reason}
    placement = route(a.bill.discom, a.bill.section)
    ticket = complaints.create(user_id, bill_id, a.bill, _issue(spike), 0.0, language, channel, reply_to,
                               note or FIRST_MESSAGE, "needs_check", kind=KIND, placement=placement, case_facts=facts)
    _audit_route(ticket, placement)
    misread.on_case_opened(ticket, user_id, a.bill)
    return ticket


async def report(user_id: str, bill_id: str, a: Analysis, language: str, channel: str, reply_to: str | None,
                 note: str | None, turn: Turn | None = None) -> str:
    """Everything that happens on a report, with no staff action: the case, its route, the evidence pack and the
    request for earlier months nobody has given us. In the chat, `turn` carries the request to the consumer."""
    ticket = open_case(user_id, bill_id, a, language, channel, reply_to, note)
    await after_report(ticket, a, turn)
    return ticket


def reroute(discom: str, names: set[str]) -> list[str]:
    """After a printed name is mapped, open cases that carried it move to the section."""
    moved = []
    for ticket, printed in complaints.unrouted(discom, names):
        placement = route(discom, printed)
        if placement.section_id:
            complaints.place(ticket, placement)
            _audit_route(ticket, placement)
            moved.append(ticket)
    return moved


def final_for(bill_id: str | None, a: Analysis) -> Final:
    """The bill for the month as it stands now: the newest approved revision, else the printed figures."""
    found = evidence_store.final_revision(bill_id) if bill_id else None
    return review.final(a.facts.bill_amount, a.bill.total_payable, a.bill.arrears,
                        found["revised_amount"] if found else None, bool(found and found["applied_at"]))


def with_final(a: Analysis, bill_id: str | None) -> Analysis:
    """The analysis a chat answer quotes: after an approved revision, the revised amount and total."""
    final = final_for(bill_id, a)
    if final.revised:
        a.facts = with_revision(a.facts, final.bill_amount)
    return a


def _consumer_state(staff_state: str, revision: dict[str, Any] | None) -> ConsumerState:
    if revision is not None and staff_state in ("decided", "applied"):
        return "revised"
    if staff_state in ("decided", "applied"):
        return "no_change"
    return "waiting_for_you" if staff_state == "info_requested" else "received"


def summary(ticket: str, language: str) -> ReviewSummary | None:
    row = review_store.row(ticket)
    complaint = complaints.get(ticket)
    if row is None or complaint is None:
        return None
    found = review_store.latest_revision(ticket)
    stored = repos.get_bill(complaint.bill_id) if complaint.bill_id else None
    revision = None
    if found:
        printed_total = stored[0].total_payable if stored else None
        arrears = stored[0].arrears if stored else 0.0
        revision = Revision(original_amount=found["original_amount"], revised_amount=found["revised_amount"],
                            original_total=printed_total,
                            revised_total=review.final_total(found["revised_amount"], arrears, printed_total),
                            reason=text(language, f"reason_{found['reason_code']}"),
                            office=office(language, complaint.discom), decided_at=found["decided_at"],
                            status="applied" if found["applied_at"] else "pending_update")
    request = evidence_store.month_request(ticket)
    return ReviewSummary(ticket=ticket, state=_consumer_state(row["state"], found),
                         requested_months=request["months"] if request else [],
                         received_months=request["received"] if request else [], revision=revision)


async def tell_consumer(complaint: Complaint, actor_id: str | None, bill_month: str | None, key: str,
                        **values: object) -> None:
    """A localised message on the consumer's own channel, kept in the thread with how it was delivered."""
    language = complaint.language or "te"
    message = text(language, key, ticket=complaint.ticket, month=case_bills.month_name(language, bill_month),
                   office=office(language, complaint.discom), **values)
    outcome = await notify.send(complaint, message)
    complaints.add_message(complaint.ticket, "system", actor_id, message, outcome.delivery, outcome.note)


async def tell_decision(complaint: Complaint, actor_id: str, bill_month: str | None, decision: dict[str, Any]) -> None:
    language = complaint.language or "te"
    if decision["revision"]:
        await tell_consumer(complaint, actor_id, bill_month, "review_revised",
                            reason=text(language, f"reason_{decision['reason_code']}"),
                            revised=rs(decision["revised_amount"]),
                            original=rs(decision["original_amount"]),
                            revision=decision["revision"])
    else:
        await tell_consumer(complaint, actor_id, bill_month, "review_correct",
                            original=rs(decision["original_amount"]))


async def offer(turn: Turn, a: Analysis) -> None:
    """One extra message after a bill that looks like a wrong reading, with the same report button as the card."""
    spike = spike_for(a)
    if not spike.flagged:
        return
    where = office(turn.lang, a.bill.discom)
    if spike.reason == "reading_went_back":
        body = turn.t("spike_back", office=where)
    else:
        body = turn.t("spike_above", units=spike.units, median=round(spike.median_units or 0), office=where)
    await turn.buttons(body, [("report_bill", "btn_report")])


async def report_from_chat(turn: Turn, a: Analysis, bill_id: str | None = None) -> None:
    """The report button or a message saying the bill is wrong, for the bill the chat is about unless `bill_id`
    names another of the consumer's bills (with `a` its analysis)."""
    bill_id = bill_id or turn.state.current_bill_id
    if bill_id is None:
        await turn.say_key("need_bill")
        return
    existing = complaints.open_for_bill(bill_id, KIND)
    if existing:
        await turn.say_key("review_exists", ticket=existing)
        return
    try:
        ticket = open_case(turn.state.user_id, bill_id, a, turn.lang, turn.inbound.channel, turn.inbound.reply_to,
                           None)
    except Conflict:  # a second tap raced the first
        await turn.say_key("review_exists", ticket=complaints.open_for_bill(bill_id, KIND) or "")
        return
    await turn.say_key("review_filed", ticket=ticket, office=office(turn.lang, a.bill.discom),
                       days=policy_store.get(a.bill.discom).decision_sla_days)
    await after_report(ticket, a, turn)


async def offer_misread(turn: Turn, found: misread.Misread | None, discom: str | None) -> None:
    """The bill just sent shows the month before was read too high. Printed readings only, no amounts."""
    if found is None:
        return
    body = turn.t("misread_offer", month=case_bills.month_name(turn.lang, found.earlier_month),
                  printed=f"{found.printed_present:g}", next=f"{found.next_previous:g}", office=office(turn.lang, discom))
    await turn.buttons(body, [("report_misread", "btn_report_misread")])


async def report_misread(turn: Turn) -> None:
    """The consumer tapped to have the earlier month checked. Found again from storage, never trusted from the tap."""
    current = repos.get_own_bill(turn.state.user_id, turn.state.current_bill_id or "")
    found = misread.earlier_for(turn.state.user_id, current.bill) if current else None
    if found is None:
        await turn.say_key("need_bill")
        return
    await report_from_chat(turn, analyse(found[1], turn.state.user_id), found[0])


async def after_report(ticket: str, a: Analysis, turn: Turn | None) -> None:
    """The automatic steps after the case exists: evidence pack and the request for missing months."""
    complaint = complaints.get(ticket)
    assert complaint is not None
    records = await billing_records.fetch(a.bill.service_number)
    evidence_store.save_records(ticket, records.status, [m.model_dump() for m in records.months])
    on_file = {h.month for h in a.history} | {m.month for m in records.months}
    accounts.audit(None, "case.pack", ticket, f"this bill, {len(a.bill.usage_history)} printed months, "
                   f"{sum(h.source == 'uploaded' for h in a.history)} uploads, DISCOM records {records.status.replace('_', ' ')}, "
                   f"spike {'flagged' if spike_for(a).flagged else 'not flagged'}", unit_id=complaint.unit_id)
    missing = review.missing_months(a.facts.month, on_file)
    if missing:
        await case_bills.request_months(complaint, a.facts.month, missing, turn)
