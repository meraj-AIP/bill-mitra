"""From a model's raw answer to a bill we can check. Pure and deterministic.

A reader returns what it sees: "Rs 1,234.50", "37,186.00 CR", "07/09/26", "Sts 1", "TSSPDCL", "PF 99". Each value is
put in one form here, and a value that still does not fit is dropped and listed as unreadable, so one bad cell never
loses the rest of a bill that was read well. Nothing here works out a value that is not printed: the only derived
field is the bill month, which is the bill date written as YYYY-MM.
"""

import re
from datetime import date
from typing import Any

from pydantic import ValidationError

from app.domain.bill import ExtractedBill, real_month

_CODES = {"energy", "fixed", "customer", "duty", "fsa", "true_up", "surcharge", "adjustment", "other"}
INTEGERS = ("units", "export_units", "billed_units", "billing_days", "carry_forward_units", "phase")
DECIMALS = ("meter_reading", "previous_reading", "present_reading", "export_previous_reading", "export_present_reading",
            "load_kw", "multiplying_factor", "recorded_md", "power_factor", "security_deposit", "bill_amount", "arrears",
            "total_payable", "subsidy_amount")
DATES = ("bill_date", "due_date", "previous_reading_date", "disconnection_date", "last_paid_date")
STATUSES = ("present_status", "previous_status")
DISCOM_ALIASES = {"TGSPDCL": "TGSPDCL", "TSSPDCL": "TGSPDCL", "TGNPDCL": "TGNPDCL", "TSNPDCL": "TGNPDCL",
                  "OTHER": "OTHER", "UNKNOWN": "UNKNOWN"}
_CREDIT = re.compile(r"\b(CR|CREDIT)\b\.?$", re.I)
_NOT_NUMBER = re.compile(r"(RS\.?|INR|₹|KWH|KVAH|KW|KVA|UNITS?|DAYS?|/-)", re.I)
# Non-domestic first: "LT-II" and "2B NON-DOMESTIC" also contain the domestic markers.
_NON_DOMESTIC = re.compile(r"NON[\s-]*DOM|COMM|INDUS|AGRI|LT[\s-]*(II|III|IV|V)\b|^\s*[2-9]", re.I)
_DOMESTIC = re.compile(r"DOMESTIC|LT[\s-]*I\b|^\s*1", re.I)
_DATE_FORMS = (re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$"), re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})$"))
MAX_SALVAGE = 6


def number(value: Any) -> float | None:
    """A printed amount or count as a number. A trailing CR, a leading minus, (-) or brackets make it negative."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip().replace("\u2212", "-")
    negative = bool(_CREDIT.search(text)) or text.startswith(("-", "(-)", "(")) or text.endswith("-") and "/-" not in text
    text = _NOT_NUMBER.sub("", _CREDIT.sub("", text))
    text = re.sub(r"[\s,()]|^\(-\)|^-|-$", "", text).replace("(-)", "")
    try:
        found = float(text)
    except ValueError:
        return None
    return -abs(found) if negative else found


def _integer(value: Any) -> int | None:
    found = number(value)
    if found is None or abs(found - round(found)) > 0.01:
        return None
    return round(found)


def iso_date(value: Any) -> str | None:
    """YYYY-MM-DD from the forms bills print (DD/MM/YY, DD-MM-YYYY, DD.MM.YY) or already ISO; None if not a date."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    for form in _DATE_FORMS:
        match = form.match(text)
        if not match:
            continue
        a, b, c = match.groups()
        year, month, day = (int(a), int(b), int(c)) if len(a) == 4 else (int(c), int(b), int(a))
        year = year + 2000 if year < 100 else year
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
    return None


def _status(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value)) if value is not None else ""
    return digits.zfill(2) if 1 <= len(digits) <= 2 else None


def _service(value: Any) -> str | None:
    digits = re.sub(r"[\s-]", "", str(value)) if value is not None else ""
    return digits if re.fullmatch(r"\d{5,16}", digits) else None


def _domestic(category: Any, said: Any) -> bool:
    """The printed category decides domestic or not; the model's own flag is used only when the category is unclear."""
    text = str(category or "")
    if _NON_DOMESTIC.search(text):
        return False
    if _DOMESTIC.search(text):
        return True
    return said if isinstance(said, bool) else True


def _lines(raw: Any) -> list[dict[str, Any]]:
    """Charge rows with an amount. A row read twice (overlapping crops of one slip) is kept once."""
    out, seen = [], set()
    for item in raw if isinstance(raw, list) else []:
        amount = number(item.get("amount")) if isinstance(item, dict) else None
        if amount is None:
            continue
        label = str(item.get("label") or "Charge").strip()[:80] or "Charge"
        key = (re.sub(r"\W", "", label).casefold(), round(amount, 2))
        if key in seen:
            continue
        seen.add(key)
        out.append({"code": item.get("code") if item.get("code") in _CODES else "other", "label": label, "amount": amount})
    return out


def _history(raw: Any) -> list[dict[str, Any]]:
    months: dict[str, int] = {}
    for point in raw if isinstance(raw, list) else []:
        if not isinstance(point, dict) or not real_month(str(point.get("month"))):
            continue
        units = _integer(point.get("units"))
        if units is not None and 0 <= units <= 100_000:
            months.setdefault(str(point["month"]), units)
    return [{"month": m, "units": u} for m, u in sorted(months.items())]


def _flag(raw: dict[str, Any], key: str) -> None:
    unreadable = raw.setdefault("unreadable_fields", [])
    if key not in unreadable:
        unreadable.append(key)


def _clean_each(raw: dict[str, Any], keys: tuple[str, ...], clean: Any) -> None:
    """Each key put in one form. A value printed but unusable becomes null and is flagged unreadable. An object or a
    list where one value belongs is not a misread cell but a broken answer, so it fails the whole reply."""
    for key in keys:
        if raw.get(key) is None:
            raw[key] = None
            continue
        if isinstance(raw[key], dict | list):
            raise ValueError(f"{key} is not a single value")
        value = clean(raw[key])
        if value is None:
            _flag(raw, key)
        raw[key] = value


def _scalars(raw: dict[str, Any]) -> None:
    _clean_each(raw, INTEGERS, _integer)
    _clean_each(raw, DECIMALS, number)
    _clean_each(raw, DATES, iso_date)
    for key in STATUSES:
        raw[key] = _status(raw.get(key))


def _ranges(raw: dict[str, Any]) -> None:
    """Values that cannot be right as read: a power factor printed as a percentage, a confidence out of 100."""
    pf = raw.get("power_factor")
    if pf is not None and 1 < pf <= 100:
        raw["power_factor"] = round(pf / 100, 3)
    days = raw.get("billing_days")
    if days is not None and not 1 <= days <= 62:
        _flag(raw, "billing_days")
        raw["billing_days"] = None
    confidence = number(raw.get("confidence"))
    if confidence is None:
        raw.pop("confidence", None)  # the bill's own default stands
        return
    if 1 < confidence <= 100:
        confidence /= 100
    raw["confidence"] = min(max(confidence, 0.0), 1.0)


def normalise(raw: dict[str, Any]) -> dict[str, Any]:
    raw = dict(raw)
    raw["source"] = "vision"
    said = raw.get("unreadable_fields")
    raw["unreadable_fields"] = [str(f) for f in said if f][:30] if isinstance(said, list) else []
    _scalars(raw)
    _ranges(raw)
    raw["arrears"] = raw.get("arrears") or 0
    raw["discom"] = DISCOM_ALIASES.get(re.sub(r"\W", "", str(raw.get("discom") or "")).upper(), "UNKNOWN")
    _clean_each(raw, ("service_number",), _service)
    raw["is_domestic"] = _domestic(raw.get("category"), raw.get("is_domestic"))
    if not real_month(str(raw.get("bill_month") or "")):
        raw["bill_month"] = raw["bill_date"][:7] if raw.get("bill_date") else None
    raw["line_items"] = _lines(raw.get("line_items"))
    raw["usage_history"] = _history(raw.get("usage_history"))
    for key in ("quality", "document_type"):
        if isinstance(raw.get(key), str):
            raw[key] = raw[key].strip().lower()
    return raw


def to_bill(raw: dict[str, Any]) -> ExtractedBill:
    """Validate, and when a field still does not fit the model, drop just that field and say it was unreadable.
    Raises ValidationError only when the answer has no usable shape at all."""
    data = normalise(raw)
    data.pop("confirmed_by_consumer", None)  # only the consumer's own tap sets it, never a model's answer
    for _ in range(MAX_SALVAGE):
        try:
            return ExtractedBill.model_validate(data)
        except ValidationError as exc:
            bad = {str(e["loc"][0]) for e in exc.errors() if e["loc"]}
            if not bad or not bad - {"__root__"}:
                raise
            for key in bad:
                data.pop(key, None)
                _flag(data, key)
    return ExtractedBill.model_validate(data)
