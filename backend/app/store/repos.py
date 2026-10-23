"""Repository functions. Service numbers are stored for the bill itself; the console only sees masked ones."""

import secrets
import sqlite3
from typing import Any

from pydantic import BaseModel, Field

from app.domain.bill import ExtractedBill, mask
from app.domain.review import final_total
from app.store import media
from app.store.db import tx


class UserState(BaseModel):
    user_id: str
    channel: str
    language: str = "te"
    current_bill_id: str | None = None
    awaiting: str | None = None
    created: bool = Field(default=False, exclude=True)  # first contact; never stored


def get_user(user_id: str, channel: str) -> UserState:
    with tx() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO users (user_id, channel) VALUES (?, ?)", (user_id, channel))
            return UserState(user_id=user_id, channel=channel, created=True)
    return UserState(user_id=row["user_id"], channel=row["channel"], language=row["language"],
                     current_bill_id=row["current_bill_id"], awaiting=row["awaiting"])


def save_user(state: UserState) -> None:
    with tx() as conn:
        conn.execute(
            "UPDATE users SET language = ?, current_bill_id = ?, awaiting = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE user_id = ?",
            (state.language, state.current_bill_id, state.awaiting, state.user_id),
        )


def set_awaiting(user_id: str, awaiting: str | None) -> None:
    """Lets the console tell the chat what the consumer's next message is for. A web consumer who only used the
    dashboard has no chat state yet, so one is made; a WhatsApp number always has one from its first message."""
    channel = "whatsapp" if user_id.startswith("wa:") else "web"
    with tx() as conn:
        conn.execute("INSERT INTO users (user_id, channel, awaiting) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE "
                     "SET awaiting = excluded.awaiting, updated_at = CURRENT_TIMESTAMP", (user_id, channel, awaiting))


def clear_awaiting(user_id: str, value: str) -> None:
    """Clear what the chat waits for, only if it is still `value`, so a newer question is not lost."""
    with tx() as conn:
        conn.execute("UPDATE users SET awaiting = NULL WHERE user_id = ? AND awaiting = ?", (user_id, value))


class StoredBill(BaseModel):
    id: str
    bill: ExtractedBill
    media_id: str | None
    created_at: str


class BillPage(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


def save_bill(user_id: str, bill: ExtractedBill, media_id: str | None, audit_status: str, overcharge: float,
              source: str = "upload") -> str:
    """Store a checked bill. Uploading the same month for the same connection again replaces the earlier copy."""
    bill_id = f"b_{secrets.token_hex(8)}"
    with tx() as conn:
        if bill.service_number and bill.bill_month:
            # A copy a complaint or case points at stays, because that record is about that exact bill.
            conn.execute("DELETE FROM bills WHERE user_id = ? AND service_number = ? AND bill_month = ? AND id NOT IN "
                         "(SELECT bill_id FROM complaints WHERE bill_id IS NOT NULL) AND id NOT IN (SELECT bill_id FROM case_bills)",
                         (user_id, bill.service_number, bill.bill_month))
        conn.execute(
            "INSERT INTO bills (id, user_id, service_number, extraction, media_id, bill_month, units, total_payable, "
            "discom, audit_status, overcharge, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (bill_id, user_id, bill.service_number, bill.model_dump_json(), media_id, bill.bill_month,
             bill.net_units(), bill.total_payable, bill.discom, audit_status, overcharge, source),
        )
    return bill_id


def get_bill(bill_id: str) -> tuple[ExtractedBill, str | None] | None:
    with tx() as conn:
        row = conn.execute("SELECT extraction, media_id FROM bills WHERE id = ?", (bill_id,)).fetchone()
    if row is None:
        return None
    return ExtractedBill.model_validate_json(row["extraction"]), row["media_id"]


def get_own_bill(user_id: str, bill_id: str) -> StoredBill | None:
    """A bill only comes back to the session that uploaded it."""
    with tx() as conn:
        row = conn.execute("SELECT id, extraction, media_id, created_at FROM bills WHERE id = ? AND user_id = ?",
                           (bill_id, user_id)).fetchone()
    if row is None:
        return None
    return StoredBill(id=row["id"], bill=ExtractedBill.model_validate_json(row["extraction"]),
                      media_id=row["media_id"], created_at=row["created_at"])


# A month the AE revised shows its latest approved amount; a month under review says so.
_REVIEW_COLUMNS = (
    "(SELECT d.revised_amount FROM review_decisions d WHERE d.bill_id = bills.id AND d.status = 'approved' "
    "AND d.revision IS NOT NULL ORDER BY d.revision DESC LIMIT 1) AS revised_amount, "
    "EXISTS (SELECT 1 FROM complaints c WHERE c.bill_id = bills.id AND c.kind = 'wrong_reading' "
    "AND c.status IN ('Open', 'In progress')) AS under_review")


def list_bills(user_id: str, page: int, page_size: int, audit_status: str | None, newest_first: bool) -> BillPage:
    where, params = "WHERE user_id = ?", [user_id]
    if audit_status:
        where += " AND audit_status = ?"
        params.append(audit_status)
    order = "DESC" if newest_first else "ASC"
    with tx() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM bills {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT id, created_at, bill_month, discom, units, total_payable, audit_status, overcharge, "
            f"service_number, CAST(json_extract(extraction, '$.arrears') AS REAL) AS arrears, {_REVIEW_COLUMNS} FROM bills {where} ORDER BY created_at {order}, id LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size]).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["service_masked"] = mask(item.pop("service_number"))
        item["under_review"] = bool(item["under_review"])
        # total_payable is what the consumer owes now: the revised amount plus the printed arrears once revised.
        item["original_total_payable"] = item["total_payable"]
        if item["revised_amount"] is not None:
            item["total_payable"] = final_total(item["revised_amount"], item.pop("arrears") or 0.0,
                                                item["original_total_payable"])
        item.pop("arrears", None)
        items.append(item)
    return BillPage(items=items, total=total, page=page, page_size=page_size)


def newest_for_service(discom: str, service_number: str) -> ExtractedBill | None:
    """Development stand-in for the DISCOM: the newest bill stored for a connection, whoever uploaded it."""
    with tx() as conn:
        row = conn.execute("SELECT extraction FROM bills WHERE service_number = ? AND discom = ? AND source != 'demo' "
                           "ORDER BY bill_month DESC, created_at DESC LIMIT 1", (service_number, discom)).fetchone()
    return ExtractedBill.model_validate_json(row["extraction"]) if row else None


def connections_of(user_id: str, limit: int = 10) -> list[tuple[str, str, str | None]]:
    """Development stand-in for the DISCOM's mobile lookup: (discom, service number, section) of this sender's own
    uploaded bills, newest first."""
    with tx() as conn:
        rows = conn.execute("SELECT discom, service_number, MAX(json_extract(extraction, '$.section')) AS section, "
                            "MAX(created_at) AS seen FROM bills WHERE user_id = ? AND service_number IS NOT NULL "
                            "AND discom IS NOT NULL AND source != 'demo' GROUP BY discom, service_number "
                            "ORDER BY seen DESC LIMIT ?", (user_id, limit)).fetchall()
    return [(r["discom"], r["service_number"], r["section"]) for r in rows]


def bills_for_service(user_id: str, service_number: str) -> list[ExtractedBill]:
    """This consumer's own earlier uploads for one connection. Another user's bills are never mixed in."""
    with tx() as conn:
        rows = conn.execute("SELECT extraction FROM bills WHERE user_id = ? AND service_number = ? "
                            "ORDER BY created_at LIMIT 60", (user_id, service_number)).fetchall()
    return [ExtractedBill.model_validate_json(row["extraction"]) for row in rows]


def erase_chat(conn: sqlite3.Connection, user_id: str) -> list[str]:
    """Delete a user's bills, chat and consents and cut the WhatsApp address from their complaints, which stay as the
    department's record. Returns the media ids those bills used, to discard once the transaction commits."""
    used = [r[0] for r in conn.execute("SELECT DISTINCT media_id FROM bills WHERE user_id = ? AND media_id IS NOT NULL",
                                       (user_id,))]
    conn.execute("DELETE FROM consents WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM bills WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM chat_drafts WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM pending_reads WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM usc_codes WHERE user_id = ?", (user_id,))
    conn.execute("UPDATE complaints SET reply_to = NULL WHERE user_id = ?", (user_id,))
    # Messages still waiting to go and bills waiting to be read hold the number; a row being sent right now finishes.
    conn.execute("DELETE FROM outbox WHERE recipient = ? AND state != 'sending'", (user_id,))
    conn.execute("DELETE FROM extract_jobs WHERE user_id = ?", (user_id,))
    return used


def forget_user(user_id: str) -> None:
    with tx() as conn:
        used = erase_chat(conn, user_id)
        # The row goes too, so a person who writes again later is a new contact and sees the privacy notice first.
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    media.discard_unreferenced(used)


def first_delivery(message_id: str) -> bool:
    """Meta retries webhooks; a message id is processed once, so one photo is never read and billed twice."""
    with tx() as conn:
        cursor = conn.execute("INSERT OR IGNORE INTO whatsapp_seen (message_id) VALUES (?)", (message_id,))
    return cursor.rowcount == 1


def log_event(channel: str, type_: str, *, language: str | None = None, intent: str | None = None,
              audit_status: str | None = None, units: int | None = None, amount: float | None = None,
              discom: str | None = None, section: str | None = None, ms: int | None = None) -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO events (channel, type, language, intent, audit_status, units, amount, discom, section, ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (channel, type_, language, intent, audit_status, units, amount, discom, section, ms),
        )


def language_of(user_id: str) -> str | None:
    """The person's language without creating their chat state, so a first message keeps its privacy notice."""
    with tx() as conn:
        row = conn.execute("SELECT language FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return row[0] if row else None
