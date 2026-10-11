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
    """Prefer v3 status; fall back to legacy v1 status helper."""
    video_id = (video_id or "").strip()
    if not video_id:
        raise ValueError("video_id is required")
    cfg = config or HeyGenConfig.from_env()
    try:
        return _request("GET", f"/v3/videos/{video_id}", config=cfg)
    except HeyGenApiError as primary:
        try:
            return _request("GET", f"/v1/video_status.get?video_id={video_id}", config=cfg)
        except HeyGenApiError:
            raise primary from None


def video_status_and_url(payload: dict[str, Any]) -> tuple[str, str]:
    status = str(payload.get("status") or "").lower()
    url = str(
        payload.get("video_url")
        or payload.get("url")
        or (payload.get("video") or {}).get("url")
        or ""
    ).strip()
    return status, url


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
        status, _url = video_status_and_url(last)
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


# Default TechTalk IDs from epic #4 / issue #7 (Creator assets — reusable on API wallet).
DEFAULT_VOICE_ID = (os.environ.get("HEYGEN_VOICE_ID") or "LXpG1p9h8viifHEGQiFJ").strip()
DEFAULT_AVATAR_LOOK_ID = (os.environ.get("HEYGEN_AVATAR_LOOK_ID") or "0f4dca86e0bd42d8a8afdae9948338ce").strip()
DEFAULT_AVATAR_GROUP_ID = (os.environ.get("HEYGEN_AVATAR_GROUP_ID") or "").strip()
DEFAULT_ENGINE = (os.environ.get("HEYGEN_ENGINE") or "avatar_iii").strip() or "avatar_iii"
# Rough API-wallet estimate for short avatar clips (override when HeyGen publishes exact rates).
DEFAULT_USD_PER_SECOND = float(os.environ.get("HEYGEN_USD_PER_SECOND") or "0.05")
DEFAULT_MAX_SECONDS_PER_JOB = float(os.environ.get("HEYGEN_MAX_SECONDS_PER_JOB") or "90")


def estimate_script_seconds(script: str, *, words_per_minute: float = 140.0) -> float:
    words = len([w for w in (script or "").split() if w.strip()])
    if words <= 0:
        return 5.0
    seconds = (words / max(60.0, words_per_minute)) * 60.0
    return max(5.0, min(15.0, seconds))


def estimate_cost_usd(total_seconds: float, *, usd_per_second: float | None = None) -> float:
    rate = DEFAULT_USD_PER_SECOND if usd_per_second is None else float(usd_per_second)
    return round(max(0.0, float(total_seconds)) * rate, 4)


def create_avatar_video(
    *,
    script: str,
    title: str = "Explainer avatar",
    avatar_id: str | None = None,
    voice_id: str | None = None,
    engine: str | None = None,
    aspect_ratio: str = "16:9",
    config: HeyGenConfig | None = None,
) -> dict[str, Any]:
    """POST /v3/videos — short talking-avatar clip (Path B / issue #7)."""
    script = (script or "").strip()
    if not script:
        raise ValueError("script is required")
    look = (avatar_id or DEFAULT_AVATAR_LOOK_ID).strip()
    voice = (voice_id or DEFAULT_VOICE_ID).strip()
    engine_type = (engine or DEFAULT_ENGINE).strip() or "avatar_iii"
    body: dict[str, Any] = {
        "type": "avatar",
        "avatar_id": look,
        "script": script,
        "voice_id": voice,
        "title": (title or "Explainer avatar")[:120],
        "aspect_ratio": aspect_ratio or "16:9",
        "engine": {"type": engine_type},
    }
    return _request("POST", "/v3/videos", config=config or HeyGenConfig.from_env(), body=body)


def extract_video_id(payload: dict[str, Any]) -> str:
    for key in ("video_id", "id"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    nested = payload.get("video")
    if isinstance(nested, dict):
        value = str(nested.get("id") or nested.get("video_id") or "").strip()
        if value:
            return value
    return ""


@dataclass
class AvatarClipResult:
    scene_id: str
    dest_name: str
    path: str
    video_id: str
    estimated_seconds: float
    estimated_usd: float
    dry_run: bool


def generate_avatar_clips_for_scenes(
    scenes: list[dict[str, Any]],
    dest_dir: Path,
    *,
    config: HeyGenConfig | None = None,
    avatar_id: str | None = None,
    voice_id: str | None = None,
    engine: str | None = None,
    max_seconds: float | None = None,
    skip_existing: bool = True,
    poll_timeout_s: float = 900,
) -> dict[str, Any]:
    """
    Batch-create 5–15s avatar MP4s for explainer ``type=avatar`` scenes.

    Cost guards: refuse when estimated total seconds exceed ``HEYGEN_MAX_SECONDS_PER_JOB``;
    dry-run writes no files and performs no network calls when ``HEYGEN_API_DRY_RUN=1``.
    """
    cfg = require_api_key(config)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    max_s = DEFAULT_MAX_SECONDS_PER_JOB if max_seconds is None else float(max_seconds)

    avatar_scenes = [
        s
        for s in scenes
        if isinstance(s, dict) and str(s.get("type") or "").lower() == "avatar" and str(s.get("script") or "").strip()
    ]
    estimates = [
        (
            str(s.get("id") or f"avatar_{idx}"),
            float(s.get("duration_target") or 0) or estimate_script_seconds(str(s.get("script") or "")),
            s,
        )
        for idx, s in enumerate(avatar_scenes, start=1)
    ]
    total_seconds = sum(item[1] for item in estimates)
    estimated_usd = estimate_cost_usd(total_seconds)
    if total_seconds > max_s + 1e-6:
        raise HeyGenApiError(
            f"HeyGen cost guard: estimated {total_seconds:.1f}s exceeds max {max_s:.1f}s "
            f"(~${estimated_usd:.2f}). Lower scene count/scripts or raise HEYGEN_MAX_SECONDS_PER_JOB."
        )

    results: list[AvatarClipResult] = []
    log_lines = [
        f"heygen avatar batch: scenes={len(estimates)} est_seconds={total_seconds:.1f} est_usd=${estimated_usd:.4f} dry_run={cfg.dry_run}"
    ]

    for scene_id, est_s, scene in estimates:
        dest_name = str(scene.get("clip_file") or f"{scene_id}.mp4").strip()
        dest_name = Path(dest_name).name
        if not dest_name.lower().endswith((".mp4", ".mov", ".webm", ".mkv")):
            dest_name = f"{Path(dest_name).stem}.mp4"
        dest = dest_dir / dest_name
        if skip_existing and dest.exists() and dest.stat().st_size > 0:
            results.append(
                AvatarClipResult(
                    scene_id=scene_id,
                    dest_name=dest_name,
                    path=str(dest),
                    video_id="",
                    estimated_seconds=est_s,
                    estimated_usd=estimate_cost_usd(est_s),
                    dry_run=cfg.dry_run,
                )
            )
            log_lines.append(f"skip existing {dest_name}")
            continue

        script = str(scene.get("script") or "").strip()
        title = str(scene.get("headline") or scene_id)[:80] or scene_id
        created = create_avatar_video(
            script=script,
            title=title,
            avatar_id=avatar_id,
            voice_id=voice_id,
            engine=engine,
            config=cfg,
        )
        if cfg.dry_run:
            video_id = f"dry_run_{scene_id}"
            log_lines.append(f"dry_run create {scene_id} (~{est_s:.1f}s ${estimate_cost_usd(est_s):.4f})")
            results.append(
                AvatarClipResult(
                    scene_id=scene_id,
                    dest_name=dest_name,
                    path="",
                    video_id=video_id,
                    estimated_seconds=est_s,
                    estimated_usd=estimate_cost_usd(est_s),
                    dry_run=True,
                )
            )
            continue

        video_id = extract_video_id(created)
        if not video_id:
            raise HeyGenApiError(f"HeyGen create returned no video_id: {created}", payload=created)
        ready = poll_video_until_ready(video_id, config=cfg, timeout_s=poll_timeout_s)
        _status, video_url = video_status_and_url(ready)
        if not video_url:
            raise HeyGenApiError(f"HeyGen video {video_id} completed without video_url", payload=ready)
        download_video_url(video_url, dest)
        log_lines.append(f"downloaded {dest_name} video_id={video_id} est=${estimate_cost_usd(est_s):.4f}")
        results.append(
            AvatarClipResult(
                scene_id=scene_id,
                dest_name=dest_name,
                path=str(dest),
                video_id=video_id,
                estimated_seconds=est_s,
                estimated_usd=estimate_cost_usd(est_s),
                dry_run=False,
            )
        )

    for line in log_lines:
        print(line, flush=True)

    return {
        "ok": True,
        "dry_run": cfg.dry_run,
        "estimated_seconds": total_seconds,
        "estimated_usd": estimated_usd,
        "max_seconds": max_s,
        "clips": [r.__dict__ for r in results],
        "log": log_lines,
    }
