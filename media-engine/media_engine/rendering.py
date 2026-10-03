"""Render contracts and local renderers for V1 verification."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from .captions import build_fallback_caption_segments, normalize_caption_groups, normalize_caption_timeline_for_render
from .db import ARTIFACTS_DIR, ROOT
from .overlay_copy import overlay_slots_for_candidate
from .hyperframes_renderer import check_hyperframes_runtime, render_premium_hyperframes as _render_hyperframes_contract
from .silence_trim import captions_duration_ms, probe_duration_ms, source_already_silence_trimmed
from .styles import load_style

PREMIUM_PRESET = "nourbit_premium_v1"
PREMIUM_MIN_DURATION_MS = 20_000
PREMIUM_MAX_DURATION_MS = 180_000


def build_caption_segments(transcript_span: str, duration_ms: int, max_words_per_caption: int = 3) -> list[dict[str, Any]]:
    """Compatibility helper for tests and diagnostics."""
    return build_fallback_caption_segments(
        transcript_span,
        duration_ms,
        max_words_per_caption=max_words_per_caption,
    )


def ms_to_timecode(ms: int) -> str:
    total = max(0, ms // 1000)
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def validate_premium_duration(duration_ms: int) -> None:
    if duration_ms < PREMIUM_MIN_DURATION_MS or duration_ms > PREMIUM_MAX_DURATION_MS:
        min_s = PREMIUM_MIN_DURATION_MS // 1000
        max_s = PREMIUM_MAX_DURATION_MS // 1000
        raise ValueError(f"premium Nourbit clips must be {min_s}-{max_s}s")


def build_caption_events(captions: list[dict[str, Any]], duration_ms: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for caption_index, caption in enumerate(captions):
        caption_start = max(0, int(caption.get("startMs", 0)))
        caption_end = min(duration_ms, int(caption.get("endMs", caption_start)))
        if caption_end <= caption_start:
            continue
        words = caption.get("words") or [{"text": word, "startMs": caption_start} for word in caption["text"].split()]
        if not words:
            continue
        for word_index, word in enumerate(words):
            start_ms = max(caption_start, int(word.get("startMs", caption_start)))
            next_start_ms = (
                max(caption_start, int(words[word_index + 1].get("startMs", caption_end)))
                if word_index + 1 < len(words)
                else caption_end
            )
            end_ms = min(caption_end, next_start_ms)
            if end_ms <= start_ms:
                end_ms = min(caption_end, start_ms + 80)
            if end_ms <= start_ms:
                continue
            events.append(
                {
                    "captionIndex": caption_index,
                    "activeWordIndex": word_index,
                    "startMs": start_ms,
                    "endMs": end_ms,
                    "text": caption["text"],
                    "words": words,
                }
            )

    normalized: list[dict[str, Any]] = []
    for event in sorted(events, key=lambda item: (item["startMs"], item["endMs"], item["captionIndex"], item["activeWordIndex"])):
        event = dict(event)
        if normalized and event["startMs"] < normalized[-1]["endMs"]:
            event["startMs"] = normalized[-1]["endMs"]
        if event["endMs"] <= event["startMs"]:
            continue
        normalized.append(event)
    return normalized


def diagnose_caption_events(events: list[dict[str, Any]]) -> dict[str, int]:
    points: list[tuple[int, int]] = []
    for event in events:
        points.append((int(event["startMs"]), 1))
        points.append((int(event["endMs"]), -1))
    active = 0
    max_active = 0
    overlap_count = 0
    for _time_ms, delta in sorted(points, key=lambda point: (point[0], point[1])):
        active += delta
        max_active = max(max_active, active)
        if active > 1:
            overlap_count += 1
    return {
        "eventCount": len(events),
        "maxConcurrentEvents": max_active,
        "overlapCount": overlap_count,
    }


def build_premium_filter_script(contract: dict[str, Any], caption_input_count: int) -> str:
    filter_parts = [
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,eq=contrast=1.06:saturation=0.96:brightness=-0.025[base]",
        "[base][1:v]overlay=0:0:enable='gte(t,0)*lt(t,4.8)'[v1]",
    ]
    current = "v1"
    overlay_index = 2
    for event in contract.get("captionEvents", []):
        next_label = f"v{overlay_index}"
        start = event["startMs"] / 1000
        end = event["endMs"] / 1000
        filter_parts.append(f"[{current}][{overlay_index}:v]overlay=0:0:enable='gte(t,{start:.3f})*lt(t,{end:.3f})'[{next_label}]")
        overlay_index += 1
        current = next_label
    cta_input_index = caption_input_count + 2
    filter_parts.append(f"[{current}][{cta_input_index}:v]overlay=0:0:enable='gte(t,{max(0, contract['durationMs'] / 1000 - 6.5):.3f})'[v]")
    return ";\n".join(filter_parts)


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


def resolve_render_duration_ms(
    candidate: dict[str, Any],
    source_video_path: str | Path | None = None,
) -> int:
    """Composition length for the working media timeline.

    Silence trim / Remove Pause can shorten the source below ``end_ms - start_ms``.
    HyperFrames must follow the shorter media, otherwise the export pads dead air.
    """
    window_ms = max(0, int(candidate.get("end_ms") or 0) - int(candidate.get("start_ms") or 0))
    probed = 0
    if source_video_path:
        try:
            probed = probe_duration_ms(source_video_path)
        except Exception:  # noqa: BLE001 - fall back to window/captions
            probed = 0
    caption_ms = 0
    timed = candidate.get("timed_captions")
    if isinstance(timed, list) and timed:
        caption_ms = captions_duration_ms(timed)
    # Only shorten the window when we probed real media (e.g. silence-trimmed source).
    # Caption-only timing must not shrink a valid YouTube window when the file is missing.
    if probed > 400:
        media_ms = probed
        if caption_ms > 400:
            media_ms = min(probed, caption_ms)
        if window_ms <= 0 or media_ms < window_ms - 80:
            return media_ms
    return window_ms


def build_premium_render_contract(
    candidate: dict[str, Any],
    profile: dict[str, Any],
    source_video_path: str,
    source_url: str,
    source_attribution: str,
    style: dict[str, Any] | None = None,
    genres: list[str] | None = None,
) -> dict[str, Any]:
    duration_ms = resolve_render_duration_ms(candidate, source_video_path)
    validate_premium_duration(duration_ms)
    style = style or load_style()
    caption_style = style["caption"]
    brand = style.get("brand") if isinstance(style.get("brand"), dict) else {}
    if style.get("template_only"):
        watermark_text = ""
        cta_text = ""
    else:
        watermark_text = str(brand.get("watermark_text") or "").strip() or str(profile.get("watermark_text") or "")
        cta_text = str(profile.get("cta_text") or "")
        if brand.get("cta_enabled") is False:
            cta_text = ""
    raw_captions = candidate.get("timed_captions") or []
    if not raw_captions:
        raise ValueError(
            "timed captions are required for premium render. "
            "Re-run with --caption-source whisper or hybrid and verify ASR output."
        )
    raw_captions = normalize_caption_timeline_for_render(
        raw_captions,
        clip_start_ms=int(candidate.get("start_ms") or 0),
        video_duration_ms=duration_ms,
        already_silence_trimmed=source_already_silence_trimmed(candidate, source_video_path),
    )
    captions = normalize_caption_groups(
        raw_captions,
        max_words_per_caption=int(caption_style.get("max_words_per_caption", 3)),
        duration_ms=duration_ms,
    )
    caption_events = build_caption_events(captions, duration_ms)
    caption_diagnostics = diagnose_caption_events(caption_events)
    if caption_diagnostics["maxConcurrentEvents"] > 1:
        raise ValueError("caption events must not overlap")
    return {
        "composition": "HyperFramesPremiumClip",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "durationMs": duration_ms,
        "candidateId": candidate["id"],
        "sourceVideoPath": source_video_path,
        "sourceUrl": source_url,
        "sourceAttribution": source_attribution,
        "startMs": candidate["start_ms"],
        "endMs": int(candidate["start_ms"]) + duration_ms,
        "startTimecode": ms_to_timecode(candidate["start_ms"]),
        "endTimecode": ms_to_timecode(int(candidate["start_ms"]) + duration_ms),
        "titleHook": candidate["title_hook"],
        "subtitle": candidate.get("hook_subtitle", candidate["viral_reason"]),
        "hookSubtitle": candidate.get("hook_subtitle", ""),
        "overlay": overlay_slots_for_candidate(candidate),
        "viralReason": candidate.get("viral_reason", ""),
        "captionText": candidate["transcript_span"],
        "captions": captions,
        "captionEvents": caption_events,
        "captionDiagnostics": caption_diagnostics,
        "visualBeats": [
            {"type": "hook", "startMs": 0, "endMs": min(4500, duration_ms)},
            {"type": "caption_emphasis", "startMs": 5500, "endMs": max(6500, duration_ms - 9000)},
            {"type": "cta", "startMs": max(0, duration_ms - 6500), "endMs": duration_ms},
        ],
        "watermarkText": watermark_text,
        "ctaText": cta_text,
        "stylePreset": PREMIUM_PRESET,
        "style": style,
        "cropStrategy": "speaker_aware_or_center_crop",
        "captionStyle": caption_style["preset"],
        "genres": genres or [],
        "sfxPack": ["whoosh", "switch", "mouse-click"],
        "publishSafety": {
            "reviewRequired": True,
            "autoPublishAllowed": True,
            "reason": "publishing is gated by approval, schedule, credentials, and selected platforms",
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


def render_premium_hyperframes(
    candidate: dict[str, Any],
    profile: dict[str, Any],
    source_video_path: str,
    source_url: str,
    source_attribution: str,
    style: dict[str, Any] | None = None,
    hyperframes_template: str = "auto",
    hyperframes_format: str = "auto",
    brand_system_template_id: str = "",
    genres: list[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    job_id = f"render_{uuid.uuid4().hex[:12]}"
    contract = build_premium_render_contract(candidate, profile, source_video_path, source_url, source_attribution, style, genres=genres)
    output_path, contract = _render_hyperframes_contract(
        contract,
        source_video_path,
        profile["id"],
        candidate["id"],
        job_id,
        quality="standard",
        hyperframes_template=hyperframes_template,
        hyperframes_format=hyperframes_format,
        brand_system_template_id=brand_system_template_id,
        genres=genres,
    )
    return output_path, contract


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


def _fit_font(draw, text: str, requested_size: int, max_width: int, stroke_width: int = 0):
    size = requested_size
    while size >= 28:
        font = _load_font(size)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        if bbox[2] - bbox[0] <= max_width:
            return font, size, bbox
        size -= 2
    font = _load_font(size)
    return font, size, draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)


def _hex_to_rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        return (255, 255, 255, alpha)
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha)


def _style_background_rgba(value: str) -> tuple[int, int, int, int]:
    value = value.strip()
    if value.startswith("rgba(") and value.endswith(")"):
        parts = [part.strip() for part in value[5:-1].split(",")]
        if len(parts) == 4:
            red, green, blue = (max(0, min(255, int(float(part)))) for part in parts[:3])
            alpha = max(0, min(255, int(float(parts[3]) * 255)))
            return (red, green, blue, alpha)
    return (0, 0, 0, 148)


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
    requested_font_size = int(caption_style.get("font_size", 54))
    stroke_width = int(caption_style.get("stroke_width", 10))
    image = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    words = caption.get("words") or [{"text": word} for word in caption["text"].split()]
    line = " ".join(word["text"] for word in words)
    font, font_size, bbox = _fit_font(draw, line, requested_font_size, 960, stroke_width)
    text_width = bbox[2] - bbox[0]
    text_x = max(36, (1080 - text_width) // 2 - bbox[0])
    box_left = text_x + bbox[0]
    box_right = text_x + bbox[2]
    box_height = bbox[3] - bbox[1]
    box_top = 1180 if caption_style.get("position") == "bottom" else 900
    text_y = box_top - bbox[1]
    pad_x = 22
    pad_y = 12
    draw.rounded_rectangle(
        (box_left - pad_x, box_top - pad_y, box_right + pad_x, box_top + box_height + pad_y),
        radius=int(caption_style.get("background_radius", 12)),
        fill=_style_background_rgba(caption_style.get("background_color", "rgba(0,0,0,0.58)")),
    )
    draw.text(
        (text_x, text_y),
        line,
        font=font,
        fill=_hex_to_rgba(caption_style["text_color"]),
        stroke_width=stroke_width,
        stroke_fill=_hex_to_rgba(caption_style.get("stroke_color", "#000000"), 255),
    )
    if 0 <= active_word_index < len(words):
        prefix = " ".join(word["text"] for word in words[:active_word_index])
        prefix_width = draw.textlength(f"{prefix} ", font=font) if prefix else 0
        draw.text(
            (text_x + prefix_width, text_y),
            words[active_word_index]["text"],
            font=font,
            fill=_hex_to_rgba(caption_style["highlight_word_color"]),
            stroke_width=stroke_width,
            stroke_fill=_hex_to_rgba(caption_style.get("stroke_color", "#000000"), 255),
        )
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
        [contract["titleHook"]],
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
    for index, event in enumerate(contract["captionEvents"], start=1):
        path = overlay_dir / f"caption_event_{index:03d}.png"
        _write_caption_overlay(path, event, int(event["activeWordIndex"]), style)
        caption_inputs.append(path)

    filter_path = out_dir / f"{job_id}_filter.txt"
    filter_path.write_text(build_premium_filter_script(contract, len(caption_inputs)), encoding="utf-8")

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
