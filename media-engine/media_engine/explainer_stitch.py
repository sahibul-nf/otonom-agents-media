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


def _pick_font(size: int):
    from PIL import ImageFont

    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
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


def _render_title_png(
    path: Path,
    *,
    headline: str,
    narration: str,
    label: str,
    scene_type: str = "text",
) -> Path:
    """TechTalk edu-finance card: slate gradient, brand chip, takeaway panel."""
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    is_broll = scene_type == "broll"
    image = Image.new("RGB", (WIDTH, HEIGHT), color=(8, 15, 28))
    _draw_vertical_gradient(image, (8, 15, 28), (15, 23, 42) if not is_broll else (2, 44, 52))

    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    cx, cy = int(WIDTH * 0.72), int(HEIGHT * 0.35)
    for radius, alpha in ((520, 28), (340, 40), (180, 55)):
        glow_draw.ellipse(
            (cx - radius, cy - radius, cx + radius, cy + radius),
            fill=(45, 212, 191, alpha),
        )
    image = Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(image)

    if is_broll:
        for x in range(120, WIDTH - 80, 48):
            draw.line([(x, 140), (x, HEIGHT - 160)], fill=(30, 58, 72), width=1)
        for y in range(160, HEIGHT - 140, 48):
            draw.line([(100, y), (WIDTH - 100, y)], fill=(30, 58, 72), width=1)
        bar_base_y = HEIGHT - 220
        bar_x = WIDTH - 420
        heights = (90, 150, 110, 200, 160)
        for i, h in enumerate(heights):
            x0 = bar_x + i * 52
            draw.rectangle(
                (x0, bar_base_y - h, x0 + 34, bar_base_y),
                fill=(45, 212, 191) if i == 3 else (56, 189, 248),
            )

    brand_font = _pick_font(28)
    label_font = _pick_font(26)
    headline_font = _pick_font(58)
    body_font = _pick_font(32)

    brand = "TECHTALK"
    chip_pad_x, chip_pad_y = 18, 10
    bw = int(draw.textlength(brand, font=brand_font)) + chip_pad_x * 2
    bh = 44
    draw.rounded_rectangle((64, 56, 64 + bw, 56 + bh), radius=22, fill=(45, 212, 191))
    draw.text((64 + chip_pad_x, 56 + chip_pad_y - 2), brand, fill=(15, 23, 42), font=brand_font)
    draw.rectangle((64, 120, 136, 124), fill=(45, 212, 191))

    panel = (64, int(HEIGHT * 0.34), WIDTH - 64, HEIGHT - 120)
    panel_img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    panel_draw = ImageDraw.Draw(panel_img)
    panel_draw.rounded_rectangle(panel, radius=28, fill=(8, 15, 28, 210), outline=(45, 212, 191, 90), width=2)
    image = Image.alpha_composite(image.convert("RGBA"), panel_img).convert("RGB")
    draw = ImageDraw.Draw(image)

    micro = "SIGNAL SNAPSHOT" if is_broll else "KEY TAKEAWAY"
    if label and label.upper() not in {"KEY POINT", "B-ROLL", "EXPLAINER"}:
        micro = label.upper()
    draw.text((96, panel[1] + 28), micro, fill=(45, 212, 191), font=label_font)

    y = panel[1] + 78
    max_width = WIDTH - 220
    for line in _wrap_text(draw, headline, headline_font, max_width)[:4]:
        draw.text((96, y), line, fill=(248, 250, 252), font=headline_font)
        y += 68

    if narration:
        y += 8
        for line in _wrap_text(draw, narration, body_font, max_width)[:4]:
            draw.text((96, y), line, fill=(186, 198, 214), font=body_font)
            y += 44

    image.save(path, format="PNG")
    return path


def render_title_card(
    *,
    output_path: Path,
    headline: str,
    narration: str = "",
    duration: float = 10.0,
    label: str = "EXPLAINER",
    scene_type: str = "text",
) -> Path:
    """Landscape TechTalk title card via Pillow PNG + gentle Ken Burns + FFmpeg."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = max(3.0, float(duration))
    headline = (headline or "Untitled").strip()[:120]
    narration = (narration or "").strip()[:220]
    label = (label or "EXPLAINER").strip()[:40]
    scene_type = "broll" if scene_type == "broll" else "text"

    png_path = output_path.with_suffix(".png")
    _render_title_png(
        png_path,
        headline=headline,
        narration=narration,
        label=label,
        scene_type=scene_type,
    )

    frames = max(1, int(duration * FPS))
    vf = (
        f"scale={WIDTH * 2}:{HEIGHT * 2},"
        f"zoompan=z='min(1.0+0.00035*on,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"
    )
    cmd = [
        _ffmpeg_bin(),
        "-y",
        "-loop",
        "1",
        "-i",
        str(png_path),
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=channel_layout=stereo:sample_rate=44100:d={duration:.3f}",
        "-t",
        f"{duration:.3f}",
        "-vf",
        vf,
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
    *,
    profile_id: str,
    candidate_id: str,
    prefer_hyperframes: bool = True,
) -> Path:
    scene_type = str(scene.get("type") or "text")
    headline = str(scene.get("headline") or "Untitled")
    narration = str(scene.get("narration") or "")
    duration = float(scene.get("duration_target") or 10)
    out = work_dir / f"{scene.get('id', 'scene')}_{scene_type}.mp4"
    label = "B-ROLL" if scene_type == "broll" else "KEY POINT"

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
    prefer_hyperframes: bool = True,
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
