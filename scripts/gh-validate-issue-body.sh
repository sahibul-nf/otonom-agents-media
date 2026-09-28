#!/usr/bin/env bash
# solo-dev-ai-kit:managed
# Validate issue body has acceptance criteria checklist.
#
# Usage: ./scripts/gh-validate-issue-body.sh --body-file /tmp/body.md
#
# Requires: ## Acceptance criteria heading and at least one "- [ ]" line.
# Exit: 0 valid; 1 missing AC structure
set -euo pipefail

BODY_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --body-file) BODY_FILE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

[[ -n "$BODY_FILE" && -f "$BODY_FILE" ]] || {
  echo "Usage: $0 --body-file path" >&2
  exit 1
}

if ! grep -Eq '^## Acceptance criteria|^### Acceptance criteria' "$BODY_FILE"; then
  echo "error: body must include '## Acceptance criteria' heading" >&2
  exit 1
fi

if ! grep -Eq '^- \[ \]' "$BODY_FILE"; then
  echo "error: body must include at least one unchecked acceptance criterion (- [ ])" >&2
  exit 1
fi

echo "OK: acceptance criteria present"
