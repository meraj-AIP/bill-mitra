#!/usr/bin/env bash
# Backup, pull, rebuild and wait for the app to report healthy.
# Run as the deploy user (needs passwordless sudo for docker and backup.sh), or as root.
#
# Env: APP_DIR (default /opt/bill-mitra), HEALTH_URL (default http://127.0.0.1:8021/api/health),
#      WAIT_SECONDS (default 180).
set -euo pipefail

# Everything sits in main so bash has read the whole script before git pull can replace it.
main() {
  local app_dir="${APP_DIR:-/opt/bill-mitra}"
  local health_url="${HEALTH_URL:-http://127.0.0.1:8021/api/health}"
  local wait_seconds="${WAIT_SECONDS:-180}"
  local here sudo=""
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  [ "$(id -u)" -eq 0 ] || sudo="sudo"

  log "backup before deploy"
  $sudo env APP_DIR="$app_dir" BACKUP_BUCKET="${BACKUP_BUCKET:-}" "$here/backup.sh" || fail "backup, deploy stopped"

  cd "$app_dir"
  log "pulling $(git -C src rev-parse --short HEAD)"
  git -C src pull --ff-only || fail "git pull"
  log "now at $(git -C src rev-parse --short HEAD), rebuilding"
  $sudo docker compose -f compose.yml up -d --build || fail "docker compose up"

  log "waiting up to ${wait_seconds}s for $health_url"
  local deadline=$((SECONDS + wait_seconds))
  until curl -fsS --max-time 5 -o /dev/null "$health_url"; do
    [ "$SECONDS" -lt "$deadline" ] || fail "not healthy after ${wait_seconds}s, check: $sudo docker compose -f $app_dir/compose.yml logs --tail 100"
    sleep 5
  done
  log "healthy, deploy done"
}

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) deploy: $*"; }
fail() { log "FAILED: $*"; exit 1; }

main "$@"
exit
