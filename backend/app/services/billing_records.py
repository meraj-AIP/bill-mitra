"""DISCOM billing records for one connection: the months the billing system holds.

Not connected unless BILLING_RECORDS_URL and BILLING_RECORDS_TOKEN are both set; then nothing leaves the server.
The service number goes only into the request path. It is never logged, and neither is the URL or the error text,
because both can carry it.
"""

import logging
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import get_settings

log = logging.getLogger(__name__)

TIMEOUT_S = 10.0
MONTHS = 12
Status = Literal["included", "missing", "not_connected"]


class _HideRecordRequests(logging.Filter):
    """httpx logs every request URL at INFO, and this URL carries the service number."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not ("/consumers/" in message and "/history" in message)


logging.getLogger("httpx").addFilter(_HideRecordRequests())


class RecordMonth(BaseModel):
    model_config = ConfigDict(extra="ignore")

    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    units: int = Field(ge=0, le=1_000_000)


class _Response(BaseModel):
    model_config = ConfigDict(extra="ignore")

    months: list[RecordMonth] = Field(max_length=MONTHS * 2)


@dataclass(frozen=True)
class Records:
    status: Status
    months: list[RecordMonth] = field(default_factory=list)


async def fetch(service_number: str | None) -> Records:
    """`GET {url}/consumers/{service_number}/history?months=12` with a bearer token. A failure is 'missing'."""
    settings = get_settings()
    if not settings.billing_records_live:
        return Records("not_connected")
    if not service_number:
        return Records("missing")
    url = f"{settings.billing_records_url.rstrip('/')}/consumers/{quote(service_number, safe='')}/history"
    headers = {"Authorization": f"Bearer {settings.billing_records_token}", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            response = await client.get(url, params={"months": MONTHS}, headers=headers)
            response.raise_for_status()
            body = _Response.model_validate(response.json())
    except httpx.HTTPError as exc:
        log.warning("billing records request failed: %s", type(exc).__name__)
        return Records("missing")
    except (ValueError, ValidationError):  # not JSON, or not the agreed shape
        log.warning("billing records response did not match the expected shape")
        return Records("missing")
    months = sorted({m.month: m for m in body.months}.values(), key=lambda m: m.month)
    return Records("included" if months else "missing", months)
