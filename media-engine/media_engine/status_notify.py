"""Best-effort Telegram status messages (not video publish)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _pick_env(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def send_status_telegram(message: str, *, require_config: bool = False) -> dict[str, Any] | None:
    """Send a plain status message via Telegram Bot API.

    Returns the API JSON on success, None when credentials are missing and
    ``require_config`` is False. Raises RuntimeError when send fails or when
    credentials are missing and ``require_config`` is True.
    """
    text = (message or "").strip()
    if not text:
        raise ValueError("message is required")

    token = _pick_env("TELEGRAM_BOT_TOKEN")
    chat_id = _pick_env("TELEGRAM_STATUS_CHAT_ID", "TELEGRAM_CHAT_ID", "TELEGRAM_CHANNEL_ID")
    thread_id = _pick_env("TELEGRAM_STATUS_THREAD_ID", "TELEGRAM_THREAD_ID")
    if not token or not chat_id:
        if require_config:
            raise RuntimeError("Telegram notification target is not configured")
        return None

    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if thread_id:
        payload["message_thread_id"] = thread_id

    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Telegram send failed: {exc}") from exc
