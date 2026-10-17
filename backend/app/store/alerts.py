"""Staff alerts raised by the system. The only SQL for alerts.

An account sees an alert addressed to it, or one addressed to a unit it covers when it holds the alert's permission.
Titles and bodies are staff English and never carry a service number or a phone number.
"""

import json
from typing import Any, Literal

from pydantic import BaseModel

from app.store.accounts import Account
from app.store.db import tx
from app.store.units import covered_sql

Kind = Literal["misread_found", "case_overdue", "case_escalated", "digest", "applied_auto", "pattern_section",
               "request_reminded", "request_lapsed", "complaint_assigned", "consumer_replied", "case_assigned",
               "decision_returned"]

# Named parameters :me (account id), :perms (JSON list of its permissions), :everywhere (1 for a global account).
_VISIBLE = ("(a.account_id = :me OR (a.account_id IS NULL AND a.perm IN (SELECT value FROM json_each(:perms)) "
            f"AND (:everywhere = 1 OR a.unit_id IN {covered_sql(':me')})))")
_READ = "EXISTS (SELECT 1 FROM alert_reads r WHERE r.alert_id = a.id AND r.account_id = :me)"


class AlertOut(BaseModel):
    id: int
    kind: str
    title: str
    body: str
    ticket: str | None
    unit_name: str | None
    created_at: str
    read: bool
    href: str | None  # the page the alert opens: a case for review kinds, the complaint for the rest


def _href(ticket: str | None, kind: str | None) -> str | None:
    if not ticket or kind is None:
        return None
    return f"/review/{ticket}" if kind == "wrong_reading" else f"/console/complaints/{ticket}"


class AlertPage(BaseModel):
    items: list[AlertOut]
    total: int
    unread: int


def raise_alert(kind: Kind, unit_id: str | None, title: str, body: str, perm: str | None, dedupe_key: str,
                ticket: str | None = None, account_id: str | None = None) -> bool:
    """False when an alert with this dedupe key already exists, so callers can run again safely."""
    with tx() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO alerts (kind, unit_id, account_id, ticket, title, body, perm, dedupe_key) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (kind, unit_id, account_id, ticket, title, body, perm, dedupe_key))
    return cursor.rowcount == 1


def _who(account: Account) -> dict[str, Any]:
    return {"me": account.id, "perms": json.dumps(account.permissions), "everywhere": int(account.is_global)}


def page(account: Account, page_no: int, page_size: int, unread_only: bool) -> AlertPage:
    """Newest first."""
    args = _who(account) | {"limit": page_size, "offset": (page_no - 1) * page_size}
    where = f"{_VISIBLE} AND NOT {_READ}" if unread_only else _VISIBLE
    with tx() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM alerts a WHERE {where}", args).fetchone()[0]
        unread = conn.execute(f"SELECT COUNT(*) FROM alerts a WHERE {_VISIBLE} AND NOT {_READ}", args).fetchone()[0]
        rows = conn.execute(
            f"SELECT a.id, a.kind, a.title, a.body, a.ticket, u.name AS unit_name, a.created_at, {_READ} AS read, "
            "(SELECT c.kind FROM complaints c WHERE c.ticket = a.ticket) AS ticket_kind "
            f"FROM alerts a LEFT JOIN units u ON u.id = a.unit_id WHERE {where} "
            "ORDER BY a.id DESC LIMIT :limit OFFSET :offset", args).fetchall()
    items = [AlertOut(**{k: v for k, v in dict(r).items() if k not in ("ticket_kind", "read")}, read=bool(r["read"]),
                      href=_href(r["ticket"], r["ticket_kind"])) for r in rows]
    return AlertPage(items=items, total=total, unread=unread)


def mark_read(account: Account, alert_id: int) -> bool:
    """False when the alert does not exist or is not visible to the account."""
    with tx() as conn:
        found = conn.execute(f"SELECT 1 FROM alerts a WHERE a.id = :id AND {_VISIBLE}",
                             _who(account) | {"id": alert_id}).fetchone()
        if found is None:
            return False
        conn.execute("INSERT OR IGNORE INTO alert_reads (alert_id, account_id) VALUES (?, ?)", (alert_id, account.id))
    return True


def mark_all_read(account: Account) -> None:
    with tx() as conn:
        conn.execute(f"INSERT OR IGNORE INTO alert_reads (alert_id, account_id) SELECT a.id, :me FROM alerts a "
                     f"WHERE {_VISIBLE} AND NOT {_READ}", _who(account))
