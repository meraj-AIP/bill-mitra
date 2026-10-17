"""Peppered hashes for matching a service number or a mobile number without storing either."""

import hashlib
import hmac
import re

from app.config import get_settings

SERVICE_NUMBER = re.compile(r"^\d{5,16}$")
INDIAN_MOBILE = re.compile(r"^[6-9]\d{9}$")


def clean_service_number(raw: str) -> str | None:
    """Digits only, spaces and dashes dropped. None when it cannot be a service number."""
    digits = re.sub(r"[\s-]", "", raw or "")
    return digits if SERVICE_NUMBER.fullmatch(digits) else None


def digest(kind: str, value: str) -> str:
    key = get_settings().hash_pepper.encode()
    return hmac.new(key, f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()


def service_hash(service_number: str) -> str:
    return digest("usc", service_number.strip())


def mobile_hash(number: str) -> str:
    """The last ten digits, so a WhatsApp id (91 and the number) and a typed mobile hash the same."""
    return digest("mobile", re.sub(r"\D", "", number)[-10:])
