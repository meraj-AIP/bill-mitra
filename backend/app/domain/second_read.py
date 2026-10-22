"""When the first read of a bill cannot be trusted: what to ask the second read to look at, and how two reads that
each fall short can still settle the bill. Pure rules; the vision service makes the calls.

The rule that keeps this safe: no number is ever worked out. Every value in a settled bill was printed and read by
the model, and a mix of the two reads is taken only when exactly one mix passes every arithmetic check.
"""

import re
from itertools import product

from app.domain import capture
from app.domain.audit import audit
from app.domain.bill import ExtractedBill, LineItem
from app.domain.pricing import price

# The figures the checks tie together, so a misread one shows up in a sum.
COMPARED = ("units", "export_units", "billed_units", "previous_reading", "present_reading", "export_previous_reading",
            "export_present_reading", "bill_amount", "total_payable", "arrears")
MAX_DIFFERENCES = 5  # 32 mixes at most; more disagreement than this means the photo is the problem
DOUBT_KEYS = (*capture.KEY_FIELDS, "total_payable")
ROW_NAMES = {"energy": "Energy Charges", "fixed": "Fixed Charges", "customer": "Customer Charges",
             "duty": "Electricity Duty", "fsa": "FSA/FCA Charges"}


def doubtful(bill: ExtractedBill) -> list[str]:
    """Key figures the reader itself was not sure of."""
    return [key for key in DOUBT_KEYS if key in bill.unreadable_fields]


def agrees_on(first: ExtractedBill, second: ExtractedBill, keys: list[str]) -> bool:
    """Both reads produced the same value for each key. A value the first read could not see never counts: asked to
    look again, a reader may supply a figure that is not printed at all."""
    def value(bill: ExtractedBill, key: str) -> object:
        return bill.item(key) if key in ROW_NAMES else getattr(bill, key)
    return all(value(first, k) is not None and value(first, k) == value(second, k) for k in keys)


def suspect_rows(bill: ExtractedBill) -> list[str]:
    """Charge rows whose printed amount is not what the tariff gives for the units read: where a misread digit most
    likely sits. Names only, never the expected amounts, so the second read cannot bend a value to fit."""
    if not bill.line_items or bill.units is None:
        return []
    try:
        result = audit(bill, price(bill, bill.net_units(), bill.import_units()))
    except (ValueError, KeyError, LookupError):
        return []
    return [ROW_NAMES.get(line.code, line.code) for line in result.lines
            if line.status in ("over", "under") and line.code in ROW_NAMES]


def _row_key(item: LineItem) -> tuple[str, str]:
    return item.code, re.sub(r"\W", "", item.label).casefold()


def _choices(first: ExtractedBill, second: ExtractedBill) -> list[tuple[str, object, object]] | None:
    """Each figure the reads disagree on, as (where, first value, second value). None when the charge rows do not
    line up, so the reads cannot be compared row by row."""
    out: list[tuple[str, object, object]] = []
    for key in COMPARED:
        a, b = getattr(first, key), getattr(second, key)
        if a is not None and b is not None and a != b:
            out.append((key, a, b))
    if first.line_items and second.line_items:
        if [_row_key(i) for i in first.line_items] != [_row_key(i) for i in second.line_items]:
            return None
        out += [(f"line:{n}", a.amount, b.amount)
                for n, (a, b) in enumerate(zip(first.line_items, second.line_items, strict=True)) if a.amount != b.amount]
    return out


def _candidate(base: ExtractedBill, picks: dict[str, object]) -> ExtractedBill:
    lines = [item.model_copy(update={"amount": picks[f"line:{n}"]}) if f"line:{n}" in picks else item
             for n, item in enumerate(base.line_items)]
    return base.model_copy(update={**{k: v for k, v in picks.items() if not k.startswith("line:")}, "line_items": lines})


def reconcile(first: ExtractedBill, second: ExtractedBill) -> ExtractedBill | None:
    """The one bill both reads support, or None. Where the reads disagree, every mix of their values is tried; the
    result stands only when exactly one mix passes every blocking check. A figure stays flagged unreadable only when
    both reads flagged it."""
    choices = _choices(first, second)
    if choices is None or len(choices) > MAX_DIFFERENCES:
        return None
    # A figure only one read produced stays flagged: a value the other read could not see may be made up to fit.
    filled = {k: getattr(second, k) for k in COMPARED if getattr(first, k) is None and getattr(second, k) is not None}
    one_sided = [k for k in COMPARED if (getattr(first, k) is None) != (getattr(second, k) is None)]
    flagged = [f for f in first.unreadable_fields if f in second.unreadable_fields]
    base = first.model_copy(update={
        **filled, "line_items": first.line_items or second.line_items,
        "unreadable_fields": [*flagged, *(k for k in one_sided if k not in flagged)],
        "confidence": min(first.confidence, second.confidence)})
    passing: dict[tuple[object, ...], ExtractedBill] = {}
    for pick in product((1, 2), repeat=len(choices)):
        values = tuple(a if side == 1 else b for (_, a, b), side in zip(choices, pick, strict=True))
        candidate = _candidate(base, {where: v for (where, _, _), v in zip(choices, values, strict=True)})
        if candidate.units is not None and capture.failed_check(candidate) is None:
            passing[values] = candidate
    return next(iter(passing.values())) if len(passing) == 1 else None
