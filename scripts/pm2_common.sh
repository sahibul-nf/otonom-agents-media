#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

load_local_env() {
  if [[ -f "${ROOT_DIR}/.env.local" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${ROOT_DIR}/.env.local"
    set +a
  fi
}

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
