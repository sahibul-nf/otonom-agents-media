#!/usr/bin/env bash
# Source from other workflow-kit scripts. Loads .workflow-kit.env from repo root.
_load_config() {
  local root="${1:-.}"
  local cfg="$root/.workflow-kit.env"
  if [[ -f "$cfg" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "$cfg"
    set +a
  fi
  GH_REPO="${GH_REPO:-}"
  GH_PROJECT_NUM="${GH_PROJECT_NUM:-}"
  GH_PROJECT_OWNER="${GH_PROJECT_OWNER:-@me}"
  GH_PROJECT_TITLE="${GH_PROJECT_TITLE:-Project delivery}"
  INTEGRATION_BRANCH="${INTEGRATION_BRANCH:-dev}"
  PRODUCTION_BRANCH="${PRODUCTION_BRANCH:-main}"
  SINGLE_BRANCH="${SINGLE_BRANCH:-false}"
}
