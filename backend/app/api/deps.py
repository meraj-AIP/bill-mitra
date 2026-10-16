"""Who is calling and what they may do. Routes depend on `require_perm`; the session lives in an httpOnly cookie.

Access is always a permission plus, for anything tied to a place, a unit scope. Role names never appear here.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException

from app.config import get_settings
from app.store import accounts, units
from app.store.accounts import Account

COOKIE = get_settings().session_cookie
FORBIDDEN = "Your account cannot do this."


def current_account(token: Annotated[str | None, Cookie(alias=COOKIE)] = None) -> Account:
    account = accounts.session_account(token) if token else None
    if account is None:
        raise HTTPException(401, "Please sign in.")
    return account


def require_perm(*perms: str) -> Callable[[Account], Account]:
    """Signed in and holding at least one of `perms`. No perms means any signed-in account."""

    def check(account: Annotated[Account, Depends(current_account)]) -> Account:
        if perms and not account.can(*perms):
            raise HTTPException(403, FORBIDDEN)
        return account

    return check


def in_scope(account: Account, unit_id: str | None) -> bool:
    """A global account reaches every unit; anyone else only the units their scopes cover."""
    return account.is_global or units.covers(account.id, unit_id)


def viewer(account: Account) -> str | None:
    """The account id store queries filter by, or None when the account sees everything."""
    return None if account.is_global else account.id


AnyAccount = Annotated[Account, Depends(require_perm())]
# Own bills and the chat: consumers, and staff previewing the Assistant page.
ChatUser = Annotated[Account, Depends(require_perm("self.bills", "chat.preview"))]
