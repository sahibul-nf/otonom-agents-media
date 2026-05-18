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
from urllib.parse import urlencode


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
        "remote_id": str(message.get("message_id") or ""),
        "message_id": message.get("message_id"),
        "chat_id": message.get("chat", {}).get("id"),
        "raw": result,
    }


def _json_request(
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    method: str = "POST",
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    data = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LivePublishError(f"publish request failed: {exc}") from exc


def _form_request(
    url: str,
    fields: dict[str, str],
    headers: dict[str, str] | None = None,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    data = urlencode(fields).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LivePublishError(f"publish request failed: {exc}") from exc


def _upload_bytes(
    url: str,
    body: bytes,
    headers: dict[str, str],
    method: str = "PUT",
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8", errors="replace")
            if not text.strip():
                return {"status": response.status}
            return json.loads(text)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LivePublishError(f"video upload failed: {exc}") from exc


def _require_file(payload: dict[str, Any]) -> Path:
    video_path = str(payload.get("video_path") or "")
    path = Path(video_path)
    if not video_path or not path.exists():
        raise LivePublishError("rendered video file is required for live publish")
    return path


def publish_youtube_short(payload: dict[str, Any], timeout_seconds: int = 300) -> dict[str, Any]:
    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()
    if not client_id or not client_secret or not refresh_token:
        raise LivePublishError("YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN are required")
    path = _require_file(payload)
    token = _form_request(
        "https://oauth2.googleapis.com/token",
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout_seconds=timeout_seconds,
    ).get("access_token")
    if not token:
        raise LivePublishError("YouTube OAuth refresh did not return an access token")
    metadata = {
        "snippet": {
            "title": str(payload.get("title") or payload.get("caption") or "Short")[:100],
            "description": str(payload.get("caption") or ""),
            "categoryId": os.environ.get("YOUTUBE_CATEGORY_ID", "22"),
        },
        "status": {
            "privacyStatus": os.environ.get("YOUTUBE_PRIVACY_STATUS", "private"),
            "selfDeclaredMadeForKids": False,
        },
    }
    init = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(metadata).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": mimetypes.guess_type(path.name)[0] or "video/mp4",
            "X-Upload-Content-Length": str(path.stat().st_size),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(init, timeout=timeout_seconds) as response:
            upload_url = response.headers.get("Location", "")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise LivePublishError(f"YouTube upload session failed: {exc}") from exc
    if not upload_url:
        raise LivePublishError("YouTube upload session did not return an upload URL")
    uploaded = _upload_bytes(
        upload_url,
        path.read_bytes(),
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": mimetypes.guess_type(path.name)[0] or "video/mp4",
            "Content-Length": str(path.stat().st_size),
        },
        method="PUT",
        timeout_seconds=timeout_seconds,
    )
    remote_id = str(uploaded.get("id") or "")
    if not remote_id:
        raise LivePublishError("YouTube upload did not return a video id")
    return {
        "platform": "youtube_shorts",
        "status": "published",
        "remote_id": remote_id,
        "remote_url": f"https://www.youtube.com/watch?v={remote_id}",
        "raw": uploaded,
    }


def publish_tiktok_video(payload: dict[str, Any], timeout_seconds: int = 300) -> dict[str, Any]:
    access_token = os.environ.get("TIKTOK_ACCESS_TOKEN", "").strip()
    if not access_token:
        raise LivePublishError("TIKTOK_ACCESS_TOKEN is required")
    path = _require_file(payload)
    init_payload = {
        "post_info": {
            "title": str(payload.get("caption") or "")[:2200],
            "privacy_level": os.environ.get("TIKTOK_DEFAULT_VISIBILITY", "SELF_ONLY"),
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": path.stat().st_size,
            "chunk_size": path.stat().st_size,
            "total_chunk_count": 1,
        },
    }
    init = _json_request(
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        init_payload,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout_seconds=timeout_seconds,
    )
    data = init.get("data") or {}
    upload_url = data.get("upload_url")
    publish_id = data.get("publish_id")
    if not upload_url or not publish_id:
        raise LivePublishError(f"TikTok init did not return upload_url/publish_id: {init}")
    _upload_bytes(
        upload_url,
        path.read_bytes(),
        {
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{path.stat().st_size - 1}/{path.stat().st_size}",
        },
        method="PUT",
        timeout_seconds=timeout_seconds,
    )
    return {
        "platform": "tiktok",
        "status": "published",
        "remote_id": str(publish_id),
        "raw": init,
    }


def publish_facebook_reel(payload: dict[str, Any], timeout_seconds: int = 300) -> dict[str, Any]:
    page_id = os.environ.get("META_PAGE_ID", "").strip()
    page_token = os.environ.get("META_PAGE_ACCESS_TOKEN", "").strip()
    api_version = os.environ.get("META_API_VERSION", "v20.0").strip() or "v20.0"
    if not page_id or not page_token:
        raise LivePublishError("META_PAGE_ID and META_PAGE_ACCESS_TOKEN are required")
    path = _require_file(payload)
    base = f"https://graph.facebook.com/{api_version}/{page_id}/video_reels"
    start = _form_request(
        base,
        {"upload_phase": "start", "access_token": page_token},
        timeout_seconds=timeout_seconds,
    )
    video_id = str(start.get("video_id") or start.get("id") or "")
    upload_url = str(start.get("upload_url") or "")
    if not video_id or not upload_url:
        raise LivePublishError(f"Facebook Reels start did not return video_id/upload_url: {start}")
    _upload_bytes(
        upload_url,
        path.read_bytes(),
        {
            "Authorization": f"OAuth {page_token}",
            "offset": "0",
            "file_size": str(path.stat().st_size),
            "Content-Type": "application/octet-stream",
        },
        method="POST",
        timeout_seconds=timeout_seconds,
    )
    finish = _form_request(
        base,
        {
            "upload_phase": "finish",
            "video_id": video_id,
            "description": str(payload.get("caption") or ""),
            "access_token": page_token,
        },
        timeout_seconds=timeout_seconds,
    )
    return {
        "platform": "facebook_reels",
        "status": "published",
        "remote_id": video_id,
        "remote_url": f"https://www.facebook.com/reel/{video_id}",
        "raw": {"start": start, "finish": finish},
    }


def publish_live_payload(platform: str, payload: dict[str, Any]) -> dict[str, Any]:
    if platform == "telegram_channel":
        return publish_telegram_video(payload)
    if platform == "youtube_shorts":
        return publish_youtube_short(payload)
    if platform == "tiktok":
        return publish_tiktok_video(payload)
    if platform == "facebook_reels":
        return publish_facebook_reel(payload)
    raise LivePublishError(f"live publishing is not supported for {platform}")
