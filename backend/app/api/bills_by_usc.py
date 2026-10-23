"""Get my bill with my service number (web). Start sends a one-time code to the mobile the DISCOM holds for the
connection; verify checks it and returns the bill report. Start answers the same whether or not the number exists.
Refusals are in the consumer's language."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.api.deps import require_perm
from app.config import get_settings
from app.core.errors import api_error
from app.core.hashing import clean_service_number
from app.domain.conversation.lang import text
from app.flows import report, usc
from app.store.accounts import Account

router = APIRouter(prefix="/api/bills/by-usc", tags=["bill dashboard"])

Owner = Annotated[Account, Depends(require_perm("self.bills"))]
Language = Literal["te", "en", "hi", "ur"]
# Status, error code and lang key per refusal.
ERRORS: dict[str, tuple[int, str, str]] = {
    "unavailable": (503, "usc_unavailable", "err_usc_unavailable"),
    "rate_limited": (429, "rate_limited", "err_usc_rate_limited"),
    "wrong": (400, "code_wrong", "err_usc_wrong"),
    "locked": (429, "code_locked", "err_usc_locked"),
    "no_bill": (404, "no_bill", "err_usc_no_bill"),
}


class UscRequest(BaseModel):
    discom: Literal["TGSPDCL", "TGNPDCL"]
    service_number: str = Field(max_length=24)

    @field_validator("service_number")
    @classmethod
    def _usc(cls, value: str) -> str:
        cleaned = clean_service_number(value)
        if cleaned is None:
            raise ValueError("A service number is 5 to 16 digits.")
        return cleaned


class UscVerify(UscRequest):
    code: str | None = Field(default=None, pattern=r"^\d{6}$")


class Started(BaseModel):
    status: Literal["accepted"] = "accepted"
    message: str
    expires_in_seconds: int
    code_required: bool  # false only on a development server, where no code is sent


def _fail(status: str, language: str, **extras: object) -> HTTPException:
    code, key, message = ERRORS[status]
    return api_error(code, key, text(language, message, **extras), **extras)


@router.post("/start", response_model=Started, status_code=202)
async def start(body: UscRequest, account: Owner, language: Language = "te") -> Started:
    status = await usc.start(account.user_id, body.discom, body.service_number, language)
    if status in ERRORS:
        raise _fail(status, language)
    return Started(message=text(language, "usc_code_started"), expires_in_seconds=usc.CODE_MINUTES * 60,
                   code_required=not get_settings().dev_bills)


@router.post("/verify", response_model=report.BillReport)
async def verify(body: UscVerify, account: Owner, language: Language = "te") -> report.BillReport:
    if body.code is None and not get_settings().dev_bills:
        raise api_error(422, "code_needed", text(language, "err_usc_code_needed"))
    result = await usc.verify(account.user_id, body.discom, body.service_number, body.code, language)
    if result.status == "wrong":
        raise _fail("wrong", language,
                    attempts_left=usc.attempts_left(account.user_id, body.discom, body.service_number))
    if result.bill_report is None:
        raise _fail(result.status if result.status in ERRORS else "no_bill", language)
    return result.bill_report
