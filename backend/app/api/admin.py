"""Staff accounts, the audit log and system health. Consumers register themselves; staff are created here.

Nobody hands out a scope outside their own, and only roles.manage holders hand out roles that manage roles,
units or policy. Every write is audited.
"""

import re
import secrets
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field

from app.api import catalog
from app.api.deps import in_scope, require_perm, viewer
from app.core.errors import REFUSED, Refusal, safe_message
from app.core.ratelimit import per_ip
from app.core.uploads import read_csv
from app.domain import rbac
from app.store import accounts, console, roles, units
from app.store.accounts import MIN_PASSWORD, Account
from app.store.units import Conflict, Unit

router = APIRouter(prefix="/api/admin", tags=["admin"])

Discom = Literal["TGSPDCL", "TGNPDCL"]
EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
Manager = Annotated[Account, Depends(require_perm("accounts.manage"))]
Auditor = Annotated[Account, Depends(require_perm("audit.view"))]
UnitIds = Annotated[list[Annotated[str, Field(max_length=40)]], Field(min_length=1, max_length=50)]
STAFF_COLUMNS = ("name", "login", "role", "unit_code")
STAFF_MAX_ROWS = 500


class NewStaff(BaseModel):
    role: str = Field(min_length=1, max_length=40)
    login: str = Field(pattern=EMAIL, max_length=120)
    name: str = Field(min_length=1, max_length=80)
    scopes: UnitIds | None = None
    discom: Discom | None = None  # older clients: one DISCOM, or both when empty; ignored when scopes are sent
    password: str = Field(min_length=MIN_PASSWORD, max_length=200)


class AccountPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    role: str | None = Field(default=None, min_length=1, max_length=40)
    scopes: UnitIds | None = None
    discom: Discom | None = None
    active: bool | None = None


class NewPassword(BaseModel):
    password: str = Field(min_length=MIN_PASSWORD, max_length=200)


def _target(actor: Account, account_id: str) -> Account:
    found = accounts.get(account_id)
    if found is None or not accounts.within(actor, found):
        raise HTTPException(404, "Account not found.")
    if set(found.permissions) & rbac.PRIVILEGED and not actor.can("roles.manage"):
        raise HTTPException(403, "Only a role manager can change an account that manages roles, units or policy.")
    return found


def _grantable_role(actor: Account, slug: str) -> None:
    role = roles.get(slug)
    if role is None or slug == rbac.CONSUMER:
        raise HTTPException(400, "Choose a staff role.")
    if set(role.permissions) & rbac.PRIVILEGED and not actor.can("roles.manage"):
        raise HTTPException(403, "Only a role manager can grant a role that manages roles, units or policy.")


def _grantable_scopes(actor: Account, unit_ids: list[str]) -> list[str]:
    chosen = list(dict.fromkeys(unit_ids))
    if units.existing(chosen) != set(chosen):
        raise HTTPException(400, "One of the scopes is not a known unit.")
    if not all(in_scope(actor, u) for u in chosen):
        raise HTTPException(403, "You cannot grant a scope outside your own.")
    return chosen


@router.get("/accounts", response_model=accounts.AccountPage)
def list_accounts(
    actor: Manager,
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(10, ge=5, le=50),
    role: str | None = Query(None, max_length=40),
    active: bool | None = None,
    q: str | None = Query(None, max_length=120),
) -> accounts.AccountPage:
    return accounts.list_accounts(page, page_size, role, active, q, viewer(actor))


@router.post("/accounts", response_model=Account)
async def create_staff(body: NewStaff, actor: Manager) -> Account:
    _grantable_role(actor, body.role)
    scopes = _grantable_scopes(actor, body.scopes or accounts.default_scopes(body.discom))
    try:
        created = accounts.create(body.role, body.login, body.name, body.password, created_by=actor.id, scopes=scopes)
    except Conflict as exc:
        raise HTTPException(409, "An account with this login already exists.") from exc
    accounts.audit(actor.id, "account.create", created.id, f"role={created.role}, scopes={len(scopes)}")
    return created


class ImportedStaff(BaseModel):
    line: int
    login: str
    name: str
    role: str
    unit: str
    password: str  # shown once in this response, never stored in clear, logged or audited


class ImportLineError(BaseModel):
    line: int
    detail: str


class StaffImport(BaseModel):
    created: list[ImportedStaff]
    errors: list[ImportLineError]


def _staff_row(actor: Account, row: dict[str, str]) -> tuple[str, str, str, Unit]:
    """(name, login, role, unit) from one CSV line. ValueError says what is wrong with the line."""
    name, login, role, code = (str(row.get(k) or "").strip() for k in STAFF_COLUMNS)
    if not name or len(name) > 80:
        raise Refusal("Give a name of up to 80 characters.")
    if len(login) > 120 or not re.fullmatch(EMAIL, login):
        raise Refusal("The login must be an email address.")
    try:
        _grantable_role(actor, role)
    except HTTPException as exc:
        raise Refusal(exc.detail) from exc
    found = [u for u in units.by_code(code) if in_scope(actor, u.id)] if code else []
    if len(found) != 1:
        raise Refusal("No unit with this code in your scope." if not found
                         else "This unit code is in both DISCOMs; create this account by hand.")
    return name, login, role, found[0]


@router.post("/accounts/import", response_model=StaffImport, dependencies=[Depends(per_ip("account-import", 5))])
async def import_staff(file: UploadFile, actor: Manager, response: Response) -> StaffImport:
    """Each line stands alone: a bad line is reported and skipped, the rest are created with a random password."""
    created, errors = [], []
    for line, row in await read_csv(file, STAFF_COLUMNS, STAFF_MAX_ROWS):
        try:
            name, login, role, unit = _staff_row(actor, row)
            password = secrets.token_urlsafe(12)
            account = accounts.create(role, login, name, password, created_by=actor.id, scopes=[unit.id])
        except Conflict:
            errors.append(ImportLineError(line=line, detail="An account with this login already exists."))
        except ValueError as exc:
            errors.append(ImportLineError(line=line, detail=safe_message(exc, REFUSED)))
        else:
            created.append(ImportedStaff(line=line, login=account.login, name=account.name, role=account.role,
                                         unit=unit.name, password=password))
    # Counts only: no logins, names or passwords in the audit log.
    accounts.audit(actor.id, "account.import", None, f"created {len(created)}, errors {len(errors)}")
    response.headers["Cache-Control"] = "no-store"
    return StaffImport(created=created, errors=errors)


@router.patch("/accounts/{account_id}", response_model=Account)
async def patch_account(account_id: str, body: AccountPatch, actor: Manager) -> Account:
    target = _target(actor, account_id)
    sent = body.model_fields_set
    rescoped = bool({"scopes", "discom"} & sent)
    if target.id == actor.id and (body.active is False or body.role not in (None, target.role) or rescoped):
        raise HTTPException(400, "You cannot deactivate, demote or rescope your own account.")
    if (body.role or rescoped) and not target.scopes:
        raise HTTPException(400, "Consumer accounts cannot be given a staff role. Create a staff account instead.")
    if body.role:
        _grantable_role(actor, body.role)
    scopes = None
    if rescoped:
        scopes = _grantable_scopes(actor, body.scopes if "scopes" in sent and body.scopes
                                   else accounts.default_scopes(body.discom))
    updated = accounts.update(account_id, name=body.name, role=body.role, active=body.active, scopes=scopes)
    assert updated is not None
    if body.active is False or (body.role and body.role != target.role) or rescoped:
        accounts.end_all_sessions(account_id)
    # Field names only; values such as a new name stay out of the log.
    accounts.audit(actor.id, "account.update", account_id, ",".join(sorted(sent)) or None)
    return updated


@router.post("/accounts/{account_id}/reset-password", status_code=204)
async def reset_password(account_id: str, body: NewPassword, actor: Manager) -> None:
    _target(actor, account_id)
    accounts.set_password(account_id, body.password)
    accounts.end_all_sessions(account_id)
    accounts.audit(actor.id, "account.reset_password", account_id)


@router.get("/audit", response_model=accounts.AuditPage)
def audit_log(
    actor: Auditor,
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(10, ge=5, le=50),
    action: str | None = Query(None, max_length=60),
) -> accounts.AuditPage:
    return accounts.list_audit(page, page_size, action, viewer(actor))


@router.get("/health")
def system_health(_: Manager) -> dict[str, object]:
    """Provider modes plus today's warning counts, so an admin sees trouble before consumers do."""
    return {"modes": catalog.health().modes.model_dump(), **console.health()}
