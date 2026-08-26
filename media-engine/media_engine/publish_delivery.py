"""Publish platform compatibility by clip orientation (landscape long-form vs portrait shorts)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .db import fetch_one

ALL_DELIVERY_PLATFORMS: tuple[str, ...] = (
    "telegram_channel",
    "youtube_shorts",
    "youtube_video",
    "facebook_reels",
    "tiktok",
)

PORTRAIT_ONLY_PLATFORMS = frozenset({"youtube_shorts", "facebook_reels", "tiktok"})
LANDSCAPE_ONLY_PLATFORMS = frozenset({"youtube_video"})


def _loads(value: Any, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return fallback or {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback or {}
    return parsed if isinstance(parsed, dict) else (fallback or {})


def _ffprobe_bin() -> str | None:
    from shutil import which

    path = which("ffprobe")
    if path:
        return path
    for candidate in (Path("/opt/homebrew/bin/ffprobe"), Path("/usr/local/bin/ffprobe"), Path("/usr/bin/ffprobe")):
        if candidate.exists():
            return str(candidate)
    return None


def probe_video_dimensions(path: str | Path) -> tuple[int, int] | None:
    ffprobe = _ffprobe_bin()
    if not ffprobe:
        return None
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0:s=x",
            str(path),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        width_text, height_text = (result.stdout or "").strip().split("x", 1)
        width = int(width_text)
        height = int(height_text)
    except (ValueError, IndexError):
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def candidate_delivery_orientation(
    candidate: dict[str, Any],
    render_job: dict[str, Any] | None = None,
) -> str:
    """Return ``landscape`` for 16:9 long-form, otherwise ``portrait`` (shorts default)."""
    metadata = _loads(candidate.get("curation_metadata_json"))
    if not metadata and isinstance(candidate.get("curation_metadata"), dict):
        metadata = candidate["curation_metadata"]
    kind = str(metadata.get("kind") or "")
    if kind in {"longform_ingest", "explainer"}:
        return "landscape"
    if str(candidate.get("caption_source") or "") in {"ingest_longform", "explainer"}:
        return "landscape"

    render_metadata = _loads(render_job.get("metadata_json") if render_job else None)
    if not render_metadata and isinstance(candidate.get("render_metadata"), dict):
        render_metadata = candidate["render_metadata"]
    if not render_metadata and candidate.get("render_metadata_json"):
        render_metadata = _loads(candidate.get("render_metadata_json"))

    preset = str(render_job.get("preset") or "") if render_job else ""
    if preset == "explainer_long_16_9":
        return "landscape"
    if str(render_metadata.get("hyperframesFormat") or "") == "long_16_9":
        return "landscape"
    if str(render_metadata.get("kind") or "") in {"longform_ingest", "explainer"}:
        return "landscape"

    output_path = ""
    if render_job:
        output_path = str(render_job.get("output_path") or "")
    if not output_path:
        output_path = str(candidate.get("output_path") or "")
    if output_path:
        dimensions = probe_video_dimensions(output_path)
        if dimensions:
            width, height = dimensions
            if width > height:
                return "landscape"
            if height > width:
                return "portrait"
    return "portrait"


def platform_compatible_with_orientation(platform: str, orientation: str) -> bool:
    if orientation == "landscape":
        return platform not in PORTRAIT_ONLY_PLATFORMS
    return platform not in LANDSCAPE_ONLY_PLATFORMS


def filter_platforms_for_orientation(platforms: list[str], orientation: str) -> list[str]:
    return [platform for platform in platforms if platform_compatible_with_orientation(platform, orientation)]


def latest_render_job(conn, candidate_id: str) -> dict[str, Any] | None:
    row = fetch_one(
        conn,
        "SELECT * FROM render_jobs WHERE candidate_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
        (candidate_id,),
    )
    return dict(row) if row else None


def candidate_orientation_for_id(conn, candidate_id: str) -> str:
    candidate = fetch_one(conn, "SELECT * FROM clip_candidates WHERE id = ?", (candidate_id,))
    if not candidate:
        return "portrait"
    render_job = latest_render_job(conn, candidate_id)
    return candidate_delivery_orientation(dict(candidate), render_job)
