#!/usr/bin/env bash
# Bill Mitra runner.
#   ./run.sh       install what is missing, build the web app once, serve everything on :8000
#   ./run.sh dev   API with reload on :8000 and the Vite dev server on :5173
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/backend/.venv"
PORT="${PORT:-8000}"
MODE="${1:-start}"

PY="$(command -v python3 || command -v python)"

# Windows venvs keep executables in Scripts/, everywhere else in bin/.
venv_bin() {
  if [ -d "$VENV/Scripts" ]; then echo "$VENV/Scripts"; else echo "$VENV/bin"; fi
}

setup_backend() {
  if [ ! -x "$VENV/bin/python" ] && [ ! -x "$VENV/Scripts/python.exe" ]; then
    echo "Creating virtualenv in backend/.venv"
    "$PY" -m venv "$VENV"
  fi
  BIN="$(venv_bin)"
  local req="$ROOT/backend/requirements.txt"
  [ "$MODE" = "dev" ] && req="$ROOT/backend/requirements-dev.txt"
  local stamp="$VENV/.installed-$(basename "$req")"
  if [ ! -f "$stamp" ] || [ "$req" -nt "$stamp" ] || [ "$ROOT/backend/requirements.txt" -nt "$stamp" ]; then
    echo "Installing backend packages"
    "$BIN/python" -m pip install --quiet --upgrade pip
    "$BIN/python" -m pip install --quiet -r "$req"
    touch "$stamp"
  fi
}

setup_frontend() {
  if [ ! -d "$ROOT/frontend/node_modules" ]; then
    echo "Installing frontend packages"
    if [ -f "$ROOT/frontend/package-lock.json" ]; then
      (cd "$ROOT/frontend" && npm ci)
    else
      (cd "$ROOT/frontend" && npm install)
    fi
  fi
}

case "$MODE" in
  start)
    setup_backend
    if [ ! -d "$ROOT/frontend/dist" ]; then
      setup_frontend
      echo "Building the web app"
      (cd "$ROOT/frontend" && npm run build)
    fi
    echo "Bill Mitra on http://localhost:$PORT"
    cd "$ROOT/backend"
    exec "$BIN/uvicorn" app.main:app --host 0.0.0.0 --port "$PORT" --no-access-log --proxy-headers
    ;;
  dev)
    setup_backend
    setup_frontend
    cd "$ROOT/backend"
    "$BIN/uvicorn" app.main:app --reload --host 0.0.0.0 --port 8000 &
    API_PID=$!
    trap 'kill $API_PID 2>/dev/null || true' EXIT INT TERM
    echo "API on http://localhost:8000, web app on http://localhost:5173"
    cd "$ROOT/frontend"
    npm run dev
    ;;
  *)
    echo "Usage: ./run.sh [dev]" >&2
    exit 1
    ;;
esac
