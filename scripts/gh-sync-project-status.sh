#!/usr/bin/env bash
# Otonom Media — optional board hygiene (not solo-dev-ai-kit:managed).
# Prefer kit scripts: gh-set-issue-status.sh, gh-close-verified-issue.sh.
#
# Usage:
#   ./scripts/gh-sync-project-status.sh              # closed issues on board → done
#   ./scripts/gh-sync-project-status.sh --summary
#   ./scripts/gh-sync-project-status.sh --qa 102     # → ai-review (maps to QA column)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=_load-config.sh
source "$(dirname "$0")/_load-config.sh"
_load_config "$ROOT"

REPO="${GH_REPO:?Set GH_REPO in .workflow-kit.env}"
PROJECT_NUM="${GH_PROJECT_NUM:-}"
OWNER="${GH_PROJECT_OWNER:-@me}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

QA_NUMBERS=""
SUMMARY=0
SYNC_CLOSED=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --qa) QA_NUMBERS="$2"; shift 2 ;;
    --summary) SUMMARY=1; shift ;;
    --no-closed-sync) SYNC_CLOSED=0; shift ;;
    -h|--help)
      grep '^#' "$0" | head -8 | sed 's/^# //'
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -n "$QA_NUMBERS" ]]; then
  IFS=',' read -ra nums <<<"$QA_NUMBERS"
  for n in "${nums[@]}"; do
    n="${n// /}"
    [[ -n "$n" ]] && "$SCRIPT_DIR/gh-set-issue-status.sh" "$n" ai-review
  done
fi

if [[ "$SYNC_CLOSED" -eq 1 && -n "$PROJECT_NUM" ]]; then
  while IFS=$'\t' read -r num _status; do
    [[ -n "$num" ]] || continue
    state="$(gh issue view "$num" --repo "$REPO" --json state --jq .state 2>/dev/null || echo OPEN)"
    if [[ "$state" == "CLOSED" ]]; then
      "$SCRIPT_DIR/gh-set-issue-status.sh" "$num" done || true
    fi
  done < <(
    gh project item-list "$PROJECT_NUM" --owner "$OWNER" --format json --limit 500 \
      | jq -r '.items[]
        | select(.content.type=="Issue")
        | select(.status!="Done")
        | [.content.number, .status]
        | @tsv'
  )
fi

if [[ "$SUMMARY" -eq 1 ]] || [[ -z "$QA_NUMBERS" && "$SYNC_CLOSED" -eq 1 ]]; then
  [[ -n "$PROJECT_NUM" ]] || { echo "GH_PROJECT_NUM unset"; exit 0; }
  gh project item-list "$PROJECT_NUM" --owner "$OWNER" --format json --limit 500 \
    | python3 -c "
import json, sys
from collections import Counter
d = json.load(sys.stdin)
c = Counter()
for it in d.get('items', []):
    cont = it.get('content') or {}
    if cont.get('type') != 'Issue':
        continue
    c[it.get('status') or '—'] += 1
print('Board Status:', dict(sorted(c.items())))
"
fi
