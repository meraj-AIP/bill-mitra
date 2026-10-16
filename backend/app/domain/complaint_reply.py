"""What an officer can say back on a complaint, built only from the bill check. No I/O.

The draft is the checked answer: every figure in it comes from the engine. A model may reword it later, and the
number guard holds the reworded text to the draft's own figures.
"""

from typing import Literal

from app.domain.audit import AuditResult
from app.domain.conversation.composer import month_label
from app.domain.conversation.facts import Facts, rs
from app.domain.conversation.lang import pack, text

Triage = Literal["overcharge", "bill_correct", "needs_check"]
RequestKind = Literal["meter_photo", "bill_photo", "details", "earlier_bills", "note"]

QUICK_KEYS = ("quick_received", "quick_correction", "quick_visit", "quick_1912")
REQUEST_KEYS: dict[RequestKind, str] = {"meter_photo": "request_meter", "bill_photo": "request_bill",
                                        "details": "request_details", "earlier_bills": "request_earlier_bills",
                                        "note": "request_details"}


def triage(audit: AuditResult) -> Triage:
    """Money over the tariff is an overcharge; a clean check means the bill is right; anything else needs a look."""
    if audit.overcharge > 0:
        return "overcharge"
    return "bill_correct" if audit.status == "verified" else "needs_check"


def draft(facts: Facts, audit: AuditResult, language: str) -> str:
    month = month_label(language, facts.month_number, facts.year)
    kind = triage(audit)
    if kind == "overcharge":
        labels: dict[str, str] = pack(language).LABEL
        lines = " ".join(
            text(language, "reply_line", label=labels.get(line.code, line.code), diff=rs(line.difference),
                 printed=rs(line.printed), expected=rs(line.expected))
            for line in audit.lines if line.status == "over")
        return text(language, "reply_overcharge", month=month, lines=lines)
    if kind == "bill_correct":
        return text(language, "reply_bill_correct", month=month, units=facts.units, amount=rs(facts.bill_amount))
    return text(language, "reply_needs_check", month=month)


def quick_replies(language: str) -> list[str]:
    return [text(language, key) for key in QUICK_KEYS]


def request_text(kind: RequestKind, language: str, ticket: str) -> str:
    return text(language, REQUEST_KEYS[kind], ticket=ticket)
