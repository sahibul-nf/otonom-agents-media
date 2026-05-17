#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from system_health import collect_status
from telegram_notify import notify_telegram

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / ".runtime"
STATE_FILE = STATE_DIR / "pm2-health-state.json"
TZ_NAME = os.environ.get("TZ", "Asia/Jakarta")


def now_label() -> str:
    return datetime.now(ZoneInfo(TZ_NAME)).strftime("%Y-%m-%d %H:%M:%S %Z")


def summarize(status: dict) -> dict:
    return {
        "healthy": bool(status.get("healthy")),
        "backend_port_open": bool(status.get("backend", {}).get("port_open")),
        "backend_review_api_ok": bool(status.get("backend", {}).get("review_api_ok")),
        "frontend_port_open": bool(status.get("frontend", {}).get("port_open")),
        "frontend_http_ok": bool(status.get("frontend", {}).get("http_ok")),
    }


def format_message(kind: str, status: dict) -> str:
    backend = status.get("backend", {})
    frontend = status.get("frontend", {})
    health = "HEALTHY" if status.get("healthy") else "UNHEALTHY"
    return (
        f"<b>Otonom Media PM2</b>\n"
        f"Event: <b>{kind}</b>\n"
        f"Status: <b>{health}</b>\n"
        f"Backend: {'ok' if backend.get('review_api_ok') else 'down'} — {backend.get('url', '-')}\n"
        f"Frontend: {'ok' if frontend.get('http_ok') else 'down'} — {frontend.get('url', '-')}\n"
        f"Clips in review: {backend.get('clip_count', '-')}\n"
        f"Time: {now_label()}"
    )


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def maybe_notify(kind: str, status: dict) -> None:
    try:
        notify_telegram(format_message(kind, status))
    except Exception as exc:  # pragma: no cover
        print(f"[pm2-health-monitor] notification failed: {exc}", flush=True)


def main() -> int:
    interval = int(os.environ.get("PM2_HEALTH_INTERVAL_SECONDS", "60"))
    once = "--once" in sys.argv
    notify_enabled = "--no-notify" not in sys.argv
    previous = load_state()
    while True:
        status = collect_status()
        current = summarize(status)
        if not previous:
            if notify_enabled:
                maybe_notify("monitor-online", status)
        elif current != previous:
            if notify_enabled:
                maybe_notify("recovered" if status.get("healthy") else "degraded", status)
        save_state(current)
        previous = current
        print(json.dumps({"time": now_label(), **current}, ensure_ascii=False), flush=True)
        if once:
            return 0
        time.sleep(max(interval, 15))


if __name__ == "__main__":
    raise SystemExit(main())
