"""The DISCOM's own bill and registered mobile for one connection, looked up by service number.

Connected when DISCOM_BILLS_URL and DISCOM_BILLS_TOKEN are set:
`GET {url}/consumers/{service_number}/bill?discom=` returns `{"bill": {...}, "section": "..."}`, and
`GET {url}/consumers/{service_number}/contact?discom=` returns `{"mobile": "9xxxxxxxxx"}`; 404 means none.
In development with OWNERSHIP_CHECK=false, bills already stored in this database stand in for the DISCOM.
The service number and the mobile go only into the request and are never logged or stored; neither is the URL.
"""

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import get_settings
from app.core.hashing import INDIAN_MOBILE, mobile_hash
from app.domain.bill import ExtractedBill
from app.store import repos

log = logging.getLogger(__name__)
TIMEOUT_S = 10.0


class _HideLookups(logging.Filter):
    """httpx logs every request URL at INFO, and these URLs carry the service number."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "/consumers/" not in record.getMessage()


logging.getLogger("httpx").addFilter(_HideLookups())


class _BillResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bill: ExtractedBill
    section: str | None = Field(default=None, max_length=80)


class _ContactResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mobile: str = Field(pattern=INDIAN_MOBILE.pattern)


@dataclass(frozen=True)
class FetchedBill:
    bill: ExtractedBill
    section: str | None


def available() -> bool:
    settings = get_settings()
    return settings.discom_bills_live or settings.dev_bills


async def _get(discom: str, service_number: str, what: str) -> dict[str, Any] | None:
    settings = get_settings()
    url = f"{settings.discom_bills_url.rstrip('/')}/consumers/{quote(service_number, safe='')}/{what}"
    headers = {"Authorization": f"Bearer {settings.discom_bills_token}", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            response = await client.get(url, params={"discom": discom}, headers=headers)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("DISCOM %s lookup failed: %s", what, type(exc).__name__)
        return None
    return body if isinstance(body, dict) else None


async def fetch_bill(discom: str, service_number: str) -> FetchedBill | None:
    settings = get_settings()
    if settings.discom_bills_live:
        body = await _get(discom, service_number, "bill")
        try:
            parsed = _BillResponse.model_validate(body) if body else None
        except ValidationError:
            log.warning("DISCOM bill response did not match the expected shape")
            return None
        if parsed is None or parsed.bill.service_number != service_number or parsed.bill.discom != discom:
            return None
        return FetchedBill(parsed.bill, parsed.section)
    if settings.dev_bills:
        stored = repos.newest_for_service(discom, service_number)
        return FetchedBill(stored, stored.section) if stored else None
    return None


async def registered_mobile(discom: str, service_number: str) -> str | None:
    """The number the DISCOM holds for the connection, used only to send a code to it. Never stored."""
    if not get_settings().discom_bills_live:
        return None
    body = await _get(discom, service_number, "contact")
    try:
        return _ContactResponse.model_validate(body).mobile if body else None
    except ValidationError:
        log.warning("DISCOM contact response did not match the expected shape")
        return None


async def registered_mobile_hash(discom: str, service_number: str) -> str | None:
    mobile = await registered_mobile(discom, service_number)
    return mobile_hash(mobile) if mobile else None
