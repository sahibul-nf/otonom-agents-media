#!/usr/bin/env bash
# Isolated dashboard + engine for coding next to a running PM2 ops stack.
# Usage: ./scripts/dev-isolated.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export MEDIA_ENGINE_PORT="${MEDIA_ENGINE_PORT:-8766}"
export DASHBOARD_PORT="${DASHBOARD_PORT:-3101}"
export MEDIA_ENGINE_DB="${MEDIA_ENGINE_DB:-$ROOT/media-engine/data/media_engine.dev.sqlite}"
export MEDIA_ENGINE_ARTIFACTS="${MEDIA_ENGINE_ARTIFACTS:-$ROOT/media-engine/artifacts-dev}"
export MEDIA_ENGINE_API_BASE="http://127.0.0.1:${MEDIA_ENGINE_PORT}"
mkdir -p "$(dirname "$MEDIA_ENGINE_DB")" "$MEDIA_ENGINE_ARTIFACTS"
echo "[otonom-media] isolated dev → engine :${MEDIA_ENGINE_PORT} dashboard :${DASHBOARD_PORT}"
echo "[otonom-media] db=${MEDIA_ENGINE_DB}"
exec bash "${ROOT}/scripts/dev.sh"
