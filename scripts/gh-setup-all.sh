#!/usr/bin/env bash
# solo-dev-ai-kit:managed
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

if ! ./scripts/gh-setup-project.sh "$REPO"; then
  echo "error: gh-setup-project.sh failed for $REPO" >&2
  echo "Check: gh auth status && gh auth refresh -h github.com -s repo,project,read:project" >&2
  exit 1
fi

if [[ -f "$ROOT/.workflow-kit.env" ]]; then
  # shellcheck disable=SC1090
  source "$ROOT/.workflow-kit.env"
  if [[ -z "${GH_PROJECT_NUM:-}" ]]; then
    echo "warning: GH_PROJECT_NUM was not written to .workflow-kit.env" >&2
  else
    echo "Project number saved: GH_PROJECT_NUM=$GH_PROJECT_NUM"
  fi
fi

echo ""
echo "Setup pass complete. See docs/github-workflow.md"
