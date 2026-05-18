#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT="${MEDIA_ENGINE_PORT:-8765}"
FRONTEND_PORT="${DASHBOARD_PORT:-3000}"

pick_python() {
  if [[ -n "${MEDIA_ENGINE_PYTHON:-}" && -x "${MEDIA_ENGINE_PYTHON}" ]]; then
    echo "${MEDIA_ENGINE_PYTHON}"
    return
  fi
  if [[ -x "/tmp/media-engine-tools-py313/bin/python" ]]; then
    echo "/tmp/media-engine-tools-py313/bin/python"
    return
  fi
  command -v python3
}

is_port_open() {
  local port="$1"
  python3 - "$port" <<'PY'
import socket, sys
port = int(sys.argv[1])
sock = socket.socket()
sock.settimeout(0.6)
try:
    sock.connect(("127.0.0.1", port))
except OSError:
    sys.exit(1)
finally:
    sock.close()
PY
}

backend_pid_for_port() {
  local port="$1"
  lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null | head -n 1 || true
}

backend_has_required_endpoints() {
  local port="$1"
  python3 - "$port" <<'PY'
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

port = int(sys.argv[1])
required = ("review", "schedule", "publish-attempts")
for endpoint in required:
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/{endpoint}", timeout=2) as response:
            if response.status >= 400:
                sys.exit(1)
            json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        sys.exit(1)
sys.exit(0)
PY
}

start_backend() {
  (
    cd "${ROOT_DIR}"
    MEDIA_ENGINE_PORT="${BACKEND_PORT}" PYTHONPATH=media-engine "${PYTHON_BIN}" -m media_engine.review_server
  ) &
  BACKEND_PID=$!
}

PYTHON_BIN="$(pick_python)"

cleanup() {
  local exit_code=$?
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "${FRONTEND_PID}" >/dev/null 2>&1 || true
  fi
  wait >/dev/null 2>&1 || true
  exit "${exit_code}"
}

trap cleanup INT TERM EXIT

echo "[otonom-media] starting backend on http://127.0.0.1:${BACKEND_PORT}"
if is_port_open "${BACKEND_PORT}"; then
  if backend_has_required_endpoints "${BACKEND_PORT}"; then
    echo "[otonom-media] backend already running on port ${BACKEND_PORT}, reusing it"
    BACKEND_PID=""
  else
    STALE_BACKEND_PID="$(backend_pid_for_port "${BACKEND_PORT}")"
    echo "[otonom-media] backend on port ${BACKEND_PORT} is stale; restarting pid=${STALE_BACKEND_PID:-unknown}"
    if [[ -n "${STALE_BACKEND_PID:-}" ]]; then
      kill "${STALE_BACKEND_PID}" >/dev/null 2>&1 || true
      sleep 0.5
    fi
    start_backend
  fi
else
  start_backend
fi

echo "[otonom-media] starting frontend on http://127.0.0.1:${FRONTEND_PORT}"
if is_port_open "${FRONTEND_PORT}"; then
  echo "[otonom-media] frontend already running on port ${FRONTEND_PORT}, reusing it"
  FRONTEND_PID=""
else
  (
    cd "${ROOT_DIR}/apps/dashboard"
    MEDIA_ENGINE_API_BASE="http://127.0.0.1:${BACKEND_PORT}" \
      npx next dev --hostname 127.0.0.1 --port "${FRONTEND_PORT}"
  ) &
  FRONTEND_PID=$!
fi

echo "[otonom-media] backend pid=${BACKEND_PID}, frontend pid=${FRONTEND_PID}"
echo "[otonom-media] press Ctrl+C to stop both services"

while true; do
  if [[ -n "${BACKEND_PID}" ]] && ! kill -0 "${BACKEND_PID}" >/dev/null 2>&1; then
    wait "${BACKEND_PID}" || true
    exit 1
  fi
  if [[ -n "${FRONTEND_PID}" ]] && ! kill -0 "${FRONTEND_PID}" >/dev/null 2>&1; then
    wait "${FRONTEND_PID}" || true
    exit 1
  fi
  if [[ -z "${BACKEND_PID}" && -z "${FRONTEND_PID}" ]]; then
    exit 0
  fi
  sleep 1
done
