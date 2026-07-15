#!/usr/bin/env bash
# Create a GitHub issue and add it to the project board.
# Usage:
#   ./scripts/gh-triage-issue.sh --title "[Bug]: …" --body-file /tmp/body.md --labels "bug,priority:high"
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=_load-config.sh
source "$(dirname "$0")/_load-config.sh"
_load_config "$ROOT"

REPO="${GH_REPO:?Set GH_REPO in .workflow-kit.env or env}"
PROJECT_NUM="${GH_PROJECT_NUM:-}"
OWNER="${GH_PROJECT_OWNER:-@me}"

TITLE=""
BODY_FILE=""
LABELS=""
MILESTONE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title) TITLE="$2"; shift 2 ;;
    --body-file) BODY_FILE="$2"; shift 2 ;;
    --body) BODY_FILE="$(mktemp)"; printf '%s' "$2" >"$BODY_FILE"; shift 2 ;;
    --labels) LABELS="$2"; shift 2 ;;
    --milestone) MILESTONE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

[[ -n "$TITLE" ]] || { echo "Missing --title" >&2; exit 1; }
[[ -n "$BODY_FILE" && -f "$BODY_FILE" ]] || { echo "Missing --body-file or --body" >&2; exit 1; }

if gh issue list --repo "$REPO" --state open --search "$TITLE in:title" --json title \
  | jq -e --arg t "$TITLE" '.[] | select(.title==$t)' >/dev/null 2>&1; then
  existing="$(gh issue list --repo "$REPO" --state open --search "$TITLE in:title" --json number,url --jq '.[0]')"
  echo "Issue already exists: $existing" >&2
  echo "$existing" | jq -r .url
  exit 0
fi

ARGS=(issue create --repo "$REPO" --title "$TITLE" --body-file "$BODY_FILE")
if [[ -n "$LABELS" ]]; then
  IFS=',' read -ra TAGS <<<"$LABELS"
  for tag in "${TAGS[@]}"; do
    ARGS+=(--label "${tag// /}")
  done
fi
[[ -n "$MILESTONE" ]] && ARGS+=(--milestone "$MILESTONE")

URL="$(gh "${ARGS[@]}")"
echo "Created: $URL"

if [[ -n "$PROJECT_NUM" ]]; then
  gh project item-add "$PROJECT_NUM" --owner "$OWNER" --url "$URL" >/dev/null 2>&1 || \
    echo "Warning: could not add to project (run ./scripts/gh-setup-project.sh)" >&2

  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  if [[ -x "$SCRIPT_DIR/gh-configure-project.sh" ]]; then
    "$SCRIPT_DIR/gh-configure-project.sh" "$REPO" >/dev/null || true
  fi
else
  echo "Note: GH_PROJECT_NUM unset — issue created but not added to board." >&2
fi

echo "$URL"
