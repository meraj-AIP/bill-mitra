"""Roles: the seeded built-in ones and the custom ones a roles.manage holder creates. Permissions are stored as a
JSON list checked against the catalogue in app/domain/rbac.py."""

import json
import sqlite3

from pydantic import BaseModel

from app.domain import rbac
from app.store.db import tx
from app.store.units import Conflict


class Role(BaseModel):
    slug: str
    name: str
    description: str
    permissions: list[str]
    builtin: bool
    accounts: int


_ROLE = ("SELECT r.*, (SELECT COUNT(*) FROM accounts a WHERE a.role = r.slug) AS accounts FROM roles r")


def _role(row: sqlite3.Row) -> Role:
    data = dict(row)
    return Role(slug=data["slug"], name=data["name"], description=data["description"],
                permissions=json.loads(data["permissions"]), builtin=bool(data["builtin"]), accounts=data["accounts"])


def get(slug: str) -> Role | None:
    with tx() as conn:
        row = conn.execute(f"{_ROLE} WHERE r.slug = ?", (slug,)).fetchone()
    return _role(row) if row else None


def all_roles() -> list[Role]:
    with tx() as conn:
        rows = conn.execute(f"{_ROLE} ORDER BY r.builtin DESC, r.name").fetchall()
    return [_role(r) for r in rows]


def create(name: str, description: str, permissions: list[str]) -> Role:
    slug, perms = rbac.slugify(name), rbac.validate(permissions)
    with tx() as conn:
        try:
            conn.execute("INSERT INTO roles (slug, name, description, permissions) VALUES (?, ?, ?, ?)",
                         (slug, name.strip(), description.strip(), json.dumps(perms)))
        except sqlite3.IntegrityError as exc:
            raise Conflict("A role with this name already exists.") from exc
    found = get(slug)
    assert found is not None
    return found


def update(slug: str, *, name: str | None, description: str | None, permissions: list[str] | None) -> Role | None:
    current = get(slug)
    if current is None:
        return None
    if permissions is not None and current.builtin:
        raise ValueError("Built-in roles keep their permissions. Create a custom role instead.")
    perms = rbac.validate(permissions) if permissions is not None else current.permissions
    with tx() as conn:
        conn.execute("UPDATE roles SET name = ?, description = ?, permissions = ? WHERE slug = ?",
                     ((name or current.name).strip(),
                      (current.description if description is None else description).strip(), json.dumps(perms), slug))
    return get(slug)


def delete(slug: str) -> bool:
    """False when there is no such role. Conflict when it is built in or still held by an account."""
    with tx() as conn:  # one lock, so no account can take the role between the check and the delete
        row = conn.execute(f"{_ROLE} WHERE r.slug = ?", (slug,)).fetchone()
        if row is None:
            return False
        if row["builtin"] or row["accounts"]:
            raise Conflict("Built-in roles and roles that accounts still hold cannot be deleted.")
        conn.execute("DELETE FROM roles WHERE slug = ?", (slug,))
    return True
