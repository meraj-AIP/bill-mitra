"""Vision helpers and the read, classify, re-read sequence. The provider calls are scripted; nothing leaves."""

import asyncio
import io

import pytest
from PIL import Image

from app.services import vision
from tests.real import MAR_2024, OCT_2025, reading, variant


def _jpeg(width: int, height: int) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, "JPEG")
    return out.getvalue()


def test_tall_slip_is_split_into_overlapping_crops():
    parts = [Image.open(io.BytesIO(p)) for p in vision.crops(_jpeg(600, 2400))]
    assert len(parts) == 3 and all(p.width == 600 for p in parts)
    assert sum(p.height for p in parts) > 2400  # overlap, so no row is cut in half at a seam


def test_normal_page_is_not_split():
    assert len(vision.crops(_jpeg(1200, 1600))) == 1


def test_clean_keeps_good_rows_and_drops_broken_ones():
    raw = vision._clean({"bill_month": "Oct-25", "arrears": None, "line_items": [
        {"code": "energy", "label": "Energy Charges", "amount": 518.2}, {"code": "rebate", "amount": -2.0},
        {"code": "fixed", "label": "Fixed", "amount": "fifty"}],
        "usage_history": [{"month": "2025-09", "units": 140}, {"month": "Sep", "units": 1}]})
    assert raw["bill_month"] is None and raw["arrears"] == 0
    assert [(i["code"], i["amount"]) for i in raw["line_items"]] == [("energy", 518.2), ("other", -2.0)]
    assert raw["usage_history"] == [{"month": "2025-09", "units": 140}]


def _script(monkeypatch: pytest.MonkeyPatch, seen: vision.Classification, *bills) -> list:
    calls: list = []

    async def classify(_jpeg: bytes) -> vision.Classification:
        return seen

    async def extract(_jpeg: bytes, _seen, failed_check=None, suspects=None, doubts=None):
        calls.append(failed_check)
        return bills[len(calls) - 1]

    monkeypatch.setattr(vision, "classify", classify)
    monkeypatch.setattr(vision, "extract", extract)
    return calls


def _read() -> vision.Reading:
    return asyncio.run(vision.read_document(_jpeg(600, 2400), "image/jpeg"))


def test_not_a_bill_is_never_read_in_detail(monkeypatch):
    calls = _script(monkeypatch, reading(None, kind="other").classification)
    assert _read().bill is None and calls == []


def test_failed_check_triggers_one_reread_naming_the_check_not_the_numbers(monkeypatch):
    shifted = variant(MAR_2024, line_items=[{**i.model_dump(), "amount": 9.42} if i.code == "customer"
                                            else i.model_dump() for i in MAR_2024.line_items])
    calls = _script(monkeypatch, reading(None).classification, shifted, MAR_2024)
    result = _read()
    assert result.bill == MAR_2024 and result.reread == "Charges add up to the bill amount"
    assert calls == [None, "Charges add up to the bill amount"]


def test_reread_that_still_fails_does_not_replace_the_first(monkeypatch):
    bad = variant(OCT_2025, bill_amount=600.0)
    _script(monkeypatch, reading(None).classification, bad, variant(OCT_2025, bill_amount=650.0))
    assert _read().bill == bad


@pytest.mark.parametrize(("data", "mime"), [(b"not an image", "image/jpeg"), (b"not a pdf", "application/pdf")])
def test_broken_file_is_refused_not_crashed(data, mime):
    result = asyncio.run(vision.read_document(data, mime))
    assert result.bill is None and result.classification.quality == "unreadable"


def _pdf(page_count: int) -> bytes:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument.new()
    for _ in range(page_count):
        pdf.new_page(200, 800)
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()


def test_multi_page_pdf_reads_the_page_that_is_a_bill(monkeypatch):
    kinds = iter(["other", "electricity_bill"])

    async def classify(_jpeg: bytes) -> vision.Classification:
        return reading(None, kind=next(kinds)).classification

    async def extract(_jpeg: bytes, seen, failed_check=None):
        return OCT_2025

    monkeypatch.setattr(vision, "classify", classify)
    monkeypatch.setattr(vision, "extract", extract)
    result = asyncio.run(vision.read_document(_pdf(5), "application/pdf"))
    assert result.classification.document_type == "electricity_bill" and result.bill == OCT_2025
    assert len(vision.pages(_pdf(5), "application/pdf")) == vision.MAX_PDF_PAGES


def test_heic_photos_open():
    out = io.BytesIO()
    Image.new("RGB", (300, 900), "white").save(out, format="HEIF")
    assert len(vision.pages(out.getvalue(), "image/heic")) == 1
