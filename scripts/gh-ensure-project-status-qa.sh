#!/usr/bin/env bash
# solo-dev-ai-kit:managed
# Legacy wrapper — ensures QA and full workflow Status columns.
# Prefer: ./scripts/gh-ensure-project-status.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/gh-ensure-project-status.sh"
