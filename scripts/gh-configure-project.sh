#!/usr/bin/env bash
# Board setup: Priority + Focus fields, sync from issue labels.
# Usage: ./scripts/gh-configure-project.sh [owner/repo]
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

# Title only — avoid `gh project edit --readme` (broken UpdateProjectV2 query in some gh versions).
gh project edit "$PROJECT_NUM" --owner "$OWNER" \
  --title "$PROJECT_TITLE" \
  --description "Dev board for $REPO — solo dev + AI workflow." >/dev/null 2>&1 || true

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

echo "Syncing project items from issue labels …"
python3 - "$OWNER" "$PROJECT_NUM" "$PROJECT_ID" <<'PY'
import json, subprocess, sys

owner, project_num, project_id = sys.argv[1:4]

def run(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(r.stderr[-800:] or f"failed: {args}")
    return r.stdout

fields = {f["name"]: f for f in json.loads(run(["gh", "project", "field-list", project_num, "--owner", owner, "--format", "json"]))["fields"]}
priority_field = fields["Priority"]["id"]
focus_field = fields["Focus"]["id"]
pri_opts = {o["name"]: o["id"] for o in fields["Priority"].get("options") or []}
foc_opts = {o["name"]: o["id"] for o in fields["Focus"].get("options") or []}

items = json.loads(run(["gh", "project", "item-list", project_num, "--owner", owner, "--format", "json", "--limit", "100"]))["items"]
for item in items:
    number = (item.get("content") or {}).get("number")
    if not number:
        continue
    labels = ",".join(item.get("labels") or [])
    if "priority:high" in labels:
        pri, focus = "High", "This week"
    elif "priority:low" in labels:
        pri, focus = "Low", "Icebox"
    else:
        pri, focus = "Medium", "Backlog"
    for field_id, opt_id in ((priority_field, pri_opts[pri]), (focus_field, foc_opts[focus])):
        subprocess.run(
            [
                "gh", "project", "item-edit",
                "--id", item["id"],
                "--project-id", project_id,
                "--field-id", field_id,
                "--single-select-option-id", opt_id,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    print(f"  #{number} → Priority={pri} Focus={focus}")
PY

URL="$(gh project view "$PROJECT_NUM" --owner "$OWNER" --format json --jq .url)"
echo ""
echo "Board ready: $URL"
echo "Add Priority + Focus columns in the project view if they are hidden."
echo "Filter Focus = 'This week' for the current sprint."
