"""Wrong reading cases: their derived state, info requests, AE decisions and bill revisions. The only SQL for review.

A case is a complaints row of kind 'wrong_reading'. The original bill is never edited; a revision is an approved
decision with a reduction, numbered per bill.
"""

import json
from typing import Any, Literal

from pydantic import BaseModel

from app.core.errors import Refusal
from app.store.complaints import OPEN_STATUSES, VISIBLE, VISIBLE_PARAMS
from app.store.db import tx

State = Literal["awaiting_review", "info_requested", "awaiting_approval", "decided", "applied", "rejected"]
CaseSort = Literal["oldest", "newest"]
EXPORT_LIMIT = 5000
DEFAULT_SLA = 3

# The latest decision that still counts: a withdrawn one is as if it never happened.
_LATEST = ("LEFT JOIN review_decisions ld ON ld.id = (SELECT MAX(d.id) FROM review_decisions d "
           "WHERE d.ticket = c.ticket AND d.status != 'withdrawn')")
_STATE = ("CASE WHEN ld.status = 'pending_approval' THEN 'awaiting_approval' "
          "WHEN ld.status = 'approved' AND ld.applied_at IS NOT NULL THEN 'applied' "
          "WHEN ld.status = 'approved' THEN 'decided' "
          "WHEN EXISTS (SELECT 1 FROM case_requests q WHERE q.ticket = c.ticket AND q.status = 'open') "
          "THEN 'info_requested' WHEN ld.status = 'rejected' THEN 'rejected' ELSE 'awaiting_review' END")
_CASES = (
    "SELECT c.ticket, c.created_at, c.user_id, c.bill_id, c.status, c.unit_id, c.section_id, c.assigned_to, "
    f"c.discom, c.bill_month, c.service_masked, c.case_facts, {_STATE} AS state, "
    "CAST(julianday('now') - julianday(c.created_at) AS INTEGER) AS days_open, "
    f"COALESCE(p.decision_sla_days, {DEFAULT_SLA}) AS sla, COALESCE(sec.name, c.section_name) AS section, "
    "sec.ero_id AS ero_id, asg.name AS assignee_name, "
    "CASE WHEN c.channel IS NOT NULL THEN c.channel WHEN c.user_id LIKE 'wa:%' THEN 'whatsapp' ELSE 'web' END "
    "AS channel FROM complaints c "
    f"{_LATEST} LEFT JOIN review_policy p ON p.discom = c.discom LEFT JOIN units sec ON sec.id = c.section_id "
    "LEFT JOIN accounts asg ON asg.id = c.assigned_to WHERE c.kind = 'wrong_reading'")
# A closed case is never overdue, whatever its state says.
_OUTER = ("SELECT x.*, CASE WHEN x.status IN ('Open', 'In progress') AND x.state NOT IN ('decided', 'applied') "
          "AND x.days_open > x.sla THEN 1 ELSE 0 END AS overdue FROM ({inner}) x")


class CasePage(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    counts: dict[str, int]  # every case the viewer may see, by state, plus 'overdue'; filters do not narrow it


def _row(raw: Any) -> dict[str, Any]:
    data = dict(raw)
    facts = json.loads(data.pop("case_facts") or "{}")
    assignee = {"id": data["assigned_to"], "name": data.pop("assignee_name")} if data["assigned_to"] else None
    return {**data, "overdue": bool(data["overdue"]), "assignee": assignee, "units": facts.get("units"),
            "median_units": facts.get("median_units"), "printed_amount": facts.get("printed_amount"),
            "usual_amount": facts.get("usual_amount")}


def _scoped(viewer: str | None) -> tuple[str, list[Any]]:
    return (f"{_CASES} AND {VISIBLE}", [viewer] * VISIBLE_PARAMS) if viewer else (_CASES, [])


def page(page_no: int, page_size: int, *, viewer: str | None, state: str | None = None, mine: str | None = None,
         overdue: bool | None = None, section_id: str | None = None, q: str | None = None,
         sort: CaseSort = "oldest") -> CasePage:
    """Cases the viewer may see (None: all). `mine` is an account id to keep only cases assigned to it."""
    inner, params = _scoped(viewer)
    where, args = ["1 = 1"], []
    for column, value in (("y.state", state), ("y.assigned_to", mine), ("y.section_id", section_id)):
        if value:
            where.append(f"{column} = ?")
            args.append(value)
    if overdue is not None:
        where.append("y.overdue = ?")
        args.append(int(overdue))
    if q:
        where.append("instr(upper(y.ticket), ?) > 0")
        args.append(q.strip().upper())
    direction = "ASC" if sort == "oldest" else "DESC"
    sql = f"SELECT * FROM ({_OUTER.format(inner=inner)}) y WHERE {' AND '.join(where)}"
    scoped = _OUTER.format(inner=inner)
    with tx() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", [*params, *args]).fetchone()[0]
        rows = conn.execute(f"{sql} ORDER BY y.created_at {direction}, y.ticket {direction} LIMIT ? OFFSET ?",
                            [*params, *args, page_size, (page_no - 1) * page_size]).fetchall()
        tally = conn.execute(f"SELECT state, COUNT(*), SUM(overdue) FROM ({scoped}) GROUP BY state", params).fetchall()
    counts = {r[0]: r[1] for r in tally} | {"overdue": sum(r[2] or 0 for r in tally)}
    return CasePage(items=[_row(r) for r in rows], total=total, page=page_no, page_size=page_size, counts=counts)


def sections(viewer: str | None) -> list[dict[str, str]]:
    inner, params = _scoped(viewer)
    with tx() as conn:
        rows = conn.execute(f"SELECT DISTINCT section_id, section FROM ({inner}) WHERE section_id IS NOT NULL "
                            "ORDER BY section LIMIT 500", params).fetchall()
    return [{"id": r[0], "name": r[1]} for r in rows]


def row(ticket: str) -> dict[str, Any] | None:
    with tx() as conn:
        found = conn.execute(f"{_OUTER.format(inner=_CASES + ' AND c.ticket = ?')}", (ticket,)).fetchone()
    return _row(found) if found else None


def add_request(ticket: str, kind: str, note: str | None, requested_by: str) -> None:
    with tx() as conn:
        conn.execute("INSERT INTO case_requests (ticket, kind, note, requested_by) VALUES (?, ?, ?, ?)",
                     (ticket, kind, note, requested_by))


# The consumer message that answers a request: their newest one, never one sent before the request was made.
# Callers store the message first, then answer the request.
ANSWERING = ("(SELECT MAX(m.id) FROM complaint_messages m WHERE m.ticket = case_requests.ticket "
             "AND m.author_kind = 'consumer' AND m.created_at >= case_requests.created_at)")


def answer_requests(ticket: str) -> None:
    """The consumer replied after being asked, so every open request on the case is answered by that message."""
    with tx() as conn:
        conn.execute(f"UPDATE case_requests SET status = 'answered', answered_at = CURRENT_TIMESTAMP, "
                     f"answer_message_id = {ANSWERING} WHERE ticket = ? AND status = 'open'", (ticket,))


def requests(ticket: str) -> list[dict[str, Any]]:
    """Newest first, each with the message that answered it (answer_* columns, null while open or lapsed)."""
    with tx() as conn:
        rows = conn.execute(
            "SELECT r.id, r.kind, r.note, r.status, r.created_at, r.answered_at, m.id AS answer_id, "
            "m.body AS answer_body, m.media_id AS answer_media_id, m.created_at AS answer_at FROM case_requests r "
            "LEFT JOIN complaint_messages m ON m.id = r.answer_message_id AND m.ticket = r.ticket "
            "WHERE r.ticket = ? ORDER BY r.id DESC LIMIT 100", (ticket,)).fetchall()
    return [dict(r) for r in rows]


_DECISION = ("SELECT d.*, pa.name AS proposed_name, da.name AS decided_name FROM review_decisions d "
             "LEFT JOIN accounts pa ON pa.id = d.proposed_by LEFT JOIN accounts da ON da.id = d.decided_by")


def _decision(raw: Any) -> dict[str, Any]:
    data = dict(raw)
    data["evidence"] = json.loads(data["evidence"])
    data["proposed_by"] = {"id": data["proposed_by"], "name": data.pop("proposed_name") or ""}
    decided = data.pop("decided_name")
    data["decided_by"] = {"id": data["decided_by"], "name": decided or ""} if data["decided_by"] else None
    return data


def decisions(ticket: str) -> list[dict[str, Any]]:
    """Newest first."""
    with tx() as conn:
        rows = conn.execute(f"{_DECISION} WHERE d.ticket = ? ORDER BY d.id DESC LIMIT 100", (ticket,)).fetchall()
    return [_decision(r) for r in rows]


def decision(decision_id: int) -> dict[str, Any] | None:
    with tx() as conn:
        found = conn.execute(f"{_DECISION} WHERE d.id = ?", (decision_id,)).fetchone()
    return _decision(found) if found else None


def _next_revision(conn: Any, bill_id: str) -> int:
    return int(conn.execute("SELECT COALESCE(MAX(revision), 0) + 1 FROM review_decisions WHERE bill_id = ?",
                            (bill_id,)).fetchone()[0])


def create_decision(ticket: str, bill_id: str, values: dict[str, Any], proposed_by: str, approved: bool) -> int:
    """Record a decision. Approved at once (policy allows it) means decided now and, with a reduction, a revision."""
    with tx() as conn:
        current = conn.execute("SELECT status FROM review_decisions WHERE ticket = ? AND status != 'withdrawn' "
                               "ORDER BY id DESC LIMIT 1", (ticket,)).fetchone()
        if current and current[0] in ("pending_approval", "approved"):
            raise Refusal("This case already has a decision. Withdraw it before recording another.")
        revision = _next_revision(conn, bill_id) if approved and values["reduction"] > 0 else None
        return int(conn.execute(
            "INSERT INTO review_decisions (ticket, bill_id, kind, status, original_amount, revised_amount, reduction, "
            "corrected_present_reading, corrected_units, reason_code, note, evidence, proposed_by, decided_at, "
            "revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? = 1 THEN CURRENT_TIMESTAMP END, ?) "
            "RETURNING id",
            (ticket, bill_id, values["kind"], "approved" if approved else "pending_approval",
             values["original_amount"], values["revised_amount"], values["reduction"],
             values["corrected_present_reading"], values["corrected_units"], values["reason_code"], values["note"],
             json.dumps(values["evidence"]), proposed_by, int(approved), revision)).fetchall()[0][0])


def approve(decision_id: int, by: str, note: str | None) -> bool:
    """False when the decision is no longer waiting for approval (someone else acted first)."""
    with tx() as conn:
        found = conn.execute("SELECT bill_id, reduction FROM review_decisions WHERE id = ? AND "
                             "status = 'pending_approval'", (decision_id,)).fetchone()
        if found is None:
            return False
        revision = _next_revision(conn, found["bill_id"]) if found["reduction"] > 0 else None
        conn.execute("UPDATE review_decisions SET status = 'approved', decided_by = ?, decided_at = CURRENT_TIMESTAMP, "
                     "decision_note = ?, revision = ? WHERE id = ?", (by, note, revision, decision_id))
    return True


def reject(decision_id: int, by: str, note: str) -> bool:
    with tx() as conn:
        cursor = conn.execute("UPDATE review_decisions SET status = 'rejected', decided_by = ?, "
                              "decided_at = CURRENT_TIMESTAMP, decision_note = ? WHERE id = ? AND "
                              "status = 'pending_approval'", (by, note, decision_id))
    return cursor.rowcount == 1


def withdraw(decision_id: int) -> bool:
    """Only before the revision reaches the billing system."""
    with tx() as conn:
        cursor = conn.execute("UPDATE review_decisions SET status = 'withdrawn' WHERE id = ? AND applied_at IS NULL "
                              "AND status IN ('pending_approval', 'approved')", (decision_id,))
    return cursor.rowcount == 1


def mark_applied(decision_id: int, by: str, billing_ref: str) -> bool:
    with tx() as conn:
        cursor = conn.execute("UPDATE review_decisions SET applied_by = ?, applied_at = CURRENT_TIMESTAMP, "
                              "billing_ref = ? WHERE id = ? AND status = 'approved' AND revision IS NOT NULL "
                              "AND applied_at IS NULL", (by, billing_ref, decision_id))
    return cursor.rowcount == 1


def least_busy_decider(section_id: str) -> str | None:
    """An active account that may decide, scoped on exactly this section, with the fewest open cases."""
    with tx() as conn:
        found = conn.execute(
            "SELECT a.id FROM accounts a JOIN account_scopes s ON s.account_id = a.id AND s.unit_id = ? "
            "JOIN roles r ON r.slug = a.role WHERE a.active = 1 AND EXISTS "
            "(SELECT 1 FROM json_each(r.permissions) WHERE value = 'cases.decide') ORDER BY "
            "(SELECT COUNT(*) FROM complaints c WHERE c.assigned_to = a.id AND c.kind = 'wrong_reading' "
            f"AND c.status IN ({', '.join('?' * len(OPEN_STATUSES))})), a.created_at, a.id LIMIT 1",
            (section_id, *OPEN_STATUSES)).fetchone()
    return found[0] if found else None


def staff_covering(unit_ids: list[str], perm: str, limit: int = 200) -> list[dict[str, str]]:
    """Active accounts holding `perm` with a scope on one of these units (a record's unit, its parents, its ERO)."""
    if not unit_ids:
        return []
    marks = ",".join("?" * len(unit_ids))
    with tx() as conn:
        rows = conn.execute(
            "SELECT DISTINCT a.id, a.name FROM accounts a JOIN account_scopes s ON s.account_id = a.id "
            f"JOIN roles r ON r.slug = a.role WHERE a.active = 1 AND s.unit_id IN ({marks}) AND EXISTS "
            "(SELECT 1 FROM json_each(r.permissions) WHERE value = ?) ORDER BY a.name LIMIT ?",
            [*unit_ids, perm, limit]).fetchall()
    return [dict(r) for r in rows]


def deciders_covering(unit_ids: list[str]) -> list[dict[str, str]]:
    """Active accounts that may decide and hold a scope on one of these units (a case's unit, its parents, its ERO)."""
    return staff_covering(unit_ids, "cases.decide")


def revisions(*, viewer: str | None, since: str | None, until: str | None, ero_id: str | None) -> list[dict[str, Any]]:
    """Approved revisions in scope for the CSV, newest first. Dates are YYYY-MM-DD on the decision day (UTC)."""
    inner, params = _scoped(viewer)
    with tx() as conn:
        rows = conn.execute(
            "SELECT x.ticket, d.revision, x.bill_month, x.service_masked, x.section, x.discom, d.kind, d.reason_code, "
            "d.original_amount, d.revised_amount, d.reduction, d.corrected_units, pa.name AS proposed_by, "
            "COALESCE(da.name, 'policy') AS approved_by, d.decided_at, "
            "CASE WHEN d.applied_at IS NULL THEN 'pending_update' ELSE 'applied' END AS status, d.applied_at, "
            f"d.billing_ref FROM ({inner}) x JOIN review_decisions d ON d.ticket = x.ticket "
            "LEFT JOIN accounts pa ON pa.id = d.proposed_by LEFT JOIN accounts da ON da.id = d.decided_by "
            "WHERE d.status = 'approved' AND d.revision IS NOT NULL AND (? IS NULL OR date(d.decided_at) >= ?) "
            "AND (? IS NULL OR date(d.decided_at) <= ?) AND (? IS NULL OR x.ero_id = ?) "
            "ORDER BY d.decided_at DESC, d.id DESC LIMIT ?",
            [*params, since, since, until, until, ero_id, ero_id, EXPORT_LIMIT]).fetchall()
    return [dict(r) for r in rows]


def latest_revision(ticket: str) -> dict[str, Any] | None:
    """The revision the consumer is told about: the newest approved decision with a reduction."""
    with tx() as conn:
        found = conn.execute(f"{_DECISION} WHERE d.ticket = ? AND d.status = 'approved' AND d.revision IS NOT NULL "
                             "ORDER BY d.id DESC LIMIT 1", (ticket,)).fetchone()
    return _decision(found) if found else None
