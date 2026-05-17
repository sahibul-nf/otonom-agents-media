#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/pm2_common.sh"
load_local_env
PYTHON_BIN="$(pick_python)"
export MEDIA_ENGINE_PORT="${MEDIA_ENGINE_PORT:-8765}"
cd "${ROOT_DIR}"
exec env PYTHONPATH=media-engine "${PYTHON_BIN}" -m media_engine.review_server
