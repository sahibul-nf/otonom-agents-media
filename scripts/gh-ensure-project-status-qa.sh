#!/usr/bin/env bash
# Idempotent: ensure GitHub Project Status has QA column before Done.
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

if echo "$STATUS_JSON" | jq -e '.options[] | select(.name=="QA")' >/dev/null 2>&1; then
  echo "Status already has option: QA (nothing to do)"
  exit 0
fi

FIELD_ID="$(echo "$STATUS_JSON" | jq -r '.id')"

if echo "$STATUS_JSON" | jq -e '.options[] | select(.name=="Testing")' >/dev/null 2>&1; then
  OPTIONS_JSON="$(echo "$STATUS_JSON" | jq -c '
    def c(n): if n == "Backlog" then "GRAY"
      elif n == "In Progress" then "ORANGE"
      elif n == "Done" then "GREEN"
      else "PURPLE" end;
    [.options[] |
      if .name == "Testing" then
        {id, name: "QA", color: "YELLOW", description: "Manual check before Done"}
      else
        {id, name, color: c(.name), description: " "}
      end]
  ')"
  MSG="Renamed Status option: Testing → QA."
else
  OPTIONS_JSON="$(echo "$STATUS_JSON" | jq -c '
    .options as $opts
    | def c(n): if n == "Backlog" then "GRAY"
        elif n == "In Progress" then "ORANGE"
        elif n == "Done" then "GREEN"
        else "PURPLE" end;
      (if ($opts | map(.name) | index("Done")) != null then
        [ $opts[] | select(.name != "Done") | {id, name, color: c(.name), description: " "} ]
        + [{name: "QA", description: "Manual check before Done", color: "YELLOW"}]
        + [ $opts[] | select(.name == "Done") | {id, name, color: c(.name), description: " "} ]
      else
        [ $opts[] | {id, name, color: c(.name), description: " "} ]
        + [{name: "QA", description: "Manual check before Done", color: "YELLOW"}]
      end)
  ')"
  MSG="Added Status option: QA (before Done)."
fi

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
jq -n \
  --argjson opts "$OPTIONS_JSON" \
  --arg fid "$FIELD_ID" \
  '{query: "mutation($input: UpdateProjectV2FieldInput!) { updateProjectV2Field(input: $input) { projectV2Field { ... on ProjectV2SingleSelectField { name options { id name } } } } }", variables: {input: {fieldId: $fid, singleSelectOptions: $opts}}}' \
  >"$TMP"

gh api graphql --input "$TMP" --jq '.data.updateProjectV2Field.projectV2Field.options' >/dev/null
echo ""
echo "$MSG Reorder columns in Kanban if needed: Project → … → Fields → Status."
