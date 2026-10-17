"""Getting a bill by service number (USC). Shared by the web routes and the chat.

The answer never reveals whether a service number exists: a start always looks the same, and a service number with
no registered mobile still gets a code row (one nobody receives), so wrong codes and lockouts behave identically.
Audits carry the masked number only.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from app.config import get_settings
from app.core import ratelimit
from app.core.hashing import digest, mobile_hash, service_hash
from app.domain import capture
from app.domain.bill import ExtractedBill, mask
from app.flows import report
from app.services import discom_bills, notify
from app.store import accounts
from app.store import usc_codes as codes

CODE_MINUTES = 5
MAX_ATTEMPTS = 5
LOCK_MINUTES = 30
STARTS_PER_ACCOUNT = 5
STARTS_PER_USC = 3
HOUR_S = 3600

StartStatus = Literal["sent", "no_code_needed", "unavailable", "rate_limited"]
VerifyStatus = Literal["ok", "wrong", "locked", "unavailable", "no_bill"]


@dataclass(frozen=True)
class Verified:
    status: VerifyStatus
    bill_report: report.BillReport | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def _ts(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def _actor(user_id: str) -> str | None:
    return user_id.removeprefix("acct:") if user_id.startswith("acct:") else None


def audit(user_id: str, action: str, discom: str, service_number: str, outcome: str) -> None:
    accounts.audit(_actor(user_id), action, None, f"{discom} {mask(service_number)}, {outcome}")


def can_use_codes() -> bool:
    settings = get_settings()
    return settings.dev_bills or (settings.discom_bills_live and notify.can_send_code())


def _code_hash(user_id: str, shash: str, code: str) -> str:
    return digest("code", f"{user_id}:{shash}:{code}")


def within_limits(user_id: str, service_number: str) -> bool:
    """Per account 5 an hour, per service number 3 an hour. Both counters move on every try, so the limits cannot
    be dodged by alternating."""
    hits = [ratelimit.hit(f"usc-account:{user_id}", STARTS_PER_ACCOUNT, HOUR_S),
            ratelimit.hit(f"usc-number:{service_hash(service_number)}", STARTS_PER_USC, HOUR_S)]
    return all(hits)


async def start(user_id: str, discom: str, service_number: str, language: str) -> StartStatus:
    if not can_use_codes():
        return "unavailable"
    shash = service_hash(service_number)
    if not within_limits(user_id, service_number):
        audit(user_id, "usc.start", discom, service_number, "rate limited")
        return "rate_limited"
    if get_settings().dev_bills:
        audit(user_id, "usc.start", discom, service_number, "development, no code")
        return "no_code_needed"
    found = codes.get(user_id, discom, shash)
    if found and found["locked_until"] and found["locked_until"] > _ts(_now()):
        audit(user_id, "usc.start", discom, service_number, "locked")
        return "sent"
    code = f"{secrets.randbelow(10**6):06d}"
    codes.put(user_id, discom, shash, _code_hash(user_id, shash, code), _ts(_now() + timedelta(minutes=CODE_MINUTES)))
    mobile = await discom_bills.registered_mobile(discom, service_number)
    delivered = bool(mobile) and await notify.send_code(mobile or "", code, language)
    audit(user_id, "usc.start", discom, service_number, "code sent" if delivered else "no code sent")
    return "sent"


def _check_code(user_id: str, discom: str, shash: str, code: str | None) -> VerifyStatus | None:
    """None when the code is right. Expired, unknown and wrong all answer the same."""
    found = codes.get(user_id, discom, shash)
    now = _ts(_now())
    if found and found["locked_until"] and found["locked_until"] > now:
        return "locked"
    if found is None:
        return "wrong"
    right = code is not None and secrets.compare_digest(found["code_hash"], _code_hash(user_id, shash, code))
    if right and found["expires_at"] > now:
        codes.used(user_id, discom, shash)
        return None
    locked = codes.failed(user_id, discom, shash, MAX_ATTEMPTS, _ts(_now() + timedelta(minutes=LOCK_MINUTES)))
    return "locked" if locked else "wrong"


def attempts_left(user_id: str, discom: str, service_number: str) -> int:
    found = codes.get(user_id, discom, service_hash(service_number))
    return max(MAX_ATTEMPTS - (found["attempts"] if found else 0), 0)


async def fetch_and_check(user_id: str, discom: str, service_number: str, language: str) -> Verified:
    fetched = await discom_bills.fetch_bill(discom, service_number)
    checked = report.check_fetched(user_id, fetched.bill, language) if fetched else None
    audit(user_id, "usc.fetch", discom, service_number, "bill saved" if checked else "no bill")
    return Verified("ok", checked) if checked else Verified("no_bill")


async def fetch_for_chat(user_id: str, discom: str, service_number: str) -> ExtractedBill | None:
    """The fetched bill when it passes the same capture checks as a photo; the chat then explains and saves it."""
    fetched = await discom_bills.fetch_bill(discom, service_number)
    bill = fetched.bill if fetched and capture.report(fetched.bill).trusted else None
    audit(user_id, "usc.fetch", discom, service_number, "bill found" if bill else "no bill")
    return bill


def verify_code(user_id: str, discom: str, service_number: str, code: str | None) -> VerifyStatus | None:
    """None when the caller may have the bill: the code is right, or a development server needs none."""
    if not can_use_codes():
        return "unavailable"
    if get_settings().dev_bills:
        return None
    problem = _check_code(user_id, discom, service_hash(service_number), code)
    audit(user_id, "usc.verify", discom, service_number, problem or "code accepted")
    return problem


async def verify(user_id: str, discom: str, service_number: str, code: str | None, language: str) -> Verified:
    problem = verify_code(user_id, discom, service_number, code)
    if problem:
        return Verified(problem)
    return await fetch_and_check(user_id, discom, service_number, language)


async def owns_by_whatsapp(sender: str | None, discom: str, service_number: str) -> bool:
    """The sender's WhatsApp number against the DISCOM's registered mobile, compared as hashes."""
    if get_settings().dev_bills:
        return True
    registered = await discom_bills.registered_mobile_hash(discom, service_number)
    return bool(sender and registered and secrets.compare_digest(registered, mobile_hash(sender)))
