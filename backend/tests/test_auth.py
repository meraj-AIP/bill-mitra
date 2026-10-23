"""Sessions, roles and account management, exercised through the real cookie flow."""

from fastapi.testclient import TestClient

from app.main import app
from app.store import accounts

SECRET = "auth-test-passphrase"
WRONG = "Login or password is wrong."
FIXTURE_PASSWORD = "test-only-passphrase"  # what the sign_in fixture in conftest uses


def _login(client: TestClient, login: str, password: str = SECRET) -> int:
    return client.post("/api/auth/login", json={"login": login, "password": password}).status_code


def test_login_sets_an_httponly_session_cookie():
    account = accounts.create("officer", "cookie-officer@example.com", "Cookie Officer", SECRET, "TGSPDCL")
    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={"login": " Cookie-Officer@example.com ", "password": SECRET})
        assert response.status_code == 200 and response.json()["id"] == account.id
        cookie = response.headers["set-cookie"].lower()
        assert cookie.startswith("bm_session=") and "httponly" in cookie and "samesite=lax" in cookie
        assert "password" not in response.json()
        assert client.get("/api/auth/me").json()["role"] == "officer"
        assert client.post("/api/auth/logout").status_code == 204
        assert client.get("/api/auth/me").status_code == 401


def test_wrong_password_and_unknown_login_get_the_same_answer():
    accounts.create("officer", "wrong-pass@example.com", "Wrong Pass", SECRET)
    with TestClient(app) as client:
        for login in ("wrong-pass@example.com", "nobody@example.com"):
            response = client.post("/api/auth/login", json={"login": login, "password": "not-the-password"})
            detail = response.json()["detail"]
            assert response.status_code == 401 and (detail["code"], detail["message"]) == ("not_signed_in", WRONG)


def test_five_failures_lock_the_login():
    accounts.create("officer", "lockout@example.com", "Lock Out", SECRET)
    with TestClient(app) as client:
        assert [_login(client, "lockout@example.com", "not-the-password") for _ in range(5)] == [401] * 5
        assert _login(client, "lockout@example.com") == 401


def test_consumer_cannot_reach_staff_routes(sign_in):
    with TestClient(app) as client:
        sign_in(client)
        assert client.get("/api/admin/accounts").status_code == 403
        assert client.get("/api/console/summary").status_code == 403


def test_signed_out_calls_get_401():
    with TestClient(app) as client:
        assert client.get("/api/bills").status_code == 401
        assert client.get("/api/media/anything").status_code == 401
        assert client.post("/api/web/reset").status_code == 401
        assert client.get("/api/health").status_code == 200


def test_admin_cannot_deactivate_or_demote_self(sign_in):
    with TestClient(app) as client:
        admin = sign_in(client, "admin")
        assert client.patch(f"/api/admin/accounts/{admin.id}", json={"active": False}).status_code == 400
        assert client.patch(f"/api/admin/accounts/{admin.id}", json={"role": "officer"}).status_code == 400
        assert client.patch(f"/api/admin/accounts/{admin.id}", json={"name": "Renamed"}).json()["name"] == "Renamed"


def test_admin_manages_staff_and_every_write_is_audited(sign_in):
    with TestClient(app) as admin_client, TestClient(app) as officer_client:
        admin = sign_in(admin_client, "admin")
        new = {"role": "officer", "login": "managed@example.com", "name": "Managed", "discom": "TGNPDCL",
               "password": SECRET}
        officer = admin_client.post("/api/admin/accounts", json=new).json()
        assert officer["discom"] == "TGNPDCL" and officer["active"]
        assert admin_client.post("/api/admin/accounts", json=new).status_code == 409
        page = admin_client.get("/api/admin/accounts?role=officer&q=managed&page_size=5").json()
        assert page["total"] == 1 and page["items"][0]["id"] == officer["id"]
        assert admin_client.get("/api/admin/accounts?q=%25").json()["total"] == 0  # % is literal, not a wildcard

        assert _login(officer_client, "managed@example.com") == 200
        patched = admin_client.patch(f"/api/admin/accounts/{officer['id']}", json={"active": False})
        assert patched.json()["active"] is False
        assert officer_client.get("/api/auth/me").status_code == 401  # deactivation ended the session
        assert _login(officer_client, "managed@example.com") == 401

        admin_client.patch(f"/api/admin/accounts/{officer['id']}", json={"active": True, "discom": None})
        reset = admin_client.post(f"/api/admin/accounts/{officer['id']}/reset-password",
                                  json={"password": "a-new-test-passphrase"})
        assert reset.status_code == 204 and _login(officer_client, "managed@example.com") == 401
        assert _login(officer_client, "managed@example.com", "a-new-test-passphrase") == 200

        audit = admin_client.get("/api/admin/audit?page_size=50").json()["items"]
        mine = [(e["action"], e["target"]) for e in audit if e["actor_id"] == admin.id]
        assert ("account.create", officer["id"]) in mine and ("account.reset_password", officer["id"]) in mine
        assert all(e["actor_name"] for e in audit if e["actor_id"] == admin.id)
        assert all(SECRET not in (e["detail"] or "") for e in audit)


def test_password_change_ends_other_sessions(sign_in):
    with TestClient(app) as phone, TestClient(app) as laptop:
        account = sign_in(phone)
        assert _login(laptop, account.login, FIXTURE_PASSWORD) == 200
        wrong = phone.post("/api/auth/password", json={"current_password": "nope", "new_password": SECRET})
        assert wrong.status_code == 400
        changed = phone.post("/api/auth/password",
                             json={"current_password": FIXTURE_PASSWORD, "new_password": SECRET})
        assert changed.status_code == 204
        assert phone.get("/api/auth/me").status_code == 200
        assert laptop.get("/api/auth/me").status_code == 401


def test_audit_log_names_the_target_account(sign_in):
    with TestClient(app) as client:
        admin = sign_in(client, role="admin")
        items = client.get("/api/admin/audit?page=1&page_size=10").json()["items"]
    own_login = next(i for i in items if i["action"] == "auth.login" and i["target"] == admin.id)
    assert own_login["target_label"] == admin.name
