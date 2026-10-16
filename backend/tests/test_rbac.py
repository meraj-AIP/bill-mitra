"""Permissions, built-in and custom roles, and who may hand out which role and scope. Logins are obviously fake."""

import secrets

import pytest
from fastapi.testclient import TestClient

from app.domain import rbac
from app.main import app
from app.store.db import DISCOM_UNITS
from tests.review_kit import tree


def _name() -> str:
    return f"Test role {secrets.token_hex(3)}"


def test_catalogue_rules():
    assert rbac.BUILTIN["super_admin"].permissions.isdisjoint(rbac.MONEY | {"self.bills"})
    assert rbac.validate(["audit.view", "roles.manage", "audit.view"]) == ["roles.manage", "audit.view"]
    for bad in (["cases.nope"], [], ["roles.manage", "cases.decide"], ["roles.manage", "cases.view"]):
        with pytest.raises(ValueError):
            rbac.validate(bad)
    assert rbac.slugify("  Billing Clerk (North) ") == "billing_clerk_north"


def test_me_carries_role_permissions_and_scopes(sign_in):
    with TestClient(app) as client:
        sign_in(client, "officer", "TGNPDCL")
        me = client.get("/api/auth/me").json()
    assert me["role"] == "officer" and me["role_name"] == "DISCOM officer" and "cases.view" in me["permissions"]
    assert me["scopes"] == [{"unit_id": DISCOM_UNITS["TGNPDCL"], "name": "TGNPDCL", "kind": "discom"}]
    assert me["discom"] == "TGNPDCL"


def test_custom_role_create_edit_delete(sign_in):
    with TestClient(app) as client:
        sign_in(client, "super_admin")
        name = _name()
        made = client.post("/api/admin/roles", json={"name": name, "description": "Reads cases",
                                                     "permissions": ["cases.view", "console.view"]})
        assert made.status_code == 200, made.text
        role = made.json()
        assert role["slug"] == rbac.slugify(name) and not role["builtin"] and role["accounts"] == 0
        assert role["permissions"] == ["console.view", "cases.view"]
        assert client.post("/api/admin/roles", json={"name": name, "permissions": ["cases.view"]}).status_code == 409

        edited = client.patch(f"/api/admin/roles/{role['slug']}", json={"permissions": ["cases.view", "cases.export"]})
        assert edited.json()["permissions"] == ["cases.view", "cases.export"]
        assert client.delete(f"/api/admin/roles/{role['slug']}").status_code == 204
        assert client.delete(f"/api/admin/roles/{role['slug']}").status_code == 404
        actions = [e["action"] for e in client.get("/api/admin/audit?page_size=50").json()["items"]]
    assert {"role.create", "role.update", "role.delete"} <= set(actions)


def test_role_refusals(sign_in):
    with TestClient(app) as admin, TestClient(app) as manager:
        sign_in(admin, "super_admin")
        sign_in(manager, "admin")
        mixed = {"name": _name(), "permissions": ["roles.manage", "cases.approve"]}
        assert admin.post("/api/admin/roles", json=mixed).status_code == 400
        assert admin.post("/api/admin/roles", json={"name": _name(), "permissions": ["x.y"]}).status_code == 400
        assert admin.patch("/api/admin/roles/officer", json={"permissions": ["cases.view"]}).status_code == 400
        assert admin.delete("/api/admin/roles/officer").status_code == 409
        held = admin.post("/api/admin/roles", json={"name": _name(), "permissions": ["cases.view"]}).json()
        made = admin.post("/api/admin/accounts", json={"role": held["slug"], "login": f"held-{held['slug']}@example.com",
                                                       "name": "Holder", "password": "test-only-passphrase"})
        assert made.status_code == 200
        assert admin.delete(f"/api/admin/roles/{held['slug']}").status_code == 409
        # accounts.manage alone may list roles but not change them
        assert manager.get("/api/admin/roles").status_code == 200
        assert manager.post("/api/admin/roles", json={"name": _name(), "permissions": ["cases.view"]}).status_code == 403
        assert manager.get("/api/admin/permissions").status_code == 403


def test_account_manager_cannot_grant_outside_own_scope_or_role_powers(sign_in):
    t = tree()
    with TestClient(app) as client:
        sign_in(client, "admin", scopes=[t.division.id])
        base = {"name": "Scoped", "password": "test-only-passphrase"}
        ok = client.post("/api/admin/accounts", json={**base, "role": "section_ae", "login": f"ae-{t.tag}@example.com",
                                                      "scopes": [t.section_a.id]})
        assert ok.status_code == 200 and ok.json()["scopes"][0]["unit_id"] == t.section_a.id
        outside = client.post("/api/admin/accounts", json={**base, "role": "section_ae", "scopes": [t.circle.id],
                                                           "login": f"out-{t.tag}@example.com"})
        assert outside.status_code == 403
        powers = client.post("/api/admin/accounts", json={**base, "role": "super_admin", "scopes": [t.section_a.id],
                                                          "login": f"sa-{t.tag}@example.com"})
        assert powers.status_code == 403
        assert client.post("/api/admin/accounts", json={**base, "role": "consumer", "scopes": [t.section_a.id],
                                                        "login": f"c-{t.tag}@example.com"}).status_code == 400
        # A scoped manager sees only staff inside their scope, and cannot rescope someone outside it.
        listed = client.get("/api/admin/accounts", params={"page_size": 50}).json()["items"]
        assert {a["id"] for a in listed} >= {ok.json()["id"]}
        assert all(s["unit_id"] in (t.division.id, t.section_a.id, t.section_b.id, t.subdivision.id, t.ero.id)
                   for a in listed for s in a["scopes"])
        widen = client.patch(f"/api/admin/accounts/{ok.json()['id']}", json={"scopes": [t.circle.id]})
        assert widen.status_code == 403


def test_account_manager_cannot_touch_a_role_manager(sign_in):
    with TestClient(app) as owner, TestClient(app) as manager:
        top = sign_in(owner, "super_admin")
        sign_in(manager, "admin")
        assert manager.patch(f"/api/admin/accounts/{top.id}", json={"active": False}).status_code == 403
        assert manager.post(f"/api/admin/accounts/{top.id}/reset-password",
                            json={"password": "another-test-passphrase"}).status_code == 403

