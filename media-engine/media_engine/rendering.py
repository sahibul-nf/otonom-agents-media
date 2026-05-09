"""Render contract and minimal FFmpeg renderer for V1 verification."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from .db import ARTIFACTS_DIR


def build_render_contract(candidate: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    duration_ms = candidate["end_ms"] - candidate["start_ms"]
    return {
        "composition": "NourbitShort",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "duration_ms": duration_ms,
        "candidate_id": candidate["id"],
        "title_hook": candidate["title_hook"],
        "caption_text": candidate["transcript_span"],
        "watermark_text": profile["watermark_text"],
        "cta_text": profile["cta_text"],
        "caption_style": "caption_pop",
        "motion_template": "lecture_clean",
        "sfx_pack": ["whoosh", "mouse-click"],
    }


def render_minimal_ffmpeg(candidate: dict[str, Any], profile: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for local render verification")

    job_id = f"render_{uuid.uuid4().hex[:12]}"
    out_dir = ARTIFACTS_DIR / profile["id"] / candidate["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{job_id}.mp4"
    metadata_path = out_dir / f"{job_id}.json"
    contract = build_render_contract(candidate, profile)

    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=0x111111:s=1080x1920:d=3",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-shortest",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(output),
    ]
    result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg render failed: {result.stderr[-1200:]}")
    metadata_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(output), contract
