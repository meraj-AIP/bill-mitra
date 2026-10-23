"""Why a photo did not end in a checked bill, said so the consumer knows what happened, which part, and what to do next
(docs/errors-contract.md section 1). One diagnosis for the chat and the dashboard.

Every figure in these messages is printed on the bill or worked out by the capture checks; none comes from a model.
"""

from app.config import get_settings
from app.domain import capture
from app.domain.conversation.facts import rs
from app.domain.conversation.lang import text
from app.services import vision

# Checks where two printed figures disagree about the units: the consumer may pick one, and the engine prices it.
CHOICES = {"chk_readings": ("difference", "units"), "chk_energy_units": ("fits", "units")}
_MONEY = {"energy", "sum", "bill_amount", "gap", "arrears", "expected", "total"}
_READINGS = {"previous", "present"}
_UNREAD = {"units": "unread_units", "energy": "unread_energy", "bill_amount": "unread_bill_amount"}
_DASHBOARD = {"reading_off": "dash_reading_off", "read_failed": "dash_read_failed", "meter": "dash_meter"}


def _other_discom(reading: vision.Reading) -> bool:
    return reading.classification.discom == "OTHER" or (reading.bill is not None and reading.bill.discom == "OTHER")


def _retake(reading: vision.Reading, report: capture.CaptureReport | None) -> str:
    bill = reading.bill
    if reading.classification.document_type == "meter" or (bill is not None and bill.document_type == "meter"):
        return "meter_unreadable"
    if report is None or report.problem_code is None:
        return "poor_quality"
    if report.problem_code == "check":
        return f"chk_{report.problem_key}"
    if report.problem_code == "low_confidence":
        return "unread_low_confidence"
    return _UNREAD.get(report.problem_key or "units", "unread_units")


def diagnose(result: str, reading: vision.Reading | None, report: capture.CaptureReport | None) -> str | None:
    """The language key for what went wrong, or None when the read gave a bill or a meter reading."""
    if result in ("reading_off", "reading_failed"):
        return "reading_off" if result == "reading_off" else "read_failed"
    if reading is None or result in ("checked", "meter"):
        return None
    if result == "not_a_bill":
        if reading.problem:
            return f"file_{reading.problem}"
        return "other_discom" if _other_discom(reading) else "not_a_bill"
    return _retake(reading, report)


def failed_check(code: str, report: capture.CaptureReport | None) -> capture.Check | None:
    if report is None or not code.startswith("chk_"):
        return None
    return next((c for c in report.checks if c.key == code.removeprefix("chk_") and c.status == "fail"), None)


def _shown(key: str, value: float) -> str:
    if key in _MONEY:
        return rs(value)
    return f"{value:g}" if key in _READINGS else str(round(value))


def values(code: str, report: capture.CaptureReport | None) -> dict[str, str]:
    """What the message for `code` fills in: the failed check's figures, or the limits a file must meet."""
    check = failed_check(code, report)
    if check is not None:
        return {key: _shown(key, value) for key, value in check.values.items()}
    return {"mb": str(get_settings().max_upload_mb), "pages": str(vision.MAX_PDF_PAGES)}


def choices(code: str, report: capture.CaptureReport | None) -> list[int]:
    """The two unit counts the consumer may pick between, or none for this problem."""
    check = failed_check(code, report)
    if check is None or code not in CHOICES:
        return []
    return sorted({round(check.values[key]) for key in CHOICES[code]})


def reason(code: str, report: capture.CaptureReport | None, language: str) -> str:
    """The same message for the dashboard, which has no buttons: a retake says what can be done instead."""
    if code in _DASHBOARD:
        return text(language, _DASHBOARD[code])
    said = text(language, code, **values(code, report))
    if code.startswith(("chk_", "unread_")) or code in ("poor_quality", "meter_unreadable"):
        said += " " + text(language, "dash_retake_hint")
    return said
