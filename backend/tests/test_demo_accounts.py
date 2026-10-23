"""Sample logins for demos: off by default, one per role when switched on, and the password never leaves the server."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import auth
from app.config import get_settings
from app.domain import rbac
from app.store import accounts, demo_accounts
from app.store.db import tx

api = FastAPI()
api.include_router(auth.router)
DEMO_PASSWORD = "not-a-real-password-1"


def test_off_when_unset_lists_nothing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(get_settings(), "demo_accounts_password", "")
    assert TestClient(api).get("/api/auth/demo-accounts").json() == []


def test_one_login_per_role_and_each_signs_in(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(get_settings(), "demo_accounts_password", DEMO_PASSWORD)
    monkeypatch.setattr(get_settings(), "demo_otp_mobile", "6000000002")  # synthetic; the consumer comes from settings
    monkeypatch.setattr(get_settings(), "demo_otp_code", "123456")
    demo_accounts.ensure()
    demo_accounts.ensure()  # a restart keeps the same accounts, it never makes duplicates
    listed = TestClient(api).get("/api/auth/demo-accounts").json()
    assert {row["role"] for row in listed} == {role.slug for role in rbac.BUILTIN_ROLES}
    assert all(set(row) == {"role", "role_name", "login"} for row in listed)
    assert {row["login"] for row in listed if row["role"] == "consumer"} == {"6000000002"}
    assert DEMO_PASSWORD not in TestClient(api).get("/api/auth/demo-accounts").text
    for row in listed:
        response = TestClient(api).post("/api/auth/login", json={"login": row["login"], "password": DEMO_PASSWORD})
        assert response.status_code == 200 and response.json()["role"] == row["role"]


def test_a_real_account_with_a_demo_login_is_never_reset(monkeypatch: pytest.MonkeyPatch):
    login = "demo.auditor@aiplanet.com"
    with tx() as conn:
        conn.execute("DELETE FROM accounts WHERE login = ?", (login,))
    real = accounts.create("officer", login, "Real Person", "a-real-password-9")
    monkeypatch.setattr(get_settings(), "demo_accounts_password", DEMO_PASSWORD)
    demo_accounts.ensure()
    assert accounts.get(real.id).role == "officer"
    assert accounts.authenticate(login, "a-real-password-9") is not None
    assert accounts.authenticate(login, DEMO_PASSWORD) is None
