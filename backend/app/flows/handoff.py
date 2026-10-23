"""Handing a general complaint from one person to another, sending it back, and the alerts on review cases.

Who may hand to whom is decided by permissions, never by role names (docs/assist-contract.md section 4):
- an account that manages accounts (admin) may hand to anyone in scope who can see complaints;
- a decider (cases.decide, the section AE) to another decider, or back to desk staff (complaints.assign);
- other desk staff (officer, call centre) to a decider.
Every hand-off needs a note, writes the timeline through the audit log and alerts the new holder.
"""

from datetime import UTC, datetime
from typing import Any

from app.core.errors import Refusal
from app.store import accounts, handoffs, units
from app.store import complaints as store
from app.store.accounts import Account
from app.store.alerts import raise_alert
from app.store.complaints import OPEN_STATUSES, Complaint
from app.store.db import DISCOM_UNITS

NOTE_MIN, NOTE_MAX = 10, 300


class Refused(Refusal):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _chain(complaint: Complaint) -> list[str]:
    """The complaint's unit, every unit above it and its section's ERO: a scope on any of them covers it."""
    anchor = complaint.section_id or complaint.unit_id or DISCOM_UNITS.get(complaint.discom or "")
    if anchor is None:
        return []
    chain = units.ancestors(anchor)
    return [u.id for u in chain] + [u.ero_id for u in chain[:1] if u.ero_id]


def _allowed(account: Account, person: dict[str, Any]) -> bool:
    held = person["permissions"]
    # Whoever receives a complaint must be able to answer it, or it sits with someone who cannot act.
    if "complaints.reply" not in held:
        return False
    if account.can("accounts.manage"):
        return True
    if account.can("cases.decide"):
        return "cases.decide" in held or "complaints.assign" in held
    return "cases.decide" in held


def targets(account: Account, complaint: Complaint) -> list[dict[str, Any]]:
    """The people this account may hand this complaint to right now. Empty when it may not hand it over at all."""
    if complaint.kind != "general" or complaint.status not in OPEN_STATUSES or not account.can("complaints.assign"):
        return []
    people = [p for p in handoffs.candidates(_chain(complaint))
              if p["id"] not in (account.id, complaint.assigned_to) and _allowed(account, p)]
    if complaint.section_id is None and complaint.discom:
        # Still in the DISCOM queue: the section AEs this account covers are offered too, and handing to one places it.
        seen = {p["id"] for p in people} | {account.id, complaint.assigned_to}
        people += [p for p in handoffs.section_deciders(complaint.discom) if p["id"] not in seen and _allowed(account, p)
                   and (account.is_global or units.covers(account.id, p["section_id"]))]
    return people[:handoffs.CANDIDATES_MAX]


def _tell_holder(ticket: str, to: str, title: str, body: str, at: str) -> None:
    raise_alert("complaint_assigned", None, title, body, None, f"complaint_assigned:{ticket}:{to}:{at}",
                ticket=ticket, account_id=to)


def assign(account: Account, complaint: Complaint, to: str, note: str) -> None:
    chosen = next((p for p in targets(account, complaint) if p["id"] == to), None)
    if chosen is None:
        raise Refused(400, "Choose someone in this area you may hand this complaint to.")
    at = _now()
    if not handoffs.hand_over(complaint.ticket, complaint.assigned_to, chosen["id"], account.id, note, at):
        raise Refused(409, "This complaint changed hands or closed meanwhile. Reload it.")
    if chosen.get("section_id"):
        store.place(complaint.ticket, store.Placement(section_id=chosen["section_id"], unit_id=chosen["section_id"],
                                                      assigned_to=chosen["id"]))
    accounts.audit(account.id, "complaint.handoff", complaint.ticket, f"{chosen['name']}: {note}",
                   unit_id=chosen.get("section_id") or complaint.unit_id)
    _tell_holder(complaint.ticket, chosen["id"], "Complaint handed to you",
                 f"Complaint {complaint.ticket} was handed to you by {account.name}.", at)


def can_return(account: Account, complaint: Complaint, row: dict[str, Any]) -> bool:
    return (complaint.kind == "general" and complaint.status in OPEN_STATUSES and complaint.assigned_to == account.id
            and account.can("complaints.reply") and bool(row.get("handed_by")) and row["handed_by"] != account.id)


def send_back(account: Account, complaint: Complaint, note: str) -> None:
    """Back to whoever handed it over, as long as they can still see it."""
    row = store.row(complaint.ticket) or {}
    if not can_return(account, complaint, row):
        raise Refused(409, "Only the person holding a handed over complaint can send it back.")
    giver = next((p for p in handoffs.candidates(_chain(complaint)) if p["id"] == row["handed_by"]), None)
    if giver is None:
        raise Refused(409, "Whoever handed this over can no longer take it. Hand it to someone else.")
    at = _now()
    if not handoffs.hand_over(complaint.ticket, account.id, giver["id"], account.id, note, at):
        raise Refused(409, "This complaint changed hands or closed meanwhile. Reload it.")
    accounts.audit(account.id, "complaint.return", complaint.ticket, f"{giver['name']}: {note}",
                   unit_id=complaint.unit_id)
    _tell_holder(complaint.ticket, giver["id"], "Complaint sent back to you",
                 f"Complaint {complaint.ticket} was sent back to you by {account.name}.", at)


def case_assigned(ticket: str, to: str, by: Account | None) -> None:
    """A case moved to a decider, by a person or by rerouting after a section was mapped."""
    who = f" by {by.name}" if by else " by its section"
    raise_alert("case_assigned", None, "Case assigned to you", f"Case {ticket} was assigned to you{who}.", None,
                f"case_assigned:{ticket}:{to}:{_now()}", ticket=ticket, account_id=to)


def decision_returned(ticket: str, decision_id: int, proposer: str, by: Account) -> None:
    raise_alert("decision_returned", None, "Decision sent back",
                f"Case {ticket}: {by.name} sent your decision back with a note.", None,
                f"decision_returned:{decision_id}", ticket=ticket, account_id=proposer)
