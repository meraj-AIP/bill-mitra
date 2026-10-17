"""A suggested decision for the AE, from rules only. Nothing here decides: the AE still records the decision.

Notes and reasons are fixed templates, never model output. The only figures in them are printed readings; every
amount comes from the engine preview the route attaches.
"""

from typing import Any, Literal

from pydantic import BaseModel

from app.domain import capture
from app.domain.review import DecisionKind, ReasonCode, Spike
from app.flows.analysis import Analysis
from app.store import repos
from app.store import suggestions as suggestion_store
from app.store.complaints import Complaint


class DraftEvidence(BaseModel):
    kind: Literal["bill", "message"]
    id: str


class Draft(BaseModel):
    kind: DecisionKind
    corrected_present_reading: int | None
    reason_code: ReasonCode
    note: str
    evidence: list[DraftEvidence]
    strength: Literal["strong", "likely"]
    why: list[str]


CORRECT_NOTE = ("Every charge on this bill matches the TGERC tariff for the units billed, the readings and billing "
                "days agree, and nothing unusual shows against earlier months. The bill stands as printed.")


def from_misread(complaint: Complaint, a: Analysis) -> Draft | None:
    """The next month's bill proves this bill's present reading too high. None when there is no suggestion or the
    later bill has since been erased."""
    found = suggestion_store.get(complaint.ticket)
    source = repos.get_own_bill(complaint.user_id, found.source_bill_id) if found else None
    printed = a.bill.present_reading
    if found is None or source is None or complaint.bill_id is None or printed is None:
        return None
    corrected = found.corrected_present_reading
    later = source.bill.bill_month or "next"
    note = (f"The {later} bill starts from a previous reading of {corrected}, below the present reading of "
            f"{printed:g} printed on this bill. A meter cannot run backwards, so this bill's present reading was "
            f"read too high and is corrected to {corrected}.")
    why = [f"The {later} bill starts at {corrected}, lower than this bill's present reading of {printed:g}.",
           "A meter cannot run backwards, so this bill's present reading was read too high.",
           "The corrected units and amount are priced by the tariff engine."]
    return Draft(kind="corrected_reading", corrected_present_reading=corrected, reason_code="photo_misread",
                 note=note, evidence=[DraftEvidence(kind="bill", id=complaint.bill_id),
                                      DraftEvidence(kind="bill", id=source.id)],
                 strength="strong", why=why)


def clear_correct(complaint: Complaint, a: Analysis, spike: Spike, requests: list[dict[str, Any]]) -> Draft | None:
    """Every rule says the bill is right. Any doubt at all gives None, and the AE decides from scratch."""
    checks = {c.key: c.status for c in capture.report(a.bill).checks}
    every_line = (a.audit.status == "verified" and bool(a.audit.lines) and "total_only" not in a.audit.notes
                  and all(line.status == "match" for line in a.audit.lines))
    nothing_open = all(r["status"] != "open" for r in requests)
    # An estimated reading (meter status other than 01) is never drafted as correct, however well the charges match.
    estimated = checks.get("reading_status") == "fail"
    if not (every_line and not spike.flagged and checks.get("readings") == "pass" and checks.get("days") == "pass"
            and nothing_open and complaint.bill_id and not estimated):
        return None
    usage = ("Units are in line with the household's usual months." if spike.median_units is not None
             else "No earlier months to compare, and nothing on the bill itself looks unusual.")
    why = ["Every charge matches the TGERC tariff for the units billed.",
           "Present minus previous reading equals the units billed.",
           "Billing days match the reading dates.", usage, "Nothing asked of the consumer is still open."]
    return Draft(kind="correct", corrected_present_reading=None, reason_code="bill_correct", note=CORRECT_NOTE,
                 evidence=[DraftEvidence(kind="bill", id=complaint.bill_id)], strength="likely", why=why)
