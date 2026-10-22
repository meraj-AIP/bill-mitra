"""The connections the DISCOM holds for a consumer's registered mobile, found when they sign up. Masked numbers and
hashes only; the plain service numbers stay with the DISCOM."""

from typing import Any

from pydantic import BaseModel

from app.store.db import tx

_DDL = ("CREATE TABLE IF NOT EXISTS account_connections (account_id TEXT NOT NULL, discom TEXT NOT NULL, "
        "service_hash TEXT NOT NULL, service_masked TEXT NOT NULL, section TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (account_id, service_hash))",)


class Connection(BaseModel):
    discom: str
    service_masked: str
    section: str | None


def ensure(conn: Any) -> None:
    for statement in _DDL:
        conn.execute(statement)


def replace(account_id: str, found: list[tuple[str, str, str, str | None]]) -> None:
    """`found` are (discom, service hash, masked number, section)."""
    with tx() as conn:
        conn.execute("DELETE FROM account_connections WHERE account_id = ?", (account_id,))
        conn.executemany("INSERT OR IGNORE INTO account_connections (account_id, discom, service_hash, service_masked, "
                         "section) VALUES (?, ?, ?, ?, ?)", [(account_id, *c) for c in found])


def for_account(account_id: str) -> list[Connection]:
    with tx() as conn:
        rows = conn.execute("SELECT discom, service_masked, section FROM account_connections WHERE account_id = ? "
                            "ORDER BY discom, service_masked", (account_id,)).fetchall()
    return [Connection(discom=r[0], service_masked=r[1], section=r[2]) for r in rows]


def erase(conn: Any, account_id: str) -> None:
    conn.execute("DELETE FROM account_connections WHERE account_id = ?", (account_id,))
