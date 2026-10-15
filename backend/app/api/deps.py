"""Who is calling. Every protected route depends on `require`; the session lives in an httpOnly cookie."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException

from app.config import get_settings
from app.store import accounts
from app.store.accounts import Account, Role

COOKIE = get_settings().session_cookie


def current_account(token: Annotated[str | None, Cookie(alias=COOKIE)] = None) -> Account:
    account = accounts.session_account(token) if token else None
    if account is None:
        raise HTTPException(401, "Please sign in.")
    return account


def require(*roles: Role) -> Callable[[Account], Account]:
    def check(account: Annotated[Account, Depends(current_account)]) -> Account:
        if roles and account.role not in roles:
            raise HTTPException(403, "Your account cannot do this.")
        return account

    return check


Staff = Annotated[Account, Depends(require("admin", "officer"))]
Admin = Annotated[Account, Depends(require("admin"))]
AnyAccount = Annotated[Account, Depends(require())]
