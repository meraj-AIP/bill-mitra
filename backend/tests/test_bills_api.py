"""Dashboard API: upload, report, list, and that one account never sees another's bills."""

import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from tests.real import MAR_2024, OCT_2025, reading, variant


def _jpeg() -> bytes:
    # Only the bytes' type matters here: the vision provider is scripted with a real bill's reading.
    out = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(out, "JPEG")
    return out.getvalue()


PHOTO = {"file": ("bill.jpg", _jpeg(), "image/jpeg")}


def test_real_bill_upload_returns_the_full_report(reader, sign_in):
    reader(reading(OCT_2025))
    with TestClient(app) as client:
        sign_in(client)
        body = client.post("/api/bills", files=PHOTO, data={"language": "en"}).json()
    assert body["outcome"] == "checked" and body["id"]
    assert body["bill"]["service_masked"] == "••••••••1111" and "service_number" not in body["bill"]
    assert body["capture"]["trusted"] and body["capture"]["captured"] == 17
    analysis = body["analysis"]
    assert analysis["audit"]["status"] == "verified" and analysis["energy"] == 518.2
    assert [(s["units"], s["rate"]) for s in analysis["slab_lines"]] == [[103, 3.4], [35, 4.8]] or \
        [(s["units"], s["rate"]) for s in analysis["slab_lines"]] == [(103, 3.4), (35, 4.8)]
    assert analysis["history"][-1]["source"] == "this_bill"
    assert analysis["explanation"] and all("*" not in line for line in analysis["explanation"])
    assert body["media_url"].startswith("/api/media/")


def test_bills_belong_to_one_account(reader, sign_in):
    reader(reading(MAR_2024))
    with TestClient(app) as owner, TestClient(app) as other:
        sign_in(owner)
        sign_in(other)
        bill_id = owner.post("/api/bills", files=PHOTO).json()["id"]
        assert owner.get(f"/api/bills/{bill_id}").status_code == 200
        assert other.get(f"/api/bills/{bill_id}").status_code == 404
        assert other.get("/api/bills").json()["total"] == 0


def test_same_month_uploaded_twice_is_kept_once(reader, sign_in):
    reader(reading(OCT_2025))
    with TestClient(app) as client:
        sign_in(client)
        client.post("/api/bills", files=PHOTO)
        client.post("/api/bills", files=PHOTO)
        assert client.get("/api/bills").json()["total"] == 1


def test_list_filters_and_paginates(reader, sign_in):
    with TestClient(app) as client:
        sign_in(client)
        reader(reading(OCT_2025))
        client.post("/api/bills", files=PHOTO)
        reader(reading(variant(MAR_2024, charge=("energy", 140.0))))  # real bill, energy printed Rs 140 higher
        client.post("/api/bills", files=PHOTO)
        mismatch = client.get("/api/bills?audit_status=mismatch").json()
        assert mismatch["total"] == 1 and mismatch["items"][0]["overcharge"] == 140.0
        page = client.get("/api/bills?page=2&page_size=5").json()
        assert page["page"] == 2 and page["items"] == []


def test_not_a_bill_is_explained_and_not_stored(reader, sign_in):
    reader(reading(None, kind="other", reason="A photo of logos."))
    with TestClient(app) as client:
        sign_in(client)
        body = client.post("/api/bills", files=PHOTO).json()
        assert body["outcome"] == "not_a_bill" and body["id"] is None and "logos" in body["outcome_reason"]
        assert client.get("/api/bills").json()["total"] == 0


def test_retake_says_why(reader, sign_in):
    reader(reading(variant(OCT_2025, bill_amount=792.0)))
    with TestClient(app) as client:
        sign_in(client)
        body = client.post("/api/bills", files=PHOTO).json()
    assert body["outcome"] == "retake" and "do not add up" in body["outcome_reason"] and body["analysis"] is None


def test_upload_rules(sign_in):
    with TestClient(app) as client:
        assert client.post("/api/bills", files=PHOTO).status_code == 401
        sign_in(client)
        assert client.post("/api/bills", files={"file": ("a.txt", b"x", "text/plain")}).status_code == 415
        assert client.post("/api/bills").status_code == 422
        assert client.post("/api/bills", files=PHOTO).json()["outcome"] == "reading_off"
