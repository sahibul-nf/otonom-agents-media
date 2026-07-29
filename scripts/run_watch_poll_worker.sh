#!/usr/bin/env bash
# Poll watched YouTube channels and enqueue clip jobs when new uploads appear.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/media-engine"
INTERVAL_SECONDS="${WATCH_POLL_INTERVAL_SECONDS:-300}"
PROFILE="${WATCH_POLL_PROFILE:-}"
while true; do
  if [[ -n "$PROFILE" ]]; then
    python3 -m media_engine.cli watch-poll --profile "$PROFILE" --force || true
  else
    python3 -m media_engine.cli watch-poll --force || true
  fi
  sleep "$INTERVAL_SECONDS"
done
