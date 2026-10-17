"""Who holds a complaint, who handed it over and the alerts that follow it around. The only SQL for hand-offs.

Alert titles and bodies are staff English and carry the ticket only: never a service number, a phone number or the
consumer's words.
"""

import json
from typing import Any

from app.store import accounts
from app.store.alerts import raise_alert
from app.store.db import tx

_OPEN = "status IN ('Open', 'In progress')"
CANDIDATES_MAX = 50


def section_holder(section_id: str) -> str | None:
    """The section's AE for a general complaint: active, scoped on exactly this section, able to see complaints and
    decide cases, holding the fewest open general complaints."""
    with tx() as conn:
        found = conn.execute(
            "SELECT a.id FROM accounts a JOIN account_scopes s ON s.account_id = a.id AND s.unit_id = ? "
            "JOIN roles r ON r.slug = a.role WHERE a.active = 1 "
            "AND EXISTS (SELECT 1 FROM json_each(r.permissions) WHERE value = 'cases.decide') "
            "AND EXISTS (SELECT 1 FROM json_each(r.permissions) WHERE value = 'complaints.view') ORDER BY "
            f"(SELECT COUNT(*) FROM complaints c WHERE c.assigned_to = a.id AND c.kind = 'general' AND c.{_OPEN}), "
            "a.created_at, a.id LIMIT 1", (section_id,)).fetchone()
    return found[0] if found else None


def candidates(unit_ids: list[str]) -> list[dict[str, Any]]:
    """Active staff who can see complaints with a scope on one of these units, each with its permissions."""
    if not unit_ids:
        return []
    marks = ",".join("?" * len(unit_ids))
    with tx() as conn:
        rows = conn.execute(
            "SELECT DISTINCT a.id, a.name, r.permissions FROM accounts a JOIN account_scopes s ON s.account_id = a.id "
            f"JOIN roles r ON r.slug = a.role WHERE a.active = 1 AND s.unit_id IN ({marks}) AND EXISTS "
            "(SELECT 1 FROM json_each(r.permissions) WHERE value = 'complaints.view') ORDER BY a.name LIMIT ?",
            [*unit_ids, CANDIDATES_MAX]).fetchall()
    return [{"id": r["id"], "name": r["name"], "permissions": set(json.loads(r["permissions"]))} for r in rows]


def section_deciders(discom: str) -> list[dict[str, Any]]:
    """Section AEs anywhere in a DISCOM, each with the section they sit on. A complaint still in the DISCOM queue can
    be handed to one of them, which also places it in that section."""
    with tx() as conn:
        rows = conn.execute(
            "SELECT DISTINCT a.id, a.name, r.permissions, u.id AS section_id, u.name AS section_name FROM accounts a "
            "JOIN account_scopes s ON s.account_id = a.id JOIN units u ON u.id = s.unit_id AND u.kind = 'section' "
            "AND u.discom = ? JOIN roles r ON r.slug = a.role WHERE a.active = 1 "
            "AND EXISTS (SELECT 1 FROM json_each(r.permissions) WHERE value = 'cases.decide') "
            "AND EXISTS (SELECT 1 FROM json_each(r.permissions) WHERE value = 'complaints.view') "
            "ORDER BY u.name, a.name LIMIT ?", (discom, CANDIDATES_MAX)).fetchall()
    return [{"id": r["id"], "name": f"{r['name']} ({r['section_name']})", "permissions": set(json.loads(r["permissions"])),
             "section_id": r["section_id"]} for r in rows]


def hand_over(ticket: str, holder: str | None, to: str, by: str, note: str, at: str) -> bool:
    """False when the complaint closed or changed hands since it was read, so two hand-offs cannot cross."""
    with tx() as conn:
        cursor = conn.execute(
            "UPDATE complaints SET assigned_to = ?, handed_by = ?, handoff_note = ?, handed_at = ?, "
            f"updated_at = CURRENT_TIMESTAMP WHERE ticket = ? AND {_OPEN} AND COALESCE(assigned_to, '') = ?",
            (to, by, note, at, ticket, holder or ""))
    return cursor.rowcount == 1


def routed(ticket: str, kind: str, holder: str, unit_id: str | None) -> None:
    """A new complaint placed straight with its section's AE: the timeline line and the holder's alert."""
    if kind == "general":
        person = accounts.get(holder)
        accounts.audit(None, "complaint.route", ticket, person.name if person else None, unit_id=unit_id)
        raise_alert("complaint_assigned", None, "New complaint for you",
                    f"Complaint {ticket} was routed to you by its section.", None,
                    f"complaint_assigned:{ticket}:route", ticket=ticket, account_id=holder)
    else:
        raise_alert("case_assigned", None, "New case for you", f"Case {ticket} was routed to you by its section.",
                    None, f"case_assigned:{ticket}:route", ticket=ticket, account_id=holder)


def consumer_replied(ticket: str, photo: bool) -> bool:
    """One alert per staff turn: the holder hears once, however many messages the consumer sends before staff
    write again. With nobody holding it, the alert goes to whoever may answer in its unit."""
    with tx() as conn:
        row = conn.execute(
            "SELECT c.kind, c.assigned_to, COALESCE(c.section_id, c.unit_id) AS unit, (SELECT MAX(m.id) FROM "
            "complaint_messages m WHERE m.ticket = c.ticket AND m.author_kind != 'consumer') AS staff_turn "
            "FROM complaints c WHERE c.ticket = ?", (ticket,)).fetchone()
    if row is None:
        return False
    case = row["kind"] == "wrong_reading"
    holder = row["assigned_to"]
    body = f"{'Case' if case else 'Complaint'} {ticket}: the consumer sent {'a photo' if photo else 'a message'}."
    perm = None if holder else "cases.decide" if case else "complaints.reply"
    return raise_alert("consumer_replied", None if holder else row["unit"], "Consumer replied", body, perm,
                       f"consumer_replied:{ticket}:{row['staff_turn'] or 0}", ticket=ticket, account_id=holder)


def on_ticket(ticket: str, media_id: str) -> bool:
    """True when the file belongs to this complaint: a message's photo, its bill or a bill attached to the case."""
    with tx() as conn:
        found = conn.execute(
            "SELECT 1 FROM complaint_messages WHERE ticket = ? AND media_id = ? UNION ALL "
            "SELECT 1 FROM complaints c JOIN bills b ON b.id = c.bill_id WHERE c.ticket = ? AND b.media_id = ? "
            "UNION ALL SELECT 1 FROM case_bills k JOIN bills b ON b.id = k.bill_id WHERE k.ticket = ? "
            "AND b.media_id = ? LIMIT 1", (ticket, media_id, ticket, media_id, ticket, media_id)).fetchone()
    return found is not None


def consumer_media(user_id: str, ticket: str, media_id: str) -> bool:
    """True only for a photo the consumer sent on their own complaint."""
    with tx() as conn:
        found = conn.execute(
            "SELECT 1 FROM complaint_messages m JOIN complaints c ON c.ticket = m.ticket WHERE m.ticket = ? "
            "AND c.user_id = ? AND m.author_kind = 'consumer' AND m.media_id = ? LIMIT 1",
            (ticket, user_id, media_id)).fetchone()
    return found is not None
