"""Parked failures across the three queues (inbox, outbox, extract jobs), for the admin Operations page.

Never a message body or a number: only the ticket, the queue, attempts, the last error class and times. A scoped
account sees the outbox rows of complaints in its scope; everything without a ticket needs a global account.
"""

from typing import Literal

from pydantic import BaseModel

from app.store.accounts import Account
from app.store.complaints import VISIBLE, VISIBLE_PARAMS
from app.store.db import tx

Kind = Literal["inbound", "outbound", "extract"]

_PARKED = (
    "SELECT 'inbound' AS kind, CAST(id AS TEXT) AS id, NULL AS ticket, attempts, last_error, created_at, "
    "updated_at AS failed_at FROM wa_turns WHERE state = 'failed' "
    "UNION ALL SELECT 'outbound', CAST(id AS TEXT), ticket, attempts, last_error, created_at, updated_at "
    "FROM outbox WHERE state = 'failed' "
    "UNION ALL SELECT 'extract', id, NULL, attempts, last_error, created_at, updated_at "
    "FROM extract_jobs WHERE state = 'failed'")
_IN_SCOPE = f"p.ticket IN (SELECT c.ticket FROM complaints c WHERE {VISIBLE})"


class Parked(BaseModel):
    id: str  # the row id within its queue, hence the kind in every path
    kind: Kind
    ticket: str | None
    attempts: int
    last_error: str | None  # an exception class and HTTP status, never message text
    created_at: str
    failed_at: str | None


class ParkedPage(BaseModel):
    items: list[Parked]
    total: int
    page: int
    page_size: int


def _where(account: Account, kind: Kind | None, item_id: str | None) -> tuple[str, list[object]]:
    clauses: list[str] = ["1 = 1"]
    params: list[object] = []
    if kind:
        clauses.append("p.kind = ?")
        params.append(kind)
    if item_id is not None:
        clauses.append("p.id = ?")
        params.append(item_id)
    if not account.is_global:
        clauses.append(_IN_SCOPE)
        params += [account.id] * VISIBLE_PARAMS
    return " AND ".join(clauses), params


def page(account: Account, page_no: int, page_size: int, kind: Kind | None, newest: bool) -> ParkedPage:
    where, params = _where(account, kind, None)
    order = "DESC" if newest else "ASC"
    with tx() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM ({_PARKED}) p WHERE {where}", params).fetchone()[0]
        rows = conn.execute(f"SELECT * FROM ({_PARKED}) p WHERE {where} ORDER BY p.failed_at {order}, p.id {order} "
                            "LIMIT ? OFFSET ?", [*params, page_size, (page_no - 1) * page_size]).fetchall()
    return ParkedPage(items=[Parked(**dict(r)) for r in rows], total=total, page=page_no, page_size=page_size)


def visible(account: Account, kind: Kind, item_id: str) -> bool:
    where, params = _where(account, kind, item_id)
    with tx() as conn:
        return conn.execute(f"SELECT 1 FROM ({_PARKED}) p WHERE {where}", params).fetchone() is not None
