"""Upload sniffing, rate limits, cross-site writes and security headers."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.uploads import sniff
from app.main import app


def _png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (4, 4)).save(out, "PNG")
    return out.getvalue()


@pytest.mark.parametrize(("head", "mime"), [
    (b"\xff\xd8\xff\xe0", "image/jpeg"), (b"%PDF-1.7", "application/pdf"), (b"RIFF\0\0\0\0WEBPVP8 ", "image/webp"),
    (b"\0\0\0\x18ftypheic", "image/heic"), (b"OggS\0", "audio/ogg"), (b"\x1a\x45\xdf\xa3", "audio/webm"),
    (b"MZ\x90\0", None), (b"<html>", None),
])
def test_sniff(head, mime):
    assert sniff(head) == mime


def test_upload_type_comes_from_the_bytes_not_the_label(sign_in):
    with TestClient(app) as client:
        sign_in(client)
        fake = client.post("/api/bills", files={"file": ("bill.jpg", b"MZ not an image", "image/jpeg")})
        assert fake.status_code == 415
        real_png = client.post("/api/web/upload", files={"file": ("x.bin", _png(), "application/octet-stream")})
        assert real_png.status_code == 200 and real_png.json()["mime_type"] == "image/png"


def test_login_is_rate_limited_per_address():
    with TestClient(app) as client:
        codes = [client.post("/api/auth/login", json={"login": "nobody@example.com", "password": "x" * 12}).status_code
                 for _ in range(21)]
    assert codes[:20] == [401] * 20 and codes[20] == 429


def test_cross_site_write_is_refused(sign_in):
    with TestClient(app) as client:
        sign_in(client)
        refused = client.post("/api/web/reset", headers={"Origin": "https://evil.example.com"})
        assert refused.status_code == 403
        assert client.post("/api/web/reset", headers={"Origin": "http://localhost:5173"}).status_code == 204


def test_security_headers():
    with TestClient(app) as client:
        headers = client.get("/api/health").headers
    assert headers["x-content-type-options"] == "nosniff" and "frame-ancestors 'self'" in headers["content-security-policy"]
