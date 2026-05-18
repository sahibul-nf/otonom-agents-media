#!/usr/bin/env bash
set -euo pipefail

cd "/Volumes/XPG SSD 1T/projects/otonom-agents-media/media-engine"

INTERVAL="${PUBLISH_WORKER_INTERVAL_SECONDS:-60}"
PYTHON_BIN="${MEDIA_ENGINE_PYTHON:-/tmp/media-engine-tools-py313/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

while true; do
  PYTHONPATH=. "$PYTHON_BIN" -m media_engine.cli publish-due \
    --env-file ../.env.local \
    --limit "${PUBLISH_WORKER_LIMIT:-5}" || true
  sleep "$INTERVAL"
done
