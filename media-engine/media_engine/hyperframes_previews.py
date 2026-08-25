"""On-demand HyperFrames template preview rendering."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any

from .db import ARTIFACTS_DIR
from .hyperframes_renderer import build_hyperframes_index_html, check_hyperframes_runtime, render_hyperframes_project, require_hyperframes_runtime
from .overlay_copy import heuristic_overlay_slots
from .hyperframes_templates import (
    PREVIEW_SECONDS,
    dimensions_for_format,
    list_hyperframes_templates,
    normalize_hyperframes_format,
    normalize_hyperframes_template,
    preview_stock_path,
    resolve_hyperframes_template,
)

PREVIEW_ROOT = ARTIFACTS_DIR / "hyperframes_template_previews"
PREVIEW_CONTRACT_VERSION = 3
# Gallery previews show recipe overlay + captions only — no shared shell hook/brand/CTA chrome.
PREVIEW_SHELL_COMPONENTS = {"hook": False, "watermark": False, "source": False, "cta": False}

_prewarm_lock = threading.Lock()
_prewarm_scheduled = False


def preview_renderer_ready() -> tuple[bool, str]:
    checks = check_hyperframes_runtime(run_doctor=False)
    if not checks.get("enabled"):
        return False, "HYPERFRAMES_ENABLED is not true"
    if not checks.get("node", {}).get("ok"):
        return False, "Node 22+ is required for HyperFrames template previews"
    if not checks.get("ffmpeg", {}).get("ok"):
        return False, "ffmpeg is required for HyperFrames template previews"
    if not checks.get("hyperframes", {}).get("ok"):
        return False, "HyperFrames CLI is not available"
    return True, ""


def _preview_cache_valid(output: Path, metadata_path: Path) -> bool:
    if not output.exists() or output.stat().st_size <= 0:
        return False
    if not metadata_path.exists():
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return metadata.get("contract_version") == PREVIEW_CONTRACT_VERSION


def schedule_builtin_preview_prewarm() -> None:
    """Background prewarm for built-in templates missing a valid preview cache."""
    global _prewarm_scheduled
    with _prewarm_lock:
        if _prewarm_scheduled:
            return
        _prewarm_scheduled = True

    def _run() -> None:
        renderer_ready, _ = preview_renderer_ready()
        if not renderer_ready:
            return
        for template in list_hyperframes_templates():
            if template.get("source") == "brand_system":
                continue
            template_id = str(template["id"])
            for hyperframes_format in template.get("formats") or ["short_9_16"]:
                status = preview_status(template_id, str(hyperframes_format))
                if status["ready"]:
                    continue
                try:
                    ensure_hyperframes_template_preview(template_id, str(hyperframes_format))
                except Exception:
                    continue

    threading.Thread(target=_run, daemon=True, name="hf-preview-prewarm").start()


def preview_path(template_id: str, hyperframes_format: str) -> Path:
    normalized_template = normalize_hyperframes_template(template_id.replace("__", ":"))
    normalized_format = normalize_hyperframes_format(hyperframes_format)
    if normalized_format == "auto":
        normalized_format = "short_9_16"
    safe_template = normalized_template.replace(":", "__")
    return PREVIEW_ROOT / safe_template / normalized_format / "preview.mp4"


def clear_template_preview_cache(template_id: str) -> bool:
    safe_template = str(template_id or "").strip().replace("__", ":").replace(":", "__")
    if not safe_template:
        return False
    preview_dir = PREVIEW_ROOT / safe_template
    if not preview_dir.exists():
        return False
    shutil.rmtree(preview_dir)
    return True


def preview_status(template_id: str, hyperframes_format: str) -> dict[str, Any]:
    output = preview_path(template_id, hyperframes_format)
    metadata_path = output.parent / "preview-metadata.json"
    metadata: dict[str, Any] = {}
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            metadata = {}
    ready = _preview_cache_valid(output, metadata_path)
    renderer_ready, unavailable_reason = preview_renderer_ready()
    return {
        "template": template_id,
        "format": normalize_hyperframes_format(hyperframes_format),
        "ready": ready,
        "renderer_ready": renderer_ready,
        "unavailable_reason": "" if ready or renderer_ready else unavailable_reason,
        "path": str(output),
        "size": output.stat().st_size if output.exists() else 0,
        "metadata": metadata,
    }


def list_hyperframes_preview_status(include_brand: bool = True) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for template in list_hyperframes_templates():
        if not include_brand and template.get("source") == "brand_system":
            continue
        for hyperframes_format in template.get("formats") or ["short_9_16"]:
            items.append(preview_status(str(template["id"]), str(hyperframes_format)))
    ready_count = sum(1 for item in items if item["ready"])
    return {
        "preview_seconds": PREVIEW_SECONDS,
        "ready": ready_count,
        "total": len(items),
        "items": items,
    }


def prewarm_hyperframes_template_previews(
    include_brand: bool = False,
    template_id: str | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    normalized_filter = (template_id or "").strip().replace("__", ":")
    for template in list_hyperframes_templates():
        if normalized_filter and str(template["id"]) != normalized_filter:
            continue
        if not include_brand and template.get("source") == "brand_system":
            continue
        for hyperframes_format in template.get("formats") or ["short_9_16"]:
            item = {"template": template["id"], "format": hyperframes_format, "ready": False, "error": "", "path": ""}
            try:
                output = ensure_hyperframes_template_preview(str(template["id"]), str(hyperframes_format))
                item.update({"ready": True, "path": str(output)})
            except Exception as exc:  # noqa: BLE001 - batch status should include every failed preview.
                item["error"] = str(exc)
            results.append(item)
    return {
        "preview_seconds": PREVIEW_SECONDS,
        "ready": sum(1 for item in results if item["ready"]),
        "total": len(results),
        "items": results,
    }


def ensure_hyperframes_template_preview(template_id: str, hyperframes_format: str) -> Path:
    output = preview_path(template_id, hyperframes_format)
    metadata_path = output.parent / "preview-metadata.json"
    if output.exists() and output.stat().st_size > 0 and metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata.get("contract_version") == PREVIEW_CONTRACT_VERSION:
                return output
        except (OSError, json.JSONDecodeError):
            pass

    require_hyperframes_runtime()
    output.parent.mkdir(parents=True, exist_ok=True)
    width, height, resolved_format = dimensions_for_format(hyperframes_format)
    project_dir = output.parent / "project"
    media_dir = project_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    source = media_dir / "source.mp4"
    if not source.exists():
        _write_preview_source(source, width, height, template_id.replace("__", ":"))

    contract = _preview_contract(template_id.replace("__", ":"), resolved_format, width, height)
    (project_dir / "index.html").write_text(
        build_hyperframes_index_html(contract, template_id.replace("__", ":"), resolved_format, genres=[]),
        encoding="utf-8",
    )
    checks = render_hyperframes_project(project_dir, output, quality="draft")
    (output.parent / "preview-metadata.json").write_text(
        json.dumps(
            {
                "template": contract["hyperframesTemplate"],
                "format": resolved_format,
                "checks": checks,
                "contract_version": PREVIEW_CONTRACT_VERSION,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return output


def _write_preview_source(path: Path, width: int, height: int, template_id: str) -> None:
    stock = preview_stock_path(template_id)
    if stock and stock.exists():
        shutil.copy2(stock, path)
        return

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to create HyperFrames template previews")
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={width}x{height}:rate=30:duration={PREVIEW_SECONDS}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:sample_rate=44100:duration={PREVIEW_SECONDS}",
        "-shortest",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(path),
    ]
    result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg preview source failed: {result.stderr[-1200:]}")


def _preview_copy_for_template(template: dict[str, Any]) -> dict[str, Any]:
    category = str(template.get("category") or "Official")
    label = str(template.get("label") or "Template preview")
    niche_copy: dict[str, dict[str, Any]] = {
    "Spiritual": {
      "captions": [
        {"text": "Allah selalu dekat", "words": ["Allah", "selalu", "dekat"]},
        {"text": "Tenangkan hati dengan dzikir", "words": ["Tenangkan", "hati", "dengan", "dzikir"]},
        {"text": "Simpan pesan ini", "words": ["Simpan", "pesan", "ini"]},
      ],
      "watermark": "Reflect",
      "cta": "Ikuti untuk pengingat harian",
      "source": "Kajian singkat",
    },
    "Data": {
      "captions": [
        {"text": "Fed pivot changes the tape", "words": ["Fed", "pivot", "changes", "the", "tape"]},
        {"text": "NVDA earnings set the tone", "words": ["NVDA", "earnings", "set", "the", "tone"]},
        {"text": "Watch the next catalyst", "words": ["Watch", "the", "next", "catalyst"]},
      ],
      "watermark": "Intel Brief",
      "cta": "Follow for weekly market notes",
      "source": "Edu-finance clip",
    },
    "News": {
      "captions": [
        {"text": "Breaking context in 30 seconds", "words": ["Breaking", "context", "in", "30", "seconds"]},
        {"text": "Source checked before publish", "words": ["Source", "checked", "before", "publish"]},
        {"text": "Stay with the verified angle", "words": ["Stay", "with", "the", "verified", "angle"]},
      ],
      "watermark": "Verified brief",
      "cta": "Subscribe for daily context",
      "source": "Regional desk",
    },
    "Promo": {
      "captions": [
        {"text": "Hook them in frame one", "words": ["Hook", "them", "in", "frame", "one"]},
        {"text": "Make the offer impossible to miss", "words": ["Make", "the", "offer", "impossible", "to", "miss"]},
        {"text": "Tap before the scroll", "words": ["Tap", "before", "the", "scroll"]},
      ],
      "watermark": "Creator promo",
      "cta": "Save this template",
      "source": "Short-form promo",
    },
    "Podcast": {
      "captions": [
        {"text": "The guest drops the real line", "words": ["The", "guest", "drops", "the", "real", "line"]},
        {"text": "Train the takeaway not the noise", "words": ["Train", "the", "takeaway", "not", "the", "noise"]},
        {"text": "Clip the moment worth replaying", "words": ["Clip", "the", "moment", "worth", "replaying"]},
      ],
      "watermark": "Podcast clip",
      "cta": "Follow for the next episode",
      "source": "Interview cut",
    },
    "Official": {
      "captions": [
        {"text": "Open with editorial clarity", "words": ["Open", "with", "editorial", "clarity"]},
        {"text": "Layer context without clutter", "words": ["Layer", "context", "without", "clutter"]},
        {"text": "Close with a confident point", "words": ["Close", "with", "a", "confident", "point"]},
      ],
      "watermark": "Editorial",
      "cta": "Use this look in Create",
      "source": "Editorial sample",
    },
    "Brand": {
      "captions": [
        {"text": "Your brand voice stays consistent", "words": ["Your", "brand", "voice", "stays", "consistent"]},
        {"text": "Reuse the same visual system", "words": ["Reuse", "the", "same", "visual", "system"]},
        {"text": "Ship clips without rework", "words": ["Ship", "clips", "without", "rework"]},
      ],
      "watermark": "Brand system",
      "cta": "Use in Create",
      "source": "Saved brand style",
    },
    }
    pack = niche_copy.get(category, niche_copy["Official"])
    caption_windows = [(1200, 3600), (5200, 8500), (10100, 13200)]
    captions = []
    for line, (start_ms, end_ms) in zip(pack["captions"], caption_windows):
        words = line["words"]
        span = max(1, end_ms - start_ms)
        step = span // max(1, len(words))
        word_rows = []
        cursor = start_ms
        for word_index, word in enumerate(words):
            word_end = end_ms if word_index == len(words) - 1 else cursor + step
            word_rows.append({"text": word, "startMs": cursor, "endMs": word_end})
            cursor = word_end
        captions.append({"text": line["text"], "startMs": start_ms, "endMs": end_ms, "words": word_rows})
    caption_text = ". ".join(line["text"] for line in pack["captions"]) + "."
    hook_line = pack["captions"][0]["text"] if pack["captions"] else label
    subtitle_line = pack["captions"][1]["text"] if len(pack["captions"]) > 1 else ""
    return {
        "captions": captions,
        "captionText": caption_text,
        "watermarkText": pack["watermark"],
        "ctaText": pack["cta"],
        "sourceAttribution": pack["source"],
        "titleHook": hook_line,
        "subtitle": subtitle_line,
    }


def _preview_contract(template_id: str, hyperframes_format: str, width: int, height: int) -> dict[str, Any]:
    template = resolve_hyperframes_template(template_id)
    duration_ms = PREVIEW_SECONDS * 1000
    copy = _preview_copy_for_template(template)
    captions = copy["captions"]
    shell_components = dict(PREVIEW_SHELL_COMPONENTS)
    return {
        "composition": "HyperFramesTemplatePreview",
        "width": width,
        "height": height,
        "fps": 30,
        "durationMs": duration_ms,
        "candidateId": f"preview_{template['id']}",
        "sourceVideoPath": "media/source.mp4",
        "sourceUrl": "preview://template-fixture",
        "sourceAttribution": "",
        "startMs": 0,
        "endMs": duration_ms,
        "startTimecode": "00:00:00",
        "endTimecode": "00:00:15",
        "titleHook": copy["titleHook"],
        "subtitle": copy["subtitle"],
        "overlay": heuristic_overlay_slots(copy["titleHook"], copy["subtitle"]),
        "captionText": copy["captionText"],
        "captions": captions,
        "captionEvents": [],
        "captionDiagnostics": {"eventCount": 0, "maxConcurrentEvents": 0, "overlapCount": 0},
        "visualBeats": [],
        "watermarkText": copy["watermarkText"],
        "ctaText": "",
        "hookSubtitle": copy["subtitle"],
        "stylePreset": "hyperframes_template_preview",
        "style": {
            "caption": {
                "text_color": "#ffffff",
                "highlight_word_color": template.get("accent", "#d8b45f"),
                "font_size": 54 if height > width else 42,
                "preset": template["caption_style"],
            },
            "shell_components": shell_components,
        },
        "shellComponents": shell_components,
        "cropStrategy": "template_preview",
        "captionStyle": template["caption_style"],
        "genres": [],
        "hyperframesTemplate": template["id"],
        "hyperframesFormat": hyperframes_format,
        "templateVersion": template["version"],
        "effectsUsed": template["effects"],
        "componentsUsed": template.get("components_used", []),
        "blocksUsed": template.get("blocks_used", []),
    }
