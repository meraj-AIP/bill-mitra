"""SQLite storage for the pilot. The repository functions are the only SQL in the app,
so moving to Postgres means replacing this module, not the flows."""

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from app.config import get_settings
from app.domain import rbac

_ACCOUNTS_DDL = """CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY, role TEXT NOT NULL, login TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    password_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, failed_logins INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT, last_login_at TEXT, created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    consent_version TEXT, consented_at TEXT
);
"""

_SCHEMA = _ACCOUNTS_DDL + """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY, channel TEXT NOT NULL, language TEXT NOT NULL DEFAULT 'te',
    current_bill_id TEXT, awaiting TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS bills (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, service_number TEXT, extraction TEXT NOT NULL,
    media_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS consents (
    service_number TEXT NOT NULL, user_id TEXT NOT NULL, granted INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (service_number, user_id)
);
CREATE TABLE IF NOT EXISTS complaints (
    ticket TEXT PRIMARY KEY, user_id TEXT NOT NULL, bill_id TEXT, service_masked TEXT,
    bill_month TEXT, discom TEXT, issue TEXT NOT NULL, amount REAL, status TEXT NOT NULL,
    language TEXT, simulated INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT DEFAULT CURRENT_TIMESTAMP, channel TEXT,
    type TEXT NOT NULL, language TEXT, intent TEXT, audit_status TEXT, units INTEGER,
    amount REAL, discom TEXT, section TEXT, simulated INTEGER NOT NULL DEFAULT 0, ms INTEGER
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL, expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT DEFAULT CURRENT_TIMESTAMP, actor_id TEXT,
    action TEXT NOT NULL, target TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS complaint_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ticket TEXT NOT NULL, author_kind TEXT NOT NULL,
    author_id TEXT, body TEXT NOT NULL, delivery TEXT NOT NULL, delivery_note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_complaint_messages ON complaint_messages(ticket, id);
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, ts TEXT DEFAULT CURRENT_TIMESTAMP,
    sender TEXT NOT NULL CHECK (sender IN ('user', 'bot')), body TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_messages(user_id, id);
CREATE INDEX IF NOT EXISTS idx_sessions_account ON sessions(account_id);
CREATE TABLE IF NOT EXISTS whatsapp_seen (
    message_id TEXT PRIMARY KEY, ts TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type, ts);
CREATE INDEX IF NOT EXISTS idx_bills_user ON bills(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_complaints_created ON complaints(created_at);
CREATE TABLE IF NOT EXISTS roles (
    slug TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', permissions TEXT NOT NULL,
    builtin INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS units (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('discom', 'circle', 'division', 'subdivision', 'section', 'ero')),
    name TEXT NOT NULL, code TEXT, discom TEXT NOT NULL, parent_id TEXT, ero_id TEXT,
    aliases TEXT NOT NULL DEFAULT '[]', active INTEGER NOT NULL DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_units_parent ON units(parent_id);
CREATE INDEX IF NOT EXISTS idx_units_ero ON units(ero_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_units_code ON units(discom, code) WHERE code IS NOT NULL;
-- Every normalised name a section answers to (its own and its aliases), one owner per DISCOM.
CREATE TABLE IF NOT EXISTS section_names (
    discom TEXT NOT NULL, norm TEXT NOT NULL, unit_id TEXT NOT NULL, PRIMARY KEY (discom, norm)
);
CREATE INDEX IF NOT EXISTS idx_section_names_unit ON section_names(unit_id);
CREATE TABLE IF NOT EXISTS account_scopes (
    account_id TEXT NOT NULL, unit_id TEXT NOT NULL, PRIMARY KEY (account_id, unit_id)
);
CREATE INDEX IF NOT EXISTS idx_scopes_unit ON account_scopes(unit_id);
CREATE TABLE IF NOT EXISTS unmapped_sections (
    discom TEXT NOT NULL, norm TEXT NOT NULL, name TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0,
    last_seen TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (discom, norm)
);
CREATE TABLE IF NOT EXISTS review_policy (
    discom TEXT PRIMARY KEY, ae_limit REAL, custom_needs_approval INTEGER NOT NULL DEFAULT 0,
    spike_ratio REAL NOT NULL DEFAULT 2.0, spike_min_increase REAL NOT NULL DEFAULT 500,
    min_history_months INTEGER NOT NULL DEFAULT 3, decision_sla_days INTEGER NOT NULL DEFAULT 3,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS case_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ticket TEXT NOT NULL, kind TEXT NOT NULL, note TEXT,
    status TEXT NOT NULL DEFAULT 'open', requested_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, answered_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_case_requests ON case_requests(ticket, status);
CREATE TABLE IF NOT EXISTS review_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ticket TEXT NOT NULL, bill_id TEXT, kind TEXT NOT NULL,
    status TEXT NOT NULL, original_amount REAL NOT NULL, revised_amount REAL NOT NULL, reduction REAL NOT NULL,
    corrected_present_reading REAL, corrected_units INTEGER, reason_code TEXT NOT NULL, note TEXT NOT NULL,
    evidence TEXT NOT NULL, proposed_by TEXT NOT NULL, proposed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    decided_by TEXT, decided_at TEXT, decision_note TEXT, applied_by TEXT, applied_at TEXT, billing_ref TEXT,
    revision INTEGER
);
CREATE INDEX IF NOT EXISTS idx_decisions_ticket ON review_decisions(ticket, id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_decisions_revision ON review_decisions(bill_id, revision)
    WHERE revision IS NOT NULL;
-- Bills the consumer sent for a case after the system asked for those months. One bill per month per case.
CREATE TABLE IF NOT EXISTS case_bills (
    ticket TEXT NOT NULL, month TEXT NOT NULL, request_id INTEGER NOT NULL, bill_id TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (ticket, month)
);
CREATE INDEX IF NOT EXISTS idx_case_bills_bill ON case_bills(bill_id);
-- What the DISCOM billing system returned when the case was reported: a snapshot, so the evidence never shifts.
CREATE TABLE IF NOT EXISTS case_records (
    ticket TEXT PRIMARY KEY, status TEXT NOT NULL, months TEXT NOT NULL DEFAULT '[]',
    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# Columns added after the first release; SQLite has no ADD COLUMN IF NOT EXISTS.
_BILL_COLUMNS = {"bill_month": "TEXT", "units": "INTEGER", "total_payable": "REAL", "discom": "TEXT",
                 "audit_status": "TEXT", "overcharge": "REAL NOT NULL DEFAULT 0"}


# reply_to is the consumer's WhatsApp address, kept only so an officer's answer can reach them; never returned.
_COMPLAINT_COLUMNS = {"channel": "TEXT", "reply_to": "TEXT", "updated_at": "TEXT", "assigned_to": "TEXT", "triage": "TEXT",
                      "kind": "TEXT NOT NULL DEFAULT 'general'", "unit_id": "TEXT", "section_id": "TEXT",
                      "section_name": "TEXT", "case_facts": "TEXT"}
_MESSAGE_COLUMNS = {"media_id": "TEXT"}
_EVENT_COLUMNS = {"ms": "INTEGER"}
_ACCOUNT_COLUMNS = {"consent_version": "TEXT", "consented_at": "TEXT"}
_AUDIT_COLUMNS = {"unit_id": "TEXT"}
_REQUEST_COLUMNS = {"months": "TEXT"}  # JSON list of YYYY-MM on a request the system raised for earlier bills


def _migrate(conn: sqlite3.Connection) -> None:
    # Table and column names come from the constants above, never from input; DDL cannot take parameters.
    for table, columns in (("bills", _BILL_COLUMNS), ("complaints", _COMPLAINT_COLUMNS), ("events", _EVENT_COLUMNS),
                           ("accounts", _ACCOUNT_COLUMNS), ("complaint_messages", _MESSAGE_COLUMNS),
                           ("audit_log", _AUDIT_COLUMNS), ("case_requests", _REQUEST_COLUMNS)):
        present = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, kind in columns.items():
            if name not in present:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")
    conn.commit()


DISCOM_UNITS = {"TGSPDCL": "u_tgspdcl", "TGNPDCL": "u_tgnpdcl"}
_ACCOUNT_COPY = ("id, role, login, name, password_hash, active, failed_logins, locked_until, last_login_at, created_by, "
                 "created_at, consent_version, consented_at")


def _seed(conn: sqlite3.Connection) -> None:
    """Runs on every start: the two DISCOMs, the built-in roles with their fixed permissions, default policies."""
    for discom, unit_id in DISCOM_UNITS.items():
        conn.execute("INSERT OR IGNORE INTO units (id, kind, name, discom) VALUES (?, 'discom', ?, ?)",
                     (unit_id, discom, discom))
        conn.execute("INSERT OR IGNORE INTO review_policy (discom) VALUES (?)", (discom,))
    # A super admin may edit built-in roles, so a restart must not undo that. Only the two locks are re-asserted:
    # the consumer role's permissions, and role management on the super admin role.
    for role in rbac.BUILTIN_ROLES:
        perms = json.dumps(rbac.default_permissions(role.slug))
        conn.execute("INSERT INTO roles (slug, name, description, permissions, builtin) VALUES (?, ?, ?, ?, 1) "
                     "ON CONFLICT(slug) DO UPDATE SET builtin = 1", (role.slug, role.name, role.description, perms))
    conn.execute("UPDATE roles SET permissions = ? WHERE slug = ?",
                 (json.dumps(rbac.default_permissions(rbac.CONSUMER)), rbac.CONSUMER))
    row = conn.execute("SELECT permissions FROM roles WHERE slug = ?", (rbac.SUPER_ADMIN,)).fetchone()
    if row and "roles.manage" not in json.loads(row[0]):
        conn.execute("UPDATE roles SET permissions = ? WHERE slug = ?",
                     (json.dumps(["roles.manage", *json.loads(row[0])]), rbac.SUPER_ADMIN))


def _rebuild_accounts(conn: sqlite3.Connection) -> None:
    """The first accounts table had a CHECK on role that SQLite cannot drop, so it is rebuilt once, keeping every
    id, hash and timestamp. admin becomes super_admin; a DISCOM officer gets a scope on that DISCOM, an officer
    without one (all DISCOMs) and every former admin a scope on both."""
    found = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'accounts'").fetchone()
    if found is None or "CHECK" not in found[0]:
        return
    conn.execute(_ACCOUNTS_DDL.replace("CREATE TABLE IF NOT EXISTS accounts (", "CREATE TABLE accounts_v2 ("))
    mapped = _ACCOUNT_COPY.replace("role,", "CASE role WHEN 'admin' THEN 'super_admin' ELSE role END,", 1)
    conn.execute(f"INSERT INTO accounts_v2 ({_ACCOUNT_COPY}) SELECT {mapped} FROM accounts")
    conn.execute("INSERT OR IGNORE INTO account_scopes (account_id, unit_id) SELECT a.id, u.id FROM accounts a "
                 "JOIN units u ON u.kind = 'discom' AND (a.role = 'admin' OR a.discom IS NULL OR u.name = a.discom) "
                 "WHERE a.role IN ('admin', 'officer')")
    conn.execute("DROP TABLE accounts")
    conn.execute("ALTER TABLE accounts_v2 RENAME TO accounts")


def _upgrade(conn: sqlite3.Connection) -> None:
    # One transaction, so a failed rebuild leaves the old table exactly as it was.
    conn.execute("BEGIN IMMEDIATE")
    try:
        _seed(conn)
        _rebuild_accounts(conn)
        # One open reading check per bill, even when two requests race. Here, not in the schema, because the kind
        # column is added to older databases by _migrate.
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_one_open_case ON complaints(bill_id) "
                     "WHERE kind = 'wrong_reading' AND status IN ('Open', 'In progress')")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        path = get_settings().data_dir / "billmitra.db"
        _conn = sqlite3.connect(path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.executescript(_SCHEMA)
        _migrate(_conn)
        _upgrade(_conn)
    return _conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    with _lock:
        conn = connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def purge_mock_data() -> None:
    """Earlier builds seeded invented pilot activity and pre-read sample bills. Only real activity is kept."""
    with tx() as conn:
        conn.execute("DELETE FROM events WHERE simulated = 1")
        conn.execute("DELETE FROM complaints WHERE simulated = 1")
        conn.execute("DELETE FROM bills WHERE json_extract(extraction, '$.source') = 'sample'")


def reset_for_tests() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
    _conn = None
