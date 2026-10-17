"""The unit picker opens on a list for every account: the DISCOMs for a global admin, the top of their own area for
a scoped one, and their sections when the picker asks for sections only."""

from fastapi.testclient import TestClient

from app.main import app
from app.store.units import DISCOM_UNITS
from tests.review_kit import tree


def opened(sign_in, role: str, scopes: list[str] | None, kind: str | None = None) -> list[dict]:
    client = TestClient(app)
    sign_in(client, role, scopes=scopes)
    response = client.get("/api/admin/units", params={"kind": kind} if kind else {})
    assert response.status_code == 200, response.text
    return response.json()


def test_global_admin_opens_on_the_discoms(sign_in):
    tree()
    assert {u["kind"] for u in opened(sign_in, "admin", None)} == {"discom"}


def test_a_division_admin_opens_on_their_division_not_an_empty_list(sign_in):
    area = tree()
    units = opened(sign_in, "admin", [area.division.id])
    assert units and units[0]["id"] == area.division.id
    assert {u["id"] for u in units} >= {area.division.id, area.section_a.id}


def test_section_pickers_list_sections_in_scope(sign_in):
    area = tree()
    ae = opened(sign_in, "section_ae", [area.section_a.id], kind="section")
    assert [u["id"] for u in ae] == [area.section_a.id]
    desk = opened(sign_in, "call_centre", [DISCOM_UNITS["TGSPDCL"]], kind="section")
    assert area.section_a.id in {u["id"] for u in desk} and all(u["kind"] == "section" for u in desk)
