#!/usr/bin/env bash
# One-shot GitHub setup: labels → project board → QA column.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="${1:-${GH_REPO:-}}"

if [[ -z "$REPO" && -f "$ROOT/.workflow-kit.env" ]]; then
  # shellcheck source=_load-config.sh
  source "$(dirname "$0")/_load-config.sh"
  _load_config "$ROOT"
  REPO="${GH_REPO:-}"
fi

[[ -n "$REPO" ]] || { echo "Usage: $0 [owner/repo] or set GH_REPO in .workflow-kit.env" >&2; exit 1; }

cd "$ROOT"
./scripts/gh-create-labels.sh "$REPO"
./scripts/gh-setup-project.sh "$REPO" || true

echo ""
echo "Setup pass complete. See docs/github-workflow.md"
