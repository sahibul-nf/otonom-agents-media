#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/pm2_common.sh"
load_local_env
PYTHON_BIN="$(pick_python)"
cd "${ROOT_DIR}/media-engine"

# Default ~24h so Mini background watch stays calm (#60). Channel interval still gates.
INTERVAL="${WATCH_POLL_INTERVAL_SECONDS:-86400}"
PROFILE="${WATCH_POLL_PROFILE:-}"

while true; do
  if [[ -n "$PROFILE" ]]; then
    PYTHONPATH=. "$PYTHON_BIN" -m media_engine.cli watch-poll --profile "$PROFILE" || true
  else
    PYTHONPATH=. "$PYTHON_BIN" -m media_engine.cli watch-poll || true
  fi
  sleep "$INTERVAL"
done
