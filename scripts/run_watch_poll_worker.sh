#!/usr/bin/env bash
# Poll watched YouTube channels and enqueue clip jobs when new uploads appear.
# Respects per-channel poll_interval_minutes (no --force). UI "Poll now" uses force.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/media-engine"
# Default ~24h; override with WATCH_POLL_INTERVAL_SECONDS (e.g. 21600 for 6h).
INTERVAL_SECONDS="${WATCH_POLL_INTERVAL_SECONDS:-86400}"
PROFILE="${WATCH_POLL_PROFILE:-}"
while true; do
  if [[ -n "$PROFILE" ]]; then
    python3 -m media_engine.cli watch-poll --profile "$PROFILE" || true
  else
    python3 -m media_engine.cli watch-poll || true
  fi
  sleep "$INTERVAL_SECONDS"
done
