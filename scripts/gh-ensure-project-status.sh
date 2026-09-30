#!/usr/bin/env bash
# solo-dev-ai-kit:managed
# Idempotent: ensure GitHub Project Status has workflow columns for solo-dev-ai-kit.
#
# Adds (never renames) orchestrator-safe options:
#   Ready for AI, AI Working, AI Review, Human Review
# Preserves existing options (Todo, In Progress, Backlog, etc.) and card positions.
#
# Legacy: renames Testing → Human Review when Human Review is not already present.
# To drop redundant QA column: ./scripts/gh-remove-qa-status.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=_load-config.sh
source "$(dirname "$0")/_load-config.sh"
_load_config "$ROOT"

OWNER="${GH_PROJECT_OWNER:-@me}"
PROJECT_NUM="${GH_PROJECT_NUM:?Set GH_PROJECT_NUM in .workflow-kit.env}"

FLIST="$(gh project field-list "$PROJECT_NUM" --owner "$OWNER" --format json)"
STATUS_JSON="$(echo "$FLIST" | jq '.fields[] | select(.name=="Status")')"

if [[ -z "$STATUS_JSON" || "$STATUS_JSON" == "null" ]]; then
  echo "error: no Status field on project $PROJECT_NUM" >&2
  exit 1
fi

FIELD_ID="$(echo "$STATUS_JSON" | jq -r '.id')"

# Rename Testing → Human Review when present (legacy); skip if Human Review already exists.
if echo "$STATUS_JSON" | jq -e '.options[] | select(.name=="Testing")' >/dev/null 2>&1 \
  && ! echo "$STATUS_JSON" | jq -e '.options[] | select(.name=="Human Review")' >/dev/null 2>&1; then
  STATUS_JSON="$(echo "$STATUS_JSON" | jq '
    .options = [.options[] |
      if .name == "Testing" then . + {name: "Human Review", description: "Human reviews PR before merge", color: "PURPLE"}
      else . end]')"
  echo "Renamed Status option: Testing → Human Review."
  ADDED=1
fi

ensure_option() {
  local name="$1"
  local color="$2"
  local description="$3"
  if echo "$STATUS_JSON" | jq -e --arg n "$name" '.options[] | select(.name==$n)' >/dev/null 2>&1; then
    echo "Status already has: $name"
    return 0
  fi
  STATUS_JSON="$(echo "$STATUS_JSON" | jq \
    --arg name "$name" --arg color "$color" --arg desc "$description" '
    .options = (.options + [{name: $name, color: $color, description: $desc}])
  ')"
  echo "Will add Status option: $name"
  ADDED=1
}

ADDED="${ADDED:-0}"

ensure_option "Ready for AI" "BLUE" "Human authorized — orchestrator may pick up"
ensure_option "AI Working" "ORANGE" "Agent implementing"
ensure_option "AI Review" "YELLOW" "Automated verify done — PR ready"
ensure_option "Human Review" "PURPLE" "Human reviews PR before merge"

if [[ "$ADDED" -eq 0 ]]; then
  echo "All workflow Status options present (nothing to do)."
  exit 0
fi

OPTIONS_JSON="$(echo "$STATUS_JSON" | jq -c '
  [.options[] |
    if has("id") then
      {id, name, color: (.color // "GRAY"), description: (.description // " ")}
    else
      {name, color: (.color // "GRAY"), description: (.description // " ")}
    end]
')"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
jq -n \
  --argjson opts "$OPTIONS_JSON" \
  --arg fid "$FIELD_ID" \
  '{query: "mutation($input: UpdateProjectV2FieldInput!) { updateProjectV2Field(input: $input) { projectV2Field { ... on ProjectV2SingleSelectField { name options { id name } } } } }", variables: {input: {fieldId: $fid, singleSelectOptions: $opts}}}' \
  >"$TMP"

gh api graphql --input "$TMP" --jq '.data.updateProjectV2Field.projectV2Field.options[].name' >/dev/null
echo ""
echo "Status field updated. Reorder columns in Kanban if needed: Project → … → Fields → Status."
echo "Existing cards were not moved — drag issues to Ready for AI only when you authorize autonomous work."
