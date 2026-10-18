#!/usr/bin/env bash
# Online backup of the Bill Mitra database (SQLite, or Postgres when DATABASE_URL is set) and media folder.
# Safe while the app runs: the SQLite backup API or pg_dump, never a plain file copy.
# Run as root (cron or sudo) because data/ is owned by the container user.
#
# Env: APP_DIR (default /opt/bill-mitra), BACKUP_DIR (default $APP_DIR/backups),
#      KEEP_DAYS (default 14), BACKUP_BUCKET (optional, gs://bucket/path),
#      PG_SERVICE (default db), the compose service that runs Postgres.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/bill-mitra}"
DATA_DIR="$APP_DIR/data"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
BACKUP_BUCKET="${BACKUP_BUCKET:-}"
PG_SERVICE="${PG_SERVICE:-db}"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) backup: $*"; }
fail() { log "FAILED: $*"; exit 1; }

# Backups hold consumer data, so nobody but root reads them.
umask 077

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
stamp="$(date -u +%Y%m%d-%H%M%S)"

# The app reads DATABASE_URL from .env: set means the data lives in Postgres, so that is what gets dumped.
database_url="$(grep -E '^DATABASE_URL=' "$APP_DIR/.env" 2>/dev/null | tail -1 | cut -d= -f2- || true)"
if [ -n "$database_url" ]; then
  db_out="$BACKUP_DIR/billmitra-pg-$stamp.dump"
  trap 'rm -f "$BACKUP_DIR"/billmitra-*.part' EXIT
  log "postgres dump to $db_out"
  docker compose -f "$APP_DIR/compose.yml" exec -T "$PG_SERVICE" sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' \
    > "$db_out.part" || fail "pg_dump"
  [ -s "$db_out.part" ] || fail "pg_dump wrote nothing"
  # A dump that pg_restore cannot list is no backup at all.
  docker compose -f "$APP_DIR/compose.yml" exec -T "$PG_SERVICE" pg_restore --list < "$db_out.part" >/dev/null \
    || fail "the dump does not read back"
  mv "$db_out.part" "$db_out"
else
[ -f "$DATA_DIR/billmitra.db" ] || fail "no database at $DATA_DIR/billmitra.db"
command -v python3 >/dev/null || fail "python3 is not installed"
command -v setpriv >/dev/null || fail "setpriv (util-linux) is not installed"

db_out="$BACKUP_DIR/billmitra-db-$stamp.sqlite3"
media_out="$BACKUP_DIR/billmitra-media-$stamp.tar.gz"

# The database is in WAL mode. Opening it as root could leave root owned -wal or -shm files that the app
# then cannot write, so the backup runs as the owner of the database file.
owner_uid="$(stat -c %u "$DATA_DIR/billmitra.db")"
owner_gid="$(stat -c %g "$DATA_DIR/billmitra.db")"
work="$(mktemp -d)"
trap 'rm -rf "$work"; rm -f "$BACKUP_DIR"/billmitra-*.part' EXIT
chown "$owner_uid:$owner_gid" "$work"

log "database backup to $db_out"
setpriv --reuid="$owner_uid" --regid="$owner_gid" --clear-groups \
  python3 - "$DATA_DIR/billmitra.db" "$work/db" <<'PY' || fail "database backup"
import sqlite3
import sys

src = sqlite3.connect(sys.argv[1], timeout=30)
dst = sqlite3.connect(sys.argv[2])
with dst:
    src.backup(dst)
ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
dst.close()
src.close()
if ok != "ok":
    sys.exit(f"integrity check: {ok}")
PY
gzip -c "$work/db" > "$db_out.gz.part"
mv "$db_out.gz.part" "$db_out.gz"
db_out="$db_out.gz"
fi

if [ -d "$DATA_DIR/media" ]; then
  log "media archive to $media_out"
  tar -czf "$media_out.part" -C "$DATA_DIR" media || fail "media archive"
  mv "$media_out.part" "$media_out"
else
  log "no media folder, skipping the media archive"
  media_out=""
fi

if [ -n "$BACKUP_BUCKET" ]; then
  command -v gsutil >/dev/null || fail "BACKUP_BUCKET is set but gsutil is not installed"
  log "copying to $BACKUP_BUCKET"
  # shellcheck disable=SC2086 # media_out is empty when there is no media, and must then vanish
  gsutil -q cp "$db_out" $media_out "${BACKUP_BUCKET%/}/" || fail "copy to bucket"
fi

log "removing local backups older than $KEEP_DAYS days"
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'billmitra-*' -mtime +"$KEEP_DAYS" -print -delete

log "done: $(basename "$db_out")${media_out:+, $(basename "$media_out")}"
