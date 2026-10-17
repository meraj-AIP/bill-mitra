"""The staff timeline of a complaint, oldest first, in the same shape as a review case's: who raised it, every audited
step (System when automatic, the staff name when a person acted) and each later message from the consumer."""

from typing import Any

from app.flows.evidence import CONSUMER_ACTIONS, TIMELINE_TEXT, UNLISTED, Actor, TimelineEntry, readable
from app.store import case_evidence as evidence_store
from app.store import complaints

COMPLAINT_TEXT = {"complaint.reply": "Replied to the consumer", "complaint.status": "Changed the status",
                  "complaint.request": "Asked the consumer for", "complaint.retry": "Retried a failed message",
                  "complaint.assign": "Assigned"}
# Hand-offs read as one sentence: "Handed to <name>: <note>". The detail is "<name>: <note>", staff words only.
HANDOFF_TEXT = {"complaint.route": "Routed to", "complaint.handoff": "Handed to", "complaint.return": "Sent back to"}
SOURCE_TEXT = {"consumer_web": "on the web", "consumer_chat": "in the web chat", "whatsapp": "on WhatsApp",
               "call_centre": "from a 1912 call", "office": "at the office", "field": "in the field"}


def _audited(row: dict[str, Any]) -> TimelineEntry:
    if row["action"] in CONSUMER_ACTIONS:
        actor = Actor(kind="consumer", name=None)
    elif row["actor_id"] is None:
        actor = Actor(kind="system", name="System")
    else:
        actor = Actor(kind="staff", name=row["actor_name"])
    if row["action"] in HANDOFF_TEXT:
        return TimelineEntry(at=row["ts"], actor=actor, text=f"{HANDOFF_TEXT[row['action']]} {row['detail'] or 'staff'}")
    label = COMPLAINT_TEXT.get(row["action"]) or TIMELINE_TEXT.get(row["action"], row["action"])
    detail = readable(row["action"], row["detail"])
    return TimelineEntry(at=row["ts"], actor=actor, text=f"{label}: {detail}" if detail else label)



def timeline(ticket: str, row: dict[str, Any]) -> list[TimelineEntry]:
    """`row` is the inbox row: created_at, source and raised_by (a staff name, or None for the consumer)."""
    where = SOURCE_TEXT.get(row.get("source") or "", "")
    raised = TimelineEntry(at=row["created_at"], text=f"Raised the complaint {where}".strip(),
                           actor=Actor(kind="staff", name=row["raised_by"]) if row.get("raised_by")
                           else Actor(kind="consumer", name=None))
    steps = [_audited(r) for r in evidence_store.timeline_rows(ticket)
             if r["action"] != "complaint.create" and r["action"] not in UNLISTED]
    later = [m for m in complaints.messages(ticket)[1:] if m["author_kind"] == "consumer"]
    replies = [TimelineEntry(at=m["created_at"], actor=Actor(kind="consumer", name=None),
                             text="Sent a photo" if m["media_id"] else "Sent a message") for m in later]
    return [raised, *sorted([*steps, *replies], key=lambda e: e.at)]
