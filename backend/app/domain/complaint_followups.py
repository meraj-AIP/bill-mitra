"""Questions asked in chat before a complaint's preview, one at a time and each skippable. The answers go into the
complaint description as labelled English lines for staff. Consumer copy lives in the language packs: the question
under `fq_ask_<key>`, its preview label under `fq_label_<key>`, a fixed answer under `fqv_<value>` (also its button
title, so 20 characters max).

The model may pre-answer a question from the consumer's first message, but only with a value from a fixed list.
"""

from dataclasses import dataclass
from typing import Literal

Since = Literal["today", "yesterday", "days", "weeks"]
PaymentMode = Literal["upi_app", "bank", "counter", "online_portal"]
Detail = Literal["since", "payment_mode", "reference_present", "whole_area"]

ANSWER_MAX = 200


@dataclass(frozen=True)
class FollowUp:
    key: str
    label: str  # English, for the staff description
    options: tuple[str, ...] = ()  # fixed answers offered as buttons, at most two so Skip still fits
    detail: Detail | None = None  # the model detail that answers it


VALUE_EN: dict[str, str] = {
    "yes": "Yes", "no": "No", "upi_app": "UPI or payment app", "bank": "Bank transfer", "counter": "Office counter",
    "online_portal": "DISCOM website", "only_home": "Only their home", "whole_street": "Whole street or area",
    "household": "Home", "shop": "Shop or business", "today": "Since today", "yesterday": "Since yesterday",
    "days": "For a few days", "weeks": "For weeks",
}

QUESTIONS: dict[str, tuple[FollowUp, ...]] = {
    "payment_not_updated": (
        FollowUp("paid_when", "Paid on"),
        FollowUp("paid_how", "Paid by", ("upi_app", "counter"), "payment_mode"),
        FollowUp("receipt", "Has a receipt or UTR", ("yes", "no"), "reference_present"),
    ),
    "power_outage": (
        FollowUp("since", "Power off since", detail="since"),
        FollowUp("area", "Affected", ("only_home", "whole_street"), "whole_area"),
    ),
    "meter_burnt": (
        FollowUp("sparks", "Sparks or burning smell", ("yes", "no")),
        FollowUp("supply_off", "Supply off now", ("yes", "no")),
    ),
    "voltage_fluctuation": (FollowUp("voltage_when", "When it happens"),),
    "bill_not_received": (FollowUp("missing_month", "Bill month not received"),),
    "wrong_category": (FollowUp("used_for", "Connection used for", ("household", "shop")),),
    "high_bill": (FollowUp("high_since", "Bill high since"),),
    "wrong_reading": (FollowUp("meter_now", "Reading on the meter now"),),
    "estimated_bill": (FollowUp("last_read", "Meter last read"),),
    "arrears_dispute": (FollowUp("which_dues", "Dues in question"),),
    "meter_issue": (FollowUp("meter_problem", "What is wrong with the meter"),),
    "supply_other": (FollowUp("what_happens", "What happens"),),
}


def for_type(code: str) -> tuple[FollowUp, ...]:
    return QUESTIONS.get(code, ())


def from_details(code: str, details: dict[str, object]) -> dict[str, str]:
    """Answers the model's fixed-list details already give, keyed by question."""
    answers: dict[str, str] = {}
    for q in for_type(code):
        value = details.get(q.detail) if q.detail else None
        if q.detail == "whole_area" and isinstance(value, bool):
            answers[q.key] = "whole_street" if value else "only_home"
        elif q.detail == "reference_present" and isinstance(value, bool):
            answers[q.key] = "yes" if value else "no"
        elif isinstance(value, str) and value in VALUE_EN:
            answers[q.key] = value
    return answers


def staff_lines(code: str, answers: dict[str, str]) -> list[str]:
    """`Label: answer` for every answered question, in the order asked."""
    return [f"{q.label}: {VALUE_EN.get(answers[q.key], answers[q.key])}" for q in for_type(code) if answers.get(q.key)]
