"""Sign in, register, sign out. The session token only ever travels in the httpOnly cookie."""

from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.api.deps import COOKIE, AnyAccount
from app.config import get_settings
from app.core.ratelimit import per_ip
from app.flows import mobile_auth
from app.store import account_connections, accounts, demo_accounts
from app.store.account_connections import Connection
from app.store.accounts import MIN_PASSWORD, Account

router = APIRouter(prefix="/api/auth", tags=["auth"])

WRONG = "Login or password is wrong."
SessionCookie = Annotated[str | None, Cookie(alias=COOKIE)]


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=200)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=MIN_PASSWORD, max_length=200)


def clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="lax", secure=get_settings().cookie_secure)


def _sign_in(response: Response, account: Account) -> None:
    settings = get_settings()
    response.set_cookie(COOKIE, accounts.start_session(account), max_age=settings.session_hours * 3600, path="/",
                        httponly=True, samesite="lax", secure=settings.cookie_secure)


# Per-login lockout stops guessing one account; this stops spraying many accounts from one address.
@router.post("/login", response_model=Account, dependencies=[Depends(per_ip("login", 20))])
async def login(body: LoginRequest, response: Response) -> Account:
    account = accounts.authenticate(body.login, body.password)
    if account is None:
        raise HTTPException(401, WRONG)
    _sign_in(response, account)
    accounts.audit(account.id, "auth.login", account.id)
    return account


@router.get("/demo-accounts", response_model=list[demo_accounts.DemoLogin])
def demo_logins() -> list[demo_accounts.DemoLogin]:
    """Sample logins for a demo server; empty everywhere else. Passwords are never sent."""
    return demo_accounts.listing()


MOBILE = r"^[6-9]\d{9}$"
Discom = Literal["TGSPDCL", "TGNPDCL"]


class CodeChannels(BaseModel):
    channels: list[mobile_auth.Channel]
    on_screen: bool  # development: the code is shown on the page instead of being sent
    whatsapp_number: str | None  # where phones are sent to chat instead of signing up here


class CodeRequest(BaseModel):
    mobile: str = Field(pattern=MOBILE)
    purpose: mobile_auth.Purpose
    channel: mobile_auth.Channel
    discom: Discom | None = None  # needed to sign up: the number is checked with that DISCOM
    language: Literal["te", "en", "hi", "ur"] = "en"


class CodeSent(BaseModel):
    channel: mobile_auth.Channel
    expires_in: int
    resend_in: int
    connections: int | None  # how many connections the DISCOM holds for the number, on sign up
    dev_code: str | None  # development only


class SignUp(BaseModel):
    mobile: str = Field(pattern=MOBILE)
    code: str = Field(pattern=r"^\d{6}$")
    name: str = Field(min_length=1, max_length=80)
    discom: Discom
    consent: Literal[True]


class SignIn(BaseModel):
    mobile: str = Field(pattern=MOBILE)
    code: str = Field(pattern=r"^\d{6}$")


START_REFUSED = {
    "not_registered": (404, "This number is not registered with {discom}. Use the mobile number on your electricity "
                            "connection, or update it at your DISCOM office."),
    "rate_limited": (429, "Too many codes for this number. Please wait an hour and try again."),
    "locked": (429, "Too many wrong codes. Please wait 30 minutes and try again."),
    "unavailable": (503, "Codes cannot be sent this way right now. Try the other option, or try again later."),
    "not_sent": (502, "The code could not be sent. Try the other option, or try again in a minute."),
    "demo_only": (403, "This demo server cannot send codes yet, so it signs in only the sample consumer and new numbers. "
                       "Please use Bill Mitra on WhatsApp."),
}
VERIFY_REFUSED = {
    "wrong": (400, "That code is not right, or it has expired. Check it, or ask for a new one."),
    "locked": (429, "Too many wrong codes. Please wait 30 minutes and try again."),
    "no_account": (404, "There is no account for this number yet. Sign up first."),
    "inactive": (403, "This account is switched off. Please contact your DISCOM."),
}


@router.get("/otp/channels", response_model=CodeChannels)
def code_channels() -> CodeChannels:
    return CodeChannels(channels=mobile_auth.channels(), on_screen=mobile_auth.on_screen(),
                        whatsapp_number=get_settings().whatsapp_display_number or None)


@router.post("/otp/start", response_model=CodeSent, dependencies=[Depends(per_ip("otp-start", 10))])
async def start_code(body: CodeRequest) -> CodeSent:
    if body.purpose == "signup" and body.discom is None:
        raise HTTPException(422, "Choose your DISCOM.")
    started = await mobile_auth.start(body.mobile, body.purpose, body.channel, body.discom, body.language)
    if started.status != "sent":
        code, message = START_REFUSED[started.status]
        raise HTTPException(code, message.format(discom=body.discom))
    return CodeSent(channel=started.channel or body.channel, expires_in=mobile_auth.CODE_MINUTES * 60, resend_in=30,
                    connections=started.connections, dev_code=started.dev_code)


def _finish(verified: mobile_auth.Verified, response: Response) -> Account:
    if verified.status != "ok" or verified.account is None:
        code, message = VERIFY_REFUSED[verified.status if verified.status != "ok" else "inactive"]
        raise HTTPException(code, message)
    accounts.signed_in(verified.account.id)
    _sign_in(response, verified.account)
    accounts.audit(verified.account.id, "auth.login", verified.account.id, "mobile code")
    return verified.account


@router.post("/otp/signup", response_model=Account, dependencies=[Depends(per_ip("otp-verify", 20))])
async def sign_up_with_code(body: SignUp, response: Response) -> Account:
    return _finish(await mobile_auth.sign_up(body.mobile, body.code, body.name.strip(), body.discom), response)


@router.post("/otp/login", response_model=Account, dependencies=[Depends(per_ip("otp-verify", 20))])
async def sign_in_with_code(body: SignIn, response: Response) -> Account:
    return _finish(mobile_auth.sign_in(body.mobile, body.code), response)


@router.get("/connections", response_model=list[Connection])
def my_connections(account: AnyAccount) -> list[Connection]:
    """The connections the DISCOM holds for this consumer's mobile, masked, as found when they signed up."""
    return account_connections.for_account(account.id)


@router.post("/logout", status_code=204)
async def logout(response: Response, token: SessionCookie = None) -> None:
    if token:
        accounts.end_session(token)
    clear_cookie(response)


@router.get("/me", response_model=Account)
def me(account: AnyAccount) -> Account:
    return account


@router.post("/password", status_code=204)
async def change_password(body: PasswordChange, account: AnyAccount, token: SessionCookie = None) -> None:
    if not accounts.check_password(account.id, body.current_password):
        raise HTTPException(400, "The current password is wrong.")
    accounts.set_password(account.id, body.new_password)
    accounts.end_other_sessions(account.id, token or "")
    accounts.audit(account.id, "account.password_change", account.id)
