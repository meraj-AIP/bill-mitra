"""Get my bill with my service number (web). Start sends a one-time code to the mobile the DISCOM holds for the
connection; verify checks it and returns the bill report. Start answers the same whether or not the number exists."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.api.deps import require_perm
from app.config import get_settings
from app.core.hashing import clean_service_number
from app.flows import report, usc
from app.store.accounts import Account

router = APIRouter(prefix="/api/bills/by-usc", tags=["bill dashboard"])

Owner = Annotated[Account, Depends(require_perm("self.bills"))]
Language = Literal["te", "en", "hi", "ur"]
UNAVAILABLE = "Getting a bill by service number is not available yet. Please upload a photo of your bill."
ERRORS: dict[str, tuple[int, str]] = {
    "unavailable": (503, UNAVAILABLE),
    "rate_limited": (429, "Too many requests for this connection. Please try again in an hour."),
    "wrong": (400, "That code is not right or has expired. Please ask for a new code."),
    "locked": (429, "Too many wrong codes. Please try again after 30 minutes."),
    "no_bill": (404, "We could not get a bill for this connection. Please upload a photo of your bill."),
}
STARTED = ("If this connection has a mobile number registered with the DISCOM, we have sent a 6 digit code to it. "
           "The code works for 5 minutes.")


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


def _fail(status: str) -> HTTPException:
    code, detail = ERRORS[status]
    return HTTPException(code, detail)


@router.post("/start", response_model=Started, status_code=202)
async def start(body: UscRequest, account: Owner, language: Language = "te") -> Started:
    status = await usc.start(account.user_id, body.discom, body.service_number, language)
    if status in ERRORS:
        raise _fail(status)
    return Started(message=STARTED, expires_in_seconds=usc.CODE_MINUTES * 60,
                   code_required=not get_settings().dev_bills)


@router.post("/verify", response_model=report.BillReport)
async def verify(body: UscVerify, account: Owner, language: Language = "te") -> report.BillReport:
    if body.code is None and not get_settings().dev_bills:
        raise HTTPException(422, "Enter the 6 digit code.")
    result = await usc.verify(account.user_id, body.discom, body.service_number, body.code, language)
    if result.status == "wrong":
        left = usc.attempts_left(account.user_id, body.discom, body.service_number)
        raise HTTPException(400, {"message": ERRORS["wrong"][1], "attempts_left": left})
    if result.bill_report is None:
        raise _fail(result.status if result.status in ERRORS else "no_bill")
    return result.bill_report
