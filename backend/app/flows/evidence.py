"""What staff see on a case besides the bill: the evidence pack and the timeline. English, staff only.

Every figure is the engine's or as printed; nothing here calls a model.
"""

from typing import Literal

from pydantic import BaseModel

from app.domain.review import Spike
from app.flows.analysis import Analysis
from app.store import case_evidence as evidence_store

SourceKey = Literal["this_bill", "printed_history", "uploads", "discom_records", "spike", "requested_bills"]
SourceStatus = Literal["included", "partial", "missing", "not_connected"]
LABELS: dict[str, str] = {"this_bill": "This bill", "printed_history": "Usage table printed on the bill",
                          "uploads": "Consumer's earlier uploads", "discom_records": "DISCOM billing records",
                          "spike": "Comparison with the usual month", "requested_bills": "Requested bills"}
SPIKE_MONTHS = 6


class EvidenceSource(BaseModel):
    key: SourceKey
    label: str
    status: SourceStatus
    months: list[str]
    detail: str


class AttachedBill(BaseModel):
    bill_id: str
    month: str
    units: int | None
    amount: float | None
    media_url: str | None


class EvidencePack(BaseModel):
    sources: list[EvidenceSource]
    requested_months: list[str]
    received_months: list[str]
    attached_bills: list[AttachedBill]


class Actor(BaseModel):
    kind: Literal["consumer", "system", "staff"]
    name: str | None


class TimelineEntry(BaseModel):
    at: str
    actor: Actor
    text: str


def _source(key: SourceKey, status: SourceStatus, months: list[str], detail: str) -> EvidenceSource:
    return EvidenceSource(key=key, label=LABELS[key], status=status, months=months, detail=detail)


def _this_bill(a: Analysis, media_id: str | None) -> EvidenceSource:
    bill = a.bill
    readings = (f"readings {bill.previous_reading:g} to {bill.present_reading:g}"
                if bill.previous_reading is not None and bill.present_reading is not None else "readings not printed")
    detail = f"{'Photo, ' if media_id else 'No photo stored, '}{readings}, {a.comp.units} units, " \
             f"charges check {a.audit.status}"
    return _source("this_bill", "included" if media_id else "partial", [a.facts.month], detail)


def _from_history(a: Analysis) -> list[EvidenceSource]:
    printed = [p.month for p in a.bill.usage_history if p.month < a.facts.month]
    uploads = [h.month for h in a.history if h.source == "uploaded"]
    return [
        _source("printed_history", "included" if printed else "missing", printed,
                f"{len(printed)} months printed on the bill" if printed else "The bill prints no usage table."),
        _source("uploads", "included" if uploads else "missing", uploads,
                f"{len(uploads)} earlier bills uploaded for this connection" if uploads
                else "No earlier bills uploaded for this connection."),
    ]


def _records(ticket: str) -> EvidenceSource:
    found = evidence_store.records(ticket)
    if found is None:
        return _source("discom_records", "not_connected", [], "Not checked: the case was reported before billing "
                       "records were part of the evidence pack.")
    status, months = found
    names = [m["month"] for m in months]
    if status == "not_connected":
        return _source("discom_records", "not_connected", [], "The DISCOM billing system is not connected yet.")
    if status == "included":
        return _source("discom_records", "included", names, f"{len(names)} months from the DISCOM billing system")
    return _source("discom_records", "missing", [], "The DISCOM billing system returned no months for this "
                   "connection.")


def _spike(a: Analysis, spike: Spike) -> EvidenceSource:
    months = [h.month for h in a.history[-SPIKE_MONTHS:]]
    if spike.median_units is None:
        return _source("spike", "missing", [], "No earlier months to compare with.")
    detail = f"{spike.units} units against a usual {spike.median_units:g} over {spike.months_used} months"
    if spike.ratio:
        detail += f" ({spike.ratio:g} times)"
    if spike.reason == "reading_went_back":
        detail += "; the present reading is lower than the previous reading"
    return _source("spike", "included", months, detail + ("; flagged" if spike.flagged else "; not flagged"))


def _requested(request: dict | None) -> EvidenceSource:
    if request is None:
        return _source("requested_bills", "included", [], "Nothing to ask for: the three months before the bill "
                       "are on file.")
    months, received = request["months"], request["received"]
    status: SourceStatus = "included" if set(months) <= set(received) else "partial" if received else "missing"
    detail = f"{len(received)} of {len(months)} received"
    if request["status"] == "answered" and status != "included":
        detail += "; the consumer says they do not have the rest"
    return _source("requested_bills", status, received, detail)


def pack(ticket: str, found: tuple[Analysis, str | None] | None, spike: Spike) -> EvidencePack:
    request = evidence_store.month_request(ticket)
    attached = [AttachedBill(bill_id=b["bill_id"], month=b["month"], units=b["units"], amount=b["amount"],
                             media_url=f"/api/media/{b['media_id']}" if b["media_id"] else None)
                for b in evidence_store.attached(ticket)]
    if found is None:
        sources = [_source("this_bill", "missing", [], "The consumer has erased this bill."), _records(ticket)]
    else:
        a, media_id = found
        sources = [_this_bill(a, media_id), *_from_history(a), _records(ticket), _spike(a, spike)]
    sources.append(_requested(request))
    return EvidencePack(sources=sources, requested_months=request["months"] if request else [],
                        received_months=request["received"] if request else [], attached_bills=attached)


TIMELINE_TEXT = {"case.route": "Routed", "case.pack": "Evidence pack built", "case.request": "Asked the consumer for",
                 "case.attach": "Sent a requested bill", "case.no_bills": "Said they do not have the requested bills",
                 "case.assign": "Assigned", "case.suggestion": "Found a misread from the next bill", "case.unmask": "Viewed the full service number",
                 "decision.create": "Recorded a decision", "decision.approve": "Approved the decision",
                 "decision.reject": "Rejected the decision", "decision.withdraw": "Withdrew the decision",
                 "decision.applied": "Marked the revision applied in the billing system",
                 "case.remind": "Reminded the consumer about", "case.lapse": "Closed the request with no reply, "
                 "checked with what is on file", "case.overdue": "Past the decision target",
                 "case.escalate": "Escalated", "revision.applied_auto": "Marked the revision applied: the DISCOM "
                 "billing records show the revised amount"}
CONSUMER_ACTIONS = {"case.attach", "case.no_bills"}


def _entry(row: dict) -> TimelineEntry:
    if row["action"] in CONSUMER_ACTIONS:
        actor = Actor(kind="consumer", name=None)
    elif row["actor_id"] is None:
        actor = Actor(kind="system", name="System")
    else:
        actor = Actor(kind="staff", name=row["actor_name"])
    label = TIMELINE_TEXT.get(row["action"], row["action"])
    detail = None if row["action"] == "case.no_bills" else row["detail"]
    return TimelineEntry(at=row["ts"], actor=actor, text=f"{label}: {detail}" if detail else label)


def timeline(ticket: str, reported_at: str) -> list[TimelineEntry]:
    """Oldest first. The report itself opens it; every later step is an audit entry on the case."""
    reported = TimelineEntry(at=reported_at, actor=Actor(kind="consumer", name=None),
                             text="Reported the bill as wrong")
    return [reported, *(_entry(r) for r in evidence_store.timeline_rows(ticket))]
