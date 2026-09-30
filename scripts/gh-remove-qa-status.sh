#!/usr/bin/env bash
# Otonom Media — remove redundant Status column "QA" (use Human Review only).
#
# 1. Moves all board items in QA → Human Review
# 2. Drops the QA option from the Status field (preserves other option ids)
#
# Run after ./scripts/gh-ensure-project-status.sh if Human Review is missing.
# Usage: ./scripts/gh-remove-qa-status.sh [--dry-run]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=_load-config.sh
source "$(dirname "$0")/_load-config.sh"
_load_config "$ROOT"

OWNER="${GH_PROJECT_OWNER:-@me}"
PROJECT_NUM="${GH_PROJECT_NUM:?Set GH_PROJECT_NUM in .workflow-kit.env}"
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

FLIST="$(gh project field-list "$PROJECT_NUM" --owner "$OWNER" --format json)"
STATUS_JSON="$(echo "$FLIST" | jq '.fields[] | select(.name=="Status")')"

if [[ -z "$STATUS_JSON" || "$STATUS_JSON" == "null" ]]; then
  echo "error: no Status field on project $PROJECT_NUM" >&2
  exit 1
fi

if ! echo "$STATUS_JSON" | jq -e '.options[] | select(.name=="QA")' >/dev/null 2>&1; then
  echo "No QA Status option on project $PROJECT_NUM — nothing to remove."
  exit 0
fi

if ! echo "$STATUS_JSON" | jq -e '.options[] | select(.name=="Human Review")' >/dev/null 2>&1; then
  echo "error: Human Review column missing. Run ./scripts/gh-ensure-project-status.sh first." >&2
  exit 1
fi

FIELD_ID="$(echo "$STATUS_JSON" | jq -r '.id')"
PROJECT_ID="$(gh project view "$PROJECT_NUM" --owner "$OWNER" --format json --jq .id)"
HUMAN_OPTION_ID="$(echo "$STATUS_JSON" | jq -r '.options[] | select(.name=="Human Review") | .id')"

QA_ITEMS="$(gh project item-list "$PROJECT_NUM" --owner "$OWNER" --format json --limit 500 \
  | jq -r '.items[] | select(.status=="QA") | .id')"

MOVED=0
while IFS= read -r item_id; do
  [[ -n "$item_id" ]] || continue
  MOVED=$((MOVED + 1))
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] Would move item $item_id: QA → Human Review"
  else
    gh project item-edit --id "$item_id" --project-id "$PROJECT_ID" \
      --field-id "$FIELD_ID" --single-select-option-id "$HUMAN_OPTION_ID" >/dev/null
    echo "Moved item $item_id: QA → Human Review"
  fi
done <<<"$QA_ITEMS"

if [[ "$MOVED" -eq 0 ]]; then
  echo "No cards in QA column."
else
  echo "Moved $MOVED card(s) to Human Review."
fi

OPTIONS_JSON="$(echo "$STATUS_JSON" | jq -c '
  [.options[] | select(.name != "QA") |
    {id, name, color: (.color // "GRAY"), description: (.description // " ")}]
')"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] Would remove QA from Status options."
  echo "$OPTIONS_JSON" | jq -r '.[].name' | paste -sd ', ' -
  exit 0
fi

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
jq -n \
  --argjson opts "$OPTIONS_JSON" \
  --arg fid "$FIELD_ID" \
  '{query: "mutation($input: UpdateProjectV2FieldInput!) { updateProjectV2Field(input: $input) { projectV2Field { ... on ProjectV2SingleSelectField { name options { id name } } } } }", variables: {input: {fieldId: $fid, singleSelectOptions: $opts}}}' \
  >"$TMP"

gh api graphql --input "$TMP" --jq '.data.updateProjectV2Field.projectV2Field.options[].name' >/dev/null
echo ""
echo "Removed QA from Status. Reorder columns in GitHub if needed: Project → … → Fields → Status."
