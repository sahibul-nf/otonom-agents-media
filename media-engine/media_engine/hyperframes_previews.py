"""On-demand HyperFrames template preview rendering."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .db import ARTIFACTS_DIR
from .hyperframes_renderer import build_hyperframes_index_html, render_hyperframes_project, require_hyperframes_runtime
from .hyperframes_templates import (
    PREVIEW_SECONDS,
    dimensions_for_format,
    list_hyperframes_templates,
    normalize_hyperframes_format,
    normalize_hyperframes_template,
    resolve_hyperframes_template,
)


PREVIEW_ROOT = ARTIFACTS_DIR / "hyperframes_template_previews"


def preview_path(template_id: str, hyperframes_format: str) -> Path:
    normalized_template = normalize_hyperframes_template(template_id.replace("__", ":"))
    normalized_format = normalize_hyperframes_format(hyperframes_format)
    if normalized_format == "auto":
        normalized_format = "short_9_16"
    safe_template = normalized_template.replace(":", "__")
    return PREVIEW_ROOT / safe_template / normalized_format / "preview.mp4"


def preview_status(template_id: str, hyperframes_format: str) -> dict[str, Any]:
    output = preview_path(template_id, hyperframes_format)
    metadata_path = output.parent / "preview-metadata.json"
    metadata: dict[str, Any] = {}
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            metadata = {}
    return {
        "template": template_id,
        "format": normalize_hyperframes_format(hyperframes_format),
        "ready": output.exists() and output.stat().st_size > 0,
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


def prewarm_hyperframes_template_previews(include_brand: bool = False) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for template in list_hyperframes_templates():
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
    if output.exists() and output.stat().st_size > 0:
        return output

    require_hyperframes_runtime()
    output.parent.mkdir(parents=True, exist_ok=True)
    width, height, resolved_format = dimensions_for_format(hyperframes_format)
    project_dir = output.parent / "project"
    media_dir = project_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    source = media_dir / "source.mp4"
    if not source.exists():
        _write_preview_source(source, width, height)

    contract = _preview_contract(template_id.replace("__", ":"), resolved_format, width, height)
    (project_dir / "index.html").write_text(
        build_hyperframes_index_html(contract, template_id.replace("__", ":"), resolved_format, genres=[]),
        encoding="utf-8",
    )
    checks = render_hyperframes_project(project_dir, output, quality="draft")
    (output.parent / "preview-metadata.json").write_text(
        json.dumps({"template": contract["hyperframesTemplate"], "format": resolved_format, "checks": checks}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output


def _write_preview_source(path: Path, width: int, height: int) -> None:
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


def _preview_contract(template_id: str, hyperframes_format: str, width: int, height: int) -> dict[str, Any]:
    template = resolve_hyperframes_template(template_id)
    duration_ms = PREVIEW_SECONDS * 1000
    captions = [
        {
            "text": "Start with a sharp hook",
            "startMs": 1200,
            "endMs": 3600,
            "words": [
                {"text": "Start", "startMs": 1200, "endMs": 1700},
                {"text": "with", "startMs": 1700, "endMs": 2100},
                {"text": "a", "startMs": 2100, "endMs": 2350},
                {"text": "sharp", "startMs": 2350, "endMs": 3000},
                {"text": "hook", "startMs": 3000, "endMs": 3600},
            ],
        },
        {
            "text": "Add context without losing pace",
            "startMs": 5200,
            "endMs": 8500,
            "words": [
                {"text": "Add", "startMs": 5200, "endMs": 5700},
                {"text": "context", "startMs": 5700, "endMs": 6600},
                {"text": "without", "startMs": 6600, "endMs": 7350},
                {"text": "losing", "startMs": 7350, "endMs": 7950},
                {"text": "pace", "startMs": 7950, "endMs": 8500},
            ],
        },
        {
            "text": "Close with a clear action",
            "startMs": 10100,
            "endMs": 13200,
            "words": [
                {"text": "Close", "startMs": 10100, "endMs": 10700},
                {"text": "with", "startMs": 10700, "endMs": 11200},
                {"text": "a", "startMs": 11200, "endMs": 11500},
                {"text": "clear", "startMs": 11500, "endMs": 12300},
                {"text": "action", "startMs": 12300, "endMs": 13200},
            ],
        },
    ]
    return {
        "composition": "HyperFramesTemplatePreview",
        "width": width,
        "height": height,
        "fps": 30,
        "durationMs": duration_ms,
        "candidateId": f"preview_{template['id']}",
        "sourceVideoPath": "media/source.mp4",
        "sourceUrl": "preview://template-fixture",
        "sourceAttribution": "Template preview fixture",
        "startMs": 0,
        "endMs": duration_ms,
        "startTimecode": "00:00:00",
        "endTimecode": "00:00:15",
        "titleHook": template["label"],
        "subtitle": template["best_for"],
        "captionText": "Start with a sharp hook. Add context without losing pace. Close with a clear action.",
        "captions": captions,
        "captionEvents": [],
        "captionDiagnostics": {"eventCount": 0, "maxConcurrentEvents": 0, "overlapCount": 0},
        "visualBeats": [],
        "watermarkText": "Brand System",
        "ctaText": "Use this template",
        "stylePreset": "hyperframes_template_preview",
        "style": {
            "caption": {
                "text_color": "#ffffff",
                "highlight_word_color": template.get("accent", "#d8b45f"),
                "font_size": 54 if height > width else 42,
                "preset": template["caption_style"],
            }
        },
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
