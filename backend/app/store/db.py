"""Storage: SQLite in data_dir by default, Postgres when DATABASE_URL is set (app/store/pg.py). The repository
functions are the only SQL in the app and are written once, in SQLite's dialect, for both."""

import fcntl
import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg_pool import ConnectionPool

from app.config import get_settings
from app.domain import rbac
from app.store import pg

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
                 "audit_status": "TEXT", "overcharge": "REAL NOT NULL DEFAULT 0",
                 "source": "TEXT NOT NULL DEFAULT 'upload'"}  # upload | discom | demo


# reply_to is the consumer's WhatsApp address, kept only so an officer's answer can reach them; never returned.
_COMPLAINT_COLUMNS = {"channel": "TEXT", "reply_to": "TEXT", "updated_at": "TEXT", "assigned_to": "TEXT", "triage": "TEXT",
                      "kind": "TEXT NOT NULL DEFAULT 'general'", "unit_id": "TEXT", "section_id": "TEXT",
                      "section_name": "TEXT", "case_facts": "TEXT"}
# Complaint types (docs/complaints-contract.md). The plain service number and contact number are never stored here.
_INTAKE_COLUMNS = {"type": "TEXT", "priority": "TEXT", "due_at": "TEXT", "source": "TEXT", "raised_by": "TEXT",
                   "service_number_hash": "TEXT", "contact_hash": "TEXT", "description": "TEXT", "ownership": "TEXT",
                   "demo": "INTEGER NOT NULL DEFAULT 0"}
_MESSAGE_COLUMNS = {"media_id": "TEXT", "wa_message_id": "TEXT"}
_EVENT_COLUMNS = {"ms": "INTEGER"}
_ACCOUNT_COLUMNS = {"consent_version": "TEXT", "consented_at": "TEXT"}
_AUDIT_COLUMNS = {"unit_id": "TEXT"}
_REQUEST_COLUMNS = {"months": "TEXT"}  # JSON list of YYYY-MM on a request the system raised for earlier bills
# Automation (app/flows/automation.py): when a request was reminded, when a case went to the division above.
# proposal_checked_at: the complaint's last change the proposal rules have seen (app/flows/proposals.py).
# mobile_*: whether it came from the DISCOM's registered mobile for the connection (app/flows/sender_check.py).
_AUTOMATION_COLUMNS = (("case_requests", {"reminded_at": "TEXT"}),
                       ("complaints", {"escalated_at": "TEXT", "proposal_checked_at": "TEXT", "mobile_check": "TEXT",
                                       "mobile_source": "TEXT", "mobile_checked_at": "TEXT"}))
# Hand-off (docs/assist-contract.md section 4): who handed the complaint to its holder, with what note, and when.
# answer_message_id is the consumer message that answered a request.
_HANDOFF_COLUMNS = (("complaints", {"handed_by": "TEXT", "handoff_note": "TEXT", "handed_at": "TEXT"}),
                    ("case_requests", {"answer_message_id": "INTEGER"}))
_AUTOMATION_DDL = (
    "CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, unit_id TEXT, account_id TEXT, "
    "ticket TEXT, title TEXT NOT NULL, body TEXT NOT NULL, perm TEXT, dedupe_key TEXT UNIQUE, "
    "created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
    "CREATE INDEX IF NOT EXISTS idx_alerts_unit ON alerts(unit_id, id)",
    "CREATE INDEX IF NOT EXISTS idx_alerts_account ON alerts(account_id, id)",
    "CREATE TABLE IF NOT EXISTS alert_reads (alert_id INTEGER NOT NULL, account_id TEXT NOT NULL, "
    "PRIMARY KEY (alert_id, account_id))",
)


# A correction the rules found for a case on their own (app/flows/misread.py). The AE still decides.
_ASSIST_DDL = ("CREATE TABLE IF NOT EXISTS assist_briefs (ticket TEXT NOT NULL, kind TEXT NOT NULL, "
               "fingerprint TEXT NOT NULL, payload TEXT NOT NULL, generated_at TEXT NOT NULL, PRIMARY KEY (ticket, kind))")
_SUGGESTIONS_DDL = ("CREATE TABLE IF NOT EXISTS case_suggestions (ticket TEXT PRIMARY KEY, kind TEXT NOT NULL, "
                    "corrected_present_reading INTEGER, source_bill_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")


# Chat drafts hold a complaint being put together over several messages; deleted once it is sent or cancelled.
# Bill by service number: one-time codes, stored only as hashes.
_INTAKE_DDL = (
    "CREATE TABLE IF NOT EXISTS chat_drafts (user_id TEXT PRIMARY KEY, data TEXT NOT NULL, "
    "updated_at TEXT DEFAULT CURRENT_TIMESTAMP)",
    "CREATE TABLE IF NOT EXISTS usc_codes (user_id TEXT NOT NULL, discom TEXT NOT NULL, service_hash TEXT NOT NULL, "
    "code_hash TEXT NOT NULL, expires_at TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, locked_until TEXT, "
    "created_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (user_id, discom, service_hash))",
    "CREATE INDEX IF NOT EXISTS idx_complaints_user ON complaints(user_id, created_at)",
)
# Existing rows: the type from the kind, the priority and due date from the type, the source from the channel.
_INTAKE_BACKFILL = (
    "UPDATE complaints SET type = CASE kind WHEN 'wrong_reading' THEN 'wrong_reading' ELSE 'high_bill' END "
    "WHERE type IS NULL",
    "UPDATE complaints SET priority = 'normal' WHERE priority IS NULL",
    "UPDATE complaints SET due_at = datetime(created_at, CASE type WHEN 'wrong_reading' THEN "
    "'+' || COALESCE((SELECT decision_sla_days FROM review_policy p WHERE p.discom = complaints.discom), 3) || ' days' "
    "ELSE '+7 days' END) WHERE due_at IS NULL",
    "UPDATE complaints SET source = CASE WHEN channel = 'whatsapp' OR user_id LIKE 'wa:%' THEN 'whatsapp' "
    "WHEN kind = 'wrong_reading' THEN 'consumer_web' ELSE 'consumer_chat' END WHERE source IS NULL",
    "UPDATE complaints SET ownership = CASE WHEN bill_id IS NULL THEN 'not_needed' ELSE 'verified' END "
    "WHERE ownership IS NULL",
)
# Staff roles that gained complaints.create with complaint types. Granted once, when the type column first appears,
# so a super admin's later edits to these roles are never undone.
_CREATE_GRANTED_TO = ("officer", "section_ae")
# Roles that gained complaints.assign with the hand-off journey, granted once when handed_by first appears.
_ASSIGN_GRANTED_TO = ("call_centre", "section_ae")


def _grant(conn: sqlite3.Connection, perm: str, slugs: tuple[str, ...]) -> None:
    for slug in slugs:
        row = conn.execute("SELECT permissions FROM roles WHERE slug = ?", (slug,)).fetchone()
        perms = json.loads(row[0]) if row else None
        if perms is not None and perm not in perms:
            conn.execute("UPDATE roles SET permissions = ? WHERE slug = ?",
                         (json.dumps([p for p in rbac.PERMISSIONS if p in {*perms, perm}]), slug))


# What a unique or check constraint raises, on either database.
IntegrityError = (sqlite3.IntegrityError, psycopg.IntegrityError)


def is_postgres() -> bool:
    return bool(get_settings().database_url)


def columns(conn: Any, table: str) -> set[str]:
    """The column names of a table; the table name is always a constant, never input."""
    if isinstance(conn, pg.Conn):
        return pg.columns(conn, table)
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _migrate(conn: sqlite3.Connection) -> None:
    complaint_columns = columns(conn, "complaints")
    first_intake = "type" not in complaint_columns
    first_handoff = "handed_by" not in complaint_columns
    # Table and column names come from the constants above, never from input; DDL cannot take parameters.
    for table, added in (("bills", _BILL_COLUMNS), ("complaints", _COMPLAINT_COLUMNS), ("events", _EVENT_COLUMNS),
                           ("complaints", _INTAKE_COLUMNS),
                           ("accounts", _ACCOUNT_COLUMNS), ("complaint_messages", _MESSAGE_COLUMNS),
                           ("audit_log", _AUDIT_COLUMNS), ("case_requests", _REQUEST_COLUMNS), *_AUTOMATION_COLUMNS,
                           *_HANDOFF_COLUMNS):
        present = columns(conn, table)
        for name, kind in added.items():
            if name not in present:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")
    for statement in _AUTOMATION_DDL:
        conn.execute(statement)
    conn.execute(_SUGGESTIONS_DDL)
    conn.execute(_ASSIST_DDL)
    for statement in (*_INTAKE_DDL, *_INTAKE_BACKFILL):
        conn.execute(statement)
    if first_intake:
        _grant(conn, "complaints.create", _CREATE_GRANTED_TO)
    if first_handoff:
        _grant(conn, "complaints.assign", _ASSIGN_GRANTED_TO)
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
    _retire_super_admin(conn)
    # An admin may edit built-in roles, so a restart must not undo that. Only the two locks are re-asserted:
    # the consumer role's permissions, and role management on the admin role.
    for role in rbac.BUILTIN_ROLES:
        perms = json.dumps(rbac.default_permissions(role.slug))
        conn.execute("INSERT INTO roles (slug, name, description, permissions, builtin) VALUES (?, ?, ?, ?, 1) "
                     "ON CONFLICT(slug) DO UPDATE SET builtin = 1", (role.slug, role.name, role.description, perms))
    conn.execute("UPDATE roles SET permissions = ? WHERE slug = ?",
                 (json.dumps(rbac.default_permissions(rbac.CONSUMER)), rbac.CONSUMER))
    row = conn.execute("SELECT permissions FROM roles WHERE slug = ?", (rbac.ADMIN,)).fetchone()
    if row and "roles.manage" not in json.loads(row[0]):
        conn.execute("UPDATE roles SET permissions = ? WHERE slug = ?",
                     (json.dumps(["roles.manage", *json.loads(row[0])]), rbac.ADMIN))


def _retire_super_admin(conn: sqlite3.Connection) -> None:
    """Super admin and admin were merged into one admin role. Once, when the old role is still there: its accounts
    become admin, admin takes over its permissions (edits included), and the old role row goes."""
    old = conn.execute("SELECT permissions FROM roles WHERE slug = ?", (rbac.RETIRED_SUPER_ADMIN,)).fetchone()
    if old is None:
        return
    perms = [p for p in json.loads(old[0]) if p in rbac.PERMISSIONS]
    conn.execute("UPDATE accounts SET role = ? WHERE role = ?", (rbac.ADMIN, rbac.RETIRED_SUPER_ADMIN))
    conn.execute("UPDATE roles SET permissions = ?, name = ?, description = ? WHERE slug = ?",
                 (json.dumps(perms), rbac.BUILTIN[rbac.ADMIN].name, rbac.BUILTIN[rbac.ADMIN].description, rbac.ADMIN))
    conn.execute("DELETE FROM roles WHERE slug = ?", (rbac.RETIRED_SUPER_ADMIN,))
    conn.execute("INSERT INTO audit_log (actor_id, action, target, detail) VALUES (NULL, 'role.merge', ?, ?)",
                 (rbac.ADMIN, "super_admin merged into admin"))


def _rebuild_accounts(conn: sqlite3.Connection) -> None:
    """The first accounts table had a CHECK on role that SQLite cannot drop, so it is rebuilt once, keeping every
    id, hash and timestamp. A DISCOM officer gets a scope on that DISCOM, an officer
    without one (all DISCOMs) and every former admin a scope on both."""
    if isinstance(conn, pg.Conn):
        return  # Postgres starts from the current accounts table
    found = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'accounts'").fetchone()
    if found is None or "CHECK" not in found[0]:
        return
    conn.execute(_ACCOUNTS_DDL.replace("CREATE TABLE IF NOT EXISTS accounts (", "CREATE TABLE accounts_v2 ("))
    conn.execute(f"INSERT INTO accounts_v2 ({_ACCOUNT_COPY}) SELECT {_ACCOUNT_COPY} FROM accounts")
    conn.execute("INSERT OR IGNORE INTO account_scopes (account_id, unit_id) SELECT a.id, u.id FROM accounts a "
                 "JOIN units u ON u.kind = 'discom' AND (a.role = 'admin' OR a.discom IS NULL OR u.name = a.discom) "
                 "WHERE a.role IN ('admin', 'officer')")
    conn.execute("DROP TABLE accounts")
    conn.execute("ALTER TABLE accounts_v2 RENAME TO accounts")


# Indexes for the queries that ran as full scans on a month of target volume (see docs/infrastructure.md). Created
# after _migrate, because several columns are added there to older databases.
_PERF_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)",
    "CREATE INDEX IF NOT EXISTS idx_events_type_discom ON events(type, discom, ts)",
    "CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_complaints_discom ON complaints(discom, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_complaints_kind ON complaints(kind, status, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_complaints_holder ON complaints(assigned_to, status)",
    "CREATE INDEX IF NOT EXISTS idx_complaints_bill ON complaints(bill_id)",
    "CREATE INDEX IF NOT EXISTS idx_complaints_updated ON complaints(status, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_messages_author ON complaint_messages(ticket, author_kind, id)",
    "CREATE INDEX IF NOT EXISTS idx_messages_delivery ON complaint_messages(delivery, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_messages_wamid ON complaint_messages(wa_message_id) WHERE wa_message_id IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_messages_media ON complaint_messages(media_id) WHERE media_id IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_bills_media ON bills(media_id) WHERE media_id IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_log(target)",
    "CREATE INDEX IF NOT EXISTS idx_audit_unit ON audit_log(unit_id, id)",
    "CREATE INDEX IF NOT EXISTS idx_chat_ts ON chat_messages(ts)",
    "CREATE INDEX IF NOT EXISTS idx_seen_ts ON whatsapp_seen(ts)",
    "CREATE INDEX IF NOT EXISTS idx_complaints_mobile_due ON complaints(created_at) WHERE mobile_check IS NULL",
)


def _upgrade(conn: sqlite3.Connection) -> None:
    # One transaction, so a failed rebuild leaves the old table exactly as it was. Postgres runs all of startup in one.
    if not isinstance(conn, pg.Conn):
        conn.execute("BEGIN IMMEDIATE")
    try:
        _seed(conn)
        _rebuild_accounts(conn)
        # One open reading check per bill, even when two requests race. Here, not in the schema, because the kind
        # column is added to older databases by _migrate.
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_one_open_case ON complaints(bill_id) "
                     "WHERE kind = 'wrong_reading' AND status IN ('Open', 'In progress')")
        for statement in _PERF_INDEXES:
            conn.execute(statement)
        # Here, not at the top: these modules import this one.
        from app.store import (
            account_connections,
            extract_jobs,
            otp_codes,
            outbox,
            proposals,
            sender_checks,
            voice_cache,
            wa_queue,
        )

        for queue in (wa_queue, outbox, extract_jobs, proposals, voice_cache, sender_checks, otp_codes, account_connections):
            queue.ensure(conn)
        if isinstance(conn, pg.Conn):
            for table in pg.ROWID_TABLES:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS rowid BIGINT GENERATED BY DEFAULT AS IDENTITY")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


_lock = threading.Lock()
_conn: sqlite3.Connection | None = None
_pg: pg.Conn | None = None  # autocommit, for startup and for callers outside tx()
_pool: ConnectionPool | None = None
# How long a statement waits for another worker's write lock. SQLite does the waiting (with its own backoff), so a
# locked database is retried for this long before "database is locked" is raised.
BUSY_TIMEOUT_MS = 5000
# During startup one worker may build ~17 indexes on a fresh database; the others wait their turn this long.
STARTUP_BUSY_MS = 30000
_starting = False  # this process holds the startup lock


@contextmanager
def startup_lock() -> Iterator[None]:
    """Several uvicorn workers start at once. Schema, migration and every startup write (bootstrap, retention sweep,
    queue resume) run while holding a blocking lock, so workers take turns and the later ones find the work done.
    SQLite takes a file lock, Postgres an advisory lock, which also covers several instances. Re-entrant within the
    process, because connection() takes it too. A worker that dies releases it."""
    global _starting
    if _starting:
        yield
        return
    if is_postgres():
        with pg.connect(get_settings().database_url) as raw, pg.advisory(raw, pg.STARTUP_LOCK):
            _starting = True
            try:
                yield
            finally:
                _starting = False
        return
    with open(get_settings().data_dir / "migrate.lock", "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        _starting = True
        try:
            if _conn is not None:
                _conn.execute(f"PRAGMA busy_timeout={STARTUP_BUSY_MS}")
            yield
        finally:
            _starting = False
            if _conn is not None:
                _conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
            fcntl.flock(handle, fcntl.LOCK_UN)


def _build(conn: Any) -> None:
    conn.executescript(_SCHEMA)
    _migrate(conn)
    _upgrade(conn)


def _postgres() -> pg.Conn:
    global _pg, _pool
    if _pg is None:
        with startup_lock():
            settings = get_settings()
            conn = pg.Conn(pg.connect(settings.database_url))
            try:
                with conn.raw.transaction():
                    conn.raw.execute(pg.FUNCTIONS)
                    _build(conn)
            except BaseException:
                conn.raw.close()
                raise
            _pool = pg.pool(settings.database_url, settings.database_pool_size)
            _pg = conn
    return _pg


def connection() -> Any:
    """The shared SQLite connection, or on Postgres an autocommit connection. Opening it builds or upgrades the
    schema. Repository code uses tx()."""
    global _conn
    if is_postgres():
        return _postgres()
    if _conn is None:
        with startup_lock():
            path = get_settings().data_dir / "billmitra.db"
            conn = sqlite3.connect(path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                # Commit without an fsync per statement (safe with WAL: a crash can lose the last commit, never
                # corrupt), and keep hot pages in memory. The startup lock sets the normal busy timeout when it ends.
                conn.execute(f"PRAGMA busy_timeout={STARTUP_BUSY_MS}")
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA temp_store=MEMORY")
                conn.execute("PRAGMA cache_size=-65536")
                _build(conn)
            except BaseException:
                conn.close()
                raise
            _conn = conn
    return _conn


def ts(moment: datetime | None = None) -> str:
    """The same text form as SQLite's CURRENT_TIMESTAMP (UTC), so the two compare as strings."""
    return (moment or datetime.now(UTC)).astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def tx(immediate: bool = False) -> Iterator[Any]:
    """A transaction. Deferred by default: a read never takes the write lock, and a write takes it at its first
    statement, waiting up to BUSY_TIMEOUT_MS. `immediate` takes the write lock up front, for the short claim paths
    that read and then write and must not interleave with another worker. On Postgres each transaction has its own
    pooled connection, and `immediate` takes the shared claim lock, so claims still run one at a time."""
    if is_postgres():
        _postgres()
        assert _pool is not None
        with _pool.connection() as raw:
            if immediate:
                raw.execute("SELECT pg_advisory_xact_lock(%s)", (pg.CLAIM_LOCK,))
            yield pg.Conn(raw)
        return
    with _lock:
        conn = connection()
        if immediate:
            conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def maintain() -> None:
    """Daily. SQLite: fold the write-ahead log back into the database file. Both: refresh the planner's statistics
    (autovacuum does it too on Postgres; a daily pass keeps the console's plans current after a busy day)."""
    if is_postgres():
        connection().execute("ANALYZE")
        return
    with tx() as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("PRAGMA optimize")


def purge_mock_data() -> None:
    """Earlier builds seeded invented pilot activity and pre-read sample bills. Only real activity is kept.
    Demo complaints (demo = 1, app/tools/demo_complaints.py) are not mock data in this sense and stay."""
    with tx() as conn:
        conn.execute("DELETE FROM events WHERE simulated = 1")
        conn.execute("DELETE FROM complaints WHERE simulated = 1")
        conn.execute("DELETE FROM bills WHERE json_extract(extraction, '$.source') = 'sample'")


def reset_for_tests() -> None:
    global _conn, _pg, _pool
    if _conn is not None:
        _conn.close()
    if _pool is not None:
        _pool.close()
    if _pg is not None:
        _pg.raw.close()
    _conn, _pg, _pool = None, None, None
