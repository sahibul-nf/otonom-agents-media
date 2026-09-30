#!/usr/bin/env bash
# solo-dev-ai-kit:managed
# Legacy wrapper — ensures workflow Status columns (same as gh-ensure-project-status.sh).
# To remove redundant QA column: ./scripts/gh-remove-qa-status.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/gh-ensure-project-status.sh"
