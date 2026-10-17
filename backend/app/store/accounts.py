"""Staff and consumer accounts, server-side sessions and the audit log. The only place passwords are touched."""

import hashlib
import hmac
import json
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel

from app.config import get_settings
from app.domain import rbac
from app.store import units
from app.store.db import DISCOM_UNITS, tx
from app.store.units import Conflict, Scope

MAX_FAILED = 5
LOCK_MINUTES = 15
MIN_PASSWORD = 8
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


class Account(BaseModel):
    id: str
    role: str
    role_name: str
    permissions: list[str]
    scopes: list[Scope]
    login: str
    name: str
    discom: str | None  # kept for older clients: the one DISCOM all scopes sit in, else None (all or none)
    active: bool
    last_login_at: str | None
    created_at: str
    consent_version: str | None = None  # privacy notice version a consumer agreed to at sign up

    @property
    def user_id(self) -> str:
        """Conversation and bill owner key, so history follows the account across devices."""
        return f"acct:{self.id}"

    def can(self, *perms: str) -> bool:
        """True when the account holds any of the permissions."""
        return any(p in self.permissions for p in perms)

    @property
    def is_global(self) -> bool:
        """Scoped on every DISCOM, so nothing in the hierarchy is outside its reach."""
        return set(DISCOM_UNITS.values()) <= {s.unit_id for s in self.scopes}


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


_SELECT = ("SELECT a.*, r.name AS role_name, r.permissions AS role_permissions FROM accounts a "
           "LEFT JOIN roles r ON r.slug = a.role")


def _accounts(rows: list[sqlite3.Row]) -> list[Account]:
    scopes = units.scopes_for([r["id"] for r in rows])
    out = []
    for row in rows:
        mine = scopes.get(row["id"], [])
        discoms = {s.discom for s in mine}
        out.append(Account(id=row["id"], role=row["role"], role_name=row["role_name"] or row["role"],
                           permissions=json.loads(row["role_permissions"] or "[]"), scopes=mine, login=row["login"],
                           name=row["name"], discom=discoms.pop() if len(discoms) == 1 else None,
                           active=bool(row["active"]), last_login_at=row["last_login_at"],
                           created_at=row["created_at"], consent_version=row["consent_version"]))
    return out


def _one(row: sqlite3.Row | None) -> Account | None:
    return _accounts([row])[0] if row else None


def default_scopes(discom: str | None) -> list[str]:
    """The old single DISCOM field as scopes: one DISCOM, or both when it was empty."""
    return [DISCOM_UNITS[discom]] if discom else list(DISCOM_UNITS.values())


def normalise_login(login: str) -> str:
    return login.strip().lower()


def create(role: str, login: str, name: str, password: str, discom: str | None = None,
           created_by: str | None = None, consent_version: str | None = None,
           scopes: list[str] | None = None) -> Account:
    """Staff without explicit scopes get the old DISCOM rule (one, or both). Consumers never carry scopes."""
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"Password must be at least {MIN_PASSWORD} characters.")
    unit_ids = [] if role == rbac.CONSUMER else (scopes if scopes is not None else default_scopes(discom))
    if role != rbac.CONSUMER and not unit_ids:
        raise ValueError("A staff account needs at least one scope.")
    account_id = secrets.token_hex(8)
    with tx() as conn:
        if not conn.execute("SELECT 1 FROM roles WHERE slug = ?", (role,)).fetchone():
            raise ValueError("Unknown role.")
        if conn.execute("SELECT 1 FROM accounts WHERE login = ?", (normalise_login(login),)).fetchone():
            raise Conflict("An account with this login already exists.")
        conn.execute("INSERT INTO accounts (id, role, login, name, password_hash, created_by, consent_version, "
                     "consented_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (account_id, role, normalise_login(login), name.strip(), hash_password(password),
                      created_by, consent_version, _iso(_now()) if consent_version else None))
        units.set_scopes(conn, account_id, unit_ids)
    found = get(account_id)
    assert found is not None
    return found


def get(account_id: str) -> Account | None:
    with tx() as conn:
        row = conn.execute(f"{_SELECT} WHERE a.id = ?", (account_id,)).fetchone()
    return _one(row)


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
        row = conn.execute(f"{_SELECT} JOIN sessions s ON s.account_id = a.id "
                           "WHERE s.token_hash = ? AND s.expires_at > ? AND a.active = 1",
                           (_token_hash(token), _iso(_now()))).fetchone()
    return _one(row)


def end_session(token: str) -> None:
    with tx() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


def end_all_sessions(account_id: str) -> None:
    with tx() as conn:
        conn.execute("DELETE FROM sessions WHERE account_id = ?", (account_id,))


def audit(actor_id: str | None, action: str, target: str | None = None, detail: str | None = None,
          unit_id: str | None = None) -> None:
    """Who did what. Never pass passwords, tokens, a full service number or a phone number in detail.
    unit_id places the entry in the hierarchy, so a scoped auditor sees what happened in their area."""
    with tx() as conn:
        conn.execute("INSERT INTO audit_log (actor_id, action, target, detail, unit_id) VALUES (?, ?, ?, ?, ?)",
                     (actor_id, action, target, detail, unit_id))


def bootstrap_admin() -> None:
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        return
    with tx() as conn:
        if conn.execute("SELECT 1 FROM accounts WHERE role = ?", (rbac.ADMIN,)).fetchone():
            return
    admin = create(rbac.ADMIN, settings.bootstrap_admin_email, "Administrator", settings.bootstrap_admin_password)
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


_ACCOUNT_FILTER = ("FROM accounts a WHERE (:role IS NULL OR a.role = :role) AND (:active IS NULL OR a.active = :active) "
                   "AND (:q IS NULL OR a.login LIKE :q ESCAPE '\\' OR a.name LIKE :q ESCAPE '\\')")
# A scoped manager sees staff who sit wholly inside their scope; consumers carry no scope, so only global ones.
_WITHIN = (" AND (:viewer IS NULL OR (EXISTS (SELECT 1 FROM account_scopes s WHERE s.account_id = a.id) "
           "AND NOT EXISTS (SELECT 1 FROM account_scopes s WHERE s.account_id = a.id AND s.unit_id NOT IN "
           f"{units.covered_sql(':viewer')})))")


def _like(text: str | None) -> str | None:
    if not text or not text.strip():
        return None
    escaped = text.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def list_accounts(page: int, page_size: int, role: str | None = None, active: bool | None = None,
                  q: str | None = None, viewer: str | None = None) -> AccountPage:
    """`viewer` limits the page to accounts inside that account's scope; None means every account."""
    args = {"role": role, "active": None if active is None else int(active), "q": _like(q), "viewer": viewer,
            "limit": page_size, "offset": (page - 1) * page_size}
    with tx() as conn:
        total = conn.execute("SELECT COUNT(*) " + _ACCOUNT_FILTER + _WITHIN, args).fetchone()[0]
        ids = [r[0] for r in conn.execute("SELECT a.id " + _ACCOUNT_FILTER + _WITHIN +
                                          " ORDER BY a.created_at DESC, a.rowid DESC LIMIT :limit OFFSET :offset",
                                          args)]
        rows = {r["id"]: r for r in conn.execute(f"{_SELECT} WHERE a.id IN ({','.join('?' * len(ids))})", ids)}
    return AccountPage(items=_accounts([rows[i] for i in ids]), total=total, page=page, page_size=page_size)


def within(viewer: Account, target: Account) -> bool:
    """A staff target sits wholly in the viewer's scope; a consumer only in a global viewer's."""
    if viewer.is_global:
        return True
    return bool(target.scopes) and all(units.covers(viewer.id, s.unit_id) for s in target.scopes)


def update(account_id: str, *, name: str | None = None, role: str | None = None, active: bool | None = None,
           scopes: list[str] | None = None) -> Account | None:
    """Only the fields passed change."""
    with tx() as conn:
        if name is not None:
            conn.execute("UPDATE accounts SET name = ? WHERE id = ?", (name.strip(), account_id))
        if role is not None:
            conn.execute("UPDATE accounts SET role = ? WHERE id = ?", (role, account_id))
        if active is not None:
            conn.execute("UPDATE accounts SET active = ? WHERE id = ?", (int(active), account_id))
        if scopes is not None:
            units.set_scopes(conn, account_id, scopes)
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


def list_audit(page: int, page_size: int, action: str | None = None, viewer: str | None = None) -> AuditPage:
    """`viewer` limits the log to entries placed in that account's scope; None means the whole log."""
    where = ("WHERE (:action IS NULL OR l.action = :action) AND "
             f"(:viewer IS NULL OR l.unit_id IN {units.covered_sql(':viewer')})")
    args = {"action": action, "viewer": viewer, "limit": page_size, "offset": (page - 1) * page_size}
    with tx() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM audit_log l {where}", args).fetchone()[0]
        rows = conn.execute("SELECT l.id, l.ts, l.actor_id, l.action, l.target, l.detail, a.name AS actor_name, "
                            "COALESCE(t.name, l.target) AS target_label FROM audit_log l "
                            "LEFT JOIN accounts a ON a.id = l.actor_id LEFT JOIN accounts t ON t.id = l.target "
                            f"{where} ORDER BY l.id DESC LIMIT :limit OFFSET :offset", args).fetchall()
    return AuditPage(items=[AuditEntry(**dict(r)) for r in rows], total=total, page=page, page_size=page_size)
