"""Copy a SQLite database into Postgres, once, when a server moves to DATABASE_URL.

    DATABASE_URL=postgresql://... python -m app.tools.sqlite_to_postgres backend/var/billmitra.db

Stop the app first, so nothing writes to either side during the copy. The tool builds the Postgres schema, refuses
when Postgres already holds accounts, complaints, bills or events, and then copies every table in one transaction:
either all of it lands or none of it does. Rows keep their ids, timestamps and insertion order, and each id sequence
is moved past the copied ids. It prints row counts per table, never row contents.
"""

import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.store import db, pg

# Postgres holding any of these means it is already in use; copying over it would mix two histories.
_IN_USE = ("accounts", "complaints", "bills", "events")
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def _plain(names: list[str]) -> list[str]:
    """Table and column names go into the SQL text, so only plain lower case names from our own schema pass."""
    bad = [n for n in names if not _IDENT.match(n)]
    if bad:
        raise SystemExit(f"Unexpected table or column names: {bad}")
    return names


def _tables(source: sqlite3.Connection) -> list[str]:
    return [r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type = 'table' "
                                         "AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def _target_columns(raw: Any, table: str) -> dict[str, str]:
    rows = raw.execute("SELECT column_name, data_type FROM information_schema.columns "
                       "WHERE table_schema = current_schema() AND table_name = %s", (table,))
    return {r[0]: r[1] for r in rows}


def _value(value: Any, kind: str) -> Any:
    # SQLite keeps whatever it was given; Postgres's integer columns take only whole numbers.
    if kind == "bigint" and isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _copy_table(source: sqlite3.Connection, raw: Any, table: str) -> int:
    target = _target_columns(raw, table)
    names = _plain([r[1] for r in source.execute(f"PRAGMA table_info({table})") if r[1] in target])
    if not target or not names:
        print(f"  {table}: skipped, not in the Postgres schema")
        return 0
    extra = ["rowid"] if "rowid" in target else []
    select = ", ".join([*names, *extra])
    kinds = [target[n] for n in [*names, *extra]]
    count = 0
    with raw.cursor().copy(f"COPY {table} ({select}) FROM STDIN") as copy:
        for row in source.execute(f"SELECT {select} FROM {table} ORDER BY rowid"):
            copy.write_row([_value(v, k) for v, k in zip(row, kinds, strict=True)])
            count += 1
    return count


def _move_sequences(raw: Any) -> None:
    rows = raw.execute("SELECT table_name, column_name FROM information_schema.columns "
                       "WHERE table_schema = current_schema() AND is_identity = 'YES'").fetchall()
    for table, column in rows:
        raw.execute(f"SELECT setval(pg_get_serial_sequence('{table}', '{column}'), "
                    f"COALESCE((SELECT MAX({column}) FROM {table}), 0) + 1, false)")


def copy(path: Path) -> dict[str, int]:
    if not db.is_postgres():
        raise SystemExit("Set DATABASE_URL to the Postgres database to copy into.")
    if not path.is_file():
        raise SystemExit(f"No SQLite database at {path}.")
    db.connection()  # builds the Postgres schema
    source = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    counts: dict[str, int] = {}
    try:
        with pg.connect(get_settings().database_url, autocommit=False) as raw:
            for table in _IN_USE:
                if raw.execute(f"SELECT EXISTS (SELECT 1 FROM {table})").fetchone()[0]:
                    raise SystemExit(f"Postgres already has rows in {table}; copy only into a new database.")
            tables = _plain([t for t in _tables(source) if _target_columns(raw, t)])
            # Startup seeded roles, DISCOM units and policies; the copy brings the source's own, edits included.
            raw.execute(f"TRUNCATE {', '.join(tables)}")
            for table in tables:
                counts[table] = _copy_table(source, raw, table)
            _move_sequences(raw)
            raw.commit()
            raw.execute("ANALYZE")  # fresh planner statistics, or the first queries plan for empty tables
            raw.commit()
    finally:
        source.close()
    return counts


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    for table, count in copy(Path(argv[0])).items():
        print(f"  {table}: {count}")
    print("Copied. Start the app with DATABASE_URL set.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
