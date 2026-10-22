"""Whether a complaint came from the mobile the DISCOM holds for the connection (app/flows/sender_check.py).

Only hashes and masked service numbers are kept; the plain numbers stay with the DISCOM. The mobile itself is never
stored here: it is the complaint's reply address, which the retention rules already govern.
"""

from typing import Any, Literal

from pydantic import BaseModel

from app.store.db import ts, tx

Status = Literal["verified", "other_connection", "registered", "not_registered", "not_checked", "no_mobile"]
Source = Literal["discom", "dev", "none"]

_DDL = (
    "CREATE TABLE IF NOT EXISTS sender_connections (ticket TEXT NOT NULL, discom TEXT NOT NULL, "
    "service_hash TEXT NOT NULL, service_masked TEXT NOT NULL, section TEXT, PRIMARY KEY (ticket, service_hash))",
)
RETRY_MINUTES = 15  # after a failed lookup


class SenderConnection(BaseModel):
    discom: str
    service_masked: str
    section: str | None
    this_one: bool  # the connection the complaint is about


class SenderCheck(BaseModel):
    """Null status means the check has not run yet."""
    status: Status | None
    source: Source | None
    checked_at: str | None
    connections: list[SenderConnection]


def ensure(conn: Any) -> None:
    for statement in _DDL:
        conn.execute(statement)


def due(limit: int) -> list[dict[str, Any]]:
    """Complaints whose check has not run, or failed long enough ago to try again. Oldest first."""
    with tx() as conn:
        rows = conn.execute("SELECT ticket, user_id, reply_to, service_number_hash FROM complaints WHERE mobile_check IS NULL "
                            "AND (mobile_checked_at IS NULL OR mobile_checked_at < datetime('now', ?)) "
                            "ORDER BY created_at LIMIT ?", (f"-{RETRY_MINUTES} minutes", limit)).fetchall()
    return [dict(r) for r in rows]


def save(ticket: str, status: Status, source: Source, connections: list[tuple[str, str, str, str | None]]) -> None:
    """`connections` are (discom, service hash, masked number, section)."""
    with tx() as conn:
        conn.execute("DELETE FROM sender_connections WHERE ticket = ?", (ticket,))
        conn.executemany("INSERT OR IGNORE INTO sender_connections (ticket, discom, service_hash, service_masked, section) "
                         "VALUES (?, ?, ?, ?, ?)", [(ticket, *c) for c in connections])
        conn.execute("UPDATE complaints SET mobile_check = ?, mobile_source = ?, mobile_checked_at = ? WHERE ticket = ?",
                     (status, source, ts(), ticket))


def failed(ticket: str) -> None:
    with tx() as conn:
        conn.execute("UPDATE complaints SET mobile_checked_at = ? WHERE ticket = ?", (ts(), ticket))


def for_ticket(ticket: str) -> SenderCheck:
    with tx() as conn:
        row = conn.execute("SELECT mobile_check, mobile_source, mobile_checked_at, service_number_hash FROM complaints "
                           "WHERE ticket = ?", (ticket,)).fetchone()
        found = conn.execute("SELECT discom, service_hash, service_masked, section FROM sender_connections WHERE ticket = ? "
                             "ORDER BY discom, service_masked", (ticket,)).fetchall()
    if row is None:
        return SenderCheck(status=None, source=None, checked_at=None, connections=[])
    own = row["service_number_hash"]
    return SenderCheck(status=row["mobile_check"], source=row["mobile_source"],
                       checked_at=row["mobile_checked_at"] if row["mobile_check"] else None,
                       connections=[SenderConnection(discom=f["discom"], service_masked=f["service_masked"], section=f["section"],
                                                     this_one=bool(own) and f["service_hash"] == own) for f in found])
