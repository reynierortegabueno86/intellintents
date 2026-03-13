#!/usr/bin/env bash
# ============================================================================
# deploy.sh — Production deployment for IntellIntents on AWS EC2
#
# Builds the frontend, then serves everything through FastAPI on a SINGLE port.
# No need to open two ports in the AWS Security Group.
#
# Usage:
#   ./deploy.sh [PORT]        # default: 8001
#
# Access:
#   http://<EC2_PUBLIC_IP>:<PORT>
# ============================================================================
set -euo pipefail

PORT="${1:-8001}"

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$ROOT_DIR/venv"

echo "============================================"
echo "  IntellIntents — Production Deploy"
echo "============================================"
echo ""

# ─── Python virtual environment ──────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
  echo "[1/4] Creating Python virtual environment..."
  python3 -m venv "$VENV_DIR"
else
  echo "[1/4] Virtual environment exists."
fi

echo "[2/4] Installing backend dependencies..."
"$VENV_DIR/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"

# ─── Frontend build ──────────────────────────────────────────────────────
echo "[3/4] Building frontend for production..."
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "  Installing npm dependencies..."
  (cd "$FRONTEND_DIR" && npm install --silent)
fi
(cd "$FRONTEND_DIR" && npx vite build)
echo "  Frontend built -> frontend/dist/"

# ─── Start the server ────────────────────────────────────────────────────
echo "[4/4] Starting server on port $PORT ..."
echo ""
echo "============================================"
echo "  App:  http://0.0.0.0:${PORT}"
echo "  API:  http://0.0.0.0:${PORT}/api"
echo "  Docs: http://0.0.0.0:${PORT}/docs"
echo "============================================"
echo "  Press Ctrl+C to stop"
echo ""

cd "$BACKEND_DIR"
BACKEND_PORT="$PORT" "$VENV_DIR/bin/python" -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --workers 2
