"""Account management for admins. Consumers register themselves; staff are created here. Every write is audited."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api import catalog
from app.api.deps import Admin
from app.store import accounts, console
from app.store.accounts import MIN_PASSWORD, Account, Role

router = APIRouter(prefix="/api/admin", tags=["admin"])

Discom = Literal["TGSPDCL", "TGNPDCL"]
StaffRole = Literal["admin", "officer"]
EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class NewStaff(BaseModel):
    role: StaffRole
    login: str = Field(pattern=EMAIL, max_length=120)
    name: str = Field(min_length=1, max_length=80)
    discom: Discom | None = None
    password: str = Field(min_length=MIN_PASSWORD, max_length=200)


class AccountPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    role: StaffRole | None = None
    discom: Discom | None = None
    active: bool | None = None


class NewPassword(BaseModel):
    password: str = Field(min_length=MIN_PASSWORD, max_length=200)


def _target(account_id: str) -> Account:
    found = accounts.get(account_id)
    if found is None:
        raise HTTPException(404, "Account not found.")
    return found


@router.get("/accounts", response_model=accounts.AccountPage)
async def list_accounts(
    _: Admin,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=5, le=50),
    role: Role | None = None,
    active: bool | None = None,
    q: str | None = Query(None, max_length=120),
) -> accounts.AccountPage:
    return accounts.list_accounts(page, page_size, role, active, q)


@router.post("/accounts", response_model=Account)
async def create_staff(body: NewStaff, admin: Admin) -> Account:
    try:
        created = accounts.create(body.role, body.login, body.name, body.password,
                                  body.discom if body.role == "officer" else None, created_by=admin.id)
    except ValueError as exc:  # password length is validated above, so this is a taken login
        raise HTTPException(409, "An account with this login already exists.") from exc
    accounts.audit(admin.id, "account.create", created.id, f"role={created.role}")
    return created


@router.patch("/accounts/{account_id}", response_model=Account)
async def patch_account(account_id: str, body: AccountPatch, admin: Admin) -> Account:
    target = _target(account_id)
    if target.id == admin.id and (body.active is False or body.role not in (None, "admin")):
        raise HTTPException(400, "You cannot deactivate or demote your own account.")
    if body.role and target.role == "consumer":
        raise HTTPException(400, "Consumer accounts cannot be given a staff role. Create a staff account instead.")
    sent = body.model_fields_set
    updated = accounts.update(account_id, name=body.name, role=body.role, active=body.active,
                              discom=body.discom, set_discom="discom" in sent)
    assert updated is not None
    if body.active is False or (body.role and body.role != target.role):
        accounts.end_all_sessions(account_id)
    # Field names only; values such as a new name stay out of the log.
    accounts.audit(admin.id, "account.update", account_id, ",".join(sorted(sent)) or None)
    return updated


@router.post("/accounts/{account_id}/reset-password", status_code=204)
async def reset_password(account_id: str, body: NewPassword, admin: Admin) -> None:
    _target(account_id)
    accounts.set_password(account_id, body.password)
    accounts.end_all_sessions(account_id)
    accounts.audit(admin.id, "account.reset_password", account_id)


@router.get("/audit", response_model=accounts.AuditPage)
async def audit_log(
    _: Admin,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=5, le=50),
    action: str | None = Query(None, max_length=60),
) -> accounts.AuditPage:
    return accounts.list_audit(page, page_size, action)


@router.get("/health")
async def system_health(_: Admin) -> dict[str, object]:
    """Provider modes plus today's warning counts, so an admin sees trouble before consumers do."""
    return {"modes": (await catalog.health()).modes.model_dump(), **console.health()}
