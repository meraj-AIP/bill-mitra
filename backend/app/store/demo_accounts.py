"""One sample account per built-in role, for demos. Off unless DEMO_ACCOUNTS_PASSWORD is set.

Logins are admin@aiplanet.com, demo.<role>@aiplanet.com for the other staff roles, and the demo consumer is the
DEMO_OTP_MOBILE number from the settings (never in the code). The "demo." prefix keeps them apart from real
aiplanet.com staff accounts, and ensure() only ever resets accounts it created itself.
"""

from pydantic import BaseModel

from app.config import get_settings
from app.domain import rbac
from app.store import accounts
from app.store.db import tx

STAFF: tuple[tuple[str, str, str], ...] = (
    # The owner's own admin login. It is a real account, so ensure() lists it but never resets its password.
    ("admin", "admin@aiplanet.com", "Admin"),
    ("officer", "demo.officer@aiplanet.com", "DISCOM Officer"),
    ("section_ae", "demo.sectionae@aiplanet.com", "Section AE"),
    ("call_centre", "demo.callcentre@aiplanet.com", "Call Centre Agent"),
    ("billing_approver", "demo.approver@aiplanet.com", "Billing Approver"),
    ("auditor", "demo.auditor@aiplanet.com", "Auditor"),
)


def demo_logins() -> tuple[tuple[str, str, str], ...]:
    """The staff sample logins, plus the one demo consumer when the settings name its mobile."""
    mobile = get_settings().demo_otp_mobile
    return STAFF + ((("consumer", mobile, "Consumer"),) if mobile else ())


def is_sample(login: str) -> bool:
    """An account the demo seed made itself, so a sign in code shown on screen for it exposes nobody."""
    login = accounts.normalise_login(login)
    if all(login != sample for _, sample, _ in demo_logins()):
        return False
    found = _id_for(login)
    return bool(found and found[1])


class DemoLogin(BaseModel):
    role: str
    role_name: str
    login: str


def _id_for(login: str) -> tuple[str, bool] | None:
    """The account id, and whether the demo seed made it (only those are ever reset)."""
    with tx() as conn:
        row = conn.execute("SELECT id, EXISTS (SELECT 1 FROM audit_log WHERE action = 'account.demo_seed' AND target = "
                           "accounts.id) FROM accounts WHERE login = ?", (accounts.normalise_login(login),)).fetchone()
    return (row[0], bool(row[1])) if row else None


def ensure() -> None:
    """Creates any missing sample account and puts every one back on the demo password, role and active state."""
    password = get_settings().demo_accounts_password
    if not password:
        return
    for role, login, name in demo_logins():
        found = _id_for(login)
        if found is None:
            consent = get_settings().privacy_notice_version if role == rbac.CONSUMER else None
            created = accounts.create(role, login, name, password, consent_version=consent)
            accounts.audit(None, "account.demo_seed", created.id, f"role={role}")
            continue
        account_id, seeded = found
        if not seeded:
            continue  # a real account already uses this login; never put it on the shared password
        accounts.update(account_id, name=name, role=role, active=True)
        accounts.set_password(account_id, password)


def listing() -> list[DemoLogin]:
    if not get_settings().demo_accounts_password:
        return []
    return [DemoLogin(role=role, role_name=rbac.BUILTIN[role].name, login=login) for role, login, _ in demo_logins()]
