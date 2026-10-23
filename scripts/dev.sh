#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x backend/.venv/bin/uvicorn || ! -d frontend/node_modules ]]; then
  echo 'Run ./scripts/setup.sh first.' >&2
  exit 1
fi
api_pid=''
web_pid=''
cleanup() {
  trap - EXIT INT TERM
  [[ -z "$api_pid" ]] || kill "$api_pid" 2>/dev/null || true
  [[ -z "$web_pid" ]] || kill "$web_pid" 2>/dev/null || true
  wait || true
}
trap cleanup EXIT INT TERM
(cd backend && exec .venv/bin/uvicorn atlas.main:app --host 127.0.0.1 --port 8000) &
api_pid=$!
(cd frontend && exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173 --strictPort) &
web_pid=$!
wait -n "$api_pid" "$web_pid"
