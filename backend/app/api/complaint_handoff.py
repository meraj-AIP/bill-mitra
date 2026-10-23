"""Handing a general complaint over and sending it back (rules in app/flows/handoff.py). Staff only, in scope.

A reading check is moved from its review case instead, where deciders are listed."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints

from app.api.complaints import ComplaintDetail, Replier, _detail, _for_staff
from app.api.deps import require_perm
from app.core.errors import REFUSED, safe_message
from app.flows import handoff
from app.store import complaints as store
from app.store.accounts import Account
from app.store.complaints import OPEN_STATUSES, Complaint

router = APIRouter(prefix="/api/console/complaints", tags=["complaints"])

Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=handoff.NOTE_MIN, max_length=handoff.NOTE_MAX)]
Assigner = Annotated[Account, Depends(require_perm("complaints.assign"))]


class AssignBody(BaseModel):
    account_id: str = Field(max_length=40)
    note: Note


class ReturnBody(BaseModel):
    note: Note


def _general(account: Account, ticket: str) -> Complaint:
    complaint = _for_staff(account, ticket)
    if complaint.kind != "general":
        raise HTTPException(409, "Move a reading check from its review case.")
    if complaint.status not in OPEN_STATUSES:
        raise HTTPException(409, "This complaint is closed.")
    return complaint


def _fresh(ticket: str, account: Account) -> ComplaintDetail:
    """The detail once more, even when the caller saw it only as its holder and has just passed it on."""
    updated = store.get(ticket)
    assert updated is not None
    return _detail(updated, account)


@router.post("/{ticket}/assign", response_model=ComplaintDetail)
async def assign(ticket: str, body: AssignBody, account: Assigner) -> ComplaintDetail:
    try:
        handoff.assign(account, _general(account, ticket), body.account_id, body.note)
    except handoff.Refused as exc:
        raise HTTPException(exc.status, safe_message(exc, REFUSED)) from exc
    return _fresh(ticket, account)


@router.post("/{ticket}/return", response_model=ComplaintDetail)
async def send_back(ticket: str, body: ReturnBody, account: Replier) -> ComplaintDetail:
    """Only the holder sends it back, and only to whoever handed it over."""
    try:
        handoff.send_back(account, _general(account, ticket), body.note)
    except handoff.Refused as exc:
        raise HTTPException(exc.status, safe_message(exc, REFUSED)) from exc
    return _fresh(ticket, account)
