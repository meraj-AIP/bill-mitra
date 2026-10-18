# 0001: Postgres behind the same SQL

**Context.** The store ran on one SQLite file. Its single writer and SQL on the event loop were the ceiling in the
load test (docs/infrastructure.md section 4), and the GCP plan needs Cloud SQL. About 180 statements in
`backend/app/store/` use SQLite's dialect: `?` placeholders, `datetime()`, `julianday()`, `json_each()`,
`INSERT OR IGNORE`, 0/1 flags and timestamps stored as text.

**Decision.** Keep one SQL text per query, written in SQLite's dialect. `DATABASE_URL` picks the database: empty is
SQLite, a `postgresql://` URL is Postgres. `app/store/pg.py` translates each statement once (cached) and creates
SQLite's date and JSON functions in Postgres with the same results, so timestamps stay in the same UTC text form and
data copies across unchanged (`app/tools/sqlite_to_postgres.py`). Each transaction takes its own pooled connection;
`tx(immediate=True)` takes a Postgres advisory lock, so queue claims keep SQLite's one-at-a-time meaning. Startup
takes another advisory lock, which also covers several instances.

**Consequences.** No repository was rewritten and SQLite keeps working for development. The test suite runs on both
(`TEST_DATABASE_URL`). Timestamps are text, not `timestamptz`, and the emulated functions cost a little more than
native SQL; a later change can move hot columns to native types one table at a time. New SQL must run on both:
compare flags with `= 1`, not as booleans, and read a `RETURNING` row before the transaction ends.
