"""SQLite storage for the pilot. The repository functions are the only SQL in the app,
so moving to Postgres means replacing this module, not the flows."""

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from app.config import get_settings

_SCHEMA = """
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
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY, role TEXT NOT NULL CHECK (role IN ('admin', 'officer', 'consumer')),
    login TEXT NOT NULL UNIQUE, name TEXT NOT NULL, password_hash TEXT NOT NULL,
    discom TEXT, active INTEGER NOT NULL DEFAULT 1, failed_logins INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT, last_login_at TEXT, created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    consent_version TEXT, consented_at TEXT
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
"""

# Columns added after the first release; SQLite has no ADD COLUMN IF NOT EXISTS.
_BILL_COLUMNS = {"bill_month": "TEXT", "units": "INTEGER", "total_payable": "REAL", "discom": "TEXT",
                 "audit_status": "TEXT", "overcharge": "REAL NOT NULL DEFAULT 0"}


# reply_to is the consumer's WhatsApp address, kept only so an officer's answer can reach them; never returned.
_COMPLAINT_COLUMNS = {"channel": "TEXT", "reply_to": "TEXT", "updated_at": "TEXT", "assigned_to": "TEXT", "triage": "TEXT"}
_MESSAGE_COLUMNS = {"media_id": "TEXT"}
_EVENT_COLUMNS = {"ms": "INTEGER"}
_ACCOUNT_COLUMNS = {"consent_version": "TEXT", "consented_at": "TEXT"}


def _migrate(conn: sqlite3.Connection) -> None:
    # Table and column names come from the constants above, never from input; DDL cannot take parameters.
    for table, columns in (("bills", _BILL_COLUMNS), ("complaints", _COMPLAINT_COLUMNS), ("events", _EVENT_COLUMNS),
                           ("accounts", _ACCOUNT_COLUMNS), ("complaint_messages", _MESSAGE_COLUMNS)):
        present = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, kind in columns.items():
            if name not in present:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")
    conn.commit()


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
