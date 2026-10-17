"""Staff alerts: who sees which alert, reading them, paging, and that consumers and strangers get nothing."""

import secrets

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store.alerts import raise_alert
from tests.review_kit import Tree, tree
from tests.test_review import _consumer, _staff


@pytest.fixture
def area() -> Tree:
    return tree()


def _key() -> str:
    return f"test:{secrets.token_hex(6)}"


def _ids(client: TestClient, **params: object) -> list[int]:
    return [a["id"] for a in client.get("/api/alerts", params={"page_size": 100, **params}).json()["items"]]


def _id_of(client: TestClient, title: str) -> int:
    return next(a["id"] for a in client.get("/api/alerts", params={"page_size": 100}).json()["items"]
                if a["title"] == title)


def test_dedupe_key_raises_once():
    key = _key()
    assert raise_alert("case_overdue", None, "Synthetic", "Synthetic body.", "cases.decide", key) is True
    assert raise_alert("case_overdue", None, "Synthetic", "Synthetic body.", "cases.decide", key) is False


def test_visibility_follows_scope_permission_and_addressee(sign_in, area):
    ae_a, ae_a_id = _staff(sign_in, "section_ae", area.section_a.id)
    ae_b, _ = _staff(sign_in, "section_ae", area.section_b.id)
    officer, _ = _staff(sign_in, "officer", area.division.id)
    tag = area.tag
    raise_alert("case_overdue", area.section_a.id, f"Section A decide {tag}", "Body.", "cases.decide", _key(),
                ticket="TSYNTH1")
    raise_alert("case_escalated", area.division.id, f"Division view {tag}", "Body.", "cases.view", _key())
    raise_alert("digest", None, f"Personal {tag}", "Body.", None, _key(), account_id=ae_a_id)

    def titles(client: TestClient) -> set[str]:
        items = client.get("/api/alerts", params={"page_size": 100}).json()["items"]
        return {a["title"] for a in items if a["title"].endswith(tag)}

    assert titles(ae_a) == {f"Section A decide {tag}", f"Personal {tag}"}
    assert titles(ae_b) == set()  # another section: nothing
    assert titles(officer) == {f"Division view {tag}"}  # covers section A but lacks cases.decide
    item = next(a for a in ae_a.get("/api/alerts").json()["items"] if a["title"] == f"Section A decide {tag}")
    assert item["unit_name"] == area.section_a.name and item["ticket"] == "TSYNTH1" and item["read"] is False


def test_consumers_get_403_and_signed_out_401(sign_in):
    consumer, _ = _consumer(sign_in)
    for method, path in (("get", "/api/alerts"), ("post", "/api/alerts/read-all"), ("post", "/api/alerts/1/read")):
        assert getattr(consumer, method)(path).status_code == 403
        assert getattr(TestClient(app), method)(path).status_code == 401


def test_read_one_read_all_and_unread_filter(sign_in, area):
    ae, _ = _staff(sign_in, "section_ae", area.section_a.id)
    other, _ = _staff(sign_in, "section_ae", area.section_b.id)
    for n in range(3):
        raise_alert("case_overdue", area.section_a.id, f"Read {n} {area.tag}", "Body.", "cases.decide", _key())
    first = _id_of(ae, f"Read 0 {area.tag}")
    before = ae.get("/api/alerts").json()["unread"]

    assert other.post(f"/api/alerts/{first}/read").status_code == 404  # not theirs to see
    assert ae.post("/api/alerts/999999999/read").status_code == 404
    assert ae.post(f"/api/alerts/{first}/read").status_code == 204
    assert ae.post(f"/api/alerts/{first}/read").status_code == 204  # reading twice is harmless
    after = ae.get("/api/alerts", params={"page_size": 100}).json()
    assert after["unread"] == before - 1
    assert next(a for a in after["items"] if a["id"] == first)["read"] is True
    assert first not in _ids(ae, unread=True)

    assert ae.post("/api/alerts/read-all").status_code == 204
    cleared = ae.get("/api/alerts", params={"unread": True}).json()
    assert cleared == {"items": [], "total": 0, "unread": 0}
    assert ae.get("/api/alerts").json()["total"] == 3


def test_paged_newest_first(sign_in, area):
    ae, _ = _staff(sign_in, "section_ae", area.section_a.id)
    for n in range(3):
        raise_alert("case_overdue", area.section_a.id, f"Page {n}", "Body.", "cases.decide", _key())
    page_one = ae.get("/api/alerts", params={"page": 1, "page_size": 2}).json()
    page_two = ae.get("/api/alerts", params={"page": 2, "page_size": 2}).json()
    assert page_one["total"] == 3 and [a["title"] for a in page_one["items"]] == ["Page 2", "Page 1"]
    assert [a["title"] for a in page_two["items"]] == ["Page 0"]
    assert ae.get("/api/alerts", params={"page_size": 101}).status_code == 422
