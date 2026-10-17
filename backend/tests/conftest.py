import itertools
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_TMP = tempfile.mkdtemp(prefix="billmitra-test-")
os.environ["DATA_DIR"] = _TMP
for key in ("OPENAI_API_KEY", "SARVAM_API_KEY", "SONIOX_API_KEY", "WHATSAPP_TOKEN"):
    os.environ[key] = ""
os.environ["AUTOMATION_ENABLED"] = "false"  # tests call the jobs directly with a fixed clock
os.environ["QUEUE_RETRY_ENABLED"] = "false"  # the same for the queue recovery jobs

from app.config import get_settings  # noqa: E402  (settings must see the environment above)
from app.services import llm, vision  # noqa: E402
from app.store import accounts  # noqa: E402

PASSWORD = "test-only-passphrase"
_ids = itertools.count(1)


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return Path(_TMP)


@pytest.fixture
def reader(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Turn bill reading on and make the vision provider return what a test scripts. The language model is kept
    off so explanations come from the checked templates and nothing leaves the machine."""
    monkeypatch.setattr(get_settings(), "openai_api_key", "test-key-not-real")

    async def no_model(*_: object, **__: object) -> None:
        return None

    monkeypatch.setattr(llm, "explain", no_model)
    monkeypatch.setattr(llm, "classify", no_model)
    monkeypatch.setattr(llm, "word_reply", no_model)

    def script(*readings: vision.Reading | Exception) -> None:
        queue = list(readings)

        async def fake(_data: bytes, _mime: str) -> vision.Reading:
            item = queue.pop(0) if len(queue) > 1 else queue[0]
            if isinstance(item, Exception):
                raise item
            return item

        monkeypatch.setattr(vision, "read_document", fake)

    return script


@pytest.fixture
def sign_in() -> Callable[..., accounts.Account]:
    """Create an account with an obviously fake login and sign the client in through the real login route,
    so every protected call in a test rides on the session cookie."""

    def go(client: TestClient, role: str = "consumer", discom: str | None = None,
           scopes: list[str] | None = None) -> accounts.Account:
        """`role` is any role slug. Staff get `scopes` (unit ids) when given, else the DISCOM rule: one, or both."""
        n = next(_ids)
        login = f"99999{n:05d}" if role == "consumer" else f"{role}{n}@example.com"
        account = accounts.create(role, login, f"Test {role} {n}", PASSWORD, discom, scopes=scopes)
        response = client.post("/api/auth/login", json={"login": login, "password": PASSWORD})
        assert response.status_code == 200, response.text
        return account

    return go


@pytest.fixture
def account_manager() -> str:
    """A custom role that manages staff accounts but not roles, the narrow admin a DISCOM may set up for a circle."""
    from app.store import roles

    slug = "test_account_manager"
    if roles.get(slug) is None:
        roles.create("Test account manager", "Manages staff accounts only.",
                     ["accounts.manage", "console.view", "complaints.view", "audit.view"])
    return slug


@pytest.fixture(autouse=True)
def fresh_rate_limits() -> None:
    """Each test starts with empty request counters, so limits never leak between tests."""
    from app.core import ratelimit
    from app.store import console

    ratelimit._hits.clear()
    console.forget_cached()  # a test reads the counts it just changed, so no minute-old cached summary


@pytest.fixture(autouse=True)
def retry_waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Retries never really sleep in tests: each wait moves a fake clock instead, so budgets still bind. Returns the
    waits asked for, in order."""
    from app.core import retry
    from app.store import db

    waits: list[float] = []
    now = [0.0]

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(retry, "sleep", fake_sleep)
    monkeypatch.setattr(retry, "clock", lambda: now[0])
    monkeypatch.setattr(db, "_sleep", lambda seconds: waits.append(seconds))
    return waits
