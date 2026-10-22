"""Consumers sign up and sign in with their mobile number and a one-time code, sent by SMS or WhatsApp.

Signing up needs the mobile the DISCOM holds for a connection: the number is checked against the DISCOM before a
code is sent, and the connections found are kept (masked) on the new account. Signing in needs only the number and
the code. Staff keep their email and password.

A development server with neither SMS nor WhatsApp connected shows the code on screen instead of sending it, and says
so, but only for the sample consumer and for numbers with no account yet: an on-screen code for a real account would let
anyone who knows the number sign in. A production server never shows codes; without a channel it refuses.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from app.config import get_settings
from app.core import ratelimit
from app.core.hashing import digest, mobile_hash, service_hash
from app.domain.bill import mask
from app.services import discom_bills, notify, sms
from app.store import account_connections, accounts, demo_accounts
from app.store import otp_codes as codes
from app.store.accounts import Account

Purpose = Literal["signup", "login"]
Channel = Literal["sms", "whatsapp"]
StartStatus = Literal["sent", "not_registered", "not_sent", "rate_limited", "locked", "unavailable", "demo_only"]
VerifyStatus = Literal["ok", "wrong", "locked", "no_account", "inactive"]

CODE_MINUTES = 5
MAX_ATTEMPTS = 5
LOCK_MINUTES = 30
STARTS_PER_MOBILE = 5  # an hour
HOUR_S = 3600


@dataclass(frozen=True)
class Started:
    status: StartStatus
    channel: Channel | None = None
    dev_code: str | None = None  # development only, when no channel is connected
    connections: int | None = None  # how many the DISCOM holds for the number, on sign up


@dataclass(frozen=True)
class Verified:
    status: VerifyStatus
    account: Account | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def _ts(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def channels() -> list[Channel]:
    """The ways a code can reach the consumer. A development server with none connected offers both, on screen."""
    settings = get_settings()
    found: list[Channel] = [c for c, on in (("sms", settings.sms_enabled), ("whatsapp", notify.can_send_code())) if on]
    return found or (["sms", "whatsapp"] if on_screen() else [])


def on_screen() -> bool:
    settings = get_settings()
    return settings.app_env == "development" and not settings.sms_enabled and not notify.can_send_code()


def demo_number(mobile: str) -> bool:
    """The demo server's fixed-code number (DEMO_OTP_MOBILE). Its code is never sent: there is no phone behind it."""
    return bool(get_settings().demo_otp_mobile) and mobile == get_settings().demo_otp_mobile


def _code_hash(purpose: str, mhash: str, code: str) -> str:
    return digest("otp", f"{purpose}:{mhash}:{code}")


def _audit(action: str, mobile: str, outcome: str) -> None:
    # The audit log is not an application log, but even here only the last four digits are kept.
    accounts.audit(None, action, None, f"mobile {mask(mobile)}, {outcome}")


async def registered(mobile: str, discom: str) -> list[discom_bills.Connection] | None:
    """The connections the DISCOM holds for this mobile, or None when it cannot be asked (not connected, or failed)."""
    try:
        found = await discom_bills.connections_for_mobile(mobile, "", (discom,))
    except discom_bills.LookupFailed:
        return None
    return found.found if found.source == "discom" else None


async def _deliver(mobile: str, code: str, channel: Channel, language: str) -> bool:
    if channel == "sms":
        return await sms.send_code(mobile, code)
    return await notify.send_code(mobile, code, language)


async def start(mobile: str, purpose: Purpose, channel: Channel, discom: str | None, language: str) -> Started:
    if channel not in channels():
        return Started("unavailable")
    mhash = mobile_hash(mobile)
    if not ratelimit.hit(f"otp:{mhash}", STARTS_PER_MOBILE, HOUR_S):
        _audit("auth.otp_start", mobile, "rate limited")
        return Started("rate_limited")
    if on_screen() and accounts.by_login(mobile) is not None and not (demo_accounts.is_sample(mobile) or demo_number(mobile)):
        _audit("auth.otp_start", mobile, "not shown on screen, the number has a real account")
        return Started("demo_only")
    count = None
    if purpose == "signup":
        found = await registered(mobile, discom or "")
        if found is None and not (on_screen() or demo_number(mobile)):
            return Started("unavailable")  # production signs up only numbers the DISCOM has confirmed
        if found is not None and not found:
            _audit("auth.otp_start", mobile, f"not registered with {discom}")
            return Started("not_registered")
        count = len(found) if found is not None else None
    held = codes.get(purpose, mhash)
    if held and held["locked_until"] and held["locked_until"] > _ts(_now()):
        return Started("locked")
    code = get_settings().demo_otp_code if demo_number(mobile) else f"{secrets.randbelow(10**6):06d}"
    codes.put(purpose, mhash, _code_hash(purpose, mhash, code), _ts(_now() + timedelta(minutes=CODE_MINUTES)))
    if demo_number(mobile):
        _audit("auth.otp_start", mobile, f"{purpose}, demo number, fixed code")
        return Started("sent", channel, dev_code=code if on_screen() else None, connections=count)
    if on_screen():
        _audit("auth.otp_start", mobile, f"{purpose}, development, code shown on screen")
        return Started("sent", channel, dev_code=code, connections=count)
    sent = await _deliver(mobile, code, channel, language)
    _audit("auth.otp_start", mobile, f"{purpose}, {channel}, {'sent' if sent else 'not sent'}")
    return Started("sent" if sent else "not_sent", channel, connections=count)


def check(mobile: str, purpose: Purpose, code: str) -> Literal["ok", "wrong", "locked"]:
    """Expired, unknown and wrong all answer the same."""
    mhash = mobile_hash(mobile)
    found = codes.get(purpose, mhash)
    now = _ts(_now())
    if found and found["locked_until"] and found["locked_until"] > now:
        return "locked"
    if found is None:
        return "wrong"
    if secrets.compare_digest(found["code_hash"], _code_hash(purpose, mhash, code)) and found["expires_at"] > now:
        codes.used(purpose, mhash)
        return "ok"
    locked = codes.failed(purpose, mhash, MAX_ATTEMPTS, _ts(_now() + timedelta(minutes=LOCK_MINUTES)))
    return "locked" if locked else "wrong"


async def sign_up(mobile: str, code: str, name: str, discom: str) -> Verified:
    """A new consumer account for a verified mobile. A number that already has one is signed in to it instead."""
    status = check(mobile, "signup", code)
    if status != "ok":
        _audit("auth.otp_verify", mobile, f"signup, {status}")
        return Verified(status)
    existing = accounts.by_login(mobile)
    if existing is not None:
        return Verified("ok" if existing.active else "inactive", existing if existing.active else None)
    # No password: a consumer signs in with codes only, so the stored hash is of a secret nobody holds.
    account = accounts.create("consumer", mobile, name, secrets.token_urlsafe(32),
                              consent_version=get_settings().privacy_notice_version)
    found = await registered(mobile, discom) or []
    account_connections.replace(account.id, [(c.discom, service_hash(c.service_number), mask(c.service_number) or "",
                                              c.section) for c in found])
    accounts.audit(account.id, "account.register", account.id, f"by mobile code, {len(found)} connections")
    return Verified("ok", account)


def sign_in(mobile: str, code: str) -> Verified:
    status = check(mobile, "login", code)
    if status != "ok":
        _audit("auth.otp_verify", mobile, f"login, {status}")
        return Verified(status)
    account = accounts.by_login(mobile)
    if account is None or account.role != "consumer":
        return Verified("no_account")
    if not account.active:
        return Verified("inactive")
    return Verified("ok", account)
