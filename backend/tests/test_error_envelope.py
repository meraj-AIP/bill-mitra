"""One error shape on every API failure, a reference that ties what the person sees to the log, no Python error text
to a client, refusals in the asker's language, and WhatsApp promises kept (docs/errors-contract.md sections 1 and 2).
"""

import asyncio
import logging
import secrets

from fastapi.testclient import TestClient

from app.core.errors import Refusal, safe_message
from app.domain.conversation.lang import PACKS
from app.flows import recovery, usc
from app.main import app
from app.services.openai_client import ProviderError
from app.store import repos
from tests.real import OCT_2025, reading, variant
from tests.test_bills_api import PHOTO
from tests.test_queues import DOWN, later, parked_turn
from tests.test_usc import discom, fake_usc  # noqa: F401
from tests.test_usc import run as usc_run
from tests.whatsapp_kit import api, bodies, graph, image, number, say, text  # noqa: F401

SECRET = "secret detail 9999999999"


def envelope_of(response) -> dict:  # type: ignore[no-untyped-def]
    detail = response.json()["detail"]
    assert set(detail) >= {"code", "message", "ref"} and detail["ref"] == response.headers["X-Request-Id"]
    return dict(detail)


def test_a_4xx_has_the_envelope_and_the_reference_header(sign_in):
    with TestClient(app) as client:
        assert envelope_of(client.get("/api/bills"))["code"] == "not_signed_in"
        assert envelope_of(client.get("/api/no-such-route"))["code"] == "not_found"
        sign_in(client)
        missing = envelope_of(client.get("/api/bills/nope?language=hi"))
        assert missing == {**missing, "code": "bill_not_found", "message": PACKS["hi"].T["err_bill_not_found"]}
        assert client.get("/api/bills").headers["X-Request-Id"]  # every response, not only errors


def test_a_422_is_one_readable_sentence(sign_in):
    with TestClient(app) as client:
        sign_in(client)
        written = envelope_of(client.post("/api/bills/by-usc/start?language=en",
                                          json={"discom": "TGSPDCL", "service_number": "abc"}))
        assert written["code"] == "invalid" and written["message"] == "A service number is 5 to 16 digits."
        missing = envelope_of(client.post("/api/auth/login?language=te", json={}))
        assert missing["message"] == PACKS["te"].T["err_invalid"] and "body" not in str(missing)


def test_a_500_says_only_the_reference_and_logs_the_type_not_the_text(sign_in, monkeypatch, caplog):
    def broken(*_: object, **__: object) -> None:
        raise RuntimeError(SECRET)

    monkeypatch.setattr(repos, "list_bills", broken)
    with TestClient(app) as client, caplog.at_level(logging.INFO):
        sign_in(client)
        response = client.get("/api/bills")
    detail = envelope_of(response)
    assert response.status_code == 500 and detail["code"] == "server_error"
    assert detail["message"] == f"Something went wrong on our side. Reference {detail['ref']}."
    assert SECRET not in response.text and SECRET not in caplog.text
    assert f"ref={detail['ref']}: RuntimeError" in caplog.text


def test_only_a_refusal_written_for_people_reaches_a_client():
    assert safe_message(Refusal("Choose a section of the same DISCOM."), "fallback") == "Choose a section of the same DISCOM."
    assert safe_message(ValueError("invalid literal for int() with base 10: 'x'"), "fallback") == "fallback"


def test_a_rate_limit_says_what_was_limited(sign_in):
    with TestClient(app) as client:
        sign_in(client)
        codes = [client.post("/api/bills/nope/review-request?language=en", json={}) for _ in range(11)]
    assert [r.status_code for r in codes] == [404] * 10 + [429]
    assert envelope_of(codes[-1])["message"] == "Too many reports. Please wait a minute and try again."


def test_a_refusal_from_middleware_has_the_envelope_too():
    response = TestClient(app).post("/api/auth/login", json={}, headers={"Origin": "https://elsewhere.example"})
    assert response.status_code == 403 and envelope_of(response)["code"] == "cross_site"


def test_the_webhook_never_names_its_setup(api, monkeypatch):  # noqa: F811
    from app.config import get_settings
    from tests.whatsapp_kit import envelope, post

    monkeypatch.setattr(get_settings(), "whatsapp_app_secret", "")
    response = post(api, envelope(text(number(), "hi")), signature=None)
    assert response.status_code == 503 and "WHATSAPP" not in response.text and "secret" not in response.text.lower()


def test_usc_code_details_are_translated_and_carry_the_tries_left(sign_in, discom):  # noqa: F811
    known = fake_usc()
    discom["numbers"].append(known)
    with TestClient(app) as client:
        sign_in(client)
        client.post("/api/bills/by-usc/start", json={"discom": "TGSPDCL", "service_number": known})
        wrong = "000000" if discom["codes"][-1] != "000000" else "111111"
        refused = client.post("/api/bills/by-usc/verify?language=te",
                              json={"discom": "TGSPDCL", "service_number": known, "code": wrong})
    detail = envelope_of(refused)
    assert detail["attempts_left"] == 4 and detail["message"] == PACKS["te"].T["err_usc_wrong"].format(attempts_left=4)


def test_the_usc_prompts_can_be_left_without_spending_a_try(discom):  # noqa: F811
    known = fake_usc()
    discom["numbers"].append(known)
    user = f"acct:{secrets.token_hex(8)}"
    usc_run(user, "web", kind="button_reply", reply_id="udis:TGSPDCL")
    assert "6 digit code" in usc_run(user, "web", kind="text", text=known)
    asked = usc_run(user, "web", kind="text", text="why is my bill so high?")
    assert "send a photo of your bill first" in asked  # answered as a question, not as a wrong code
    assert usc.attempts_left(user, "TGSPDCL", known) == 5 and repos.get_user(user, "web").awaiting is None
    usc_run(user, "web", kind="button_reply", reply_id="udis:TGSPDCL")
    usc_run(user, "web", kind="text", text=known)
    wrong = "000000" if discom["codes"][-1] != "000000" else "111111"
    assert "You have 4 tries left" in usc_run(user, "web", kind="text", text=wrong)
    assert "I have stopped" in usc_run(user, "web", kind="button_reply", reply_id="usc_cancel")
    assert repos.get_user(user, "web").awaiting is None


def test_a_parked_whatsapp_turn_ends_with_one_neutral_next_step(api, graph, reader):  # noqa: F811
    reader(reading(OCT_2025))
    sender = number()
    say(api, graph, text(sender, "hi"))
    graph.media_down = 10**6
    say(api, graph, image(sender))
    for seconds in (61, 400, 1400, 2400, 5000):
        asyncio.run(recovery.retry_inbox(later(seconds)))
    assert parked_turn(sender) is not None
    assert bodies(graph.messages()).count(PACKS["te"].T["turn_gave_up"]) == 1


def test_a_deferred_read_that_fails_on_its_last_try_says_so_once(api, graph, reader):  # noqa: F811
    reader(DOWN, RuntimeError(SECRET))
    sender = number()
    say(api, graph, text(sender, "hi"))
    say(api, graph, image(sender))
    for seconds in (61, 61 + 301, 61 + 301 + 901, 61 + 301 + 901 + 2000):
        asyncio.run(recovery.run_extracts(later(seconds)))
    sent = bodies(graph.messages())
    assert sent.count(PACKS["te"].T["read_gave_up"]) == 1 and not any(SECRET in s for s in sent)


def test_a_queued_dashboard_read_always_ends_with_an_outcome(reader, sign_in):
    reader(DOWN, reading(variant(OCT_2025, bill_amount=792.0)))
    with TestClient(app) as client:
        sign_in(client)
        job = client.post("/api/bills", files=PHOTO, data={"language": "en"}).json()
        asyncio.run(recovery.run_extracts(later(61)))
        done = client.get(f"/api/bills/jobs/{job['job_id']}?language=en").json()
    assert (done["status"], done["bill_id"], done["outcome"], done["problem"]) == (
        "done", None, "retake", "chk_charges_sum")
    assert "a gap of Rs 100" in done["detail"]


def test_a_dashboard_read_that_gives_up_says_so_in_the_uploaders_language(reader, sign_in):
    reader(DOWN, ProviderError("HTTPStatusError", transient=True))
    with TestClient(app) as client:
        sign_in(client)
        job = client.post("/api/bills", files=PHOTO, data={"language": "hi"}).json()
        for seconds in (61, 61 + 301, 61 + 301 + 901):
            asyncio.run(recovery.run_extracts(later(seconds)))
        done = client.get(f"/api/bills/jobs/{job['job_id']}").json()
    assert (done["status"], done["outcome"]) == ("failed", "reading_failed")
    assert done["detail"] == PACKS["hi"].T["dash_read_failed"]
