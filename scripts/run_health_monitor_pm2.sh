#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/pm2_common.sh"
load_local_env
PYTHON_BIN="$(pick_python)"
cd "${ROOT_DIR}/scripts"
exec "${PYTHON_BIN}" ./pm2_health_monitor.py
