"""Parse the bill SMS DISCOMs send, for consumers who have the SMS but not the paper bill."""

import re
from datetime import date

from app.domain.bill import ExtractedBill

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

_SERVICE = re.compile(r"(?:usc|sc\s*no|service\s*(?:no|number)|scno)[\s.:#-]*(\d{6,15})", re.I)
_UNITS = re.compile(r"units?[\s.:-]*(\d{1,5})|(\d{1,5})\s*units?", re.I)
_AMOUNT = re.compile(r"(?:amount|amt)[^\d]{0,12}?(?:rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)|(?:rs\.?|₹)\s*([\d,]+(?:\.\d{1,2})?)",
                     re.I)
_DUE = re.compile(r"due\s*(?:date|dt)?[\s.:-]*(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", re.I)
_MONTH = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s'-]*(\d{2,4})\b", re.I)


def looks_like_sms(message: str) -> bool:
    lowered = message.lower()
    return bool(_SERVICE.search(message)) and ("unit" in lowered or "amount" in lowered or "amt" in lowered)


def parse(message: str) -> ExtractedBill | None:
    units_match = _UNITS.search(message)
    if not units_match:
        return None
    units = int(units_match.group(1) or units_match.group(2))
    service = _SERVICE.search(message)
    amount_match = _AMOUNT.search(message)
    amount = float((amount_match.group(1) or amount_match.group(2)).replace(",", "")) if amount_match else None
    due = _DUE.search(message)
    month = _MONTH.search(message)
    bill_month = None
    if month:
        year = int(month.group(2))
        bill_month = f"{year + 2000 if year < 100 else year:04d}-{_MONTHS[month.group(1).lower()[:3]]:02d}"
    due_date = None
    if due:
        year = int(due.group(3))
        due_date = date(year + 2000 if year < 100 else year, int(due.group(2)), int(due.group(1))).isoformat()
    lowered = message.lower()
    discom = "TGSPDCL" if "spdcl" in lowered else "TGNPDCL" if "npdcl" in lowered else "UNKNOWN"
    return ExtractedBill(
        discom=discom, service_number=service.group(1) if service else None, bill_month=bill_month,
        units=units, bill_amount=amount, total_payable=amount,
        due_date=due_date, source="sms", confidence=0.95,
    )


def manual(units: int, message: str) -> ExtractedBill:
    month = _MONTH.search(message)
    bill_month = None
    if month:
        year = int(month.group(2))
        bill_month = f"{year + 2000 if year < 100 else year:04d}-{_MONTHS[month.group(1).lower()[:3]]:02d}"
    return ExtractedBill(units=units, bill_month=bill_month, source="manual", confidence=1.0)
