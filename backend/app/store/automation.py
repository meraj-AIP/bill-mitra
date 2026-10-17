"""Queries behind the scheduled jobs in app/flows/automation.py. The only SQL for automation.

Every time comes from the caller's clock (UTC, 'YYYY-MM-DD HH:MM:SS' like CURRENT_TIMESTAMP), so tests can fix it.
Every list is bounded: a job that falls behind catches up over the next runs.
"""

import json
from typing import Any

from app.store.complaints import OPEN_STATUSES, VISIBLE, VISIBLE_PARAMS
from app.store.db import tx
from app.store.review import DEFAULT_SLA

BATCH = 100
_MARKS = ", ".join("?" * len(OPEN_STATUSES))
_OPEN_CASE = f"c.kind = 'wrong_reading' AND c.status IN ({_MARKS})"
# No decision waiting for approval or standing approved: the case still needs someone to decide.
_UNDECIDED = ("NOT EXISTS (SELECT 1 FROM review_decisions d WHERE d.ticket = c.ticket "
              "AND d.status IN ('pending_approval', 'approved'))")
_DAYS = "CAST(julianday(?) - julianday(c.created_at) AS INTEGER)"
_SLA = f"COALESCE(p.decision_sla_days, {DEFAULT_SLA})"


def system_requests(cutoff: str, *, unreminded: bool) -> list[dict[str, Any]]:
    """Open requests the system raised for earlier bills, on open cases, raised at or before `cutoff`."""
    extra = " AND q.reminded_at IS NULL" if unreminded else ""
    with tx() as conn:
        rows = conn.execute(
            "SELECT q.id, q.ticket, q.months FROM case_requests q JOIN complaints c ON c.ticket = q.ticket "
            f"WHERE {_OPEN_CASE} AND q.status = 'open' AND q.requested_by IS NULL AND q.months IS NOT NULL "
            f"AND q.created_at <= ?{extra} ORDER BY q.id LIMIT ?", (*OPEN_STATUSES, cutoff, BATCH)).fetchall()
    return [{"id": r["id"], "ticket": r["ticket"], "months": json.loads(r["months"])} for r in rows]


def claim_reminder(request_id: int, at: str) -> bool:
    """True for the one caller that gets to send the reminder."""
    with tx() as conn:
        cursor = conn.execute("UPDATE case_requests SET reminded_at = ? WHERE id = ? AND status = 'open' "
                              "AND reminded_at IS NULL", (at, request_id))
    return cursor.rowcount == 1


def lapse(request_id: int, note: str, at: str) -> bool:
    with tx() as conn:
        cursor = conn.execute("UPDATE case_requests SET status = 'answered', answered_at = ?, note = ? "
                              "WHERE id = ? AND status = 'open'", (at, note, request_id))
    return cursor.rowcount == 1


def undecided_past(now: str, sla_multiple: int, *, unescalated: bool = False,
                   unalerted: str | None = None) -> list[dict[str, Any]]:
    """Open cases with no decision, open longer than `sla_multiple` times their DISCOM's decision SLA.
    `unalerted` is an alert kind: cases that already have that alert are left out, so each run reaches new ones
    instead of picking the same oldest batch again."""
    extra = " AND c.escalated_at IS NULL" if unescalated else ""
    if unalerted:
        extra += " AND NOT EXISTS (SELECT 1 FROM alerts a WHERE a.dedupe_key = ? || c.ticket)"
    with tx() as conn:
        rows = conn.execute(
            f"SELECT c.ticket, c.unit_id, c.section_id, {_DAYS} AS days_open, {_SLA} AS sla FROM complaints c "
            f"LEFT JOIN review_policy p ON p.discom = c.discom WHERE {_OPEN_CASE} AND {_UNDECIDED}{extra} "
            f"AND {_DAYS} > {_SLA} * ? ORDER BY c.created_at LIMIT ?",
            (now, *OPEN_STATUSES, *([f"{unalerted}:"] if unalerted else []), now, sla_multiple, BATCH)).fetchall()
    return [dict(r) for r in rows]




def mark_escalated(ticket: str, at: str) -> bool:
    with tx() as conn:
        cursor = conn.execute("UPDATE complaints SET escalated_at = ? WHERE ticket = ? AND escalated_at IS NULL",
                              (at, ticket))
    return cursor.rowcount == 1


def alerted(dedupe_key: str) -> bool:
    with tx() as conn:
        return conn.execute("SELECT 1 FROM alerts WHERE dedupe_key = ?", (dedupe_key,)).fetchone() is not None


def deciders() -> list[str]:
    """Active accounts whose role may decide."""
    with tx() as conn:
        rows = conn.execute("SELECT a.id FROM accounts a JOIN roles r ON r.slug = a.role WHERE a.active = 1 AND "
                            "EXISTS (SELECT 1 FROM json_each(r.permissions) WHERE value = 'cases.decide') "
                            "ORDER BY a.id LIMIT 1000").fetchall()
    return [r[0] for r in rows]


def digest_counts(account_id: str, now: str) -> dict[str, int]:
    """Undecided open cases the account can see: all of them, those whose decision falls due today, the overdue."""
    with tx() as conn:
        row = conn.execute(
            f"SELECT COUNT(*), COALESCE(SUM(x.days = x.sla), 0), COALESCE(SUM(x.days > x.sla), 0) FROM "
            f"(SELECT {_DAYS} AS days, {_SLA} AS sla FROM complaints c LEFT JOIN review_policy p ON p.discom = c.discom "
            f"WHERE {_OPEN_CASE} AND {_UNDECIDED} AND {VISIBLE}) x",
            (now, *OPEN_STATUSES, *[account_id] * VISIBLE_PARAMS)).fetchone()
    return {"awaiting": row[0], "due_today": row[1], "overdue": row[2]}


def pending_revisions() -> list[dict[str, Any]]:
    """Approved revisions still waiting for the billing system, with what is needed to look them up there."""
    with tx() as conn:
        rows = conn.execute(
            "SELECT d.id, d.ticket, d.revised_amount, b.service_number, c.bill_month, c.unit_id "
            "FROM review_decisions d JOIN complaints c ON c.ticket = d.ticket JOIN bills b ON b.id = d.bill_id "
            "WHERE d.status = 'approved' AND d.revision IS NOT NULL AND d.applied_at IS NULL "
            "ORDER BY d.id LIMIT ?", (BATCH,)).fetchall()
    return [dict(r) for r in rows]


def mark_applied_auto(decision_id: int, billing_ref: str, at: str) -> bool:
    """applied_by stays NULL: nobody marked it, the billing records showed it."""
    with tx() as conn:
        cursor = conn.execute("UPDATE review_decisions SET applied_at = ?, billing_ref = ? WHERE id = ? "
                              "AND status = 'approved' AND revision IS NOT NULL AND applied_at IS NULL",
                              (at, billing_ref, decision_id))
    return cursor.rowcount == 1


def corrected_reading_sections(since: str, min_cases: int) -> list[dict[str, Any]]:
    """Sections with at least `min_cases` approved corrected readings decided since `since`."""
    with tx() as conn:
        rows = conn.execute(
            "SELECT c.section_id, COUNT(*) AS cases FROM review_decisions d JOIN complaints c ON c.ticket = d.ticket "
            "WHERE d.kind = 'corrected_reading' AND d.status = 'approved' AND d.decided_at >= ? "
            "AND c.section_id IS NOT NULL GROUP BY c.section_id HAVING COUNT(*) >= ? ORDER BY c.section_id LIMIT ?",
            (since, min_cases, BATCH)).fetchall()
    return [dict(r) for r in rows]
