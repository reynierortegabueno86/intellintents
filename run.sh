#!/usr/bin/env bash
set -euo pipefail

# ─── Defaults ───────────────────────────────────────────────
BACKEND_PORT="${1:-8001}"
FRONTEND_PORT="${2:-5174}"

# ─── Paths ──────────────────────────────────────────────────
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$ROOT_DIR/venv"

# ─── Cleanup on exit ───────────────────────────────────────
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "Shutting down..."
  [ -n "$BACKEND_PID" ]  && kill "$BACKEND_PID"  2>/dev/null && echo "  Backend stopped"
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null && echo "  Frontend stopped"
  wait 2>/dev/null
  echo "Done."
}
trap cleanup EXIT INT TERM

# ─── Preflight checks ──────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

echo "Installing backend dependencies..."
"$VENV_DIR/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Installing frontend dependencies..."
  (cd "$FRONTEND_DIR" && npm install --silent)
fi

# ─── Update vite proxy to point at the chosen backend port ─
VITE_CFG="$FRONTEND_DIR/vite.config.js"
if grep -q "localhost" "$VITE_CFG"; then
  sed -i.bak "s|http://localhost:[0-9]*|http://localhost:${BACKEND_PORT}|" "$VITE_CFG"
  rm -f "${VITE_CFG}.bak"
fi

# ─── Start backend ─────────────────────────────────────────
echo ""
echo "Starting backend on port $BACKEND_PORT ..."
(
  cd "$BACKEND_DIR"
  BACKEND_PORT="$BACKEND_PORT" "$VENV_DIR/bin/python" run.py
) &
BACKEND_PID=$!

# Wait for backend to be ready
echo -n "  Waiting for backend"
for _ in $(seq 1 30); do
  if curl -sf "http://localhost:${BACKEND_PORT}/" >/dev/null 2>&1; then
    echo " ready"
    break
  fi
  echo -n "."
  sleep 1
done

# ─── Start frontend ────────────────────────────────────────
echo "Starting frontend on port $FRONTEND_PORT ..."
(cd "$FRONTEND_DIR" && npx vite --port "$FRONTEND_PORT") &
FRONTEND_PID=$!

# ─── Ready ──────────────────────────────────────────────────
echo ""
echo "============================================"
echo "  IntellIntents is running"
echo "  Backend  : http://localhost:${BACKEND_PORT}"
echo "  Frontend : http://localhost:${FRONTEND_PORT}"
echo "  API docs : http://localhost:${BACKEND_PORT}/docs"
echo "============================================"
echo "  Press Ctrl+C to stop"
echo ""

wait
