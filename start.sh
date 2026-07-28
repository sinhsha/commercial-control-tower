#!/usr/bin/env bash
# ── Hotel Control Tower — local dev launcher ─────────────────────────────────
# Usage: ./start.sh
# Starts backend (port 8000) and frontend dev server (port 5173) in parallel.
# Press Ctrl-C once to stop both.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RESET='\033[0m'

echo -e "${GREEN}╔══════════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}║   Hotel Commercial Control Tower — Local     ║${RESET}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${RESET}"
echo ""

# ── Backend ───────────────────────────────────────────────────────────────────
VENV="$SCRIPT_DIR/backend/.venv"
if [ ! -d "$VENV" ]; then
  echo -e "${YELLOW}Creating Python venv…${RESET}"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet -r "$SCRIPT_DIR/backend/requirements.txt"
fi

echo -e "${BLUE}▶ Backend  →  http://localhost:8000${RESET}"
echo -e "  API docs →  http://localhost:8000/docs"
"$VENV/bin/uvicorn" app.main:app \
  --host 0.0.0.0 --port 8000 --reload \
  --app-dir "$SCRIPT_DIR/backend" &
BACKEND_PID=$!

# ── Frontend ──────────────────────────────────────────────────────────────────
cd "$SCRIPT_DIR/frontend"
if [ ! -d node_modules ]; then
  echo -e "${YELLOW}Installing npm packages…${RESET}"
  npm install --silent
fi

echo -e "${BLUE}▶ Frontend →  http://localhost:5173${RESET}"
npm run dev -- --host 0.0.0.0 &
FRONTEND_PID=$!

# ── Cleanup on Ctrl-C ─────────────────────────────────────────────────────────
cleanup() {
  echo ""
  echo -e "${YELLOW}Stopping servers…${RESET}"
  kill "$BACKEND_PID"  2>/dev/null || true
  kill "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID"  2>/dev/null || true
  wait "$FRONTEND_PID" 2>/dev/null || true
  echo "Done."
}
trap cleanup INT TERM

echo ""
echo -e "${GREEN}Both servers running. Press Ctrl-C to stop.${RESET}"
wait
