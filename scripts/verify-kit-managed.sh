#!/usr/bin/env bash
# Report kit manifest paths missing solo-dev-ai-kit:managed marker.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$ROOT/.workflow-kit/manifest"

[[ -f "$MANIFEST" ]] || {
  echo "No .workflow-kit/manifest — re-bootstrap with kit v12+ or use legacy uninstall."
  exit 0
}

missing=0
while IFS= read -r line; do
  line="${line%%#*}"
  line="${line// /}"
  [[ "$line" == path=* ]] || continue
  rel="${line#path=}"
  [[ -n "$rel" ]] || continue
  abs="$ROOT/$rel"
  if [[ ! -f "$abs" ]]; then
    echo "missing file: $rel"
    missing=$((missing + 1))
    continue
  fi
  if [[ "$rel" == "AGENTS.md" ]]; then
    if ! grep -q 'solo-dev-ai-kit:partial-managed' "$abs" 2>/dev/null; then
      echo "no partial-managed marker (customized?): $rel"
      missing=$((missing + 1))
    fi
  elif ! python3 "$(dirname "$0")/kit-managed.py" has-marker "$abs"; then
    echo "no marker (customized?): $rel"
    missing=$((missing + 1))
  fi
done <"$MANIFEST"

if [[ "$missing" -eq 0 ]]; then
  echo "All manifest paths have kit markers."
else
  echo "$missing path(s) missing marker or file — uninstall will skip them."
fi
