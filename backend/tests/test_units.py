"""Units, scopes, section matching, the unmapped list, CSV import and the accounts table migration."""

import sqlite3

from fastapi.testclient import TestClient

from app.domain import rbac
from app.main import app
from app.store import db, units
from app.store.db import DISCOM_UNITS
from tests.review_kit import tree


def test_hierarchy_rules_and_alias_matching(sign_in):
    t = tree()
    with TestClient(app) as client:
        sign_in(client, "admin")
        wrong = client.post("/api/admin/units", json={"kind": "section", "name": "Misplaced", "parent_id": t.circle.id})
        assert wrong.status_code == 400
        assert client.post("/api/admin/units", json={"kind": "discom", "name": "X", "parent_id": t.circle.id}
                           ).status_code == 400
        clash = client.post("/api/admin/units", json={"kind": "section", "name": f"section-a {t.tag}",
                                                      "parent_id": t.subdivision.id})
        assert clash.status_code == 409  # normalises to Section A's own name
        top = client.get("/api/admin/units").json()
        assert {u["name"] for u in top} >= {"TGSPDCL", "TGNPDCL"} and all(u["kind"] == "discom" for u in top)
        kids = client.get("/api/admin/units", params={"parent_id": t.subdivision.id}).json()
        assert {u["id"] for u in kids} == {t.section_a.id, t.section_b.id}
        found = client.get("/api/admin/units", params={"q": f"section a {t.tag}"[:12], "kind": "section"}).json()
        assert t.section_a.id in {u["id"] for u in found}
    assert units.match_section("TGSPDCL", f"sec a {t.tag} (OLD)") == t.section_a.id
    assert units.match_section("TGSPDCL", f"SECTION-B-{t.tag}") == t.section_b.id
    assert units.match_section("TGNPDCL", f"Section B {t.tag}") is None  # another DISCOM


def test_scope_covers_the_tree_and_ero_sections(sign_in):
    t = tree()
    with TestClient(app) as client:
        division_staff = sign_in(client, "officer", scopes=[t.division.id])
        ero_staff = sign_in(client, "billing_approver", scopes=[t.ero.id])
    assert units.covers(division_staff.id, t.section_b.id) and not units.covers(division_staff.id, t.circle.id)
    assert units.covers(ero_staff.id, t.section_a.id) and not units.covers(ero_staff.id, t.section_b.id)


def test_unmapped_names_are_listed_then_mapped(sign_in):
    t = tree()
    printed = f"Old Town {t.tag}"
    units.record_unmapped("TGSPDCL", printed)
    units.record_unmapped("TGSPDCL", printed.upper())
    with TestClient(app) as client:
        sign_in(client, "admin")
        listed = {u["name"]: u for u in client.get("/api/admin/units/unmapped").json()}
        assert listed[printed]["count"] == 2 and listed[printed]["discom"] == "TGSPDCL"
        mapped = client.post("/api/admin/units/unmapped/map",
                             json={"name": printed, "discom": "TGSPDCL", "section_id": t.section_b.id})
        assert mapped.status_code == 204
        assert printed not in {u["name"] for u in client.get("/api/admin/units/unmapped").json()}
        north = client.post("/api/admin/units/unmapped/map",
                            json={"name": printed, "discom": "TGNPDCL", "section_id": t.section_b.id})
        assert north.status_code == 400
    assert units.match_section("TGSPDCL", printed) == t.section_b.id


def test_csv_import_creates_updates_and_reports_lines(sign_in):
    t = tree()
    tag = t.tag
    body = ("kind,name,code,parent_code,discom,ero_code,aliases\n"
            f"section,Section C {tag},SC{tag},S{tag},TGSPDCL,E{tag},C-{tag} old;C-{tag} older\n"
            f"section,Section A {tag} renamed,SA{tag},S{tag},TGSPDCL,,\n"
            f"section,Nowhere {tag},SN{tag},MISSING{tag},TGSPDCL,,\n"
            f"circle,North {tag},CN{tag},,TGNPDCL,,\n")
    with TestClient(app) as client:
        sign_in(client, "admin")
        result = client.post("/api/admin/units/import", files={"file": ("units.csv", body.encode(), "text/csv")}).json()
        assert result["created"] == 2 and result["updated"] == 1
        assert [e["line"] for e in result["errors"]] == [4]
        bad = client.post("/api/admin/units/import", files={"file": ("u.csv", b"name\nx\n", "text/csv")})
        assert bad.status_code == 400
    assert units.match_section("TGSPDCL", f"c-{tag} OLDER") is not None
    assert units.get(t.section_a.id).name == f"Section A {tag} renamed"


def test_scoped_unit_manager_cannot_import_another_discom(sign_in):
    t = tree()
    body = f"kind,name,code,parent_code,discom,ero_code,aliases\ncircle,Far {t.tag},CF{t.tag},,TGNPDCL,,\n"
    with TestClient(app) as client:
        sign_in(client, "admin", scopes=[DISCOM_UNITS["TGSPDCL"]])
        result = client.post("/api/admin/units/import", files={"file": ("u.csv", body.encode(), "text/csv")}).json()
    assert result["created"] == 0 and result["errors"][0]["detail"] == "This DISCOM is outside your scope."


OLD_ACCOUNTS = """CREATE TABLE accounts (
    id TEXT PRIMARY KEY, role TEXT NOT NULL CHECK (role IN ('admin', 'officer', 'consumer')),
    login TEXT NOT NULL UNIQUE, name TEXT NOT NULL, password_hash TEXT NOT NULL,
    discom TEXT, active INTEGER NOT NULL DEFAULT 1, failed_logins INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT, last_login_at TEXT, created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);"""


def test_old_accounts_table_is_rebuilt_keeping_ids_hashes_and_times():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(OLD_ACCOUNTS)
    rows = [("a1", "admin", "old-admin@example.com", None), ("o1", "officer", "old-south@example.com", "TGSPDCL"),
            ("o2", "officer", "old-all@example.com", None), ("c1", "consumer", "9999999999", None)]
    for account_id, role, login, discom in rows:
        conn.execute("INSERT INTO accounts (id, role, login, name, password_hash, discom, created_at, last_login_at) "
                     "VALUES (?, ?, ?, 'Old', ?, ?, '2026-01-02 03:04:05', '2026-02-03 04:05:06')",
                     (account_id, role, login, f"scrypt$fake-hash-{account_id}", discom))
    conn.commit()
    conn.executescript(db._SCHEMA)
    db._migrate(conn)
    db._upgrade(conn)
    db._upgrade(conn)  # every start runs it again; nothing changes the second time

    shape = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'accounts'").fetchone()[0]
    assert "CHECK" not in shape and "discom" not in shape
    got = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM accounts")}
    assert {i: got[i]["role"] for i in got} == {"a1": "admin", "o1": "officer", "o2": "officer", "c1": "consumer"}
    assert all(got[i]["password_hash"] == f"scrypt$fake-hash-{i}" and got[i]["created_at"] == "2026-01-02 03:04:05"
               and got[i]["last_login_at"] == "2026-02-03 04:05:06" for i in got)
    scopes = {}
    for r in conn.execute("SELECT account_id, unit_id FROM account_scopes"):
        scopes.setdefault(r["account_id"], set()).add(r["unit_id"])
    both = set(DISCOM_UNITS.values())
    assert scopes == {"a1": both, "o1": {DISCOM_UNITS["TGSPDCL"]}, "o2": both}
    roles = {r[0] for r in conn.execute("SELECT slug FROM roles WHERE builtin = 1")}
    assert roles == {r.slug for r in rbac.BUILTIN_ROLES}
    assert conn.execute("SELECT COUNT(*) FROM units WHERE kind = 'discom'").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM review_policy WHERE ae_limit IS NULL AND custom_needs_approval = 0"
                        ).fetchone()[0] == 2
    conn.close()
