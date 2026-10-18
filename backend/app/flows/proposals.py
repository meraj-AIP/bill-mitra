"""Routine work the rules can prepare for a person to approve (maker-checker). Nothing here acts on a complaint: it
only proposes, and app/api/proposals.py carries out what an officer approves, after checking the proposal again.

The rules propose only what an officer does the same way every time:
- explain_correct: the bill checks out line by line, so send the checked explanation and resolve.
- request_bill: a bill complaint came without a bill, so ask for a photo of it.
- request_meter: the bill's reading was estimated, so ask for a photo of the meter.
- decide_correct: a reading check where every rule says the bill is right, so record it as correct.
Any doubt and nothing is proposed; the complaint stays with its officer as before. Every reason given is a fixed
sentence, never model output, and carries no consumer data.
"""

from datetime import datetime, timedelta

from app.config import get_settings
from app.domain import capture, complaint_options
from app.flows import cases, drafts
from app.flows import complaint as complaint_flow
from app.flows.analysis import Analysis, analyse
from app.store import case_evidence, complaints, repos
from app.store import proposals as store
from app.store import review as review_store
from app.store.complaints import OPEN_STATUSES, Complaint
from app.store.proposals import Kind

PERMISSION: dict[Kind, str] = {"explain_correct": "complaints.reply", "request_bill": "complaints.reply",
                               "request_meter": "complaints.reply", "decide_correct": "cases.decide"}
# Raised from the bill: the types whose question is about the bill itself.
BILL_TYPES = ("high_bill", "estimated_bill", "wrong_category", "arrears_dispute")
Found = tuple[Kind, list[str]] | None


def _estimated(a: Analysis) -> bool:
    return any(c.key == "reading_status" and c.status == "fail" for c in capture.report(a.bill).checks)


def _reading_check(complaint: Complaint) -> Found:
    row = review_store.row(complaint.ticket)
    found = repos.get_bill(complaint.bill_id) if complaint.bill_id else None
    if row is None or row["state"] not in cases.DECIDABLE or found is None:
        return None
    records = case_evidence.records(complaint.ticket)
    a = analyse(found[0], complaint.user_id, [(m["month"], m["units"]) for m in records[1]] if records else [])
    if drafts.from_misread(complaint, a):
        return None  # a corrected reading changes money, so the AE decides it
    draft = drafts.clear_correct(complaint, a, cases.spike_for(a), review_store.requests(complaint.ticket))
    return ("decide_correct", draft.why) if draft else None


def _general(complaint: Complaint) -> Found:
    # Only a consumer who wrote in on WhatsApp or the web can be answered or asked there; a call is called back.
    if complaint.channel not in ("whatsapp", "web"):
        return None
    ctx = complaint_flow.options_context(complaint)
    if ctx.type not in BILL_TYPES or ctx.waiting or store.staff_replied(complaint.ticket):
        return None
    asks = complaint_options.allowed_asks(ctx)
    found = repos.get_bill(complaint.bill_id) if complaint.bill_id else None
    if found is None:
        if "bill_photo" in asks and "bill_photo" not in ctx.asked:
            return "request_bill", ["The complaint is about a bill, but no bill came with it.",
                                    "Every check needs the bill, so the consumer is asked for a photo of it."]
        return None
    a = analyse(found[0], complaint.user_id)
    if _estimated(a):
        if "meter_photo" in asks and "meter_photo" not in ctx.asked:
            return "request_meter", ["The meter status on the bill says the reading was estimated, not read.",
                                     "A photo of the meter shows the real reading before anyone decides."]
        return None
    if ctx.triage == "bill_correct" and complaint_flow.checked_reply(complaint):
        return "explain_correct", ["Every charge matches the TGERC tariff for the units billed.",
                                   "The meter was read, not estimated.",
                                   "The reply is the checked explanation; the complaint is then resolved."]
    return None


def assess(complaint: Complaint) -> Found:
    """What the rules would do with this complaint now, or None."""
    if complaint.status not in OPEN_STATUSES:
        return None
    return _reading_check(complaint) if complaint.kind == cases.KIND else _general(complaint)


def run(now: datetime) -> int:
    """One pass: proposals on closed complaints expire, then complaints that changed are looked at again. A complaint
    younger than PROPOSAL_WAIT_MINUTES waits for a later pass, since the consumer may still be sending things."""
    settings = get_settings()
    store.expire_closed()
    settled = (now - timedelta(minutes=settings.proposal_wait_minutes)).strftime("%Y-%m-%d %H:%M:%S")
    made = 0
    for ticket in store.candidates(settings.proposal_batch, settled):
        complaint = complaints.get(ticket)
        if complaint is None:
            continue
        found = assess(complaint)
        if found and store.add(ticket, *found):
            made += 1
        store.mark_checked(ticket)
    return made
