"""Case suggestions the rules found on their own, and the bill lookups the misread check needs."""

from typing import Literal

from pydantic import BaseModel

from app.domain.bill import ExtractedBill
from app.store.db import tx

SuggestionKind = Literal["corrected_reading"]
MAX_COPIES = 10  # copies of one month a consumer kept; save_bill normally leaves one


class Suggestion(BaseModel):
    ticket: str
    kind: SuggestionKind
    corrected_present_reading: int
    source_bill_id: str
    created_at: str


def bills_for_month(user_id: str, service_number: str, month: str) -> list[tuple[str, ExtractedBill]]:
    """This consumer's own bills for one connection and month, newest first. Nobody else's bills are mixed in."""
    with tx() as conn:
        rows = conn.execute("SELECT id, extraction FROM bills WHERE user_id = ? AND service_number = ? AND bill_month = ? "
                            "ORDER BY created_at DESC, rowid DESC LIMIT ?",
                            (user_id, service_number, month, MAX_COPIES)).fetchall()
    return [(row["id"], ExtractedBill.model_validate_json(row["extraction"])) for row in rows]


def save(ticket: str, kind: SuggestionKind, corrected_present_reading: int, source_bill_id: str) -> bool:
    """False when the case already has a suggestion; the first one found stands."""
    with tx() as conn:
        cursor = conn.execute("INSERT OR IGNORE INTO case_suggestions (ticket, kind, corrected_present_reading, "
                              "source_bill_id) VALUES (?, ?, ?, ?)",
                              (ticket, kind, corrected_present_reading, source_bill_id))
    return cursor.rowcount == 1


def get(ticket: str) -> Suggestion | None:
    with tx() as conn:
        row = conn.execute("SELECT * FROM case_suggestions WHERE ticket = ?", (ticket,)).fetchone()
    return Suggestion(**dict(row)) if row else None
