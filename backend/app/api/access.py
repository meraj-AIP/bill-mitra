"""Roles, units and review policy: the access setup a super admin owns. Every write is audited."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import in_scope, require_perm, viewer
from app.core.uploads import read_csv
from app.domain import rbac
from app.domain.review import Policy
from app.domain.section_match import closest
from app.flows import cases
from app.store import accounts, roles, units
from app.store import policy as policy_store
from app.store.accounts import Account
from app.store.db import DISCOM_UNITS
from app.store.roles import Role
from app.store.units import Conflict, SectionSuggestion, Unit, Unmapped

router = APIRouter(prefix="/api/admin", tags=["access"])

Discom = Literal["TGSPDCL", "TGNPDCL"]
RoleManager = Annotated[Account, Depends(require_perm("roles.manage"))]
UnitManager = Annotated[Account, Depends(require_perm("units.manage"))]
# Staff who log complaints pick a section in their scope, so they read units too (results stay scoped).
UnitReader = Annotated[Account, Depends(require_perm("units.manage", "accounts.manage", "complaints.create"))]
PolicyManager = Annotated[Account, Depends(require_perm("policy.manage"))]
RoleReader = Annotated[Account, Depends(require_perm("accounts.manage"))]
Name = Annotated[str, Field(min_length=1, max_length=80)]
Aliases = Annotated[list[Annotated[str, Field(max_length=80)]], Field(max_length=20)]
IMPORT_MAX_ROWS = 5000
IMPORT_COLUMNS = ("kind", "name", "code", "parent_code", "discom", "ero_code", "aliases")


class Permission(BaseModel):
    code: str
    label: str
    group: str


class NewRole(BaseModel):
    name: Name
    description: str = Field(default="", max_length=300)
    permissions: list[str] = Field(max_length=len(rbac.PERMISSIONS))


class RolePatch(BaseModel):
    name: Name | None = None
    description: str | None = Field(default=None, max_length=300)
    permissions: list[str] | None = Field(default=None, max_length=len(rbac.PERMISSIONS))


class NewUnit(BaseModel):
    kind: units.Kind
    name: Name
    code: str | None = Field(default=None, max_length=40)
    parent_id: str = Field(max_length=40)
    ero_id: str | None = Field(default=None, max_length=40)
    aliases: Aliases = []


class UnitPatch(BaseModel):
    name: Name | None = None
    code: str | None = Field(default=None, max_length=40)
    ero_id: str | None = Field(default=None, max_length=40)
    aliases: Aliases | None = None
    active: bool | None = None


class MapUnmapped(BaseModel):
    name: Name
    discom: Discom
    section_id: str = Field(max_length=40)


class PolicyUpdate(Policy):
    discom: Discom | None = None  # type: ignore[assignment]  (the path names the DISCOM)


@router.get("/permissions", response_model=list[Permission])
async def permissions(_: RoleManager) -> list[Permission]:
    return [Permission(code=c, label=label, group=group) for c, (label, group) in rbac.PERMISSIONS.items()]


@router.get("/roles", response_model=list[Role])
async def list_roles(_: RoleReader) -> list[Role]:
    return roles.all_roles()


@router.post("/roles", response_model=Role)
async def create_role(body: NewRole, actor: RoleManager) -> Role:
    try:
        role = roles.create(body.name, body.description, body.permissions)
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    accounts.audit(actor.id, "role.create", role.slug, ",".join(role.permissions))
    return role


@router.patch("/roles/{slug}", response_model=Role)
async def patch_role(slug: str, body: RolePatch, actor: RoleManager) -> Role:
    try:
        role = roles.update(slug, name=body.name, description=body.description, permissions=body.permissions)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if role is None:
        raise HTTPException(404, "Role not found.")
    accounts.audit(actor.id, "role.update", slug, ",".join(sorted(body.model_fields_set)) or None)
    return role


@router.post("/roles/{slug}/reset", response_model=Role)
async def reset_role(slug: str, actor: RoleManager) -> Role:
    role = roles.reset(slug)
    if role is None:
        raise HTTPException(404, "Only a built-in role can be reset.")
    accounts.audit(actor.id, "role.reset", slug)
    return role


@router.delete("/roles/{slug}", status_code=204)
async def delete_role(slug: str, actor: RoleManager) -> Response:
    try:
        if not roles.delete(slug):
            raise HTTPException(404, "Role not found.")
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    accounts.audit(actor.id, "role.delete", slug)
    return Response(status_code=204)


@router.get("/units", response_model=list[Unit])
async def list_units(actor: UnitReader, parent_id: Annotated[str | None, Query(max_length=40)] = None,
                     q: Annotated[str | None, Query(max_length=80)] = None, kind: units.Kind | None = None
                     ) -> list[Unit]:
    return units.search(parent_id=parent_id, q=q, kind=kind, viewer=viewer(actor))


def _own_unit(actor: Account, unit_id: str | None) -> Unit:
    found = units.get(unit_id) if unit_id else None
    if found is None or not in_scope(actor, found.id):
        raise HTTPException(404, "Unit not found.")
    return found


@router.post("/units", response_model=Unit)
async def create_unit(body: NewUnit, actor: UnitManager) -> Unit:
    _own_unit(actor, body.parent_id)
    try:
        unit = units.create(body.kind, body.name, body.code, body.parent_id, body.ero_id, body.aliases)
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    accounts.audit(actor.id, "unit.create", unit.id, unit.kind, unit_id=unit.id)
    return unit


@router.patch("/units/{unit_id}", response_model=Unit)
async def patch_unit(unit_id: str, body: UnitPatch, actor: UnitManager) -> Unit:
    _own_unit(actor, unit_id)
    try:
        unit = units.update(unit_id, body.model_dump(include=body.model_fields_set))
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    assert unit is not None
    accounts.audit(actor.id, "unit.update", unit_id, ",".join(sorted(body.model_fields_set)) or None, unit_id=unit_id)
    return unit


@router.post("/units/import", response_model=units.ImportResult)
async def import_units(file: UploadFile, actor: UnitManager) -> units.ImportResult:
    numbered = await read_csv(file, IMPORT_COLUMNS, IMPORT_MAX_ROWS)
    allowed = {d for d, u in DISCOM_UNITS.items() if in_scope(actor, u)}
    result = units.import_rows([(n, r) for n, r in numbered if (r.get("discom") or "").strip() in allowed])
    result.errors += [{"line": n, "detail": "This DISCOM is outside your scope."}
                      for n, r in numbered if (r.get("discom") or "").strip() not in allowed]
    result.errors.sort(key=lambda e: e["line"])
    accounts.audit(actor.id, "unit.import", None,
                   f"created {result.created}, updated {result.updated}, errors {len(result.errors)}")
    return result


@router.get("/units/unmapped", response_model=list[Unmapped])
async def list_unmapped(actor: UnitManager) -> list[Unmapped]:
    """Each name carries up to three likely sections the actor may map it to."""
    items = [u for u in units.unmapped() if in_scope(actor, DISCOM_UNITS[u.discom])]
    names = {d: units.section_names(d, viewer(actor)) for d in {u.discom for u in items}}
    for item in items:
        item.suggestions = [SectionSuggestion(section_id=i, name=n, score=score)
                            for i, n, score in closest(units.norm(item.name), names[item.discom])]
    return items


@router.post("/units/unmapped/map", status_code=204)
async def map_unmapped(body: MapUnmapped, actor: UnitManager) -> Response:
    _own_unit(actor, body.section_id)
    try:
        section = units.map_unmapped(body.name, body.discom, body.section_id)
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    moved = cases.reroute(body.discom, {units.norm(n) for n in [section.name, *section.aliases]})
    accounts.audit(actor.id, "unit.map", section.id, f"{len(moved)} open cases re-routed", unit_id=section.id)
    return Response(status_code=204)


@router.get("/policy", response_model=list[Policy])
async def list_policy(actor: PolicyManager) -> list[Policy]:
    return [p for p in policy_store.all_policies() if in_scope(actor, DISCOM_UNITS[p.discom])]


@router.put("/policy/{discom}", response_model=Policy)
async def put_policy(discom: Discom, body: PolicyUpdate, actor: PolicyManager) -> Policy:
    if not in_scope(actor, DISCOM_UNITS[discom]):
        raise HTTPException(403, "This DISCOM is outside your scope.")
    # Fields left out keep their current value; an explicit null ae_limit means no limit.
    current = policy_store.get(discom).model_dump()
    saved = policy_store.save(Policy(**{**current, **body.model_dump(exclude_unset=True), "discom": discom}))
    detail = ", ".join(f"{k}={v}" for k, v in saved.model_dump(exclude={"discom"}).items())
    accounts.audit(actor.id, "policy.update", discom, detail, unit_id=DISCOM_UNITS[discom])
    return saved
