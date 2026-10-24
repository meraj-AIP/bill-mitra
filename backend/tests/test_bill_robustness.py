"""Bill reading that survives real answers and real meters: odd number and date formats, one bad field, meters with a
multiplying factor or that rolled over, solar export registers, and two reads that each fall short.

Bills are the real fixtures in tests/real.py or labelled variants of them; nothing here calls a model.
"""

import asyncio

import pytest
from PIL import Image, ImageDraw

from app.domain import capture, second_read
from app.domain.bill_normalise import iso_date, normalise, number, to_bill
from app.domain.pricing import price
from app.domain.review import Policy, detect
from app.services import vision
from tests.real import MAR_2024, OCT_2025, SOLAR_DOM_AUG_2026, SOLAR_DOM_OCT_2026, SOLAR_SEP_2026, reading, variant


@pytest.mark.parametrize(("raw", "expected"), [
    ("Rs 1,234.50", 1234.5), ("37,186.00 CR", -37186.0), ("(-) 545.00", -545.0), ("(12.00)", -12.0),
    ("-545", -545.0), ("− 20", -20.0), ("699 /-", 699.0), ("3101 KVAH", 3101.0), (" 40 KW", 40.0),
    (12, 12.0), ("fifty", None), (True, None), (None, None), ("", None),
])
def test_numbers_in_the_forms_bills_print(raw, expected):
    assert number(raw) == expected


@pytest.mark.parametrize(("raw", "expected"), [
    ("2026-09-07", "2026-09-07"), ("07/09/26", "2026-09-07"), ("7-9-2026", "2026-09-07"), ("05.08.26", "2026-08-05"),
    ("31/02/26", None), ("Sept 7", None), (None, None),
])
def test_dates_in_the_forms_bills_print(raw, expected):
    assert iso_date(raw) == expected


def test_one_bad_field_never_loses_the_rest_of_the_bill():
    raw = {"discom": "TSSPDCL", "service_number": "9999 0000 1111", "category": "2B NON-DOMESTIC/COMM",
           "is_domestic": True, "bill_date": "07/09/26", "previous_reading_date": "not printed", "billing_days": 400,
           "units": "3,101", "present_status": "1", "power_factor": 99, "phase": "three",
           "line_items": [{"code": "energy", "label": "Energy Charges", "amount": "33,384.90"},
                          {"code": "energy", "label": "Energy  Charges", "amount": 33384.9},
                          {"code": "fixed", "label": "Fixed", "amount": "n/a"}],
           "usage_history": [{"month": "2026-08", "units": "3,050"}, {"month": "2026-08", "units": 1},
                             {"month": "2026-07", "units": 2990}],
           "bill_amount": "Rs 37,731.00", "arrears": "545.00 CR", "quality": "GOOD", "confidence": 95}
    bill = to_bill(raw)
    assert (bill.discom, bill.service_number, bill.is_domestic) == ("TGSPDCL", "999900001111", False)
    assert (bill.bill_date, bill.bill_month, bill.previous_reading_date, bill.billing_days) == (
        "2026-09-07", "2026-09", None, None)
    assert (bill.units, bill.present_status, bill.power_factor, bill.phase) == (3101, "01", 0.99, None)
    assert [(i.code, i.amount) for i in bill.line_items] == [("energy", 33384.9)]  # read twice from overlapping crops
    assert [(h.month, h.units) for h in bill.usage_history] == [("2026-07", 2990), ("2026-08", 3050)]
    assert (bill.bill_amount, bill.arrears, bill.quality, bill.confidence) == (37731.0, -545.0, "good", 0.95)
    assert {"previous_reading_date", "billing_days", "phase"} <= set(bill.unreadable_fields)


def test_the_printed_category_decides_domestic():
    assert normalise({"category": "1B(i) DOMESTIC", "is_domestic": False})["is_domestic"] is True
    assert normalise({"category": "LT-II(A)", "is_domestic": True})["is_domestic"] is False
    assert normalise({"category": "LT-I(B)", "is_domestic": False})["is_domestic"] is True
    assert normalise({"category": None, "is_domestic": False})["is_domestic"] is False


def test_a_meter_with_a_multiplying_factor_passes_the_readings_check():
    ct = variant(OCT_2025, previous_reading=1000.0, present_reading=1023.0, units=138, multiplying_factor=6.0)
    assert capture.failed_check(ct) is None
    assert capture.failed_check(variant(ct, multiplying_factor=1.0)) == "Present minus previous reading equals units"


def test_a_meter_that_rolled_over_is_not_a_reading_gone_back():
    rolled = variant(OCT_2025, previous_reading=99950.0, present_reading=88.0, units=138)
    assert capture.failed_check(rolled) is None
    assert "rolled over" in next(c.detail for c in capture.report(rolled).checks if c.key == "readings")
    spike = detect(rolled, price(rolled, rolled.net_units()), [], Policy(discom="TGSPDCL"))
    assert spike.reason != "reading_went_back"
    backwards = variant(OCT_2025, previous_reading=351.0, present_reading=213.0, units=138)
    assert detect(backwards, price(backwards, 138), [], Policy(discom="TGSPDCL")).reason == "reading_went_back"


def test_a_misread_solar_export_register_is_caught():
    good = variant(SOLAR_SEP_2026, export_previous_reading=120.0, export_present_reading=129.0)
    assert capture.failed_check(good) is None
    misread = variant(good, export_present_reading=139.0, billed_units=None)
    assert capture.failed_check(misread) == "Export meter readings equal the units exported"
    # With the net units confirmed, a misread export register alone does not block, like the import readings.
    assert capture.failed_check(variant(good, export_present_reading=139.0)) is None


def _with_customer(bill, amount: float):
    return variant(bill, line_items=[{**i.model_dump(), "amount": amount} if i.code == "customer" else i.model_dump()
                                     for i in bill.line_items])


def test_the_second_read_is_pointed_at_the_rows_that_look_wrong_by_name_only():
    shifted = _with_customer(MAR_2024, 9.42)
    assert second_read.suspect_rows(shifted) == ["Customer Charges"]
    assert second_read.suspect_rows(MAR_2024) == []


def test_two_reads_that_each_fall_short_are_settled_by_the_one_mix_that_adds_up():
    first = _with_customer(MAR_2024, 9.42)  # customer charge misread
    second = variant(MAR_2024, bill_amount=744.0, units=None)  # bill amount misread, units missed
    settled = second_read.reconcile(first, second)
    assert settled is not None and settled.item("customer") == MAR_2024.item("customer")
    assert settled.bill_amount == MAR_2024.bill_amount and settled.units == MAR_2024.units


def test_reads_are_not_settled_when_more_than_one_mix_adds_up_or_rows_do_not_line_up():
    first = variant(OCT_2025, unreadable_fields=["units"])
    assert second_read.reconcile(first, first) == first.model_copy(update={"unreadable_fields": ["units"]})
    swapped = variant(OCT_2025, line_items=[i.model_dump() for i in reversed(OCT_2025.line_items)])
    assert second_read.reconcile(_with_customer(OCT_2025, 9.0), swapped) is None
    far = variant(OCT_2025, units=1, bill_amount=1.0, total_payable=1.0, previous_reading=1.0, present_reading=2.0,
                  arrears=1.0)
    assert second_read.reconcile(OCT_2025, far) is None  # six disagreements: the photo is the problem


def test_a_flag_stays_only_when_both_reads_were_unsure():
    first = variant(OCT_2025, unreadable_fields=["units", "bill_amount"])
    second = variant(OCT_2025, unreadable_fields=["units"])
    settled = second_read.reconcile(first, second)
    assert settled is not None and settled.unreadable_fields == ["units"]
    assert second_read.reconcile(first, OCT_2025).unreadable_fields == []  # type: ignore[union-attr]


def _script(monkeypatch: pytest.MonkeyPatch, *bills) -> list[dict]:
    calls: list[dict] = []

    async def classify(_jpeg: bytes) -> vision.Classification:
        return reading(None).classification

    async def extract(_jpeg: bytes, _seen, failed_check=None, suspects=None, doubts=None):
        calls.append({"failed": failed_check, "suspects": suspects, "doubts": doubts})
        return bills[len(calls) - 1]

    monkeypatch.setattr(vision, "classify", classify)
    monkeypatch.setattr(vision, "extract", extract)
    return calls


def _read() -> vision.Reading:
    from tests.test_vision import _jpeg

    return asyncio.run(vision.read_document(_jpeg(600, 900), "image/jpeg"))


def test_a_read_unsure_of_key_figures_gets_a_second_look_and_both_agreeing_settles_it(monkeypatch):
    unsure = variant(OCT_2025, unreadable_fields=["units", "bill_amount"])
    calls = _script(monkeypatch, unsure, OCT_2025)
    result = _read()
    assert calls[1] == {"failed": None, "suspects": None, "doubts": ["units", "bill_amount"]}
    assert result.bill == OCT_2025 and capture.report(result.bill).trusted


def test_a_failed_check_names_the_suspect_rows_and_reconciles_when_neither_read_stands(monkeypatch):
    first = _with_customer(MAR_2024, 9.42)
    second = variant(MAR_2024, bill_amount=744.0)
    calls = _script(monkeypatch, first, second)
    result = _read()
    assert calls[1]["failed"] == "Charges add up to the bill amount" and calls[1]["suspects"] == ["Customer Charges"]
    assert result.reconciled and result.bill is not None and capture.failed_check(result.bill) is None
    assert result.bill.item("customer") == MAR_2024.item("customer") and result.bill.bill_amount == MAR_2024.bill_amount


def test_when_nothing_settles_the_first_read_is_kept_and_not_trusted(monkeypatch):
    first = _with_customer(MAR_2024, 9.42)
    _script(monkeypatch, first, _with_customer(MAR_2024, 8.42))
    result = _read()
    assert result.bill == first and not result.reconciled and not capture.report(result.bill).trusted


def test_sharpened_copy_is_a_valid_image_of_the_same_size():
    from io import BytesIO

    from PIL import Image

    from tests.test_vision import _jpeg

    original = _jpeg(300, 700)
    assert Image.open(BytesIO(vision.sharpened(original))).size == Image.open(BytesIO(original)).size


def test_the_explanation_gets_the_solar_figures_and_the_guard_allows_them():
    from app.domain.conversation import guard
    from app.flows.analysis import analyse

    banked = variant(SOLAR_SEP_2026, carry_forward_units=40)
    facts = analyse(banked, "web:test-solar-facts").facts
    assert (facts.import_units, facts.export_units, facts.carry_forward_units) == (3101, 9, 40)
    assert guard.check("You drew 3101 units, sent 9 back and 40 units are kept for next time.", facts).passed
    plain = analyse(OCT_2025, "web:test-plain-facts").facts
    assert plain.import_units is None and plain.carry_forward_units is None


def _slip(lines: int = 40) -> Image.Image:
    image = Image.new("RGB", (600, 1800), "white")
    draw = ImageDraw.Draw(image)
    for n in range(lines):  # rows of print: a label on the left, an amount on the right
        y = 60 + n * 42
        draw.rectangle((40, y, 300, y + 16), fill="black")
        draw.rectangle((420, y, 560, y + 16), fill="black")
    return image


@pytest.mark.parametrize("tilt", [-9.0, -4.0, 6.0, 11.0])
def test_a_tilted_photo_is_turned_straight_before_it_is_read(tilt: float):
    turned = _slip().rotate(tilt, expand=True, fillcolor=(110, 90, 70))  # on a table
    assert abs(vision.skew_angle(turned) + tilt) <= 1.0


def test_a_straight_photo_is_left_alone():
    assert vision.skew_angle(_slip()) == 0.0
    assert vision.deskewed(_slip()).size == _slip().size


def test_units_misread_together_with_a_reading_are_caught_by_the_energy_charge():
    # The fully degraded October photo: 5 read as 3 in both the present reading and the units, so they still agree.
    misread = variant(OCT_2025, present_reading=331.0, units=118)
    assert capture.failed_check(misread) == "Units agree with the energy charge"
    detail = next(c.detail for c in capture.report(misread).checks if c.key == "energy_units")
    assert "fits 138 units" in detail and not capture.report(misread).trusted


def test_an_energy_charge_no_unit_count_explains_is_a_pricing_question_not_a_misread():
    priced_wrong = variant(OCT_2025, line_items=[{**i.model_dump(), "amount": i.amount + 1.7} if i.code == "energy"
                                                 else i.model_dump() for i in OCT_2025.line_items],
                           bill_amount=OCT_2025.bill_amount)
    check = next(c for c in capture.report(priced_wrong).checks if c.key == "energy_units")
    assert check.status == "skipped" and "cannot confirm" in check.detail


def test_a_figure_the_first_read_could_not_see_is_never_supplied_by_the_reread(monkeypatch):
    cut = variant(OCT_2025, bill_amount=None, total_payable=None, unreadable_fields=["bill_amount", "total_payable"])
    invented = variant(OCT_2025, bill_amount=658.28, total_payable=658.28, arrears=0.0)
    _script(monkeypatch, cut, invented)
    result = _read()
    assert result.bill is not None and result.bill.bill_amount is None and not capture.report(result.bill).trusted


def test_reconcile_keeps_one_sided_figures_flagged():
    cut = variant(OCT_2025, bill_amount=None)
    settled = second_read.reconcile(cut, OCT_2025)
    assert settled is not None and "bill_amount" in settled.unreadable_fields
    assert not capture.report(settled).trusted


# Domestic rooftop solar: the two real slips that were refused or misread before.


@pytest.mark.parametrize("bill", [SOLAR_DOM_OCT_2026, SOLAR_DOM_AUG_2026], ids=["exported_more", "billed_23"])
def test_domestic_solar_bills_are_trusted_and_every_charge_checks(bill):
    from app.flows.analysis import analyse

    report = capture.report(bill)
    assert report.trusted, report.problem
    assert {c.key: c.status for c in report.checks}["net_units"] == "pass"
    audit = analyse(bill, "web:test-solar-domestic").audit
    assert audit.status == "verified" and audit.overcharge == 0  # duty on import, energy on billed units


def test_units_banked_from_export_are_carried_not_failed():
    assert SOLAR_DOM_OCT_2026.import_units() == 256 and SOLAR_DOM_OCT_2026.net_units() == 0
    assert SOLAR_DOM_AUG_2026.import_units() == 160 and SOLAR_DOM_AUG_2026.net_units() == 23
    wrong_carry = variant(SOLAR_DOM_OCT_2026, carry_forward_units=19)  # a misread banked figure
    assert {c.key: c.status for c in capture.report(wrong_carry).checks}["net_units"] == "fail"
    banked_in = variant(SOLAR_DOM_AUG_2026, previous_carry_forward_units=5, billed_units=18)
    assert {c.key: c.status for c in capture.report(banked_in).checks}["net_units"] == "pass"


def test_the_printed_import_and_units_labels_take_their_places():
    read = normalise({"units": "0", "import_units": "256.0", "export_units": "266"})
    assert (read["units"], read["billed_units"]) == (256, 0) and "import_units" not in read
    copied = normalise({"units": 160, "import_units": 160, "export_units": 137})
    assert (copied["units"], copied["billed_units"]) == (160, None)  # a copy of Import is not the billed figure
    plain = normalise({"units": 138})
    assert (plain["units"], plain.get("billed_units")) == (138, None)


def test_an_export_register_read_backwards_is_put_in_order_but_a_rollover_is_not():
    swapped = normalise({"export_previous_reading": "40355", "export_present_reading": "40218"})
    assert (swapped["export_previous_reading"], swapped["export_present_reading"]) == (40218.0, 40355.0)
    rolled = normalise({"export_previous_reading": "99950", "export_present_reading": "40"})
    assert (rolled["export_previous_reading"], rolled["export_present_reading"]) == (99950.0, 40.0)


def test_a_misread_reading_on_a_bill_whose_amounts_agree_is_never_shown():
    misread = variant(SOLAR_DOM_AUG_2026, present_reading=54769.0, export_previous_reading=40210.0)
    assert capture.register_misreads(misread) == ["previous_reading", "present_reading", "export_previous_reading",
                                                  "export_present_reading"]
    assert capture.register_misreads(SOLAR_DOM_AUG_2026) == []
    cleared = vision._registers_checked(reading(misread)).bill
    assert cleared is not None and cleared.present_reading is None and cleared.export_previous_reading is None
    assert {"present_reading", "export_previous_reading"} <= set(cleared.unreadable_fields) and cleared.units == 160


def _slip_on_cloth(marker: bool) -> Image.Image:
    photo = Image.new("RGB", (1200, 1600), (60, 90, 170))  # a patterned bedsheet, simplified to blue
    draw = ImageDraw.Draw(photo)
    draw.rectangle((450, 20, 760, 1590), fill=(245, 245, 240))
    for y in range(60, 1560, 26):
        draw.line((480, y, 700, y), fill=(30, 30, 30), width=3)
    if marker:  # the green pen over the name and address
        draw.rectangle((440, 470, 800, 580), fill=(80, 230, 170))
    return photo


@pytest.mark.parametrize("marker", [False, True])
def test_a_slip_on_a_cloth_is_cropped_to_the_whole_paper(marker):
    box = vision.paper_box(_slip_on_cloth(marker))
    assert box is not None
    left, top, right, bottom = box
    assert left < 460 and right > 750 and top < 60 and bottom > 1560  # top to bottom, past the marker
    assert right - left < 450  # the cloth on both sides is gone


def test_a_page_that_fills_the_photo_is_left_alone():
    assert vision.paper_box(Image.new("RGB", (1000, 1400), (250, 250, 250))) is None
    assert vision.paper_box(Image.new("RGB", (1000, 1400), (60, 90, 170))) is None


def test_the_energy_charge_confirms_the_billed_units_on_a_solar_bill():
    from app.flows import read_problem

    checks = {c.key: c for c in capture.report(SOLAR_DOM_AUG_2026).checks}
    assert checks["energy_units"].status == "pass"  # 23 billed units give Rs 44.85
    misread = variant(SOLAR_DOM_AUG_2026, billed_units=28, units=165)  # import and billed both misread, so net agrees
    report = capture.report(misread)
    energy = next(c for c in report.checks if c.key == "energy_units")
    assert energy.status == "fail" and energy.values["fits"] == 23 and not report.trusted
    assert read_problem.choices("chk_energy_units", report) == []  # billed units are not offered as a pick


@pytest.mark.parametrize(("fields", "key"), [
    ({"billed_units": 5}, "chk_net_units"),
    ({"billed_units": 5, "previous_carry_forward_units": 3}, "chk_net_units_banked"),
    ({"carry_forward_units": 19}, "chk_net_units_carried"),
])
def test_each_net_units_mismatch_is_said_plainly_in_every_language(fields, key):
    from app.domain.conversation.lang import text
    from app.flows import read_problem

    base = SOLAR_DOM_OCT_2026 if key == "chk_net_units_carried" else SOLAR_DOM_AUG_2026
    report = capture.report(variant(base, **fields))
    code = read_problem.diagnose("retake", reading(variant(base, **fields)), report)
    assert code == key
    for language in ("te", "en", "hi", "ur"):
        said = text(language, code, **read_problem.values(code, report))
        assert "{" not in said and said.strip()


@pytest.mark.parametrize("category", ["3 INDUSTRIAL", "LT-III INDUSTRY", "5 AGRICULTURE", "LT-V AGRI", "4 COTTAGE",
                                      "LT-VI STREET LIGHTS", "7 GENERAL PURPOSE", "Cat:8 TEMPORARY SUPPLY"])
def test_a_category_without_a_loaded_tariff_is_read_but_never_checked_on_the_wrong_rates(category):
    from app.domain.conversation import composer
    from app.flows.analysis import analyse

    bill = variant(SOLAR_SEP_2026, category=category, is_domestic=False)
    assert bill.tariff_category() == "other"
    report = capture.report(bill)
    assert report.trusted  # read fine; its energy charge is not judged against slabs it was never priced on
    assert {c.key: c.status for c in report.checks}["energy_units"] == "skipped"
    a = analyse(bill, "web:test-other-category")
    assert a.audit.status == "not_checkable" and a.audit.overcharge == 0
    assert "not one I can check yet" in " ".join(composer.explain(a.facts, "en"))


@pytest.mark.parametrize("category", ["2B NON-DOMESTIC/COMM", "LT-II COMMERCIAL", "2 NON DOMESTIC", "Cat:2A"])
def test_commercial_bills_are_still_checked(category):
    from app.flows.analysis import analyse

    bill = variant(SOLAR_SEP_2026, category=category, is_domestic=False)
    assert bill.tariff_category() == "non_domestic"
    assert analyse(bill, "web:test-commercial").audit.status == "verified"
