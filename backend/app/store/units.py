"""The DISCOM hierarchy, staff scopes on it, and matching a bill's printed section to a section unit.

A scope on a unit covers that unit and everything under it; a scope on an ERO also covers the sections billed by it.
"""

import json
import secrets
import sqlite3
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.store.db import DISCOM_UNITS, tx

Kind = Literal["discom", "circle", "division", "subdivision", "section", "ero"]
PARENT_KIND: dict[str, str] = {"circle": "discom", "division": "circle", "subdivision": "division",
                               "section": "subdivision", "ero": "division"}
MAX_ALIASES = 20
LIST_LIMIT = 200


class Conflict(ValueError):
    """The request is well formed but clashes with what is stored (a 409)."""


class Unit(BaseModel):
    id: str
    kind: Kind
    name: str
    code: str | None
    discom: Literal["TGSPDCL", "TGNPDCL"]
    parent_id: str | None
    ero_id: str | None
    aliases: list[str]
    active: bool
    children_count: int


class Scope(BaseModel):
    unit_id: str
    name: str
    kind: Kind
    discom: str = Field(exclude=True)


class SectionSuggestion(BaseModel):
    section_id: str
    name: str
    score: float


class Unmapped(BaseModel):
    name: str
    discom: str
    count: int
    last_seen: str
    suggestions: list[SectionSuggestion] = []


def norm(name: str) -> str:
    """Upper case, letters and digits only, so "Kukatpally-II" and "KUKATPALLY II" are one section."""
    return "".join(ch for ch in name.upper() if ch.isalnum())


def covered_sql(param: str = "?") -> str:
    """Unit ids an account covers, as a subquery. With the default "?" the caller passes the account id twice;
    with a named parameter such as ":viewer", once."""
    return (f"(WITH RECURSIVE tree(id) AS (SELECT unit_id FROM account_scopes WHERE account_id = {param} "
            "UNION SELECT u.id FROM units u JOIN tree t ON u.parent_id = t.id) SELECT id FROM tree "
            f"UNION SELECT u.id FROM units u JOIN account_scopes s ON u.ero_id = s.unit_id WHERE s.account_id = {param})")


_UNIT = ("SELECT u.*, (SELECT COUNT(*) FROM units k WHERE k.parent_id = u.id) AS children_count FROM units u")


def _unit(row: sqlite3.Row) -> Unit:
    data = dict(row)
    return Unit(**{**data, "aliases": json.loads(data["aliases"]), "active": bool(data["active"])})


def _get(conn: sqlite3.Connection, unit_id: str | None) -> Unit | None:
    row = conn.execute(f"{_UNIT} WHERE u.id = ?", (unit_id,)).fetchone() if unit_id else None
    return _unit(row) if row else None


def get(unit_id: str) -> Unit | None:
    with tx() as conn:
        return _get(conn, unit_id)


def search(*, parent_id: str | None, q: str | None, kind: str | None, viewer: str | None) -> list[Unit]:
    """Children of a unit, or the DISCOMs when no parent is given. A text or kind filter searches every level.
    `viewer` limits the answer to what that account covers; None means everything."""
    where, params = [], []
    if q or kind:
        if q:
            where.append("(instr(upper(u.name), ?) > 0 OR instr(upper(COALESCE(u.code, '')), ?) > 0)")
            params += [q.strip().upper()] * 2
        if kind:
            where.append("u.kind = ?")
            params.append(kind)
        if parent_id:
            where.append("u.parent_id = ?")
            params.append(parent_id)
    elif parent_id:
        where.append("u.parent_id = ?")
        params.append(parent_id)
    else:
        where.append("u.kind = 'discom'")
    if viewer:
        where.append(f"u.id IN {covered_sql()}")
        params += [viewer, viewer]
    with tx() as conn:
        rows = conn.execute(f"{_UNIT} WHERE {' AND '.join(where)} ORDER BY u.kind = 'discom' DESC, u.name LIMIT ?",
                            [*params, LIST_LIMIT]).fetchall()
    return [_unit(r) for r in rows]


def _clean_aliases(aliases: list[str]) -> list[str]:
    cleaned = list(dict.fromkeys(a.strip() for a in aliases if a.strip()))
    if len(cleaned) > MAX_ALIASES or any(len(a) > 80 or not norm(a) for a in cleaned):
        raise ValueError(f"Up to {MAX_ALIASES} aliases, each 1 to 80 characters with a letter or digit.")
    return cleaned


def _index_names(conn: sqlite3.Connection, unit: Unit) -> None:
    """Keep section_names in step with a section's name and aliases; a name already owned elsewhere is refused."""
    conn.execute("DELETE FROM section_names WHERE unit_id = ?", (unit.id,))
    if unit.kind != "section":
        return
    for key in dict.fromkeys(norm(n) for n in [unit.name, *unit.aliases]):
        owner = conn.execute("SELECT unit_id FROM section_names WHERE discom = ? AND norm = ?",
                             (unit.discom, key)).fetchone()
        if owner:
            raise Conflict(f"Another section in {unit.discom} already answers to that name.")
        conn.execute("INSERT INTO section_names (discom, norm, unit_id) VALUES (?, ?, ?)", (unit.discom, key, unit.id))


def _check_ero(conn: sqlite3.Connection, kind: str, discom: str, ero_id: str | None) -> None:
    if ero_id is None:
        return
    if kind != "section":
        raise ValueError("Only a section can point at an ERO.")
    ero = _get(conn, ero_id)
    if ero is None or ero.kind != "ero" or ero.discom != discom:
        raise ValueError("The ERO must be an ERO unit of the same DISCOM.")


def _create(conn: sqlite3.Connection, kind: str, name: str, code: str | None, parent_id: str | None,
            ero_id: str | None, aliases: list[str]) -> Unit:
    if kind not in PARENT_KIND:
        raise ValueError("DISCOM units are fixed; create circles, divisions and the rest under them.")
    parent = _get(conn, parent_id)
    if parent is None or parent.kind != PARENT_KIND[kind]:
        raise ValueError(f"A {kind} must sit under a {PARENT_KIND[kind]}.")
    _check_ero(conn, kind, parent.discom, ero_id)
    unit_id = f"u_{secrets.token_hex(6)}"
    try:
        conn.execute("INSERT INTO units (id, kind, name, code, discom, parent_id, ero_id, aliases) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (unit_id, kind, name.strip(), code or None, parent.discom, parent.id, ero_id,
                      json.dumps(_clean_aliases(aliases))))
    except sqlite3.IntegrityError as exc:
        raise Conflict("A unit with this code already exists in the DISCOM.") from exc
    unit = _get(conn, unit_id)
    assert unit is not None
    _index_names(conn, unit)
    return unit


def create(kind: str, name: str, code: str | None, parent_id: str | None, ero_id: str | None = None,
           aliases: list[str] | None = None) -> Unit:
    with tx() as conn:
        return _create(conn, kind, name, code, parent_id, ero_id, aliases or [])


def _update(conn: sqlite3.Connection, unit: Unit, changes: dict[str, Any]) -> Unit:
    if unit.kind == "discom" and set(changes) - {"aliases"}:
        raise ValueError("DISCOM units are fixed.")
    if "ero_id" in changes:
        _check_ero(conn, unit.kind, unit.discom, changes["ero_id"])
    if "aliases" in changes:
        changes["aliases"] = json.dumps(_clean_aliases(changes["aliases"]))
    if "active" in changes:
        changes["active"] = int(changes["active"])
    # Column names come from the fixed set the API accepts, never from input.
    allowed = {k: v for k, v in changes.items() if k in ("name", "code", "ero_id", "aliases", "active")}
    try:
        for column, value in allowed.items():
            conn.execute(f"UPDATE units SET {column} = ? WHERE id = ?", (value, unit.id))
    except sqlite3.IntegrityError as exc:
        raise Conflict("A unit with this code already exists in the DISCOM.") from exc
    updated = _get(conn, unit.id)
    assert updated is not None
    _index_names(conn, updated)
    return updated


def update(unit_id: str, changes: dict[str, Any]) -> Unit | None:
    with tx() as conn:
        unit = _get(conn, unit_id)
        return _update(conn, unit, changes) if unit else None


class ImportResult(BaseModel):
    created: int
    updated: int
    errors: list[dict[str, Any]]


def _by_code(conn: sqlite3.Connection, discom: str, code: str) -> Unit | None:
    row = conn.execute(f"{_UNIT} WHERE u.discom = ? AND u.code = ?", (discom, code)).fetchone()
    return _unit(row) if row else None


def _import_row(conn: sqlite3.Connection, row: dict[str, str]) -> bool:
    """True when a unit was created, False when updated. ValueError explains a bad line."""
    kind, name, code, discom = (row.get(k, "").strip() for k in ("kind", "name", "code", "discom"))
    if discom not in DISCOM_UNITS or not name or not code:
        raise ValueError("kind, name, code and a discom of TGSPDCL or TGNPDCL are required.")
    parent_code, ero_code = row.get("parent_code", "").strip(), row.get("ero_code", "").strip()
    parent = _by_code(conn, discom, parent_code) if parent_code else _get(conn, DISCOM_UNITS[discom])
    if parent is None:
        raise ValueError(f"No unit with code {parent_code} in {discom}.")
    ero = _by_code(conn, discom, ero_code) if ero_code else None
    if ero_code and ero is None:
        raise ValueError(f"No ERO with code {ero_code} in {discom}.")
    aliases = [a for a in row.get("aliases", "").split(";") if a.strip()]
    existing = _by_code(conn, discom, code)
    if existing is None:
        _create(conn, kind, name, code, parent.id, ero.id if ero else None, aliases)
        return True
    if existing.kind != kind or existing.parent_id != parent.id:
        raise ValueError("A unit with this code exists with another kind or parent; units are not moved by import.")
    _update(conn, existing, {"name": name, "aliases": aliases, "ero_id": ero.id if ero else existing.ero_id})
    return False


def import_rows(rows: list[tuple[int, dict[str, str]]]) -> ImportResult:
    """Rows as (file line, values). Each line stands alone: a bad line is reported and skipped, the rest land."""
    created = updated = 0
    errors: list[dict[str, Any]] = []
    with tx() as conn:
        for line, row in rows:
            conn.execute("SAVEPOINT unit_row")
            try:
                if _import_row(conn, row):
                    created += 1
                else:
                    updated += 1
                conn.execute("RELEASE unit_row")
            except ValueError as exc:
                conn.execute("ROLLBACK TO unit_row")
                conn.execute("RELEASE unit_row")
                errors.append({"line": line, "detail": str(exc)})
    return ImportResult(created=created, updated=updated, errors=errors)


def match_section(discom: str | None, printed: str | None) -> str | None:
    """The active section a printed `Sec:` name belongs to, or None."""
    if not discom or not printed or not norm(printed):
        return None
    with tx() as conn:
        row = conn.execute("SELECT n.unit_id FROM section_names n JOIN units u ON u.id = n.unit_id "
                           "WHERE n.discom = ? AND n.norm = ? AND u.active = 1", (discom, norm(printed))).fetchone()
    return row[0] if row else None


def record_unmapped(discom: str, printed: str) -> None:
    with tx() as conn:
        conn.execute("INSERT INTO unmapped_sections (discom, norm, name, count) VALUES (?, ?, ?, 1) "
                     "ON CONFLICT(discom, norm) DO UPDATE SET count = count + 1, last_seen = CURRENT_TIMESTAMP",
                     (discom, norm(printed), printed.strip()[:80]))


def unmapped() -> list[Unmapped]:
    with tx() as conn:
        rows = conn.execute("SELECT name, discom, count, last_seen FROM unmapped_sections "
                            "ORDER BY count DESC, last_seen DESC LIMIT ?", (LIST_LIMIT,)).fetchall()
    return [Unmapped(**dict(r)) for r in rows]


def section_names(discom: str, viewer: str | None) -> list[tuple[str, str, str]]:
    """(section id, section name, normalised name or alias) for the active sections of a DISCOM. `viewer` keeps
    only sections that account covers; None means all."""
    with tx() as conn:
        rows = conn.execute("SELECT u.id, u.name, n.norm FROM section_names n JOIN units u ON u.id = n.unit_id "
                            "WHERE n.discom = :d AND u.kind = 'section' AND u.active = 1 AND "
                            f"(:v IS NULL OR u.id IN {covered_sql(':v')})",
                            {"d": discom, "v": viewer}).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def by_code(code: str) -> list[Unit]:
    """Units with this code in any DISCOM (codes are unique within a DISCOM only)."""
    with tx() as conn:
        rows = conn.execute(f"{_UNIT} WHERE u.code = ? LIMIT 3", (code,)).fetchall()
    return [_unit(r) for r in rows]


def map_unmapped(name: str, discom: str, section_id: str) -> Unit:
    """Add the printed name as an alias of the section and drop it from the unmapped list."""
    with tx() as conn:
        section = _get(conn, section_id)
        if section is None or section.kind != "section" or section.discom != discom:
            raise ValueError("Choose a section of the same DISCOM.")
        updated = _update(conn, section, {"aliases": [*section.aliases, name.strip()]})
        conn.execute("DELETE FROM unmapped_sections WHERE discom = ? AND norm = ?", (discom, norm(name)))
    return updated


def covers(account_id: str, unit_id: str | None) -> bool:
    if not unit_id:
        return False
    with tx() as conn:
        found = conn.execute(f"SELECT 1 WHERE ? IN {covered_sql()}", (unit_id, account_id, account_id)).fetchone()
    return found is not None


def ancestors(unit_id: str) -> list[Unit]:
    """The unit and every unit above it, nearest first."""
    out: list[Unit] = []
    with tx() as conn:
        unit = _get(conn, unit_id)
        while unit is not None and len(out) < len(PARENT_KIND) + 2:
            out.append(unit)
            unit = _get(conn, unit.parent_id)
    return out


def scopes_for(account_ids: list[str]) -> dict[str, list[Scope]]:
    if not account_ids:
        return {}
    marks = ",".join("?" * len(account_ids))
    with tx() as conn:
        rows = conn.execute(f"SELECT s.account_id, u.id AS unit_id, u.name, u.kind, u.discom FROM account_scopes s "
                            f"JOIN units u ON u.id = s.unit_id WHERE s.account_id IN ({marks}) "
                            "ORDER BY s.rowid", account_ids).fetchall()
    out: dict[str, list[Scope]] = {}
    for r in rows:
        out.setdefault(r["account_id"], []).append(Scope(unit_id=r["unit_id"], name=r["name"], kind=r["kind"],
                                                         discom=r["discom"]))
    return out


def set_scopes(conn: sqlite3.Connection, account_id: str, unit_ids: list[str]) -> None:
    """Replace an account's scopes inside the caller's transaction."""
    conn.execute("DELETE FROM account_scopes WHERE account_id = ?", (account_id,))
    conn.executemany("INSERT OR IGNORE INTO account_scopes (account_id, unit_id) VALUES (?, ?)",
                     [(account_id, u) for u in unit_ids])


def existing(unit_ids: list[str]) -> set[str]:
    if not unit_ids:
        return set()
    marks = ",".join("?" * len(unit_ids))
    with tx() as conn:
        return {r[0] for r in conn.execute(f"SELECT id FROM units WHERE id IN ({marks})", unit_ids)}
