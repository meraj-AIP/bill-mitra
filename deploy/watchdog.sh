#!/usr/bin/env bash
# Restarts the bill-mitra container after three failed health checks in a row.
# Touches only the bill-mitra compose project in $APP_DIR; the VM runs other apps.
#
# Env: APP_DIR (default /opt/bill-mitra), HEALTH_URL (default http://127.0.0.1:8021/api/health),
#      SERVICE (default bill-mitra), MAX_FAILURES (default 3).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/bill-mitra}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8021/api/health}"
SERVICE="${SERVICE:-bill-mitra}"
MAX_FAILURES="${MAX_FAILURES:-3}"
STATE_FILE="${STATE_FILE:-$APP_DIR/run/watchdog.failures}"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) watchdog: $*"; }

mkdir -p "$(dirname "$STATE_FILE")"
failures="$(cat "$STATE_FILE" 2>/dev/null || echo 0)"
[[ "$failures" =~ ^[0-9]+$ ]] || failures=0

if curl -fsS --max-time 10 -o /dev/null "$HEALTH_URL"; then
  [ "$failures" -gt 0 ] && log "healthy again after $failures failed checks"
  echo 0 > "$STATE_FILE"
  exit 0
fi

failures=$((failures + 1))
log "health check failed ($failures of $MAX_FAILURES)"

if [ "$failures" -lt "$MAX_FAILURES" ]; then
  echo "$failures" > "$STATE_FILE"
  exit 0
fi

log "restarting service $SERVICE in $APP_DIR"
cd "$APP_DIR"
if docker compose -f compose.yml restart "$SERVICE"; then
  log "restart issued"
  echo 0 > "$STATE_FILE"
else
  log "FAILED: restart of $SERVICE"
  echo "$failures" > "$STATE_FILE"
  exit 1
fi
