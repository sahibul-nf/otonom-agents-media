#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _pick_env(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def notify_telegram(message: str) -> dict:
    token = _pick_env("TELEGRAM_BOT_TOKEN")
    chat_id = _pick_env("TELEGRAM_STATUS_CHAT_ID", "TELEGRAM_CHAT_ID", "TELEGRAM_CHANNEL_ID")
    thread_id = _pick_env("TELEGRAM_STATUS_THREAD_ID", "TELEGRAM_THREAD_ID")
    if not token or not chat_id:
        raise RuntimeError("Telegram notification target is not configured")
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if thread_id:
        payload["message_thread_id"] = thread_id
    data = urlencode(payload).encode("utf-8")
    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Telegram send failed: {exc}") from exc


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: telegram_notify.py '<message>'", file=sys.stderr)
        return 2
    notify_telegram(sys.argv[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
