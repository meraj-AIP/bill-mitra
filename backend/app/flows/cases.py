"""Wrong reading cases: spotting a suspicious bill, opening a case, routing it to the section AE and telling the
consumer what was decided. Every amount the consumer hears comes from the engine or the printed bill."""

from typing import Any, Literal

from pydantic import BaseModel

from app.domain import review
from app.domain.conversation.composer import month_label
from app.domain.conversation.facts import rs
from app.domain.conversation.lang import text
from app.domain.review import Spike
from app.flows.analysis import Analysis
from app.flows.turn import Turn
from app.services import notify
from app.store import accounts, complaints, units
from app.store import policy as policy_store
from app.store import review as review_store
from app.store.complaints import Complaint, Placement
from app.store.db import DISCOM_UNITS
from app.store.units import Conflict

KIND = "wrong_reading"
FIRST_MESSAGE = "Consumer asked the section AE to check the meter reading on this bill."


class Revision(BaseModel):
    original_amount: float
    revised_amount: float
    reason: str  # in the consumer's language
    decided_by: str
    decided_at: str
    status: Literal["pending_update", "applied"]


class ReviewSummary(BaseModel):
    ticket: str
    state: review_store.State
    revision: Revision | None


def spike_for(a: Analysis) -> Spike:
    return review.detect(a.bill, a.comp, a.history, policy_store.get(a.bill.discom))


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
    accounts.audit(None, "case.route", ticket, f"section {placement.section_id or 'unmapped'}, "
                   f"assignee {placement.assigned_to or 'none'}", unit_id=placement.unit_id)


def _issue(spike: Spike) -> str:
    """What the AE reads in the case list, in English."""
    if spike.reason == "reading_went_back":
        return "Consumer asked for a reading check. The present reading is lower than the previous reading."
    if spike.reason == "above_normal" and spike.median_units:
        return (f"Consumer asked for a reading check. {spike.units} units against a usual "
                f"{spike.median_units:g} over {spike.months_used} months.")
    return "Consumer asked for a reading check."


def open_case(user_id: str, bill_id: str, a: Analysis, language: str, channel: str, reply_to: str | None,
              note: str | None) -> str:
    spike = spike_for(a)
    facts = {"units": spike.units, "median_units": spike.median_units, "printed_amount": a.bill.bill_amount,
             "usual_amount": spike.usual_amount, "reason": spike.reason}
    placement = route(a.bill.discom, a.bill.section)
    ticket = complaints.create(user_id, bill_id, a.bill, _issue(spike), 0.0, language, channel, reply_to,
                               note or FIRST_MESSAGE, "needs_check", kind=KIND, placement=placement, case_facts=facts)
    _audit_route(ticket, placement)
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


def summary(ticket: str, language: str) -> ReviewSummary | None:
    row = review_store.row(ticket)
    if row is None:
        return None
    found = review_store.latest_revision(ticket)
    revision = None
    if found:
        by = found["decided_by"] or found["proposed_by"]
        revision = Revision(original_amount=found["original_amount"], revised_amount=found["revised_amount"],
                            reason=text(language, f"reason_{found['reason_code']}"), decided_by=by["name"],
                            decided_at=found["decided_at"], status="applied" if found["applied_at"] else "pending_update")
    return ReviewSummary(ticket=ticket, state=row["state"], revision=revision)


def _month(language: str, bill_month: str | None) -> str:
    if not bill_month:
        return ""
    return month_label(language, int(bill_month[5:7]), int(bill_month[:4]))


async def tell_consumer(complaint: Complaint, actor_id: str, bill_month: str | None, key: str,
                        **values: object) -> None:
    """A localised message on the consumer's own channel, kept in the thread with how it was delivered."""
    language = complaint.language or "te"
    message = text(language, key, ticket=complaint.ticket, month=_month(language, bill_month), **values)
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
    """One extra message after a bill that looks like a wrong reading, with a button to ask the AE."""
    spike = spike_for(a)
    if not spike.flagged:
        return
    if spike.reason == "reading_went_back":
        body = turn.t("spike_back")
    else:
        body = turn.t("spike_above", units=spike.units, median=round(spike.median_units or 0))
    await turn.buttons(body, [("review_request", "btn_review")])


async def request_from_chat(turn: Turn, a: Analysis) -> None:
    bill_id = turn.state.current_bill_id
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
    await turn.say_key("review_filed", ticket=ticket, days=policy_store.get(a.bill.discom).decision_sla_days)
