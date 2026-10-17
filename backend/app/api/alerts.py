"""Alerts for staff: what the system noticed in their area or for them. Consumers never see alerts."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.deps import FORBIDDEN, AnyAccount
from app.store import alerts as store
from app.store.accounts import Account
from app.store.alerts import AlertPage

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

CONSUMER_ONLY = {"self.bills"}


def _staff(account: AnyAccount) -> Account:
    """Staff means holding any permission beyond a consumer's own bills."""
    if not set(account.permissions) - CONSUMER_ONLY:
        raise HTTPException(403, FORBIDDEN)
    return account


Staff = Annotated[Account, Depends(_staff)]


@router.get("", response_model=AlertPage)
async def list_alerts(account: Staff, page: Annotated[int, Query(ge=1, le=10_000)] = 1,
                      page_size: Annotated[int, Query(ge=1, le=100)] = 20, unread: bool = False) -> AlertPage:
    return store.page(account, page, page_size, unread)


@router.post("/read-all", status_code=204)
async def read_all(account: Staff) -> Response:
    store.mark_all_read(account)
    return Response(status_code=204)


@router.post("/{alert_id}/read", status_code=204)
async def read_one(alert_id: int, account: Staff) -> Response:
    if not store.mark_read(account, alert_id):
        raise HTTPException(404, "Alert not found.")
    return Response(status_code=204)
