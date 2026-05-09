"""Render contracts and local renderers for V1 verification."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from .db import ARTIFACTS_DIR, ROOT

PREMIUM_PRESET = "nourbit_premium_v1"
PREMIUM_MIN_DURATION_MS = 90_000
PREMIUM_MAX_DURATION_MS = 150_000


def ms_to_timecode(ms: int) -> str:
    total = max(0, ms // 1000)
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def build_caption_segments(transcript_span: str, duration_ms: int) -> list[dict[str, Any]]:
    words = [word.strip() for word in transcript_span.split() if word.strip()]
    if not words:
        return []

    chunk_size = 7
    chunks = [" ".join(words[index : index + chunk_size]) for index in range(0, len(words), chunk_size)]
    step = max(1800, duration_ms // max(1, len(chunks)))
    captions: list[dict[str, Any]] = []
    cursor = 0
    for chunk in chunks:
        end = min(duration_ms, cursor + step)
        captions.append(
            {
                "text": chunk,
                "startMs": cursor,
                "endMs": max(end, cursor + 1000),
                "timestampMs": cursor,
                "confidence": None,
            }
        )
        cursor = end
        if cursor >= duration_ms:
            break
    return captions


def validate_premium_duration(duration_ms: int) -> None:
    if duration_ms < PREMIUM_MIN_DURATION_MS or duration_ms > PREMIUM_MAX_DURATION_MS:
        min_s = PREMIUM_MIN_DURATION_MS // 1000
        max_s = PREMIUM_MAX_DURATION_MS // 1000
        raise ValueError(f"premium Nourbit clips must be {min_s}-{max_s}s")


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


def build_premium_render_contract(
    candidate: dict[str, Any],
    profile: dict[str, Any],
    source_video_path: str,
    source_url: str,
    source_attribution: str,
) -> dict[str, Any]:
    duration_ms = candidate["end_ms"] - candidate["start_ms"]
    validate_premium_duration(duration_ms)
    captions = build_caption_segments(candidate["transcript_span"], duration_ms)
    return {
        "composition": "NourbitPremiumShort",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "durationMs": duration_ms,
        "candidateId": candidate["id"],
        "sourceVideoPath": source_video_path,
        "sourceUrl": source_url,
        "sourceAttribution": source_attribution,
        "startMs": candidate["start_ms"],
        "endMs": candidate["end_ms"],
        "startTimecode": ms_to_timecode(candidate["start_ms"]),
        "endTimecode": ms_to_timecode(candidate["end_ms"]),
        "titleHook": candidate["title_hook"],
        "subtitle": candidate["viral_reason"],
        "captionText": candidate["transcript_span"],
        "captions": captions,
        "visualBeats": [
            {"type": "hook", "startMs": 0, "endMs": min(4500, duration_ms)},
            {"type": "caption_emphasis", "startMs": 5500, "endMs": max(6500, duration_ms - 9000)},
            {"type": "cta", "startMs": max(0, duration_ms - 6500), "endMs": duration_ms},
        ],
        "watermarkText": profile["watermark_text"],
        "ctaText": profile["cta_text"],
        "stylePreset": PREMIUM_PRESET,
        "cropStrategy": "speaker_aware_or_center_crop",
        "captionStyle": "nourbit_kinetic_safezone",
        "sfxPack": ["whoosh", "switch", "mouse-click"],
        "publishSafety": {
            "reviewRequired": True,
            "autoPublishAllowed": False,
            "reason": "public third-party source remains review-gated until permission evidence is recorded",
        },
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


def ensure_remotion_runtime_asset(source_path: str, job_id: str) -> str:
    public_runtime = ROOT / "render" / "remotion" / "public" / "runtime" / job_id
    public_runtime.mkdir(parents=True, exist_ok=True)
    source = Path(source_path)
    target = public_runtime / "source.mp4"
    shutil.copy2(source, target)
    return f"runtime/{job_id}/source.mp4"


def render_premium_remotion(
    candidate: dict[str, Any],
    profile: dict[str, Any],
    source_video_path: str,
    source_url: str,
    source_attribution: str,
) -> tuple[str, dict[str, Any]]:
    job_id = f"render_{uuid.uuid4().hex[:12]}"
    out_dir = ARTIFACTS_DIR / profile["id"] / candidate["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{job_id}_premium.mp4"
    metadata_path = out_dir / f"{job_id}_premium.json"
    props_path = out_dir / f"{job_id}_remotion_props.json"
    remotion_src = ensure_remotion_runtime_asset(source_video_path, job_id)
    contract = build_premium_render_contract(candidate, profile, remotion_src, source_url, source_attribution)
    metadata_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")
    props_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")

    remotion_dir = ROOT / "render" / "remotion"
    cmd = [
        "npx",
        "remotion",
        "render",
        "src/index.tsx",
        "NourbitPremiumShort",
        str(output),
        "--props",
        str(props_path),
        "--codec",
        "h264",
        "--pixel-format",
        "yuv420p",
        "--concurrency",
        "1",
    ]
    result = subprocess.run(cmd, cwd=remotion_dir, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"remotion render failed: {result.stderr[-1600:] or result.stdout[-1600:]}")
    return str(output), contract


def _load_font(size: int):
    try:
        from PIL import ImageFont
    except ImportError as exc:
        raise RuntimeError("Pillow is required for FFmpeg premium overlays") from exc

    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _wrap_text(draw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _write_overlay(path: Path, lines: list[str], top: int, font_size: int, accent_last: bool = False) -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _load_font(font_size)
    y = top
    max_width = 920
    for raw_line in lines:
        wrapped = _wrap_text(draw, raw_line, font, max_width)
        for line in wrapped:
            bbox = draw.textbbox((0, 0), line, font=font)
            x = (1080 - (bbox[2] - bbox[0])) // 2
            pad_x = 24
            pad_y = 10
            draw.rounded_rectangle(
                (x - pad_x, y - pad_y, x + (bbox[2] - bbox[0]) + pad_x, y + (bbox[3] - bbox[1]) + pad_y),
                radius=18,
                fill=(0, 0, 0, 168),
                outline=(255, 255, 255, 36),
                width=2,
            )
            fill = (244, 211, 94, 255) if accent_last and line == wrapped[-1] else (255, 255, 255, 255)
            draw.text((x, y), line, font=font, fill=fill, stroke_width=2, stroke_fill=(0, 0, 0, 210))
            y += font_size + 18
    image.save(path)


def render_premium_ffmpeg(
    candidate: dict[str, Any],
    profile: dict[str, Any],
    source_video_path: str,
    source_url: str,
    source_attribution: str,
) -> tuple[str, dict[str, Any]]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for local premium render")

    job_id = f"render_{uuid.uuid4().hex[:12]}"
    out_dir = ARTIFACTS_DIR / profile["id"] / candidate["id"]
    overlay_dir = out_dir / f"{job_id}_overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{job_id}_premium.mp4"
    metadata_path = out_dir / f"{job_id}_premium.json"
    contract = build_premium_render_contract(candidate, profile, source_video_path, source_url, source_attribution)

    title_png = overlay_dir / "title.png"
    cta_png = overlay_dir / "cta.png"
    _write_overlay(title_png, ["NOURBIT CLIPS", contract["titleHook"]], 170, 58)
    _write_overlay(cta_png, [contract["watermarkText"], contract["ctaText"], contract["sourceAttribution"]], 1535, 36, True)

    caption_inputs: list[Path] = []
    for index, caption in enumerate(contract["captions"][:18], start=1):
        path = overlay_dir / f"caption_{index:02d}.png"
        _write_overlay(path, [caption["text"]], 1180, 50, True)
        caption_inputs.append(path)

    filter_parts = [
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,eq=contrast=1.06:saturation=0.96:brightness=-0.025[base]",
        "[base][1:v]overlay=0:0:enable='between(t,0,4.8)'[v1]",
    ]
    current = "v1"
    for index, caption in enumerate(contract["captions"][:18], start=1):
        next_label = f"v{index + 1}"
        start = max(5.0, caption["startMs"] / 1000)
        end = caption["endMs"] / 1000
        filter_parts.append(f"[{current}][{index + 1}:v]overlay=0:0:enable='between(t,{start:.3f},{end:.3f})'[{next_label}]")
        current = next_label
    cta_input_index = len(caption_inputs) + 2
    filter_parts.append(f"[{current}][{cta_input_index}:v]overlay=0:0:enable='gte(t,{max(0, contract['durationMs'] / 1000 - 6.5):.3f})'[v]")
    filter_path = out_dir / f"{job_id}_filter.txt"
    filter_path.write_text(";\n".join(filter_parts), encoding="utf-8")

    cmd = [ffmpeg, "-y", "-i", source_video_path, "-i", str(title_png)]
    for caption_input in caption_inputs:
        cmd.extend(["-i", str(caption_input)])
    cmd.extend(
        [
            "-i",
            str(cta_png),
            "-filter_complex_script",
            str(filter_path),
            "-map",
            "[v]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg premium render failed: {result.stderr[-1600:]}")
    metadata_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(output), contract
