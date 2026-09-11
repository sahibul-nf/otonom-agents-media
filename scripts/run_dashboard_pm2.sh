#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pm2_common.sh
source "${SCRIPT_DIR}/pm2_common.sh"
load_local_env
export MEDIA_ENGINE_PORT="${MEDIA_ENGINE_PORT:-8765}"
export DASHBOARD_PORT="${DASHBOARD_PORT:-3100}"
export MEDIA_ENGINE_API_BASE="http://127.0.0.1:${MEDIA_ENGINE_PORT}"
cd "${ROOT_DIR}/apps/dashboard"

MODE="${DASHBOARD_MODE:-production}"
if [[ "${MODE}" == "dev" ]]; then
  exec npx next dev --hostname 127.0.0.1 --port "${DASHBOARD_PORT}"
fi

if [[ ! -d .next ]]; then
  echo "[otonom-media] building dashboard for production (next start)..."
  npx next build
fi
exec npx next start --hostname 127.0.0.1 --port "${DASHBOARD_PORT}"
