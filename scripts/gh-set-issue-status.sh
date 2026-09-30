#!/usr/bin/env bash
# solo-dev-ai-kit:managed
# Set GitHub Project board Status for an issue.
#
# Usage:
#   ./scripts/gh-set-issue-status.sh 14 progress
#   ./scripts/gh-set-issue-status.sh 14 ready-for-ai
#   ./scripts/gh-set-issue-status.sh 14 ai-review
#
# Status keys (preferred → fallback column on board):
#   backlog              → Backlog | Todo
#   ready-for-ai         → Ready for AI (no fallback — run gh-ensure-project-status.sh)
#   progress, ai-working → AI Working | In Progress
#   ai-review            → AI Review
#   qa, human-review     → Human Review
#   done                 → Done
#
# Project Status is the workflow authorization gate — not issue labels.
# If GH_PROJECT_NUM is unset: prints note and exits 0 (no-op).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=_load-config.sh
source "$(dirname "$0")/_load-config.sh"
_load_config "$ROOT"

REPO="${GH_REPO:?Set GH_REPO in .workflow-kit.env}"
OWNER="${GH_PROJECT_OWNER:-@me}"
PROJECT_NUM="${GH_PROJECT_NUM:-}"

ISSUE=""
STATUS=""

normalize_status_key() {
  case "$1" in
    backlog) echo "backlog" ;;
    ready-for-ai|ready_for_ai|readyforai) echo "ready-for-ai" ;;
    progress|ai-working|ai_working|aiworking) echo "ai-working" ;;
    ai-review|ai_review|aireview) echo "ai-review" ;;
    qa|human-review|human_review|humanreview) echo "human-review" ;;
    done) echo "done" ;;
    *)
      echo "error: unknown status '$1'" >&2
      echo "  use: backlog | ready-for-ai | progress | ai-working | ai-review | qa | human-review | done" >&2
      exit 1
      ;;
  esac
}

status_option_names() {
  case "$1" in
    backlog) printf '%s\n' "Backlog" "Todo" ;;
    ready-for-ai) printf '%s\n' "Ready for AI" ;;
    ai-working) printf '%s\n' "AI Working" "In Progress" ;;
    ai-review) printf '%s\n' "AI Review" ;;
    human-review) printf '%s\n' "Human Review" ;;
    done) printf '%s\n' "Done" ;;
    *)
      echo "error: internal unknown key '$1'" >&2
      exit 1
      ;;
  esac
}

resolve_status_label() {
  local key="$1"
  local options_json="$2"
  local candidate resolved=""
  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    resolved="$(echo "$options_json" | jq -r --arg name "$candidate" \
      '.[]? | select(.name == $name) | .name' | head -n1)"
    if [[ -n "$resolved" && "$resolved" != "null" ]]; then
      echo "$resolved"
      return 0
    fi
  done < <(status_option_names "$key")

  if [[ "$key" == "ready-for-ai" ]]; then
    echo "error: Status option 'Ready for AI' not found on project $PROJECT_NUM" >&2
    echo "Run ./scripts/gh-ensure-project-status.sh to add orchestrator-safe columns." >&2
    exit 1
  fi

  local tried
  tried="$(status_option_names "$key" | paste -sd '|' -)"
  echo "error: none of ($tried) found on project $PROJECT_NUM" >&2
  echo "Run ./scripts/gh-ensure-project-status.sh if columns are missing." >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -*) echo "Unknown arg: $1" >&2; exit 1 ;;
    *)
      if [[ -z "$ISSUE" ]]; then ISSUE="$1"; shift
      elif [[ -z "$STATUS" ]]; then STATUS="$1"; shift
      else echo "Unexpected arg: $1" >&2; exit 1
      fi
      ;;
  esac
done

[[ -n "$ISSUE" && -n "$STATUS" ]] || {
  echo "Usage: $0 <issue-number> <status-key>" >&2
  echo "  keys: backlog | ready-for-ai | progress | ai-working | ai-review | qa | human-review | done" >&2
  exit 1
}

[[ -n "$PROJECT_NUM" ]] || {
  echo "Note: GH_PROJECT_NUM unset — cannot update board status for #$ISSUE" >&2
  exit 0
}

STATUS_KEY="$(normalize_status_key "$STATUS")"
ISSUE_URL="$(gh issue view "$ISSUE" --repo "$REPO" --json url --jq .url)"

PROJECT_ID="$(gh project view "$PROJECT_NUM" --owner "$OWNER" --format json --jq .id)"
STATUS_FIELD="$(gh project field-list "$PROJECT_NUM" --owner "$OWNER" --format json \
  | jq -r '.fields[] | select(.name=="Status") | .id')"

[[ -n "$STATUS_FIELD" && "$STATUS_FIELD" != "null" ]] || {
  echo "error: no Status field on project $PROJECT_NUM" >&2
  exit 1
}

STATUS_OPTIONS="$(gh project field-list "$PROJECT_NUM" --owner "$OWNER" --format json \
  | jq -c '.fields[] | select(.name=="Status") | .options')"

LABEL="$(resolve_status_label "$STATUS_KEY" "$STATUS_OPTIONS")"

OPTION_ID="$(echo "$STATUS_OPTIONS" | jq -r --arg label "$LABEL" \
  '.[]? | select(.name==$label) | .id')"

[[ -n "$OPTION_ID" && "$OPTION_ID" != "null" ]] || {
  echo "error: could not resolve option id for '$LABEL'" >&2
  exit 1
}

ITEM_ID="$(gh project item-list "$PROJECT_NUM" --owner "$OWNER" --format json --limit 200 \
  | jq -r --arg url "$ISSUE_URL" '.items[] | select(.content.url==$url) | .id' | head -n1)"

if [[ -z "$ITEM_ID" || "$ITEM_ID" == "null" ]]; then
  gh project item-add "$PROJECT_NUM" --owner "$OWNER" --url "$ISSUE_URL" >/dev/null
  ITEM_ID="$(gh project item-list "$PROJECT_NUM" --owner "$OWNER" --format json --limit 200 \
    | jq -r --arg url "$ISSUE_URL" '.items[] | select(.content.url==$url) | .id' | head -n1)"
fi

[[ -n "$ITEM_ID" && "$ITEM_ID" != "null" ]] || {
  echo "error: could not find or add project item for #$ISSUE" >&2
  exit 1
}

gh project item-edit --id "$ITEM_ID" --project-id "$PROJECT_ID" \
  --field-id "$STATUS_FIELD" --single-select-option-id "$OPTION_ID" >/dev/null

echo "Set #$ISSUE board Status → $LABEL"
