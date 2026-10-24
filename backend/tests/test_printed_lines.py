"""Every line printed on a bill is kept (never the personal ones), and a question outside the fixed topics is answered
by quoting the line it is about. The model only picks line numbers; it is faked here."""

import pytest

from app.domain.bill_normalise import normalise
from app.services import llm
from tests.real import SOLAR_DOM_OCT_2026, reading, variant
from tests.test_conversation import bodies, new_user, run

PRINTED = [{"label": "STR CODE", "value": "1510097001"}, {"label": "Recorded MD", "value": "1.84 KW"},
           {"label": "Disc Date", "value": "03-11-2026"}, {"label": "FOC No2.", "value": "8712471494"}]


def test_every_printed_line_is_kept_but_never_a_personal_one():
    raw = normalise({"printed": [*PRINTED, {"label": "Name", "value": "T C"}, {"label": "Addr", "value": "13-1"},
                                 {"label": "Mobile No", "value": "8xxxxxxxxx"}, {"label": "Email ID", "value": ""},
                                 {"label": "STR CODE", "value": "1510097001"}, {"label": "  ", "value": "x"}, "junk"]})
    assert raw["printed"] == PRINTED  # personal lines, a repeat, an empty label and a stray value are all gone


def test_a_bill_without_printed_lines_still_reads():
    assert normalise({"units": 138})["printed"] == []


@pytest.fixture
def picker(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, list[str]]]:
    asked: list[tuple[str, list[str]]] = []
    answer: dict[str, list[int] | None] = {"picked": [1]}

    async def fake(question: str, lines: list[str]) -> list[int] | None:
        asked.append((question, lines))
        return answer["picked"]

    monkeypatch.setattr(llm, "pick_lines", fake)
    asked.append(("__answer__", answer))  # type: ignore[arg-type]
    return asked


def test_a_named_term_the_reader_kept_only_as_a_line_quotes_that_line(reader):
    user = new_user()
    reader(reading(variant(SOLAR_DOM_OCT_2026, printed=PRINTED)))
    run(user, kind="image")
    said = bodies(run(user, kind="text", text="what is MD on my bill?"))
    assert "1.84 KW" in said and "not printed" not in said


def test_a_question_about_any_line_is_answered_by_quoting_it(reader, picker):
    user = new_user()
    reader(reading(variant(SOLAR_DOM_OCT_2026, printed=PRINTED)))
    run(user, kind="image")
    said = bodies(run(user, kind="text", text="tell me the figure printed near the bottom of the slip"))
    assert "Recorded MD: 1.84 KW" in said and "On your bill" in said  # the fake picks line 2
    question, lines = picker[1]
    assert "STR CODE: 1510097001" in lines and not any("Name" in line for line in lines)


def test_no_matching_line_keeps_the_usual_reply(reader, picker):
    user = new_user()
    reader(reading(variant(SOLAR_DOM_OCT_2026, printed=PRINTED)))
    run(user, kind="image")
    picker[0][1]["picked"] = []  # type: ignore[index]
    said = bodies(run(user, kind="text", text="what is the capital of France?"))
    assert "On your bill" not in said and said.strip()


def test_a_term_without_a_field_quotes_its_printed_line(reader):
    user = new_user()
    reader(reading(variant(SOLAR_DOM_OCT_2026, printed=PRINTED)))
    run(user, kind="image")
    said = bodies(run(user, kind="text", text="what is my str code"))
    assert "STR CODE: 1510097001" in said


def test_figures_the_checks_cover_and_the_personal_block_never_reach_the_printed_list():
    from app.domain.bill_normalise import printed_lines

    raw = [{"label": "ERO:", "value": "SITHAPHALMANDI(010)"}, {"label": "Consumer Details:", "value": ""},
           {"label": "SRIN", "value": ""}, {"label": "T CHI", "value": "13-1-2"}, {"label": "STR CODE:", "value": "1614"},
           {"label": "Present", "value": "17/08/26 01 57169"}, {"label": "Export Read :", "value": "40210 40355"},
           {"label": "Import:", "value": "160.0"}, {"label": "Units:", "value": "23"},
           {"label": "Energy Charges", "value": "44.85"}, {"label": "Total Due", "value": "220.00"},
           {"label": "Recorded MD", "value": "2.00 KW"}, {"label": "Disc Date", "value": "14-09-2026"}]
    kept = [line["label"] for line in printed_lines(raw)]
    assert kept == ["ERO:", "STR CODE:", "Recorded MD", "Disc Date"]


def test_the_line_copy_is_attached_to_the_final_bill(monkeypatch):
    import asyncio

    from app.domain.bill import PrintedLine
    from app.services import vision
    from tests.real import OCT_2025

    async def read(_jpeg, _seen):
        return OCT_2025

    async def lines(_jpeg):
        return [PrintedLine(label="STR CODE", value="1510097001")]

    monkeypatch.setattr(vision, "_read_twice", read)
    monkeypatch.setattr(vision, "transcribe", lines)
    monkeypatch.setattr(vision, "_first_document", lambda images: _first(images))
    reading_ = asyncio.run(vision.read_document(_jpeg_bytes(), "image/jpeg"))
    assert reading_.bill is not None and [p.label for p in reading_.bill.printed] == ["STR CODE"]


async def _first(images):
    from app.services import vision

    return images[0], vision.Classification(document_type="electricity_bill", discom="TGSPDCL")


def _jpeg_bytes() -> bytes:
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (400, 800), "white").save(out, format="JPEG")
    return out.getvalue()
