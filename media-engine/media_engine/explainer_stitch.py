"""Render and stitch hybrid explainer scene segments with FFmpeg (+ optional HyperFrames)."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from .db import ARTIFACTS_DIR
from .hyperframes_renderer import check_hyperframes_runtime
from .hyperframes_templates import normalize_hyperframes_template
from .rendering import render_premium_hyperframes

WIDTH = 1920
HEIGHT = 1080
FPS = 30


def _resolve_bin(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    for candidate in (
        Path("/opt/homebrew/bin") / name,
        Path("/usr/local/bin") / name,
        Path("/usr/bin") / name,
    ):
        if candidate.exists():
            return str(candidate)
    raise RuntimeError(f"{name} is required for explainer stitch")


def _ffmpeg_bin() -> str:
    return _resolve_bin("ffmpeg")


def _ffprobe_bin() -> str:
    return _resolve_bin("ffprobe")


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd[:6])}…\n{result.stderr[-1500:]}")


def probe_duration_seconds(path: Path) -> float:
    cmd = [
        _ffprobe_bin(),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {result.stderr[-800:]}")
    try:
        return max(0.1, float(result.stdout.strip()))
    except ValueError as exc:
        raise RuntimeError(f"invalid duration for {path}") from exc


def _pick_font(size: int, *, bold: bool = False):
    from PIL import ImageFont

    # Prefer expressive display faces; fall back to Arial on Linux CI.
    candidates: list[tuple[str, int | None]] = [
        ("/System/Library/Fonts/Avenir Next.ttc", 1 if bold else 0),
        ("/System/Library/Fonts/Avenir.ttc", 1 if bold else 0),
        ("/System/Library/Fonts/HelveticaNeue.ttc", 1 if bold else 0),
        ("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf", None),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", None),
    ]
    for path, index in candidates:
        if not Path(path).exists():
            continue
        try:
            if index is None:
                return ImageFont.truetype(path, size=size)
            return ImageFont.truetype(path, size=size, index=index)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text(draw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_vertical_gradient(image, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> None:
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        t = y / max(1, HEIGHT - 1)
        color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.line([(0, y), (WIDTH, y)], fill=color)


def _metric_chip(text: str) -> str:
    """Pull a short metric-like token from narration/headline for broll callouts."""
    import re

    match = re.search(r"\b(\d[\d,]*(?:\.\d+)?\s*[kKmMbB%]?|\d+\s*million)\b", text or "")
    if match:
        return match.group(1).upper().replace(" MILLION", "M")
    words = [w for w in (text or "").split() if w.isalpha()]
    if words:
        return words[0][:8].upper()
    return "SIGNAL"


def _render_card_layers(
    work_dir: Path,
    *,
    headline: str,
    narration: str,
    label: str,
    scene_type: str = "text",
) -> tuple[Path, Path, Path]:
    """Build base / content / accent PNG layers for staggered motion-graphics reveals."""
    from PIL import Image, ImageDraw

    work_dir.mkdir(parents=True, exist_ok=True)
    is_broll = scene_type == "broll"
    accent = (45, 212, 191)
    ink = (248, 250, 252)
    muted = (148, 163, 184)

    base = Image.new("RGB", (WIDTH, HEIGHT), color=(6, 12, 24))
    if is_broll:
        _draw_vertical_gradient(base, (4, 18, 28), (6, 40, 48))
    else:
        _draw_vertical_gradient(base, (6, 12, 24), (14, 22, 40))

    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    if is_broll:
        cx, cy = int(WIDTH * 0.78), int(HEIGHT * 0.42)
        for radius, alpha in ((480, 36), (300, 48), (160, 70)):
            glow_draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(56, 189, 248, alpha))
    else:
        cx, cy = int(WIDTH * 0.18), int(HEIGHT * 0.55)
        for radius, alpha in ((420, 22), (260, 34), (120, 50)):
            glow_draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(*accent, alpha))
    base = Image.alpha_composite(base.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(base)

    # Left rail + top brand row (always on base so motion overlays feel grounded).
    draw.rectangle((0, 0, 10, HEIGHT), fill=accent)
    brand_font = _pick_font(26, bold=True)
    brand = "TECHTALK"
    draw.rounded_rectangle((48, 44, 48 + 168, 44 + 40), radius=8, fill=accent)
    draw.text((48 + 18, 44 + 8), brand, fill=(8, 15, 28), font=brand_font)
    draw.text((240, 52), "EDU · FINANCE", fill=muted, font=_pick_font(20, bold=True))
    draw.text((WIDTH - 280, 52), "LONG-FORM BRIEF", fill=muted, font=_pick_font(18))

    if is_broll:
        # Right data stage on base (distinct from text takeaway).
        panel = (int(WIDTH * 0.54), 140, WIDTH - 56, HEIGHT - 120)
        stage = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        stage_draw = ImageDraw.Draw(stage)
        stage_draw.rounded_rectangle(panel, radius=20, fill=(8, 24, 32, 230), outline=(56, 189, 248, 120), width=2)
        for x in range(panel[0] + 36, panel[2] - 24, 36):
            stage_draw.line([(x, panel[1] + 36), (x, panel[3] - 36)], fill=(30, 64, 80, 160), width=1)
        for y in range(panel[1] + 48, panel[3] - 48, 36):
            stage_draw.line([(panel[0] + 28, y), (panel[2] - 28, y)], fill=(30, 64, 80, 120), width=1)
        base = Image.alpha_composite(base.convert("RGBA"), stage).convert("RGB")
        draw = ImageDraw.Draw(base)
        metric = _metric_chip(f"{headline} {narration}")
        metric_font = _pick_font(96, bold=True)
        draw.text((panel[0] + 48, panel[1] + 56), metric, fill=ink, font=metric_font)
        draw.text((panel[0] + 52, panel[1] + 170), "HARD CAP / ISSUANCE", fill=accent, font=_pick_font(22, bold=True))
        bar_base = panel[3] - 80
        heights = (90, 140, 110, 210, 160, 190)
        for i, h in enumerate(heights):
            x0 = panel[0] + 56 + i * 58
            draw.rectangle((x0, bar_base - h, x0 + 34, bar_base), fill=accent if i == 3 else (56, 189, 248))

    base_path = work_dir / "layer_base.png"
    base.save(base_path, format="PNG")

    # Content layer: eyebrow + headline + support (transparent).
    content = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(content)
    micro = "SIGNAL SNAPSHOT" if is_broll else "KEY TAKEAWAY"
    if label and label.upper() not in {"KEY POINT", "B-ROLL", "EXPLAINER", "KEY TAKEAWAY"}:
        micro = label.upper()
    eyebrow_font = _pick_font(24, bold=True)
    headline_font = _pick_font(72 if not is_broll else 58, bold=True)
    body_font = _pick_font(30)

    left = 56
    max_copy_w = int(WIDTH * 0.46) - 40 if is_broll else WIDTH - 160
    y = 220 if not is_broll else 260
    cdraw.text((left, y), micro, fill=(*accent, 255), font=eyebrow_font)
    y += 48
    cdraw.rectangle((left, y, left + 72, y + 4), fill=(*accent, 255))
    y += 28
    for line in _wrap_text(cdraw, headline, headline_font, max_copy_w)[:3]:
        cdraw.text((left, y), line, fill=(*ink, 255), font=headline_font)
        y += 82 if not is_broll else 68
    if narration:
        y += 12
        for line in _wrap_text(cdraw, narration, body_font, max_copy_w)[:4]:
            cdraw.text((left, y), line, fill=(*muted, 255), font=body_font)
            y += 40
    if not is_broll:
        # Takeaway chips under support copy.
        chips = ["Scarce", "Clear", "Actionable"]
        chip_font = _pick_font(22, bold=True)
        chip_x = left
        chip_y = min(y + 36, HEIGHT - 160)
        for chip in chips:
            tw = int(cdraw.textlength(chip, font=chip_font)) + 28
            cdraw.rounded_rectangle((chip_x, chip_y, chip_x + tw, chip_y + 40), radius=10, outline=(*accent, 180), width=2)
            cdraw.text((chip_x + 14, chip_y + 8), chip, fill=(*ink, 255), font=chip_font)
            chip_x += tw + 14

    content_path = work_dir / "layer_content.png"
    content.save(content_path, format="PNG")

    # Accent layer: footer + underline pulse bars (fades in last).
    accent_img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    adraw = ImageDraw.Draw(accent_img)
    adraw.rectangle((56, HEIGHT - 88, WIDTH - 56, HEIGHT - 86), fill=(*accent, 160))
    footer = "TECHTALK  ·  HYBRID EXPLAINER  ·  SAHIBUL NF"
    adraw.text((56, HEIGHT - 72), footer, fill=(*muted, 255), font=_pick_font(20, bold=True))
    if not is_broll:
        adraw.rectangle((56, 180, 64, HEIGHT - 140), fill=(*accent, 220))
    accent_path = work_dir / "layer_accent.png"
    accent_img.save(accent_path, format="PNG")

    # Flat composite kept for tests / previews.
    flat = Image.alpha_composite(base.convert("RGBA"), content)
    flat = Image.alpha_composite(flat, accent_img).convert("RGB")
    flat_path = work_dir / "composite.png"
    flat.save(flat_path, format="PNG")
    return base_path, content_path, accent_path


def _render_title_png(
    path: Path,
    *,
    headline: str,
    narration: str,
    label: str,
    scene_type: str = "text",
) -> Path:
    """TechTalk v2 card composite (multi-beat layout)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    base, content, accent = _render_card_layers(
        path.parent / f"{path.stem}_layers",
        headline=headline,
        narration=narration,
        label=label,
        scene_type=scene_type,
    )
    from PIL import Image

    flat = Image.alpha_composite(Image.open(base).convert("RGBA"), Image.open(content).convert("RGBA"))
    flat = Image.alpha_composite(flat, Image.open(accent).convert("RGBA")).convert("RGB")
    flat.save(path, format="PNG")
    return path


def extract_audio_track(source: Path, output_path: Path) -> Path:
    """Extract AAC/M4A audio from a HeyGen avatar proxy clip (Creator-plan VO path)."""
    if not source.exists():
        raise FileNotFoundError(f"audio source not found: {source}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _ffmpeg_bin(),
        "-y",
        "-i",
        str(source),
        "-vn",
        "-c:a",
        "aac",
        "-ar",
        "44100",
        "-ac",
        "2",
        str(output_path),
    ]
    _run(cmd)
    return output_path


def resolve_narration_audio(scene: dict[str, Any], clips_dir: Path) -> Path | None:
    """Resolve optional VO fixture for text/broll scenes."""
    audio_file = str(scene.get("audio_file") or "").strip()
    scene_id = str(scene.get("id") or "scene")
    candidates: list[Path] = []
    if audio_file:
        candidates.append(clips_dir / audio_file)
    candidates.extend(
        [
            clips_dir / f"{scene_id}.m4a",
            clips_dir / f"{scene_id}.mp3",
            clips_dir / f"{scene_id}.wav",
            clips_dir / f"scene_{scene_id[-2:]}.m4a" if scene_id.startswith("s") else clips_dir / f"{scene_id}_vo.m4a",
            clips_dir / f"{scene_id}_vo.m4a",
            clips_dir / f"audio_{scene_id}.m4a",
        ]
    )
    # Common pattern: scene_02.m4a for plan id s02
    if scene_id.startswith("s") and scene_id[1:].isdigit():
        num = int(scene_id[1:])
        candidates.append(clips_dir / f"scene_{num:02d}.m4a")
        candidates.append(clips_dir / f"scene_{num:02d}.mp3")
        candidates.append(clips_dir / f"vo_scene_{num:02d}.m4a")
    for path in candidates:
        if path.exists():
            return path
    return None


def render_title_card(
    *,
    output_path: Path,
    headline: str,
    narration: str = "",
    duration: float = 10.0,
    label: str = "EXPLAINER",
    scene_type: str = "text",
    audio_path: Path | None = None,
) -> Path:
    """Landscape TechTalk v2 card: layered reveals + optional Sahibul NF VO mux."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    headline = (headline or "Untitled").strip()[:120]
    narration = (narration or "").strip()[:220]
    label = (label or "EXPLAINER").strip()[:40]
    scene_type = "broll" if scene_type == "broll" else "text"

    layer_dir = output_path.parent / f"{output_path.stem}_layers"
    base_png, content_png, accent_png = _render_card_layers(
        layer_dir,
        headline=headline,
        narration=narration,
        label=label,
        scene_type=scene_type,
    )
    # Keep flat composite next to mp4 for QA/tests.
    _render_title_png(
        output_path.with_suffix(".png"),
        headline=headline,
        narration=narration,
        label=label,
        scene_type=scene_type,
    )

    audio_duration = 0.0
    if audio_path and audio_path.exists():
        audio_duration = probe_duration_seconds(audio_path)
        # Prefer VO length so graphics don't sit mute after narration ends.
        duration = max(3.0, audio_duration + 0.45)
    else:
        duration = max(3.0, float(duration))
    frames = max(1, int(duration * FPS))

    # Base Ken Burns + staggered fade-in overlays (motion-graphics beat).
    filter_complex = (
        f"[0:v]scale={WIDTH * 2}:{HEIGHT * 2},"
        f"zoompan=z='min(1.0+0.00028*on,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}[base];"
        f"[1:v]fps={FPS},format=rgba,fade=t=in:st=0.12:d=0.35:alpha=1[content];"
        f"[2:v]fps={FPS},format=rgba,fade=t=in:st=0.42:d=0.35:alpha=1[accent];"
        f"[base][content]overlay=0:0:format=auto[tmp];"
        f"[tmp][accent]overlay=0:0:format=auto,format=yuv420p[v]"
    )

    cmd = [
        _ffmpeg_bin(),
        "-y",
        "-loop",
        "1",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(base_png),
        "-loop",
        "1",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(content_png),
        "-loop",
        "1",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(accent_png),
    ]
    if audio_path and audio_path.exists():
        cmd.extend(["-i", str(audio_path)])
        # Pad short VO with silence to match video duration.
        filter_complex += (
            f";[3:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"apad=whole_dur={duration:.3f}[a]"
        )
        cmd.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-t",
                f"{duration:.3f}",
                "-r",
                str(FPS),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(output_path),
            ]
        )
    else:
        cmd.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=channel_layout=stereo:sample_rate=44100:d={duration:.3f}",
                "-filter_complex",
                filter_complex,
                "-map",
                "[v]",
                "-map",
                "3:a",
                "-t",
                f"{duration:.3f}",
                "-r",
                str(FPS),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(output_path),
            ]
        )
    _run(cmd)
    return output_path


def normalize_avatar_clip(source: Path, output_path: Path, *, max_seconds: float | None = None) -> Path:
    """Normalize avatar MP4 to 16:9 H.264 + AAC for concat."""
    if not source.exists():
        raise FileNotFoundError(f"avatar clip not found: {source}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    vf = f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,fps={FPS}"
    cmd = [
        _ffmpeg_bin(),
        "-y",
        "-i",
        str(source),
    ]
    if max_seconds and max_seconds > 0:
        cmd.extend(["-t", f"{max_seconds:.3f}"])
    cmd.extend(
        [
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ar",
            "44100",
            "-ac",
            "2",
            str(output_path),
        ]
    )
    _run(cmd)
    return output_path


def _silent_color_source(path: Path, duration: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _ffmpeg_bin(),
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=0x111827:s={WIDTH}x{HEIGHT}:d={duration:.3f}:r={FPS}",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=channel_layout=stereo:sample_rate=44100:d={duration:.3f}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(path),
    ]
    _run(cmd)
    return path


def render_hyperframes_card(
    *,
    work_dir: Path,
    profile_id: str,
    candidate_id: str,
    headline: str,
    narration: str,
    duration: float,
    template: str = "techtalk_explainer",
    scene_type: str = "text",
) -> Path:
    """Render a text/broll card via HyperFrames when runtime is ready."""
    status = check_hyperframes_runtime(run_doctor=False)
    if not status.get("ready"):
        raise RuntimeError(status.get("reason") or "HyperFrames not ready")

    duration = max(3.0, float(duration))
    duration_ms = int(duration * 1000)
    source = _silent_color_source(work_dir / "hf_source.mp4", duration)
    job_id = f"explainer_hf_{uuid.uuid4().hex[:10]}"
    scene_kind = "broll" if scene_type == "broll" else "text"
    candidate = {
        "id": candidate_id,
        "profile_id": profile_id,
        "start_ms": 0,
        "end_ms": duration_ms,
        "title_hook": headline,
        "hook_subtitle": narration,
        "viral_reason": f"explainer {scene_kind} scene",
        "transcript_span": narration or headline,
        "caption_source": "explainer",
        "asr_metadata": {},
        "captions": [
            {
                "startMs": 0,
                "endMs": duration_ms,
                "text": narration or headline,
                "words": [],
            }
        ],
    }
    profile = {
        "id": profile_id,
        "default_render_preset": "explainer_long_16_9",
        "cta_text": "",
        "watermark_text": "TechTalk",
    }
    template_id = normalize_hyperframes_template(template or "techtalk_explainer")
    output_path, _contract = render_premium_hyperframes(
        candidate,
        profile,
        str(source),
        source_url=f"explainer://scene/{candidate_id}",
        source_attribution="Explainer Mode",
        hyperframes_template=template_id,
        hyperframes_format="long_16_9",
        genres=["explainer", "techtalk", "tech"],
    )
    # render_premium_hyperframes writes under ARTIFACTS_DIR; copy into work_dir for stitch locality
    dest = work_dir / f"{job_id}.mp4"
    shutil.copy2(output_path, dest)
    return dest


def render_text_or_broll_scene(
    scene: dict[str, Any],
    work_dir: Path,
    clips_dir: Path,
    *,
    profile_id: str,
    candidate_id: str,
    prefer_hyperframes: bool = False,
) -> Path:
    scene_type = str(scene.get("type") or "text")
    headline = str(scene.get("headline") or "Untitled")
    narration = str(scene.get("narration") or "")
    duration = float(scene.get("duration_target") or 10)
    out = work_dir / f"{scene.get('id', 'scene')}_{scene_type}.mp4"
    label = "SIGNAL SNAPSHOT" if scene_type == "broll" else "KEY TAKEAWAY"
    audio_path = resolve_narration_audio(scene, clips_dir)

    if prefer_hyperframes:
        try:
            return render_hyperframes_card(
                work_dir=work_dir / f"hf_{scene.get('id', 'scene')}",
                profile_id=profile_id,
                candidate_id=f"{candidate_id}_{scene.get('id', 'scene')}",
                headline=headline,
                narration=narration,
                duration=duration,
                template=str(scene.get("template") or "techtalk_explainer"),
                scene_type=scene_type,
            )
        except Exception:
            pass

    return render_title_card(
        output_path=out,
        headline=headline,
        narration=narration,
        duration=duration,
        label=label,
        scene_type=scene_type,
        audio_path=audio_path,
    )


def resolve_avatar_source(scene: dict[str, Any], clips_dir: Path) -> Path:
    clip_file = str(scene.get("clip_file") or "").strip()
    scene_id = str(scene.get("id") or "avatar")
    candidates = []
    if clip_file:
        candidates.append(clips_dir / clip_file)
    candidates.extend(
        [
            clips_dir / f"{scene_id}.mp4",
            clips_dir / f"{scene_id}.mov",
            clips_dir / f"scene_{scene_id}.mp4",
        ]
    )
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        f"avatar fixture missing for scene {scene_id}. "
        f"Expected one of: {', '.join(str(p.name) for p in candidates)}"
    )


def build_scene_segments(
    plan: dict[str, Any],
    clips_dir: Path,
    work_dir: Path,
    *,
    profile_id: str,
    candidate_id: str,
    prefer_hyperframes: bool = False,
) -> list[Path]:
    work_dir.mkdir(parents=True, exist_ok=True)
    segments: list[Path] = []
    for scene in plan["scenes"]:
        scene_type = scene["type"]
        if scene_type == "avatar":
            source = resolve_avatar_source(scene, clips_dir)
            out = work_dir / f"{scene['id']}_avatar.mp4"
            max_seconds = float(scene.get("duration_target") or 0) or None
            segments.append(normalize_avatar_clip(source, out, max_seconds=max_seconds))
        else:
            segments.append(
                render_text_or_broll_scene(
                    scene,
                    work_dir,
                    clips_dir,
                    profile_id=profile_id,
                    candidate_id=candidate_id,
                    prefer_hyperframes=prefer_hyperframes,
                )
            )
    if not segments:
        raise ValueError("no scene segments produced")
    return segments


def stitch_segments(segments: list[Path], output_path: Path) -> Path:
    if not segments:
        raise ValueError("segments required")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    list_file = output_path.with_suffix(".concat.txt")
    lines = []
    for segment in segments:
        # concat demuxer needs escaped single quotes
        escaped = str(segment.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cmd = [
        _ffmpeg_bin(),
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    _run(cmd)
    return output_path


def write_stitch_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def explainer_artifact_dir(profile_id: str, job_id: str) -> Path:
    path = ARTIFACTS_DIR / profile_id / "explainers" / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path
