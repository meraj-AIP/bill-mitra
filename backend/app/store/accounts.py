"""Staff and consumer accounts, server-side sessions and the audit log. The only place passwords are touched."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel

from app.config import get_settings
from app.store.db import tx

Role = Literal["admin", "officer", "consumer"]
MAX_FAILED = 5
LOCK_MINUTES = 15
MIN_PASSWORD = 8
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


class Account(BaseModel):
    id: str
    role: Role
    login: str
    name: str
    discom: str | None
    active: bool
    last_login_at: str | None
    created_at: str
    consent_version: str | None = None  # privacy notice version a consumer agreed to at sign up

    @property
    def user_id(self) -> str:
        """Conversation and bill owner key, so history follows the account across devices."""
        return f"acct:{self.id}"


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def _verify(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
    except ValueError:
        return False
    candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **_SCRYPT)
    return hmac.compare_digest(candidate.hex(), digest)


def _account(row: object) -> Account:
    data = dict(row)  # type: ignore[call-overload]
    return Account(id=data["id"], role=data["role"], login=data["login"], name=data["name"], discom=data["discom"],
                   active=bool(data["active"]), last_login_at=data["last_login_at"], created_at=data["created_at"],
                   consent_version=data.get("consent_version"))


def normalise_login(login: str) -> str:
    return login.strip().lower()


def create(role: Role, login: str, name: str, password: str, discom: str | None = None,
           created_by: str | None = None, consent_version: str | None = None) -> Account:
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"Password must be at least {MIN_PASSWORD} characters.")
    account_id = secrets.token_hex(8)
    with tx() as conn:
        if conn.execute("SELECT 1 FROM accounts WHERE login = ?", (normalise_login(login),)).fetchone():
            raise ValueError("An account with this login already exists.")
        conn.execute("INSERT INTO accounts (id, role, login, name, password_hash, discom, created_by, consent_version, "
                     "consented_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (account_id, role, normalise_login(login), name.strip(), hash_password(password), discom,
                      created_by, consent_version, _iso(_now()) if consent_version else None))
    found = get(account_id)
    assert found is not None
    return found


def get(account_id: str) -> Account | None:
    with tx() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    return _account(row) if row else None


def authenticate(login: str, password: str) -> Account | None:
    """Same answer for unknown login, wrong password, disabled or locked, so the response leaks nothing."""
    with tx() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE login = ?", (normalise_login(login),)).fetchone()
        if row is None:
            hash_password(password)  # spend the same time as a real check
            return None
        locked = row["locked_until"] and row["locked_until"] > _iso(_now())
        if locked or not row["active"] or not _verify(password, row["password_hash"]):
            if not locked:
                failed = row["failed_logins"] + 1
                until = _iso(_now() + timedelta(minutes=LOCK_MINUTES)) if failed >= MAX_FAILED else None
                conn.execute("UPDATE accounts SET failed_logins = ?, locked_until = ? WHERE id = ?",
                             (0 if until else failed, until, row["id"]))
            return None
        conn.execute("UPDATE accounts SET failed_logins = 0, locked_until = NULL, last_login_at = ? WHERE id = ?",
                     (_iso(_now()), row["id"]))
    return get(row["id"])


def start_session(account: Account) -> str:
    token = secrets.token_urlsafe(32)
    expires = _now() + timedelta(hours=get_settings().session_hours)
    with tx() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (_iso(_now()),))
        conn.execute("INSERT INTO sessions (token_hash, account_id, expires_at) VALUES (?, ?, ?)",
                     (_token_hash(token), account.id, _iso(expires)))
    return token


def _token_hash(token: str) -> str:
    # Only the hash is stored, so a copied database cannot be used to sign in.
    return hashlib.sha256(token.encode()).hexdigest()


def session_account(token: str) -> Account | None:
    with tx() as conn:
        row = conn.execute("SELECT a.* FROM sessions s JOIN accounts a ON a.id = s.account_id "
                           "WHERE s.token_hash = ? AND s.expires_at > ? AND a.active = 1",
                           (_token_hash(token), _iso(_now()))).fetchone()
    return _account(row) if row else None


def end_session(token: str) -> None:
    with tx() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


def end_all_sessions(account_id: str) -> None:
    with tx() as conn:
        conn.execute("DELETE FROM sessions WHERE account_id = ?", (account_id,))


def audit(actor_id: str | None, action: str, target: str | None = None, detail: str | None = None) -> None:
    """Who did what. Never pass passwords, tokens or a consumer's phone number in detail."""
    with tx() as conn:
        conn.execute("INSERT INTO audit_log (actor_id, action, target, detail) VALUES (?, ?, ?, ?)",
                     (actor_id, action, target, detail))


def bootstrap_admin() -> None:
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        return
    with tx() as conn:
        if conn.execute("SELECT 1 FROM accounts WHERE role = 'admin'").fetchone():
            return
    admin = create("admin", settings.bootstrap_admin_email, "Administrator", settings.bootstrap_admin_password)
    audit(None, "account.bootstrap_admin", admin.id)


class AccountPage(BaseModel):
    items: list[Account]
    total: int
    page: int
    page_size: int


class AuditEntry(BaseModel):
    id: int
    ts: str
    actor_id: str | None
    actor_name: str | None
    action: str
    target: str | None
    target_label: str | None  # the account's name when the target is an account, else the target itself
    detail: str | None


class AuditPage(BaseModel):
    items: list[AuditEntry]
    total: int
    page: int
    page_size: int


_ACCOUNT_FILTER = ("FROM accounts WHERE (:role IS NULL OR role = :role) AND (:active IS NULL OR active = :active) "
                   "AND (:q IS NULL OR login LIKE :q ESCAPE '\\' OR name LIKE :q ESCAPE '\\')")


def _like(text: str | None) -> str | None:
    if not text or not text.strip():
        return None
    escaped = text.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def list_accounts(page: int, page_size: int, role: Role | None = None, active: bool | None = None,
                  q: str | None = None) -> AccountPage:
    args = {"role": role, "active": None if active is None else int(active), "q": _like(q),
            "limit": page_size, "offset": (page - 1) * page_size}
    with tx() as conn:
        total = conn.execute("SELECT COUNT(*) " + _ACCOUNT_FILTER, args).fetchone()[0]
        rows = conn.execute("SELECT * " + _ACCOUNT_FILTER + " ORDER BY created_at DESC, rowid DESC "
                            "LIMIT :limit OFFSET :offset", args).fetchall()
    return AccountPage(items=[_account(r) for r in rows], total=total, page=page, page_size=page_size)


def update(account_id: str, *, name: str | None = None, role: Role | None = None, active: bool | None = None,
           discom: str | None = None, set_discom: bool = False) -> Account | None:
    """Only the fields passed change. `set_discom` says discom was sent, because None is a real value there."""
    with tx() as conn:
        if name is not None:
            conn.execute("UPDATE accounts SET name = ? WHERE id = ?", (name.strip(), account_id))
        if role is not None:
            conn.execute("UPDATE accounts SET role = ? WHERE id = ?", (role, account_id))
        if active is not None:
            conn.execute("UPDATE accounts SET active = ? WHERE id = ?", (int(active), account_id))
        if set_discom:
            conn.execute("UPDATE accounts SET discom = ? WHERE id = ?", (discom, account_id))
        # Only officers are scoped to a DISCOM.
        conn.execute("UPDATE accounts SET discom = NULL WHERE id = ? AND role != 'officer'", (account_id,))
    return get(account_id)


def check_password(account_id: str, password: str) -> bool:
    with tx() as conn:
        row = conn.execute("SELECT password_hash FROM accounts WHERE id = ?", (account_id,)).fetchone()
    return bool(row) and _verify(password, row["password_hash"])


def set_password(account_id: str, password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"Password must be at least {MIN_PASSWORD} characters.")
    with tx() as conn:
        conn.execute("UPDATE accounts SET password_hash = ?, failed_logins = 0, locked_until = NULL WHERE id = ?",
                     (hash_password(password), account_id))


def end_other_sessions(account_id: str, keep_token: str) -> None:
    with tx() as conn:
        conn.execute("DELETE FROM sessions WHERE account_id = ? AND token_hash != ?",
                     (account_id, _token_hash(keep_token)))


def list_audit(page: int, page_size: int, action: str | None = None) -> AuditPage:
    args = {"action": action, "limit": page_size, "offset": (page - 1) * page_size}
    with tx() as conn:
        total = conn.execute("SELECT COUNT(*) FROM audit_log WHERE :action IS NULL OR action = :action",
                             args).fetchone()[0]
        rows = conn.execute("SELECT l.*, a.name AS actor_name, COALESCE(t.name, l.target) AS target_label "
                            "FROM audit_log l LEFT JOIN accounts a ON a.id = l.actor_id "
                            "LEFT JOIN accounts t ON t.id = l.target WHERE :action IS NULL OR l.action = :action "
                            "ORDER BY l.id DESC LIMIT :limit OFFSET :offset", args).fetchall()
    return AuditPage(items=[AuditEntry(**dict(r)) for r in rows], total=total, page=page, page_size=page_size)
