"""Bill by service number. The DISCOM connector and the code sender are stubbed at their boundary; the codes, the
rate limits, the checks and the engine run for real. Service numbers and mobiles are obviously synthetic."""

import asyncio
import secrets
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core import service
from app.core.messages import Inbound
from app.core.trace import Event
from app.flows import usc
from app.main import app
from app.services import discom_bills, notify
from app.store import db, repos
from tests.real import OCT_2025

REGISTERED = "9999999002"


def fake_usc() -> str:
    return "99" + str(secrets.randbelow(10**10)).zfill(10)


def stored_bill(number: str) -> None:
    """Somebody uploaded this connection's bill earlier: what the development server serves."""
    repos.save_bill(f"web:{secrets.token_hex(6)}", OCT_2025.model_copy(update={"service_number": number}), None,
                    "verified", 0.0)


@pytest.fixture
def dev_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "ownership_check", False)


@pytest.fixture
def discom(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """A connected DISCOM that knows one service number, and a code sender that records what it sent."""
    settings = get_settings()
    monkeypatch.setattr(settings, "discom_bills_url", "https://discom.example.invalid")
    monkeypatch.setattr(settings, "discom_bills_token", "test-token-not-real")
    known: dict[str, list[str]] = {"numbers": [], "codes": []}

    async def mobile(_discom: str, number: str) -> str | None:
        return REGISTERED if number in known["numbers"] else None

    async def bill(_discom: str, number: str) -> discom_bills.FetchedBill | None:
        if number not in known["numbers"]:
            return None
        return discom_bills.FetchedBill(OCT_2025.model_copy(update={"service_number": number}), None)

    async def send_code(to: str, code: str, _language: str) -> bool:
        assert to == REGISTERED
        known["codes"].append(code)
        return True

    monkeypatch.setattr(discom_bills, "registered_mobile", mobile)
    monkeypatch.setattr(discom_bills, "fetch_bill", bill)
    monkeypatch.setattr(notify, "can_send_code", lambda: True)
    monkeypatch.setattr(notify, "send_code", send_code)
    return known


def run(user: str, channel: str, sender: str | None = None, **fields: object) -> str:
    events: list[Event] = []

    async def emit(event: Event) -> None:
        events.append(event)

    inbound = Inbound(channel=channel, user_id=user, reply_to=sender, **fields)  # type: ignore[arg-type]
    asyncio.run(service.handle(inbound, emit, language="en"))
    return "\n".join(getattr(e.message, "body", "") or "" for e in events if e.kind == "message")


def test_development_serves_the_stored_bill_and_audits_masked_only(sign_in, dev_mode):
    number = fake_usc()
    stored_bill(number)
    with TestClient(app) as client:
        account = sign_in(client, "consumer")
        started = client.post("/api/bills/by-usc/start", json={"discom": "TGSPDCL", "service_number": number})
        assert started.status_code == 202 and started.json()["code_required"] is False
        got = client.post("/api/bills/by-usc/verify", json={"discom": "TGSPDCL", "service_number": number})
        assert got.status_code == 200, got.text
        report = got.json()
        assert report["outcome"] == "checked" and report["analysis"]["audit"]["status"]
        assert number not in got.text and report["bill"]["service_masked"].endswith(number[-4:])
    conn = db.connection()
    assert conn.execute("SELECT source FROM bills WHERE id = ?", (report["id"],)).fetchone()[0] == "discom"
    assert repos.get_own_bill(account.user_id, report["id"]) is not None
    details = [r[0] for r in conn.execute("SELECT detail FROM audit_log WHERE action LIKE 'usc.%'")]
    assert details and all(number not in d for d in details)


def test_nothing_configured_says_unavailable(sign_in):
    with TestClient(app) as client:
        sign_in(client, "consumer")
        got = client.post("/api/bills/by-usc/start", json={"discom": "TGSPDCL", "service_number": fake_usc()})
    assert got.status_code == 503 and got.json()["detail"]["code"] == "usc_unavailable"


def test_web_code_flow_wrong_expired_locked_and_unknown_look_alike(sign_in, discom, monkeypatch):
    known, unknown = fake_usc(), fake_usc()
    discom["numbers"].append(known)
    with TestClient(app) as client:
        sign_in(client, "consumer")

        def start(number: str):
            return client.post("/api/bills/by-usc/start", json={"discom": "TGSPDCL", "service_number": number})

        def verify(number: str, code: str):
            return client.post("/api/bills/by-usc/verify", json={"discom": "TGSPDCL", "service_number": number,
                                                                  "code": code})

        a, b = start(known), start(unknown)
        assert a.status_code == b.status_code == 202 and a.json() == b.json() and a.json()["code_required"]
        assert len(discom["codes"]) == 1
        code = discom["codes"][0]
        wrong = "000000" if code != "000000" else "111111"
        first, other = verify(known, wrong), verify(unknown, wrong)
        assert first.status_code == other.status_code == 400
        assert {**first.json()["detail"], "ref": None} == {**other.json()["detail"], "ref": None}  # alike but the ref
        assert first.json()["detail"]["attempts_left"] == 4
        later = usc._now() + timedelta(minutes=usc.CODE_MINUTES + 1)
        with monkeypatch.context() as m:
            m.setattr(usc, "_now", lambda: later)
            assert verify(known, code).status_code == 400  # expired
        start(known)
        fresh = discom["codes"][-1]
        assert verify(known, fresh).status_code == 200
        start(known)
        for _ in range(usc.MAX_ATTEMPTS - 1):
            assert verify(known, wrong).status_code == 400
        locked = verify(known, wrong)
        assert locked.status_code == 429
        assert verify(known, discom["codes"][-1]).status_code == 429  # even the right code, while locked


def test_rate_limit_per_service_number(sign_in, discom):
    number = fake_usc()
    with TestClient(app) as client:
        sign_in(client, "consumer")
        body = {"discom": "TGSPDCL", "service_number": number}
        statuses = [client.post("/api/bills/by-usc/start", json=body).status_code for _ in range(usc.STARTS_PER_USC + 1)]
    assert statuses == [202] * usc.STARTS_PER_USC + [429]


def test_whatsapp_ownership_mismatch_is_neutral_and_a_match_explains_the_bill(discom):
    number = fake_usc()
    discom["numbers"].append(number)
    for sender, expect in (("919999999001", "could not confirm this connection is yours"),
                           (f"91{REGISTERED}", "Your October 2025 bill")):
        user = f"wa:{secrets.token_hex(10)}"
        run(user, "whatsapp", sender, kind="text", text="get my bill")
        run(user, "whatsapp", sender, kind="button_reply", reply_id="udis:TGSPDCL")
        reply = run(user, "whatsapp", sender, kind="text", text=number)
        assert expect in reply and number not in reply
    unknown_reply = run(f"wa:{secrets.token_hex(10)}", "whatsapp", "919999999001", kind="text", text="get my bill")
    assert "pick your electricity company" in unknown_reply


def test_web_chat_sends_a_code_and_takes_it(discom):
    number = fake_usc()
    discom["numbers"].append(number)
    user = f"acct:{secrets.token_hex(8)}"
    run(user, "web", kind="text", text="get my bill")
    run(user, "web", kind="button_reply", reply_id="udis:TGSPDCL")
    assert "6 digit code" in run(user, "web", kind="text", text=number)
    assert "not right" in run(user, "web", kind="text", text="000001" if discom["codes"][-1] != "000001" else "000002")
    assert "Your October 2025 bill" in run(user, "web", kind="text", text=discom["codes"][-1])
