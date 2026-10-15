"""The two real TGSPDCL spot bills in tests/real_bills, as read by the vision model and checked by hand.

Identifiers are replaced (USC by a 9999 placeholder) and the section is dropped; every printed figure is real.
A test that needs a situation no real bill shows yet changes ONE printed figure through `variant`, and says so.
"""

from app.domain.bill import ExtractedBill
from app.services import vision

PLACEHOLDER_USC = "999900001111"


def _items(*rows: tuple[str, str, float]) -> list[dict[str, object]]:
    return [{"code": code, "label": label, "amount": amount} for code, label, amount in rows]


OCT_2025 = ExtractedBill.model_validate({
    "discom": "TGSPDCL", "service_number": PLACEHOLDER_USC, "category": "1B(i) DOMESTIC", "is_domestic": True,
    "bill_month": "2025-10", "bill_date": "2025-10-05", "due_date": "2025-10-19",
    "previous_reading_date": "2025-09-04", "billing_days": 31, "previous_reading": 213.0, "present_reading": 351.0,
    "units": 138, "load_kw": 5.0,
    "line_items": _items(("energy", "Energy Charges", 518.2), ("fixed", "Fixed Charges", 50.0),
                         ("customer", "Customer Charges", 90.0), ("duty", "Electricity Duty", 8.28),
                         ("other", "Interest on ED", 0.05), ("surcharge", "Surcharge", 25.0),
                         ("fsa", "FSA/FCA Charges", 0.0), ("other", "Subsidy", 0.0),
                         ("adjustment", "Adjustment", 0.0), ("other", "Interest on CD", 0.0),
                         ("adjustment", "Loss/Gain", 0.47)),
    "bill_amount": 692.0, "arrears": 553.0, "total_payable": 1245.0, "gruha_jyothi_household": False,
    "subsidy_amount": 0.0, "confidence": 0.99,
})

MAR_2024 = ExtractedBill.model_validate({
    "discom": "TGSPDCL", "service_number": PLACEHOLDER_USC, "category": "1B(1) Domestic", "is_domestic": True,
    "bill_month": "2024-03", "bill_date": "2024-03-06", "due_date": "2024-03-20",
    "previous_reading_date": "2024-02-03", "billing_days": 32, "previous_reading": 5106.0, "present_reading": 5263.0,
    "units": 157, "load_kw": 5.0,
    "line_items": _items(("energy", "Energy Charges", 599.6), ("fixed", "Fixed Charges", 50.0),
                         ("customer", "Customer Charges", 90.0), ("duty", "Electricity Duty", 9.42),
                         ("other", "Interest on ED", 0.03), ("surcharge", "Surcharge", 25.0),
                         ("surcharge", "ACD Surcharge", 0.0), ("fsa", "FSA/FCA Charges", 0.0),
                         ("other", "Interest on SD", 0.0), ("adjustment", "Adjustment", 0.0),
                         ("adjustment", "Loss/Gain", -0.05)),
    "bill_amount": 774.0, "arrears": 0.0, "total_payable": 774.0, "gruha_jyothi_household": False,
    "confidence": 0.99,
})


def variant(base: ExtractedBill, *, charge: tuple[str, float] | None = None, **fields: object) -> ExtractedBill:
    """A real bill with one printed figure changed. `charge` shifts one line and the totals with it, the way a
    billing error would print."""
    data = base.model_dump()
    if charge:
        code, delta = charge
        data["line_items"] = [{**i, "amount": round(i["amount"] + delta, 2)} if i["code"] == code else i
                              for i in data["line_items"]]
        data["bill_amount"] = round(data["bill_amount"] + delta, 2)
        data["total_payable"] = round(data["total_payable"] + delta, 2)
    data.update(fields)
    return ExtractedBill.model_validate(data)


def reading(extracted: ExtractedBill | None, kind: str = "electricity_bill", quality: str = "good",
            reason: str = "A TGSPDCL electricity bill cum notice.") -> vision.Reading:
    seen = vision.Classification.model_validate({"document_type": kind, "discom": "TGSPDCL", "quality": quality,
                                                 "reason": reason})
    return vision.Reading(seen, extracted)
