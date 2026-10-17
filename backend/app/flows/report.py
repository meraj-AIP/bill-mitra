"""Bill dashboard: one upload in; the reading, what was captured, and the engine's check out.

Same reader, gate and engine as the chat, so the two surfaces never disagree about a photo.
"""

import logging
import time
from dataclasses import asdict
from typing import Any

from pydantic import BaseModel

from app.config import get_settings
from app.domain import capture
from app.domain.bill import ExtractedBill
from app.domain.conversation import composer
from app.domain.prediction import MonthUsage
from app.domain.review import Final
from app.flows import case_bills, cases, misread
from app.flows.analysis import Analysis, analyse
from app.flows.bill import Outcome, log_read, outcome, read_ms
from app.flows.complaint import LABEL_EN
from app.flows.misread import Misread
from app.services import vision
from app.services.openai_client import ProviderError
from app.store import complaints, media, repos

log = logging.getLogger(__name__)

REASONS: dict[str, str] = {
    "reading_off": "Bill reading is switched off on this server because no vision model key is set.",
    "reading_failed": "The bill reader did not respond. Please try again in a minute.",
    "meter": "This is a meter photo. Upload the bill itself here; meter photos work in the Assistant.",
}


class BillReport(BaseModel):
    id: str | None
    created_at: str | None
    media_url: str
    mime_type: str
    outcome: Outcome
    outcome_reason: str | None
    classification: dict[str, Any] | None
    bill: dict[str, Any] | None
    capture: capture.CaptureReport | None
    analysis: dict[str, Any] | None
    review: cases.ReviewSummary | None = None
    final: Final | None = None  # the bill for the month as it stands now; original figures stay in `bill`
    misread: Misread | None = None  # the month before looks read too high and nobody has reported it


def bill_out(bill: ExtractedBill) -> dict[str, Any]:
    """The bill as staff and consumers see it: everything printed, the service number masked."""
    out = bill.model_dump(exclude={"service_number", "meter_reading", "document_type", "is_electricity_bill",
                                   "quality", "quality_issue"})
    out["service_masked"] = bill.masked_service_number()
    return out


def _bill_out(reading: vision.Reading | None) -> dict[str, Any] | None:
    return bill_out(reading.bill) if reading and reading.bill else None


def history_rows(a: Analysis) -> list[dict[str, Any]]:
    this_month = MonthUsage(month=a.facts.month, units=a.comp.units, amount=a.comp.net, source="this_bill")
    return [h.model_dump() for h in [*a.history, this_month]]


def _analysis(a: Analysis, language: str) -> dict[str, Any]:
    lines = [{**line.model_dump(), "label": LABEL_EN.get(line.code, line.code.replace("_", " ").title())}
             for line in a.audit.lines]
    return {
        **asdict(a.comp),
        "audit": {**a.audit.model_dump(), "lines": lines},
        "prediction": a.prediction.model_dump(),
        "history": history_rows(a),
        "spike": cases.spike_for(a).model_dump(),
        "cliffs": [c.model_dump() for c in a.insights.cliffs],
        "saving": a.insights.saving.model_dump() if a.insights.saving else None,
        "explanation": [composer.plain(sentence) for sentence in composer.explain(a.facts, language)],
    }


def _reason(result: Outcome, reading: vision.Reading | None, report: capture.CaptureReport | None) -> str | None:
    if result in REASONS:
        return REASONS[result]
    seen = reading.classification if reading else None
    if result == "not_a_bill" and seen:
        return f"{seen.reason} Upload a TGSPDCL or TGNPDCL electricity bill."
    if result == "retake":
        return (report.problem if report else None) or (seen.quality_issue if seen else None) or \
            "The photo is not clear enough to read."
    if reading and reading.reread:
        return "The first reading did not add up, so the bill was read a second time. The second reading checks out."
    return None


async def check_upload(user_id: str, data: bytes, mime: str, media_id: str, language: str) -> BillReport:
    reading: vision.Reading | None = None
    started = time.perf_counter()
    if get_settings().vision_live:
        try:
            reading = await vision.read_document(data, mime)
        except ProviderError as exc:
            log.warning("dashboard read failed: %s", exc)
    ms = read_ms(started)
    report = capture.report(reading.bill) if reading and reading.bill else None
    result = outcome(reading, report)
    log_read("dashboard", language, result, reading, ms)
    result_out: Outcome = "not_a_bill" if result == "meter" else result
    bill_id, created, analysis, final, found = None, None, None, None, None
    if result == "checked" and reading and reading.bill:
        a = analyse(reading.bill, user_id)
        bill_id = repos.save_bill(user_id, reading.bill, media_id, a.audit.status, a.audit.overcharge)
        created = repos.get_own_bill(user_id, bill_id)
        analysis = _analysis(a, language)
        final = cases.final_for(bill_id, a)
        case_bills.attach_upload(user_id, bill_id, reading.bill, media_id)
        found = misread.after_bill_saved(user_id, reading.bill, bill_id)
        repos.log_event("dashboard", "bill_read", language=language, audit_status=a.audit.status,
                        units=a.comp.units, amount=a.comp.net, discom=reading.bill.discom, section=reading.bill.section)
    return BillReport(
        id=bill_id, created_at=created.created_at if created else None, media_url=f"/api/media/{media_id}",
        mime_type=mime, outcome=result_out, outcome_reason=_reason(result, reading, report),
        classification=reading.classification.model_dump() if reading else None, bill=_bill_out(reading),
        capture=report, analysis=analysis, final=final, misread=found)


def load(user_id: str, bill_id: str, language: str) -> BillReport | None:
    stored = repos.get_own_bill(user_id, bill_id)
    if stored is None:
        return None
    a = analyse(stored.bill, user_id)
    media_id = stored.media_id or ""
    reading = vision.Reading(classification=vision.Classification(document_type="electricity_bill",
                                                                  discom=stored.bill.discom), bill=stored.bill)
    return BillReport(
        id=stored.id, created_at=stored.created_at, media_url=f"/api/media/{media_id}",
        mime_type=media.mime_for(media_id) if media_id else "image/jpeg", outcome="checked", outcome_reason=None,
        classification=reading.classification.model_dump(), bill=_bill_out(reading),
        capture=capture.report(stored.bill), analysis=_analysis(a, language),
        review=review_for(user_id, bill_id, language), final=cases.final_for(stored.id, a),
        misread=misread.find(user_id, stored.bill))


def review_for(user_id: str, bill_id: str, language: str) -> cases.ReviewSummary | None:
    """The newest reading check the owner asked for on this bill, as the consumer sees it."""
    ticket = complaints.latest_for_bill(user_id, bill_id, cases.KIND)
    return cases.summary(ticket, language) if ticket else None
