#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT="${MEDIA_ENGINE_PORT:-8765}"
FRONTEND_PORT="${DASHBOARD_PORT:-3100}"
# Default: free ports and start fresh. Set DEV_REUSE=1 to keep healthy existing processes.
DEV_REUSE="${DEV_REUSE:-0}"

pick_python() {
  if [[ -n "${MEDIA_ENGINE_PYTHON:-}" && -x "${MEDIA_ENGINE_PYTHON}" ]]; then
    echo "${MEDIA_ENGINE_PYTHON}"
    return
  fi
  if [[ -x "${ROOT_DIR}/media-engine/.venv-tools/bin/python" ]]; then
    echo "${ROOT_DIR}/media-engine/.venv-tools/bin/python"
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

pids_for_port() {
  local port="$1"
  lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true
}

backend_pid_for_port() {
  local port="$1"
  pids_for_port "${port}" | head -n 1 || true
}

kill_port_listeners() {
  local port="$1"
  local label="$2"
  local pids
  pids="$(pids_for_port "${port}")"
  if [[ -z "${pids}" ]]; then
    return 0
  fi
  echo "[otonom-media] stopping ${label} on :${port} (pid ${pids//$'\n'/, })"
  # shellcheck disable=SC2086
  kill ${pids} >/dev/null 2>&1 || true
  sleep 0.4
  pids="$(pids_for_port "${port}")"
  if [[ -n "${pids}" ]]; then
    # shellcheck disable=SC2086
    kill -9 ${pids} >/dev/null 2>&1 || true
    sleep 0.2
  fi
}

backend_has_required_endpoints() {
  local port="$1"
  python3 - "$port" <<'PY'
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

port = int(sys.argv[1])
required = ("review", "schedule", "publish-attempts", "connections", "explainers", "path-a-jobs")
for endpoint in required:
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/{endpoint}", timeout=2) as response:
            if response.status >= 400:
                sys.exit(1)
            json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        sys.exit(1)

try:
    req = Request(
        f"http://127.0.0.1:{port}/api/connection-test",
        data=b'{"platform":"youtube_shorts"}',
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=2) as response:
        if response.status >= 500:
            sys.exit(1)
        json.loads(response.read().decode("utf-8"))
except HTTPError as exc:
    if exc.code not in (400, 401, 409):
        sys.exit(1)
    try:
        json.loads(exc.read().decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        sys.exit(1)
except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
    sys.exit(1)

# POST-only routes: 400/404-with-specific-error means route exists; generic "not found" is stale.
try:
    req = Request(
        f"http://127.0.0.1:{port}/api/remove-pause",
        data=b'{"candidate_id":"","pause_at_ms":0,"gap_ms":500}',
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=2) as response:
        json.loads(response.read().decode("utf-8"))
except HTTPError as exc:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        sys.exit(1)
    if exc.code == 404 and str(payload.get("error", "")).lower() == "not found":
        sys.exit(1)
    if exc.code not in (400, 404):
        sys.exit(1)
except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
    sys.exit(1)

try:
    req = Request(
        f"http://127.0.0.1:{port}/api/remove-pauses-batch",
        data=b'{"candidate_id":"","min_gap_ms":500,"dry_run":true}',
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=2) as response:
        json.loads(response.read().decode("utf-8"))
except HTTPError as exc:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        sys.exit(1)
    if exc.code == 404 and str(payload.get("error", "")).lower() == "not found":
        sys.exit(1)
    if exc.code not in (400, 404):
        sys.exit(1)
except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
    sys.exit(1)
sys.exit(0)
PY
}

start_backend() {
  (
    cd "${ROOT_DIR}"
    MEDIA_ENGINE_PORT="${BACKEND_PORT}" MEDIA_ENGINE_PYTHON="${PYTHON_BIN}" PYTHONPATH=media-engine "${PYTHON_BIN}" -m media_engine.review_server
  ) &
  BACKEND_PID=$!
}

start_frontend() {
  if [[ ! -x "${ROOT_DIR}/apps/dashboard/node_modules/.bin/next" ]]; then
    echo "[otonom-media] missing apps/dashboard/node_modules — run: (cd apps/dashboard && npm install)" >&2
    exit 1
  fi
  (
    cd "${ROOT_DIR}/apps/dashboard"
    MEDIA_ENGINE_API_BASE="http://127.0.0.1:${BACKEND_PORT}" \
      ./node_modules/.bin/next dev --hostname 127.0.0.1 --port "${FRONTEND_PORT}"
  ) &
  FRONTEND_PID=$!
}

PYTHON_BIN="$(pick_python)"

# Production PM2 owns these ports on the ops checkout. Isolated dev uses 8766/3101.
if [[ "${ALLOW_STEAL_OPS_PORTS:-0}" != "1" ]]; then
  ops_backend="${OTONOM_OPS_ENGINE_PORT:-8765}"
  ops_frontend="${OTONOM_OPS_DASHBOARD_PORT:-3100}"
  if [[ "${BACKEND_PORT}" == "${ops_backend}" || "${FRONTEND_PORT}" == "${ops_frontend}" ]]; then
    if is_port_open "${ops_backend}" || is_port_open "${ops_frontend}"; then
      echo "[otonom-media] refusing to take ops ports :${ops_backend}/:${ops_frontend} while something is already listening." >&2
      echo "[otonom-media] production PM2 uses this checkout and these ports. Use a worktree:" >&2
      echo "  git worktree add ../otonom-agents-media-dev && cd ../otonom-agents-media-dev && npm run dev:isolated" >&2
      echo "[otonom-media] override only if you intend to replace ops: ALLOW_STEAL_OPS_PORTS=1 npm run dev" >&2
      exit 1
    fi
  fi
fi

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
if [[ "${DEV_REUSE}" == "1" ]] && is_port_open "${BACKEND_PORT}" && backend_has_required_endpoints "${BACKEND_PORT}"; then
  echo "[otonom-media] backend already running on port ${BACKEND_PORT}, reusing it (DEV_REUSE=1)"
  BACKEND_PID=""
else
  kill_port_listeners "${BACKEND_PORT}" "backend"
  start_backend
fi

echo "[otonom-media] starting frontend on http://127.0.0.1:${FRONTEND_PORT}"
if [[ "${DEV_REUSE}" == "1" ]] && is_port_open "${FRONTEND_PORT}"; then
  echo "[otonom-media] frontend already running on port ${FRONTEND_PORT}, reusing it (DEV_REUSE=1)"
  FRONTEND_PID=""
else
  kill_port_listeners "${FRONTEND_PORT}" "frontend"
  start_frontend
fi

echo "[otonom-media] backend pid=${BACKEND_PID:-reused}, frontend pid=${FRONTEND_PID:-reused}"
echo "[otonom-media] press Ctrl+C to stop processes started by this script"
if [[ "${DEV_REUSE}" != "1" ]]; then
  echo "[otonom-media] tip: DEV_REUSE=1 npm run dev  → keep healthy existing servers"
fi

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
