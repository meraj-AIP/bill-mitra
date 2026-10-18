"""Sign in, register, sign out. The session token only ever travels in the httpOnly cookie."""

from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.api.deps import COOKIE, AnyAccount
from app.config import get_settings
from app.core.ratelimit import per_ip
from app.store import accounts, demo_accounts
from app.store.accounts import MIN_PASSWORD, Account

router = APIRouter(prefix="/api/auth", tags=["auth"])

WRONG = "Login or password is wrong."
SessionCookie = Annotated[str | None, Cookie(alias=COOKIE)]


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=200)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    mobile: str = Field(pattern=r"^[6-9]\d{9}$")
    password: str = Field(min_length=MIN_PASSWORD, max_length=200)
    consent: Literal[True]  # the privacy notice was shown and accepted; anything else is a 422


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


@router.post("/register", response_model=Account, dependencies=[Depends(per_ip("register", 5))])
async def register(body: RegisterRequest, response: Response) -> Account:
    try:
        account = accounts.create("consumer", body.mobile, body.name, body.password,
                                  consent_version=get_settings().privacy_notice_version)
    except ValueError as exc:  # length is already validated above, so this is a taken mobile
        raise HTTPException(409, "This mobile number is already registered. Please sign in.") from exc
    _sign_in(response, account)
    accounts.audit(account.id, "account.register", account.id)
    return account


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
