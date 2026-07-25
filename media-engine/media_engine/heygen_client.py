"""HeyGen Direct API client (Path B scaffold).

Creator MCP/OAuth uses premium credits. This module uses ``HEYGEN_API_KEY`` and the
**separate** USD API wallet. Avatar look IDs and voice IDs created on Creator still work.

Path A (Cursor + HeyGen MCP) remains the default near-term path — see
``docs/heygen-paths.md``. Do not call this client unless API key + wallet are configured.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlretrieve


API_BASE = "https://api.heygen.com"


@dataclass(frozen=True)
class HeyGenConfig:
    api_key: str
    dry_run: bool = False

    @classmethod
    def from_env(cls, *, dry_run: bool | None = None) -> HeyGenConfig:
        key = (os.environ.get("HEYGEN_API_KEY") or "").strip()
        if dry_run is None:
            dry_run = (os.environ.get("HEYGEN_API_DRY_RUN") or "").strip().lower() in {
                "1",
                "true",
                "yes",
            }
        return cls(api_key=key, dry_run=bool(dry_run))


class HeyGenApiError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status = status
        self.payload = payload


def require_api_key(config: HeyGenConfig | None = None) -> HeyGenConfig:
    cfg = config or HeyGenConfig.from_env()
    if cfg.dry_run:
        return cfg
    if not cfg.api_key:
        raise HeyGenApiError(
            "HEYGEN_API_KEY is not set. Path B uses the Direct API wallet (USD), "
            "not Creator premium credits. For Path A use Cursor + HeyGen MCP instead "
            "(see docs/heygen-paths.md)."
        )
    return cfg


def _request(
    method: str,
    path: str,
    *,
    config: HeyGenConfig,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = require_api_key(config)
    if cfg.dry_run:
        return {
            "dry_run": True,
            "method": method,
            "path": path,
            "body": body or {},
        }

    url = f"{API_BASE}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method.upper(),
        headers={
            "X-Api-Key": cfg.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(err_body) if err_body else None
        except json.JSONDecodeError:
            payload = err_body
        raise HeyGenApiError(
            f"HeyGen API {method} {path} failed ({exc.code}): {err_body[:800]}",
            status=exc.code,
            payload=payload,
        ) from exc
    except urllib.error.URLError as exc:
        raise HeyGenApiError(f"HeyGen API network error: {exc}") from exc

    if not raw:
        return {}
    parsed = json.loads(raw)
    if isinstance(parsed, dict) and "data" in parsed and isinstance(parsed["data"], dict):
        return parsed["data"]
    return parsed if isinstance(parsed, dict) else {"result": parsed}


def create_video_agent_session(
    *,
    prompt: str,
    voice_id: str | None = None,
    avatar_id: str | None = None,
    orientation: str = "landscape",
    mode: str = "generate",
    config: HeyGenConfig | None = None,
) -> dict[str, Any]:
    """POST /v3/video-agents — Path B Video Agent create."""
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    body: dict[str, Any] = {
        "prompt": prompt,
        "mode": mode or "generate",
        "orientation": orientation or "landscape",
    }
    if voice_id:
        body["voice_id"] = voice_id
    if avatar_id:
        body["avatar_id"] = avatar_id
    return _request("POST", "/v3/video-agents", config=config or HeyGenConfig.from_env(), body=body)


def get_video_agent_session(session_id: str, *, config: HeyGenConfig | None = None) -> dict[str, Any]:
    session_id = (session_id or "").strip()
    if not session_id:
        raise ValueError("session_id is required")
    return _request(
        "GET",
        f"/v3/video-agents/{session_id}",
        config=config or HeyGenConfig.from_env(),
    )


def get_video(video_id: str, *, config: HeyGenConfig | None = None) -> dict[str, Any]:
    video_id = (video_id or "").strip()
    if not video_id:
        raise ValueError("video_id is required")
    return _request("GET", f"/v1/video_status.get?video_id={video_id}", config=config or HeyGenConfig.from_env())


def poll_video_until_ready(
    video_id: str,
    *,
    config: HeyGenConfig | None = None,
    timeout_s: float = 900,
    interval_s: float = 8,
) -> dict[str, Any]:
    """Poll until video status is completed/failed or timeout."""
    cfg = require_api_key(config)
    if cfg.dry_run:
        return {"dry_run": True, "video_id": video_id, "status": "completed", "video_url": None}

    deadline = time.time() + timeout_s
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = get_video(video_id, config=cfg)
        status = str(last.get("status") or last.get("data", {}).get("status") or "").lower()
        if status in {"completed", "done", "success"}:
            return last
        if status in {"failed", "error"}:
            raise HeyGenApiError(f"HeyGen video failed: {last}", payload=last)
        time.sleep(interval_s)
    raise HeyGenApiError(f"Timed out waiting for video {video_id}", payload=last)


def download_video_url(video_url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(video_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("video_url must be https")
    urlretrieve(video_url, dest)  # noqa: S310
    return dest


# Default TechTalk / Sahibul NF IDs (Creator assets — reusable on API wallet).
DEFAULT_VOICE_ID = os.environ.get("HEYGEN_VOICE_ID", "0e0c18c072cf4ab6b617dd981f271670")
DEFAULT_AVATAR_LOOK_ID = os.environ.get("HEYGEN_AVATAR_LOOK_ID", "3ad1d28c72c14ac7940be96b896cac60")
DEFAULT_AVATAR_GROUP_ID = os.environ.get("HEYGEN_AVATAR_GROUP_ID", "3fd3a245e31047eaa28c8578ab252338")
