#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$ROOT_DIR/apps/api"
PYTHON_BIN="${PYTHON:-python3}"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"

api_log="$(mktemp -t ubiqx-api)"
web_log="$(mktemp -t ubiqx-web)"
api_pid=""
web_pid=""

cleanup() {
  if [[ -n "$web_pid" ]]; then
    kill "$web_pid" 2>/dev/null || true
  fi
  if [[ -n "$api_pid" ]]; then
    kill "$api_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

"$PYTHON_BIN" -m uvicorn app.main:app --app-dir "$API_DIR" --port "$API_PORT" >"$api_log" 2>&1 &
api_pid=$!

npm run dev:web >"$web_log" 2>&1 &
web_pid=$!

for _ in {1..60}; do
  if curl -fsS "http://127.0.0.1:${API_PORT}/ready" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

for _ in {1..60}; do
  if curl -fsS "http://127.0.0.1:${WEB_PORT}" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if ! curl -fsS "http://127.0.0.1:${API_PORT}/ready" >/dev/null 2>&1; then
  echo "Backend did not become ready. Logs:" >&2
  cat "$api_log" >&2
  exit 1
fi

if ! curl -fsS "http://127.0.0.1:${WEB_PORT}" >/dev/null 2>&1; then
  echo "Front end did not become ready. Logs:" >&2
  cat "$web_log" >&2
  exit 1
fi

npx playwright test

