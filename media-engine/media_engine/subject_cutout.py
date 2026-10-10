"""Optional local subject cutout matting and depth layer integration for talking-head reels."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def is_rembg_available() -> bool:
    """Check whether rembg or local background matting model is installed."""
    try:
        import rembg  # noqa: F401
        return True
    except ImportError:
        pass
    if shutil.which("rembg"):
        return True
    return False


def extract_keyframe_from_video(
    video_path: Path | str,
    output_image_path: Path | str,
    timestamp_s: float = 1.0,
) -> bool:
    """Extract a representative keyframe image from the source video via FFmpeg."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    
    out = Path(output_image_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        f"{timestamp_s:.3f}",
        "-i",
        str(video_path),
        "-vframes",
        "1",
        "-q:v",
        "2",
        str(out),
    ]
    result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0 and out.exists() and out.stat().st_size > 0


def extract_subject_matte(
    input_image_path: Path | str,
    output_image_path: Path | str,
    model_name: str = "u2netp",
) -> bool:
    """Extract foreground subject mask / alpha matte using rembg (u2netp by default)."""
    inp = Path(input_image_path)
    out = Path(output_image_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # 1. Try python library
    try:
        import rembg
        from PIL import Image

        with Image.open(inp) as img:
            session = rembg.new_session(model_name)
            cutout = rembg.remove(img, session=session)
            cutout.save(out, format="PNG")
            return out.exists() and out.stat().st_size > 0
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("rembg python execution failed: %s", exc)

    # 2. Try CLI fallback
    cli = shutil.which("rembg")
    if cli:
        cmd = [cli, "i", "-m", model_name, str(inp), str(out)]
        result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.returncode == 0 and out.exists() and out.stat().st_size > 0

    return False


def resolve_depth_keyword(contract: dict[str, Any]) -> str:
    """Resolve the prominent punch keyword to display behind the speaker."""
    # 1. Explicit override in contract or style
    style = contract.get("style") if isinstance(contract.get("style"), dict) else {}
    keyword = str(contract.get("depthKeyword") or style.get("depth_keyword") or "").strip()
    if keyword:
        return keyword.upper()

    # 2. Title hook primary word
    title_hook = str(contract.get("titleHook") or "").strip()
    if title_hook:
        words = [w.strip("?,!.:;\"'") for w in title_hook.split() if len(w.strip("?,!.:;\"'")) >= 3]
        if words:
            # Prefer uppercase or longest punch word
            longest = max(words, key=len)
            return longest.upper()

    # 3. Fallback
    return "IMPACT"


def generate_subject_depth_assets(
    source_video_path: Path | str,
    target_media_dir: Path,
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Prepare subject cutout assets for placing keyword layers behind the speaker.
    
    If rembg is unavailable, falls back gracefully without crashing the render pipeline.
    """
    target_media_dir.mkdir(parents=True, exist_ok=True)
    depth_keyword = resolve_depth_keyword(contract)
    output_cutout = target_media_dir / "subject_cutout.png"
    temp_frame = target_media_dir / "keyframe_temp.jpg"

    available = is_rembg_available()
    has_cutout = False

    if available and Path(source_video_path).exists():
        extracted = extract_keyframe_from_video(source_video_path, temp_frame, timestamp_s=1.0)
        if extracted:
            has_cutout = extract_subject_matte(temp_frame, output_cutout, model_name="u2netp")
            if temp_frame.exists():
                temp_frame.unlink(missing_ok=True)

    return {
        "enabled": True,
        "rembg_available": available,
        "has_cutout_matte": has_cutout,
        "cutout_matte_rel_path": "media/subject_cutout.png" if has_cutout else None,
        "depth_keyword": depth_keyword,
        "reason": "" if has_cutout else ("rembg not installed; running in graceful depth fallback mode" if not available else "cutout extraction failed"),
    }
