"""AI help for the AE on a wrong reading case, on request only (docs/assist-contract.md section 2).

Conflicts always come from the engine's facts, never from the model. The model writes the summary and questions and
picks one next step from a fixed set; it never decides, and the drafted decision stays the rules' job
(app/flows/drafts.py).
"""

from typing import Any, Literal

from pydantic import BaseModel

from app.domain import capture
from app.domain.conversation.facts import rs
from app.domain.conversation.lang import text
from app.domain.review import Spike
from app.flows import drafts
from app.flows.analysis import Analysis
from app.flows.assist import SUMMARY_MAX, Question, consumer_words, figures, line, questions
from app.services import llm
from app.store import complaints
from app.store import review as review_store
from app.store import suggestions as suggestion_store
from app.store.complaints import OPEN_STATUSES, Complaint

Suggested = Literal["draft", "ask_consumer", "decide"]
DECIDABLE = ("awaiting_review", "info_requested", "rejected")  # as app/api/review.py
CASE_WHY = "Shows the real reading to set against the bill."
SUGGESTED_WHY: dict[str, str] = {
    "draft": "The rules have drafted a decision from the evidence: check it, then record it.",
    "ask_consumer": "The bill looks unusual and nothing from the consumer is on file yet.",
    "decide": "The evidence on file is enough to decide.",
}


class CaseAssist(BaseModel):
    summary: str
    conflicts: list[str]
    questions: list[Question]
    suggested: Suggested
    why: str  # one English line on why that next step
    worded_by: Literal["ai", "rules"]


def conflicts(ticket: str, a: Analysis, spike: Spike) -> list[str]:
    """What the engine's facts disagree on. Staff English; every figure is the engine's or as printed."""
    out = []
    if spike.reason == "reading_went_back":
        out.append("The present reading is lower than the previous reading.")
    elif spike.flagged and spike.median_units is not None:
        out.append(f"{spike.units} units billed against a usual {spike.median_units:g} over {spike.months_used} "
                   "months.")
    found = suggestion_store.get(ticket)
    if found and a.bill.present_reading is not None:
        out.append(f"The next bill starts from {found.corrected_present_reading}, below this bill's present reading "
                   f"of {a.bill.present_reading:g}: a misread.")
    if any(c.key == "reading_status" and c.status == "fail" for c in capture.report(a.bill).checks):
        out.append("The reading is marked estimated on the bill, not read from the meter.")
    if a.audit.overcharge:
        out.append(f"Charges are Rs {rs(a.audit.overcharge)} above the TGERC tariff for the units billed.")
    elif a.audit.status == "mismatch":
        out.append("A printed charge does not match the TGERC tariff.")
    return out


def _has_draft(complaint: Complaint, a: Analysis, spike: Spike, state: str, requests: list[dict[str, Any]]) -> bool:
    if complaint.status not in OPEN_STATUSES or state not in DECIDABLE:
        return False
    return bool(drafts.from_misread(complaint, a) or drafts.clear_correct(complaint, a, spike, requests))


def _facts(complaint: Complaint, row: dict[str, Any], a: Analysis, spike: Spike, found: list[str],
           requests: list[dict[str, Any]], photo: bool) -> dict[str, Any]:
    return {"ticket": complaint.ticket, "state": row["state"], "days_open": row["days_open"],
            "bill": {"month": a.facts.month, "units": a.facts.units, "bill_amount": a.facts.bill_amount,
                     "previous_reading": a.bill.previous_reading, "present_reading": a.bill.present_reading,
                     "audit_status": a.audit.status, "above_tariff": a.audit.overcharge},
            "usual_units": spike.median_units, "months_compared": spike.months_used, "conflicts": found,
            "open_requests": sorted({r["kind"] for r in requests if r["status"] == "open"}),
            "consumer_sent_photo": photo}


def _rules(complaint: Complaint, row: dict[str, Any], a: Analysis, found: list[str], open_now: bool, photo: bool,
           has_draft: bool) -> CaseAssist:
    state = row["state"].replace("_", " ")
    seen = f" {len(found)} conflict{'s' if len(found) > 1 else ''} found." if found else " The rules found no conflict."
    summary = (f"Wrong reading case, {state}, open {row['days_open']} days. Bill for {a.facts.month}: "
               f"{a.facts.units} units, Rs {rs(a.facts.bill_amount)}.{seen}")
    thin = not open_now and not photo
    suggested: Suggested = "draft" if has_draft else "ask_consumer" if thin and found else "decide"
    asks = [] if open_now or complaint.status not in OPEN_STATUSES else \
        [Question(text=text(complaint.language or "te", "assist_q_wrong_reading"), why=CASE_WHY)]
    return CaseAssist(summary=summary, conflicts=found, questions=asks, suggested=suggested,
                      why=SUGGESTED_WHY[suggested], worded_by="rules")


async def for_case(complaint: Complaint, a: Analysis, spike: Spike) -> CaseAssist:
    row = review_store.row(complaint.ticket) or {}
    requests = review_store.requests(complaint.ticket)
    photo = any(m["author_kind"] == "consumer" and m["media_id"] for m in complaints.messages(complaint.ticket))
    found = conflicts(complaint.ticket, a, spike)
    has_draft = _has_draft(complaint, a, spike, row["state"], requests)
    open_now = any(r["status"] == "open" for r in requests)
    rules = _rules(complaint, row, a, found, open_now, photo, has_draft)
    facts = _facts(complaint, row, a, spike, found, requests, photo)
    allowed: list[Suggested] = ["draft", "ask_consumer", "decide"] if has_draft else ["ask_consumer", "decide"]
    words = consumer_words(complaint.ticket, None)
    reply = await llm.assist("case", complaint.language or "te",
                             {"facts": facts, "allowed": allowed, "consumer_words": words})
    ok = figures(facts)
    summary = line(reply.get("summary"), ok, SUMMARY_MAX) if reply else None
    if reply is None or summary is None:
        return rules
    pick = next((s for s in allowed if s == reply.get("suggested")), None)
    why = line(reply.get("why"), ok) if pick else None
    chosen = pick or rules.suggested
    return CaseAssist(summary=summary, conflicts=found, questions=questions(reply.get("questions"), ok) or rules.questions,
                      suggested=chosen, why=why or SUGGESTED_WHY[chosen], worded_by="ai")
