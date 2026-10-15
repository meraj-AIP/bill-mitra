"""Privacy notice for the web app, and a consumer erasing their own account (DPDP Act 2023)."""

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.api.auth import clear_cookie
from app.api.deps import AnyAccount
from app.config import get_settings
from app.store import accounts
from app.store import privacy as store

router = APIRouter(tags=["privacy"])

PURPOSES = [
    "Read your electricity bill and check every charge against the TGERC tariff.",
    "Explain your bill in plain words, in your language.",
    "Estimate next month's units and amount from your own bills.",
    "Record your complaints so the electricity department can act on them.",
    "Your data is never sold or shared outside the electricity department.",
    "Outside vision and voice providers process your bill photo or message only to produce the answer.",
]


class PrivacyNotice(BaseModel):
    version: str
    retention_days: int
    contact: str | None
    purposes: list[str]


@router.get("/api/privacy", response_model=PrivacyNotice)
async def notice() -> PrivacyNotice:
    settings = get_settings()
    return PrivacyNotice(version=settings.privacy_notice_version, retention_days=settings.retention_days,
                         contact=settings.privacy_contact or None, purposes=PURPOSES)


@router.delete("/api/me", status_code=204)
async def delete_me(account: AnyAccount, response: Response) -> None:
    # Staff accounts carry audit history and DISCOM scope, so only an administrator closes them.
    if account.role != "consumer":
        raise HTTPException(403, "Staff accounts are closed by an administrator.")
    store.erase_account(account.id, account.user_id)
    accounts.audit(account.id, "account.delete_self", account.id)
    clear_cookie(response)
