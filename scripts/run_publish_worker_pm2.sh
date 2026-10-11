#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/pm2_common.sh"
load_local_env
PYTHON_BIN="$(pick_python)"
cd "${ROOT_DIR}/media-engine"

INTERVAL="${PUBLISH_WORKER_INTERVAL_SECONDS:-60}"
# Empty / "all" → every workspace (Postiz vault is per profile_id).
PROFILE_ARGS=()
if [[ -n "${PUBLISH_WORKER_PROFILE:-}" && "${PUBLISH_WORKER_PROFILE}" != "all" ]]; then
  PROFILE_ARGS=(--profile "${PUBLISH_WORKER_PROFILE}")
else
  PROFILE_ARGS=(--profile all)
fi

while true; do
  PYTHONPATH=. "$PYTHON_BIN" -m media_engine.cli publish-due \
    --env-file ../.env.local \
    --limit "${PUBLISH_WORKER_LIMIT:-5}" \
    "${PROFILE_ARGS[@]}" || true
  sleep "$INTERVAL"
done
