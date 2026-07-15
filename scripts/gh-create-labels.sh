#!/usr/bin/env bash
# Creates standard workflow labels (idempotent). Extra labels via EXTRA_LABELS env.
# EXTRA_LABELS format: name:color:description|name:color:description
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=_load-config.sh
source "$(dirname "$0")/_load-config.sh"
_load_config "$ROOT"

REPO="${1:-${GH_REPO:?Set GH_REPO}}"

create_label() {
  local name="$1"
  local color="$2"
  local description="$3"
  if gh label list --repo "$REPO" --json name --jq '.[].name' | grep -Fxq "$name"; then
    echo "label exists: $name"
  else
    gh label create "$name" --repo "$REPO" --color "$color" --description "$description"
    echo "created: $name"
  fi
}

create_label "bug" "d73a4a" "Something is broken"
create_label "enhancement" "a2eeef" "New feature or improvement"
create_label "priority:high" "B60205" "Do soon — blocks testing or demo"
create_label "priority:medium" "D93F0B" "Important but not blocking"
create_label "priority:low" "0E8A16" "Polish / later"

if [[ "${HAS_CLIENT_REPORTS:-false}" == "true" ]]; then
  create_label "client-facing" "FBCA04" "Worth mentioning in progress reports when shipped"
fi

if [[ -n "${EXTRA_LABELS:-}" ]]; then
  IFS='|' read -ra PAIRS <<<"$EXTRA_LABELS"
  for pair in "${PAIRS[@]}"; do
    IFS=':' read -r name color desc <<<"$pair"
    [[ -n "$name" && -n "$color" ]] && create_label "$name" "$color" "${desc:-}"
  done
fi

echo "Done."
