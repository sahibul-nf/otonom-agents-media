#!/usr/bin/env bash
# solo-dev-ai-kit:managed
# Idempotent: ensure GitHub Project Status has workflow columns for solo-dev-ai-kit.
#
# Adds (never renames) orchestrator-safe options:
#   Ready for AI, AI Working, AI Review, Human Review
# Preserves existing options (Todo, In Progress, QA, Backlog, etc.) and card positions.
#
# Also ensures QA exists (renames Testing → QA if needed) for legacy boards.
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

# Rename Testing → QA when present (legacy); do not rename In Progress or Todo.
if echo "$STATUS_JSON" | jq -e '.options[] | select(.name=="Testing")' >/dev/null 2>&1; then
  STATUS_JSON="$(echo "$STATUS_JSON" | jq '
    .options = [.options[] |
      if .name == "Testing" then . + {name: "QA", description: "Manual check before Done", color: "YELLOW"}
      else . end]')"
  echo "Renamed Status option: Testing → QA."
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

ADDED=0

# QA column (human review fallback) — insert before Done if missing
if ! echo "$STATUS_JSON" | jq -e '.options[] | select(.name=="QA")' >/dev/null 2>&1; then
  if echo "$STATUS_JSON" | jq -e '.options[] | select(.name=="Done")' >/dev/null 2>&1; then
    STATUS_JSON="$(echo "$STATUS_JSON" | jq '
      .options as $opts
      | ($opts | map(.name) | index("Done")) as $done_idx
      | if $done_idx == null then .
        else .options = (
          [ $opts[0:$done_idx][] ]
          + [{name: "QA", color: "YELLOW", description: "Manual check before Done"}]
          + [ $opts[$done_idx:][] ]
        ) end
    ')"
  else
    STATUS_JSON="$(echo "$STATUS_JSON" | jq \
      '.options += [{name: "QA", color: "YELLOW", description: "Manual check before Done"}]')"
  fi
  echo "Will add Status option: QA (before Done)"
  ADDED=1
fi

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
    if has("id") then {id, name, color, description: (.description // " ")}
    else {name, color, description: (.description // " ")} end]
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
