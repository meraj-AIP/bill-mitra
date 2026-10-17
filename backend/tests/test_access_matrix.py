"""Every built-in role against every protected area: allowed exactly where its permissions say, refused elsewhere.

The expectation is read from the role catalogue itself, so a change to a role's permissions changes what this test
demands, and a route that forgets its permission check fails here.
"""

import pytest
from fastapi.testclient import TestClient

from app.domain import rbac
from app.main import app

# Each protected area and the permissions that open it (any one of them).
AREAS: dict[str, set[str]] = {
    "/api/console/summary": {"console.view"},
    "/api/console/complaints": {"complaints.view"},
    "/api/review/cases": {"cases.view"},
    "/api/review/sections": {"cases.view"},
    "/api/review/revisions.csv": {"cases.export"},
    "/api/admin/accounts": {"accounts.manage"},
    "/api/admin/roles": {"accounts.manage"},
    "/api/admin/permissions": {"roles.manage"},
    "/api/admin/units": {"units.manage", "accounts.manage", "complaints.create"},
    "/api/admin/units/unmapped": {"units.manage"},
    "/api/admin/policy": {"policy.manage"},
    "/api/admin/audit": {"audit.view"},
    "/api/bills": {"self.bills", "chat.preview"},
    "/api/web/history": {"self.bills", "chat.preview"},
    "/api/complaints": {"self.bills"},
}
# Write routes, called with an empty body: a holder gets past the permission check to validation (422).
POSTS: dict[str, set[str]] = {
    "/api/console/complaints": {"complaints.create"},
    "/api/complaints": {"self.bills"},
    "/api/bills/by-usc/start": {"self.bills"},
    "/api/bills/by-usc/verify": {"self.bills"},
    "/api/console/complaints/BM-000000-NONE0/assign": {"complaints.assign"},
}


@pytest.mark.parametrize("role", [r.slug for r in rbac.BUILTIN_ROLES])
def test_each_role_reaches_exactly_its_areas(sign_in, role):
    held = rbac.BUILTIN[role].permissions
    with TestClient(app) as client:
        sign_in(client, role)
        for path, opens in AREAS.items():
            status = client.get(path).status_code
            if held & opens:
                assert status == 200, f"{role} should open {path}, got {status}"
            else:
                assert status == 403, f"{role} must be refused {path}, got {status}"
        for path, opens in POSTS.items():
            status = client.post(path, json={}).status_code
            if held & opens:
                assert status == 422, f"{role} should reach {path}, got {status}"
            else:
                assert status == 403, f"{role} must be refused {path}, got {status}"


def test_signed_out_reaches_nothing():
    with TestClient(app) as client:
        for path in AREAS:
            assert client.get(path).status_code == 401, path
        for path in POSTS:
            assert client.post(path, json={}).status_code == 401, path


def test_money_and_role_management_never_meet_in_a_builtin_role():
    for role in rbac.BUILTIN_ROLES:
        if "roles.manage" in role.permissions:
            assert not role.permissions & rbac.MONEY, role.slug
