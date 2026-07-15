#!/usr/bin/env bash
# Board setup: title, readme, Priority + Focus fields, sync from issue labels.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=_load-config.sh
source "$(dirname "$0")/_load-config.sh"
_load_config "$ROOT"

REPO="${1:-${GH_REPO:?Set GH_REPO}}"
OWNER="${GH_PROJECT_OWNER:-@me}"
PROJECT_NUM="${GH_PROJECT_NUM:?Set GH_PROJECT_NUM}"
PROJECT_TITLE="${GH_PROJECT_TITLE:-Project delivery}"

PROJECT_ID="$(gh project view "$PROJECT_NUM" --owner "$OWNER" --format json --jq .id)"

README_FILE="$(dirname "$0")/project-readme.md"
if [[ ! -f "$README_FILE" ]]; then
  README_FILE="$ROOT/scripts/project-readme.md"
fi

gh project edit "$PROJECT_NUM" --owner "$OWNER" \
  --title "$PROJECT_TITLE" \
  --description "Dev board for $REPO — solo dev + AI workflow." \
  --readme "$(cat "$README_FILE")"

ensure_field() {
  local name="$1"
  local options="$2"
  if gh project field-list "$PROJECT_NUM" --owner "$OWNER" --format json \
    | jq -e --arg n "$name" '.fields[] | select(.name==$n)' >/dev/null; then
    echo "field exists: $name"
  else
    gh project field-create "$PROJECT_NUM" --owner "$OWNER" \
      --name "$name" --data-type SINGLE_SELECT --single-select-options "$options"
    echo "created field: $name"
  fi
}

ensure_field "Priority" "High,Medium,Low"
ensure_field "Focus" "This week,Backlog,Icebox"

field_option_id() {
  local field_name="$1"
  local option_name="$2"
  gh project field-list "$PROJECT_NUM" --owner "$OWNER" --format json \
    | jq -r --arg fn "$field_name" --arg on "$option_name" \
      '.fields[] | select(.name==$fn) | .options[]? | select(.name==$on) | .id'
}

PRIORITY_FIELD="$(gh project field-list "$PROJECT_NUM" --owner "$OWNER" --format json \
  | jq -r '.fields[] | select(.name=="Priority") | .id')"
FOCUS_FIELD="$(gh project field-list "$PROJECT_NUM" --owner "$OWNER" --format json \
  | jq -r '.fields[] | select(.name=="Focus") | .id')"

priority_option() {
  case "$1" in
    high) field_option_id "Priority" "High" ;;
    medium) field_option_id "Priority" "Medium" ;;
    low) field_option_id "Priority" "Low" ;;
    *) field_option_id "Priority" "Medium" ;;
  esac
}

focus_option() {
  case "$1" in
    week) field_option_id "Focus" "This week" ;;
    backlog) field_option_id "Focus" "Backlog" ;;
    icebox) field_option_id "Focus" "Icebox" ;;
    *) field_option_id "Focus" "Backlog" ;;
  esac
}

label_priority() {
  local labels="$1"
  [[ "$labels" == *"priority:high"* ]] && echo high && return
  [[ "$labels" == *"priority:low"* ]] && echo low && return
  echo medium
}

echo "Syncing project items from open issues …"
gh project item-list "$PROJECT_NUM" --owner "$OWNER" --format json --limit 100 \
  | jq -c '.items[]' | while read -r row; do
  item_id="$(echo "$row" | jq -r '.id')"
  number="$(echo "$row" | jq -r '.content.number // empty')"
  labels="$(echo "$row" | jq -r '[.labels[]?] | join(",")')"
  [[ -z "$number" ]] && continue

  pri="$(label_priority "$labels")"
  if [[ "$pri" == "high" ]]; then
    focus=week
  elif [[ "$pri" == "low" ]]; then
    focus=icebox
  else
    focus=backlog
  fi

  pri_id="$(priority_option "$pri")"
  foc_id="$(focus_option "$focus")"
  [[ -n "$pri_id" ]] && gh project item-edit --id "$item_id" --project-id "$PROJECT_ID" \
    --field-id "$PRIORITY_FIELD" --single-select-option-id "$pri_id" >/dev/null
  [[ -n "$foc_id" ]] && gh project item-edit --id "$item_id" --project-id "$PROJECT_ID" \
    --field-id "$FOCUS_FIELD" --single-select-option-id "$foc_id" >/dev/null

  gh issue edit "$number" --repo "$REPO" --add-assignee @me 2>/dev/null || true
  echo "  #$number → Priority=$pri Focus=$focus"
done

URL="$(gh project view "$PROJECT_NUM" --owner "$OWNER" --format json --jq .url)"
echo ""
echo "Board ready: $URL"
echo "Use Kanban view · filter Focus = 'This week' for your sprint."
