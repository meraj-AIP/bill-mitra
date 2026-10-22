"""The DISCOM's own bill and registered mobile for one connection, looked up by service number.

Connected when DISCOM_BILLS_URL and DISCOM_BILLS_TOKEN are set:
`GET {url}/consumers/{service_number}/bill?discom=` returns `{"bill": {...}, "section": "..."}`, and
`GET {url}/consumers/{service_number}/contact?discom=` returns `{"mobile": "9xxxxxxxxx"}`, and
`GET {url}/mobiles/{mobile}/consumers?discom=` returns `{"consumers": [{"service_number": "...", "section": "..."}]}`,
the connections registered to a mobile; 404 means none.
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
from app.core import retry
from app.core.hashing import INDIAN_MOBILE, mobile_hash
from app.domain.bill import ExtractedBill
from app.store import repos

log = logging.getLogger(__name__)
TIMEOUT_S = 10.0
DISCOMS = ("TGSPDCL", "TGNPDCL")
# The consumer is waiting in the chat or on the page, so the budget is short.
LOOKUP = retry.Policy(attempts=3, base_s=0.5, max_s=3.0, budget_s=10.0)


class _HideLookups(logging.Filter):
    """httpx logs every request URL at INFO, and these URLs carry the service number or the mobile."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return "/consumers/" not in message and "/mobiles/" not in message


logging.getLogger("httpx").addFilter(_HideLookups())


class _BillResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bill: ExtractedBill
    section: str | None = Field(default=None, max_length=80)


class _ContactResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mobile: str = Field(pattern=INDIAN_MOBILE.pattern)


class _Connection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    service_number: str = Field(pattern=r"^\d{5,16}$")
    section: str | None = Field(default=None, max_length=80)


class _ConnectionsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    consumers: list[_Connection] = Field(default_factory=list, max_length=50)


@dataclass(frozen=True)
class Connection:
    discom: str
    service_number: str  # in memory only: callers store its hash and masked form
    section: str | None


@dataclass(frozen=True)
class Connections:
    """What the DISCOM holds for a mobile. `source` is "discom", "dev" (this database standing in) or "none"
    (no lookup connected), so nobody reads a stand-in as the DISCOM's word."""
    source: str
    found: list[Connection]


@dataclass(frozen=True)
class FetchedBill:
    bill: ExtractedBill
    section: str | None


def available() -> bool:
    settings = get_settings()
    return settings.discom_bills_live or settings.dev_bills


class LookupFailed(Exception):
    """The DISCOM could not be asked (network, server or a malformed answer). Distinct from "none found"."""


async def _request(path: str, discom: str, what: str) -> dict[str, Any] | None:
    """The body, or None on 404. Raises LookupFailed when the DISCOM could not answer."""
    settings = get_settings()
    url = f"{settings.discom_bills_url.rstrip('/')}{path}"
    headers = {"Authorization": f"Bearer {settings.discom_bills_token}", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            async def once() -> httpx.Response:
                response = await client.get(url, params={"discom": discom}, headers=headers)
                return response if response.status_code == 404 else response.raise_for_status()

            response = await retry.call(once, f"DISCOM {what}", LOOKUP)
            if response.status_code == 404:
                return None
            body = response.json()
    except (httpx.HTTPError, *retry.TRANSPORT, ValueError) as exc:
        log.warning("DISCOM %s lookup failed: %s", what, type(exc).__name__)
        raise LookupFailed(what) from exc
    if not isinstance(body, dict):
        raise LookupFailed(what)
    return body


async def connections_for_mobile(mobile: str, user_id: str, discoms: tuple[str, ...] = DISCOMS) -> Connections:
    """The connections registered to this mobile in these DISCOMs. Raises LookupFailed so the caller can try later."""
    digits = mobile[-10:]
    settings = get_settings()
    if settings.discom_bills_live:
        found: list[Connection] = []
        for discom in discoms:
            body = await _request(f"/mobiles/{quote(digits, safe='')}/consumers", discom, "connections")
            try:
                parsed = _ConnectionsResponse.model_validate(body or {})
            except ValidationError as exc:
                log.warning("DISCOM connections response did not match the expected shape")
                raise LookupFailed("connections") from exc
            found += [Connection(discom, c.service_number, c.section) for c in parsed.consumers]
        return Connections("discom", found)
    if settings.dev_bills:
        return Connections("dev", [Connection(d, n, s) for d, n, s in repos.connections_of(user_id) if d in discoms])
    return Connections("none", [])


async def _get(discom: str, service_number: str, what: str) -> dict[str, Any] | None:
    settings = get_settings()
    url = f"{settings.discom_bills_url.rstrip('/')}/consumers/{quote(service_number, safe='')}/{what}"
    headers = {"Authorization": f"Bearer {settings.discom_bills_token}", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            async def once() -> httpx.Response:
                response = await client.get(url, params={"discom": discom}, headers=headers)
                return response if response.status_code == 404 else response.raise_for_status()

            response = await retry.call(once, f"DISCOM {what}", LOOKUP)
            if response.status_code == 404:
                return None
            body = response.json()
    except (httpx.HTTPError, *retry.TRANSPORT, ValueError) as exc:
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
