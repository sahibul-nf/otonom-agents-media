"""Live publishing adapters.

Only Telegram is enabled first because it has the smallest operational blast
radius. Other platforms remain dry-run until their OAuth/app-review flows are
implemented explicitly.
"""

from __future__ import annotations

import json
import mimetypes
import os
import secrets
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class LivePublishError(RuntimeError):
    pass


def _multipart_form(fields: dict[str, str], file_field: str, file_path: str) -> tuple[bytes, str]:
    boundary = f"mediaengine{secrets.token_hex(12)}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )

    path = Path(file_path)
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{file_field}"; filename="{path.name}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks), boundary


def publish_telegram_video(payload: dict[str, Any], timeout_seconds: int = 120) -> dict[str, Any]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()
    if not token or not chat_id:
        raise LivePublishError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID are required")

    video_path = str(payload.get("video_path") or "")
    if not video_path or not Path(video_path).exists():
        raise LivePublishError("rendered video file is required for Telegram publish")

    fields = {
        "chat_id": chat_id,
        "caption": str(payload.get("caption") or "")[:1024],
        "parse_mode": str(payload.get("parse_mode") or "HTML"),
        "supports_streaming": "true" if payload.get("supports_streaming", True) else "false",
    }
    body, boundary = _multipart_form(fields, "video", video_path)
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendVideo",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LivePublishError(f"Telegram publish failed: {exc}") from exc
    if not result.get("ok"):
        raise LivePublishError(f"Telegram publish rejected: {result.get('description', 'unknown error')}")
    message = result.get("result", {})
    return {
        "platform": "telegram_channel",
        "status": "published",
        "message_id": message.get("message_id"),
        "chat_id": message.get("chat", {}).get("id"),
    }
