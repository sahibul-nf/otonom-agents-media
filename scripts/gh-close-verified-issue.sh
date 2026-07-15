#!/usr/bin/env bash
# After user confirms QA, check acceptance criteria and post closing comment.
#
# Usage:
#   ./scripts/gh-close-verified-issue.sh 14 --comment-file /tmp/close-14.md
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=_load-config.sh
source "$(dirname "$0")/_load-config.sh"
_load_config "$ROOT"

REPO="${GH_REPO:?Set GH_REPO in .workflow-kit.env}"
ISSUE=""
COMMENT=""
COMMENT_FILE=""
CHECK_AC=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --comment) COMMENT="$2"; shift 2 ;;
    --comment-file) COMMENT_FILE="$2"; shift 2 ;;
    --no-check-ac) CHECK_AC=0; shift ;;
    -*) echo "Unknown arg: $1" >&2; exit 1 ;;
    *)
      if [[ -z "$ISSUE" ]]; then ISSUE="$1"; shift; else echo "Unexpected arg: $1" >&2; exit 1; fi
      ;;
  esac
done

[[ -n "$ISSUE" ]] || { echo "Usage: $0 <issue-number> --comment-file path | --comment text" >&2; exit 1; }
[[ -n "$COMMENT" || -n "$COMMENT_FILE" ]] || {
  echo "Provide --comment or --comment-file" >&2
  exit 1
}

BODY="$(gh issue view "$ISSUE" --repo "$REPO" --json body --jq .body)"

if [[ "$CHECK_AC" -eq 1 ]]; then
  UPDATED="$(printf '%s\n' "$BODY" | awk '
    /^## Acceptance criteria/ || /^### Acceptance criteria/ { in_ac = 1 }
    /^## / && $0 !~ /^## Acceptance criteria/ && $0 !~ /^### Acceptance criteria/ { if (in_ac) in_ac = 0 }
    in_ac && /^- \[ \]/ { sub(/^- \[ \]/, "- [x]") }
    { print }
  ')"
  if [[ "$UPDATED" != "$BODY" ]]; then
    TMP_BODY="$(mktemp)"
    printf '%s' "$UPDATED" >"$TMP_BODY"
    gh issue edit "$ISSUE" --repo "$REPO" --body-file "$TMP_BODY" >/dev/null
    rm -f "$TMP_BODY"
    echo "Checked acceptance criteria on #$ISSUE"
  else
    echo "No unchecked acceptance criteria boxes to update on #$ISSUE"
  fi
fi

if [[ -n "$COMMENT_FILE" ]]; then
  gh issue comment "$ISSUE" --repo "$REPO" --body-file "$COMMENT_FILE"
else
  gh issue comment "$ISSUE" --repo "$REPO" --body "$COMMENT"
fi

echo "Posted closing comment on #$ISSUE"
