"""Work the system does by itself on a schedule (app/services/scheduler.py), so staff and consumers chase less.

Each job takes the clock as `now` (aware UTC) and returns how many things it did. Each is safe to run again: a
dedupe key, a claimed column or a state check stops a second run from doing anything twice. Every action is audited
with no actor, so the case timeline shows it as System. Nothing here decides or approves a case; the only change to
a decision is marking a revision applied when the DISCOM billing records show the revised amount.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.domain.conversation.facts import rs
from app.flows import case_bills, cases
from app.services import billing_records
from app.store import accounts, complaints, units
from app.store import automation as store
from app.store.alerts import raise_alert

IST = ZoneInfo("Asia/Kolkata")
LAPSE_NOTE = "No reply; checked with what is on file"
APPLIED_TOLERANCE = 1.0  # rupees between the revised amount and what the billing system now bills


def _ts(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def _division_of(unit_id: str | None) -> str | None:
    """The division above a unit, or the unit itself when nothing above it is a division."""
    if not unit_id:
        return None
    return next((u.id for u in units.ancestors(unit_id) if u.kind == "division"), unit_id)


def _bill_month(ticket: str) -> str | None:
    found = complaints.row(ticket)
    return found["bill_month"] if found else None


async def run_reminders(now: datetime) -> int:
    """One reminder for a request for earlier bills left unanswered for REMINDER_AFTER_DAYS."""
    cutoff = _ts(now - timedelta(days=get_settings().reminder_after_days))
    done = 0
    for request in store.system_requests(cutoff, unreminded=True):
        complaint = complaints.get(request["ticket"])
        if complaint is None or not store.claim_reminder(request["id"], _ts(now)):
            continue
        language = complaint.language or "te"
        await cases.tell_consumer(complaint, None, _bill_month(complaint.ticket), "request_reminder",
                                  months=case_bills.month_list(language, request["months"]))
        accounts.audit(None, "case.remind", complaint.ticket, f"earlier bills for {', '.join(request['months'])}",
                       unit_id=complaint.unit_id)
        raise_alert("request_reminded", complaint.section_id or complaint.unit_id, "Consumer reminded",
                    f"Case {complaint.ticket}: the consumer was reminded to send the earlier bills.", "cases.decide",
                    f"request_reminded:{request['id']}", ticket=complaint.ticket)
        done += 1
    return done


async def run_lapses(now: datetime) -> int:
    """A request still open after LAPSE_AFTER_DAYS is closed, so the case is checked with what is on file."""
    cutoff = _ts(now - timedelta(days=get_settings().lapse_after_days))
    done = 0
    for request in store.system_requests(cutoff, unreminded=False):
        complaint = complaints.get(request["ticket"])
        if complaint is None or not store.lapse(request["id"], LAPSE_NOTE, _ts(now)):
            continue
        language = complaint.language or "te"
        complaints.add_message(complaint.ticket, "system", None, LAPSE_NOTE + ".", "stored")
        await cases.tell_consumer(complaint, None, _bill_month(complaint.ticket), "request_lapsed",
                                  months=case_bills.month_list(language, request["months"]))
        accounts.audit(None, "case.lapse", complaint.ticket, f"earlier bills for {', '.join(request['months'])}",
                       unit_id=complaint.unit_id)
        raise_alert("request_lapsed", complaint.section_id or complaint.unit_id, "Ready to decide",
                    f"Case {complaint.ticket}: no reply to the request for earlier bills. Check it with what is on "
                    "file.", "cases.decide", f"request_lapsed:{request['id']}", ticket=complaint.ticket)
        done += 1
    return done


def _overdue(now: datetime) -> int:
    done = 0
    for case in store.undecided_past(_ts(now), 1):
        if raise_alert("case_overdue", case["section_id"] or case["unit_id"], "Case overdue",
                       f"Case {case['ticket']} has waited {case['days_open']} days for a decision (target "
                       f"{case['sla']} days).", "cases.decide", f"case_overdue:{case['ticket']}", ticket=case["ticket"]):
            accounts.audit(None, "case.overdue", case["ticket"], f"open {case['days_open']} days, target {case['sla']}",
                           unit_id=case["unit_id"])
            done += 1
    return done


def _escalations(now: datetime) -> int:
    done = 0
    for case in store.undecided_past(_ts(now), 2, unescalated=True):
        division = _division_of(case["section_id"] or case["unit_id"])
        if not store.mark_escalated(case["ticket"], _ts(now)):
            continue
        raise_alert("case_escalated", division, "Case escalated",
                    f"Case {case['ticket']} has waited {case['days_open']} days for a decision, past twice the "
                    f"{case['sla']} day target.", "cases.view", f"case_escalated:{case['ticket']}", ticket=case["ticket"])
        found = units.get(division) if division else None
        accounts.audit(None, "case.escalate", case["ticket"], f"to {found.name if found else 'no unit'}, open "
                       f"{case['days_open']} days", unit_id=case["unit_id"])
        done += 1
    return done


async def run_overdue(now: datetime) -> int:
    """Past the SLA: an alert to the section. Past twice the SLA: escalated to the division above."""
    return _overdue(now) + _escalations(now)


async def run_digest(now: datetime) -> int:
    """Once a day after DIGEST_HOUR_IST, one summary per account that may decide and has open cases in scope."""
    local = now.astimezone(IST)
    if local.hour < get_settings().digest_hour_ist:
        return 0
    done = 0
    for account_id in store.deciders():
        counts = store.digest_counts(account_id, _ts(now))
        if not counts["awaiting"]:
            continue
        body = (f"Waiting for a decision: {counts['awaiting']}. Due today: {counts['due_today']}. "
                f"Overdue: {counts['overdue']}.")
        if raise_alert("digest", None, "Daily summary", body, None, f"digest:{account_id}:{local.date()}",
                       account_id=account_id):
            accounts.audit(None, "alert.digest", account_id, body)
            done += 1
    return done


async def run_auto_applied(now: datetime) -> int:
    """When the DISCOM billing records already bill the revised amount, the revision is marked applied."""
    if not get_settings().billing_records_live:
        return 0
    done = 0
    for revision in store.pending_revisions():
        records = await billing_records.fetch(revision["service_number"])
        match = next((m for m in records.months if m.month == revision["bill_month"] and m.billed_amount is not None
                      and abs(m.billed_amount - revision["revised_amount"]) <= APPLIED_TOLERANCE), None)
        if match is None or not store.mark_applied_auto(revision["id"], f"DISCOM records {match.month}", _ts(now)):
            continue
        complaint = complaints.get(revision["ticket"])
        if complaint is None:
            continue
        complaints.set_status(complaint.ticket, "Resolved")
        accounts.audit(None, "revision.applied_auto", complaint.ticket, f"decision {revision['id']}, DISCOM records "
                       f"{match.month}", unit_id=complaint.unit_id)
        raise_alert("applied_auto", complaint.section_id or complaint.unit_id, "Revision applied",
                    f"Case {complaint.ticket}: the DISCOM billing records now show the revised amount, so the "
                    "revision is marked applied.", "cases.view", f"applied_auto:{revision['id']}", ticket=complaint.ticket)
        await cases.tell_consumer(complaint, None, revision["bill_month"], "review_applied",
                                  revised=rs(revision["revised_amount"]))
        done += 1
    return done


async def run_patterns(now: datetime) -> int:
    """A section with many approved corrected readings lately: an alert to its division, once a month."""
    settings = get_settings()
    since = _ts(now - timedelta(days=settings.pattern_window_days))
    done = 0
    for row in store.corrected_reading_sections(since, settings.pattern_min_cases):
        section = units.get(row["section_id"])
        name = section.name if section else "A section"
        if raise_alert("pattern_section", _division_of(row["section_id"]), "Many reading corrections",
                       f"{name}: {row['cases']} corrected readings approved in the last "
                       f"{settings.pattern_window_days} days.", "cases.view",
                       f"pattern_section:{row['section_id']}:{now.strftime('%Y-%m')}"):
            accounts.audit(None, "alert.pattern", row["section_id"], f"{row['cases']} corrected readings",
                           unit_id=row["section_id"])
            done += 1
    return done


# Lapses first: a request already past the lapse point is closed, not reminded and closed in the same run.
JOBS: tuple[tuple[str, Callable[[datetime], Awaitable[int]]], ...] = (
    ("lapses", run_lapses), ("reminders", run_reminders), ("overdue", run_overdue), ("digest", run_digest),
    ("auto_applied", run_auto_applied), ("patterns", run_patterns))
