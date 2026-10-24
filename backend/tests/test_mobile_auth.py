"""Consumers sign up and sign in with their mobile and a one-time code. Sign up needs a number the DISCOM holds for a
connection. The DISCOM and the SMS gateway are faked at their HTTP boundary; numbers are synthetic (9999 prefix)."""

import secrets

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services import discom_bills, sms
from app.store import accounts, demo_accounts


def _mobile() -> str:
    return "99990" + f"{secrets.randbelow(10**5):05d}"


@pytest.fixture
def discom(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """A connected DISCOM: mobile to service numbers, per DISCOM key "TGSPDCL:<mobile>"."""
    settings = get_settings()
    monkeypatch.setattr(settings, "discom_bills_url", "https://discom.invalid/api")
    monkeypatch.setattr(settings, "discom_bills_token", "test-token-not-real")
    registry: dict[str, list[str]] = {}

    async def fake(path: str, which: str, what: str) -> dict[str, object] | None:
        mobile = path.split("/")[2]
        found = registry.get(f"{which}:{mobile}")
        return {"consumers": [{"service_number": n, "section": "Isnapur"} for n in found]} if found else None

    monkeypatch.setattr(discom_bills, "_request", fake)
    return registry


@pytest.fixture
def sms_sent(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """A connected SMS gateway that records what it would send, so codes are never shown on screen."""
    settings = get_settings()
    monkeypatch.setattr(settings, "sms_api_url", "https://sms.invalid/send")
    monkeypatch.setattr(settings, "sms_api_key", "test-key-not-real")
    sent: list[tuple[str, str]] = []

    async def fake(mobile: str, code: str) -> bool:
        sent.append((mobile, code))
        return True

    monkeypatch.setattr(sms, "send_code", fake)
    return sent


def _start(client: TestClient, mobile: str, purpose: str = "signup", channel: str = "sms", discom: str | None = "TGSPDCL"):
    body = {"mobile": mobile, "purpose": purpose, "channel": channel, **({"discom": discom} if discom else {})}
    return client.post("/api/auth/otp/start", json=body)


def _sign_up(client: TestClient, mobile: str, code: str):
    return client.post("/api/auth/otp/signup", json={"mobile": mobile, "code": code, "name": "Test Consumer",
                                                     "discom": "TGSPDCL", "consent": True})


def test_a_registered_number_signs_up_and_gets_its_connections(discom):
    mobile = _mobile()
    discom[f"TGSPDCL:{mobile}"] = ["99990000012345", "99990000067890"]
    with TestClient(app) as client:
        started = _start(client, mobile)
        assert started.status_code == 200, started.text
        sent = started.json()
        assert sent["connections"] == 2 and len(sent["dev_code"]) == 6 and sent["expires_in"] == 300
        made = _sign_up(client, mobile, sent["dev_code"])
        assert made.status_code == 200 and made.json()["role"] == "consumer" and made.json()["login"] == mobile
        assert client.get("/api/auth/me").json()["consent_version"] == get_settings().privacy_notice_version
        found = client.get("/api/auth/connections")
        assert [c["service_masked"][-4:] for c in found.json()] == ["2345", "7890"]
        assert "99990000012345" not in found.text
        assert _sign_up(client, mobile, sent["dev_code"]).status_code == 400  # a code works once


def test_a_number_the_discom_does_not_hold_cannot_sign_up(discom):
    mobile = _mobile()
    with TestClient(app) as client:
        refused = _start(client, mobile)
        assert refused.status_code == 404 and "not registered with TGSPDCL" in refused.json()["detail"]["message"]
        assert _start(client, mobile, discom=None).status_code == 422  # the DISCOM must be chosen
        assert client.get("/api/auth/me").status_code == 401


def test_wrong_codes_lock_the_number(discom):
    mobile = _mobile()
    discom[f"TGSPDCL:{mobile}"] = ["99990000011111"]
    with TestClient(app) as client:
        code = _start(client, mobile).json()["dev_code"]
        wrong = "000000" if code != "000000" else "111111"
        assert [_sign_up(client, mobile, wrong).status_code for _ in range(4)] == [400] * 4
        assert _sign_up(client, mobile, wrong).status_code == 429
        assert _sign_up(client, mobile, code).status_code == 429  # locked, even with the right code
        assert _start(client, mobile).status_code == 429


def test_sign_in_with_a_code_and_an_unknown_number_is_told_to_sign_up(discom, sms_sent):
    mobile = _mobile()
    discom[f"TGSPDCL:{mobile}"] = ["99990000022222"]
    with TestClient(app) as client:
        _start(client, mobile)
        account_id = _sign_up(client, mobile, sms_sent[-1][1]).json()["id"]
        client.post("/api/auth/logout")
        _start(client, mobile, purpose="login", discom=None)
        signed = client.post("/api/auth/otp/login", json={"mobile": mobile, "code": sms_sent[-1][1]})
        assert signed.status_code == 200 and signed.json()["id"] == account_id
        stranger = _mobile()
        _start(client, stranger, purpose="login", discom=None)
        assert client.post("/api/auth/otp/login", json={"mobile": stranger, "code": sms_sent[-1][1]}).status_code == 404


def test_signing_up_again_signs_in_to_the_same_account(discom, sms_sent):
    mobile = _mobile()
    discom[f"TGSPDCL:{mobile}"] = ["99990000033333"]
    with TestClient(app) as client:
        _start(client, mobile)
        first = _sign_up(client, mobile, sms_sent[-1][1]).json()["id"]
        _start(client, mobile)
        again = _sign_up(client, mobile, sms_sent[-1][1])
        assert again.status_code == 200 and again.json()["id"] == first


def test_an_on_screen_code_never_opens_a_real_account(discom, monkeypatch):
    mobile = _mobile()
    discom[f"TGSPDCL:{mobile}"] = ["99990000055555"]
    with TestClient(app) as client:
        assert _sign_up(client, mobile, _start(client, mobile).json()["dev_code"]).status_code == 200  # a new number may
        client.post("/api/auth/logout")
        for purpose in ("login", "signup"):
            refused = _start(client, mobile, purpose=purpose)
            assert refused.status_code == 403 and "dev_code" not in refused.text and "WhatsApp" in refused.json()["detail"]["message"]
        monkeypatch.setattr(get_settings(), "demo_accounts_password", "test-only-demo-passphrase")
        monkeypatch.setattr(get_settings(), "demo_otp_mobile", "6000000001")  # synthetic: the demo consumer comes from settings
        monkeypatch.setattr(get_settings(), "demo_otp_code", "123456")
        demo_accounts.ensure()
        sample = _start(client, "6000000001", purpose="login", discom=None)
        assert sample.status_code == 200 and sample.json()["dev_code"] == "123456"
        signed = client.post("/api/auth/otp/login", json={"mobile": "6000000001", "code": sample.json()["dev_code"]})
        assert signed.status_code == 200 and signed.json()["role"] == "consumer"


def test_a_connected_channel_sends_the_code_and_never_shows_it(discom, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "sms_api_url", "https://sms.invalid/send")
    monkeypatch.setattr(settings, "sms_api_key", "test-key-not-real")
    sent: list[tuple[str, str]] = []

    async def fake(mobile: str, code: str) -> bool:
        sent.append((mobile, code))
        return True

    monkeypatch.setattr(sms, "send_code", fake)
    mobile = _mobile()
    discom[f"TGSPDCL:{mobile}"] = ["99990000044444"]
    with TestClient(app) as client:
        assert client.get("/api/auth/otp/channels").json()["channels"] == ["sms"]
        started = _start(client, mobile)
        assert started.status_code == 200 and started.json()["dev_code"] is None
        assert sent and sent[0][0] == mobile
        assert _start(client, mobile, channel="whatsapp").status_code == 503  # WhatsApp is not connected here
        assert _sign_up(client, mobile, sent[-1][1]).status_code == 200


def test_production_without_a_channel_or_the_discom_refuses(monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "production")
    with TestClient(app) as client:
        assert client.get("/api/auth/otp/channels").json() == {"channels": [], "on_screen": False, "whatsapp_number": None}
        assert _start(client, _mobile()).status_code == 503


def test_old_password_sign_up_is_gone():
    with TestClient(app) as client:
        body = {"name": "Test", "mobile": _mobile(), "password": "test-only-passphrase", "consent": True}
        assert client.post("/api/auth/register", json=body).status_code in (404, 405)
    assert accounts.by_login(body["mobile"]) is None


def test_the_demo_number_takes_its_fixed_code_and_is_never_sent(sms_sent, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_otp_mobile", "9999012345")
    monkeypatch.setattr(settings, "demo_otp_code", "123456")
    with TestClient(app) as client:
        started = _start(client, "9999012345")
        assert started.status_code == 200 and started.json()["dev_code"] is None and sms_sent == []
        assert _sign_up(client, "9999012345", "123456").status_code == 200
        client.post("/api/auth/logout")
        _start(client, "9999012345", purpose="login", discom=None)
        assert client.post("/api/auth/otp/login", json={"mobile": "9999012345", "code": "123456"}).status_code == 200


def test_production_refuses_a_fixed_code():
    from app.config import Settings

    with pytest.raises(ValueError, match="DEMO_OTP_MOBILE"):
        Settings(app_env="production", hash_pepper="test-pepper-not-real", demo_otp_mobile="9999012345", demo_otp_code="123456")
    with pytest.raises(ValueError, match="together"):
        Settings(demo_otp_mobile="9999012345", demo_otp_code="")  # explicit, so a developer's .env cannot fill it
