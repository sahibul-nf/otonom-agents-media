"""Render contracts and local renderers for V1 verification."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from .captions import build_fallback_caption_segments
from .db import ARTIFACTS_DIR, ROOT
from .styles import load_style

PREMIUM_PRESET = "nourbit_premium_v1"
PREMIUM_MIN_DURATION_MS = 90_000
PREMIUM_MAX_DURATION_MS = 150_000


def ms_to_timecode(ms: int) -> str:
    total = max(0, ms // 1000)
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def build_caption_segments(transcript_span: str, duration_ms: int, max_words_per_caption: int = 3) -> list[dict[str, Any]]:
    return build_fallback_caption_segments(
        transcript_span,
        duration_ms,
        max_words_per_caption=max_words_per_caption,
    )


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
    style: dict[str, Any] | None = None,
) -> dict[str, Any]:
    duration_ms = candidate["end_ms"] - candidate["start_ms"]
    validate_premium_duration(duration_ms)
    style = style or load_style()
    caption_style = style["caption"]
    captions = candidate.get("timed_captions") or build_caption_segments(
        candidate["transcript_span"],
        duration_ms,
        max_words_per_caption=int(caption_style.get("max_words_per_caption", 3)),
    )
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
        "style": style,
        "cropStrategy": "speaker_aware_or_center_crop",
        "captionStyle": caption_style["preset"],
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
    style: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    job_id = f"render_{uuid.uuid4().hex[:12]}"
    out_dir = ARTIFACTS_DIR / profile["id"] / candidate["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{job_id}_premium.mp4"
    metadata_path = out_dir / f"{job_id}_premium.json"
    props_path = out_dir / f"{job_id}_remotion_props.json"
    remotion_src = ensure_remotion_runtime_asset(source_video_path, job_id)
    contract = build_premium_render_contract(candidate, profile, remotion_src, source_url, source_attribution, style)
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
        "/System/Library/Fonts/Supplemental/Sora-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Sora-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _hex_to_rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        return (255, 255, 255, alpha)
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha)


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


def _write_overlay(
    path: Path,
    lines: list[str],
    top: int,
    font_size: int,
    accent_last: bool = False,
    text_color: str = "#ffffff",
    highlight_color: str = "#f4d35e",
    stroke_width: int = 2,
    stroke_color: str = "#000000",
) -> None:
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
            fill = _hex_to_rgba(highlight_color) if accent_last and line == wrapped[-1] else _hex_to_rgba(text_color)
            draw.text((x, y), line, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=_hex_to_rgba(stroke_color, 230))
            y += font_size + 18
    image.save(path)


def _write_caption_overlay(
    path: Path,
    caption: dict[str, Any],
    active_word_index: int,
    style: dict[str, Any],
) -> None:
    from PIL import Image, ImageDraw

    caption_style = style["caption"]
    font_size = int(caption_style.get("font_size", 54))
    font = _load_font(font_size)
    image = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    words = caption.get("words") or [{"text": word} for word in caption["text"].split()]
    line = " ".join(word["text"] for word in words)
    bbox = draw.textbbox((0, 0), line, font=font, stroke_width=int(caption_style.get("stroke_width", 10)))
    text_width = bbox[2] - bbox[0]
    x = max(48, (1080 - text_width) // 2)
    y = 1180 if caption_style.get("position") == "bottom" else 900
    pad_x = 22
    pad_y = 12
    draw.rounded_rectangle(
        (x - pad_x, y - pad_y, x + text_width + pad_x, y + (bbox[3] - bbox[1]) + pad_y),
        radius=int(caption_style.get("background_radius", 12)),
        fill=(0, 0, 0, 148),
    )
    cursor = x
    for index, word in enumerate(words):
        token = word["text"]
        color = caption_style["highlight_word_color"] if index == active_word_index else caption_style["text_color"]
        draw.text(
            (cursor, y),
            token,
            font=font,
            fill=_hex_to_rgba(color),
            stroke_width=int(caption_style.get("stroke_width", 10)),
            stroke_fill=_hex_to_rgba(caption_style.get("stroke_color", "#000000"), 255),
        )
        token_bbox = draw.textbbox((0, 0), token + " ", font=font, stroke_width=int(caption_style.get("stroke_width", 10)))
        cursor += token_bbox[2] - token_bbox[0]
    image.save(path)


def render_premium_ffmpeg(
    candidate: dict[str, Any],
    profile: dict[str, Any],
    source_video_path: str,
    source_url: str,
    source_attribution: str,
    style: dict[str, Any] | None = None,
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
    style = style or load_style()
    caption_style = style["caption"]
    contract = build_premium_render_contract(candidate, profile, source_video_path, source_url, source_attribution, style)

    title_png = overlay_dir / "title.png"
    cta_png = overlay_dir / "cta.png"
    _write_overlay(
        title_png,
        ["NOURBIT CLIPS", contract["titleHook"]],
        170,
        58,
        stroke_width=int(caption_style.get("stroke_width", 10)),
        stroke_color=caption_style.get("stroke_color", "#000000"),
    )
    _write_overlay(
        cta_png,
        [contract["watermarkText"], contract["ctaText"], contract["sourceAttribution"]],
        1535,
        36,
        True,
        highlight_color=caption_style["highlight_word_color"],
        stroke_width=6,
        stroke_color=caption_style.get("stroke_color", "#000000"),
    )

    caption_inputs: list[Path] = []
    for index, caption in enumerate(contract["captions"][:18], start=1):
        words = caption.get("words") or []
        if not words:
            path = overlay_dir / f"caption_{index:02d}_word_01.png"
            _write_caption_overlay(path, caption, 0, style)
            caption_inputs.append(path)
            continue
        for word_index, _word in enumerate(words):
            path = overlay_dir / f"caption_{index:02d}_word_{word_index + 1:02d}.png"
            _write_caption_overlay(path, caption, word_index, style)
            caption_inputs.append(path)

    filter_parts = [
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,eq=contrast=1.06:saturation=0.96:brightness=-0.025[base]",
        "[base][1:v]overlay=0:0:enable='between(t,0,4.8)'[v1]",
    ]
    current = "v1"
    overlay_index = 2
    for caption in contract["captions"][:18]:
        words = caption.get("words") or []
        word_windows = words or [{"startMs": caption["startMs"], "endMs": caption["endMs"]}]
        for word_window in word_windows:
            next_label = f"v{overlay_index}"
            start = max(5.0, word_window["startMs"] / 1000)
            end = max(start + 0.08, word_window["endMs"] / 1000)
            filter_parts.append(f"[{current}][{overlay_index}:v]overlay=0:0:enable='between(t,{start:.3f},{end:.3f})'[{next_label}]")
            overlay_index += 1
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
