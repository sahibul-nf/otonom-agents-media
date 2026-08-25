"""Render style profiles for SaaS-like configurable short templates."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .db import ROOT


DEFAULT_STYLE_PATH = ROOT / "profiles" / "default_workspace_style.json"
PROFILES_DIR = ROOT / "profiles"
TEMPLATE_ONLY_STYLE_TOKEN = "auto"
_LEGACY_DEFAULT_STYLE_REFS = frozenset(
    {
        "profiles/default_workspace_style.json",
        "default_workspace_style.json",
    }
)


def is_template_only_style(style_path: str | Path | None) -> bool:
    text = str(style_path or "").strip().lower()
    if text in {"", TEMPLATE_ONLY_STYLE_TOKEN, "template", "none"}:
        return True
    return str(style_path or "").strip() in _LEGACY_DEFAULT_STYLE_REFS


TEMPLATE_ONLY_CAPTION_FONT_SIZE = 48
TEMPLATE_ONLY_CAPTION_FONT_MIN = 36
TEMPLATE_ONLY_CAPTION_FONT_MAX = 50
TEMPLATE_ONLY_CAPTION_STROKE_WIDTH = 6
TEMPLATE_ONLY_CAPTION_BACKGROUND = "rgba(0,0,0,0.62)"


def _caption_background_is_off(value: Any) -> bool:
    text = str(value or "").strip().lower().replace(" ", "")
    return text in {"", "transparent", "none", "rgba(0,0,0,0)", "#00000000"}


def apply_readable_template_only_caption(caption: dict[str, Any]) -> dict[str, Any]:
    """Karaoke must stay in the 40–50px band with stroke or a caption card."""
    size = int(caption.get("font_size") or TEMPLATE_ONLY_CAPTION_FONT_SIZE)
    if size < TEMPLATE_ONLY_CAPTION_FONT_MIN:
        size = TEMPLATE_ONLY_CAPTION_FONT_SIZE
    caption["font_size"] = max(40, min(TEMPLATE_ONLY_CAPTION_FONT_MAX, size))
    stroke = float(caption.get("stroke_width") or 0)
    if stroke <= 0:
        caption["stroke_width"] = TEMPLATE_ONLY_CAPTION_STROKE_WIDTH
    if _caption_background_is_off(caption.get("background_color")):
        caption["background_color"] = TEMPLATE_ONLY_CAPTION_BACKGROUND
    return caption


def normalize_brand_template_ref(value: Any) -> str:
    text = str(value or "").strip()
    if is_template_only_style(text):
        return TEMPLATE_ONLY_STYLE_TOKEN
    return text


def resolve_style_path(style_path: str | Path | None = None) -> Path:
    if not style_path:
        return DEFAULT_STYLE_PATH
    path = Path(style_path)
    if not path.is_absolute():
        path = ROOT / path
    resolved = path.resolve()
    if ROOT.resolve() not in resolved.parents and resolved != ROOT.resolve():
        raise ValueError("style path must be inside the media engine project")
    if not resolved.exists():
        raise ValueError("style template not found")
    return resolved


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_style(style_path: str | Path | None = None) -> dict[str, Any]:
    base = json.loads(DEFAULT_STYLE_PATH.read_text(encoding="utf-8"))
    if not style_path:
        return base
    override_path = resolve_style_path(style_path)
    override = json.loads(override_path.read_text(encoding="utf-8"))
    return deep_merge(base, override)


def style_from_recipe(template_id: str) -> dict[str, Any]:
    """Minimal render style driven by the HyperFrames recipe — no platform brand overlay."""
    from .hyperframes_recipes import get_recipe, recipe_style_meta
    from .hyperframes_templates import normalize_hyperframes_template, resolve_hyperframes_template

    resolved = resolve_hyperframes_template(normalize_hyperframes_template(template_id))
    recipe_id = str(resolved.get("recipe_module") or resolved["id"])
    recipe = get_recipe(recipe_id)
    meta = recipe_style_meta(recipe_id)
    font_primary = str(meta.font_family or "Arial").split(",")[0].strip() or "Arial"
    default_doc = json.loads(DEFAULT_STYLE_PATH.read_text(encoding="utf-8"))
    default_layout = default_doc.get("layout") if isinstance(default_doc.get("layout"), dict) else {}
    return {
        "id": "template_only",
        "label": "Template default",
        "template_only": True,
        "layout": deepcopy(default_layout),
        "caption": apply_readable_template_only_caption({
            "preset": "mozi",
            "font_family": font_primary,
            "fallback_font_family": "Arial",
            "font_size": TEMPLATE_ONLY_CAPTION_FONT_SIZE,
            "font_weight": "black",
            "uppercase": False,
            "position": "bottom",
            "lines": 1,
            "max_words_per_caption": 3,
            "text_color": "#ffffff",
            "stroke_color": "#000000",
            "stroke_width": TEMPLATE_ONLY_CAPTION_STROKE_WIDTH,
            "highlight_word_color": "",
            "animation": "bounce",
            "background_color": TEMPLATE_ONLY_CAPTION_BACKGROUND,
            "background_radius": 8,
        }),
        "brand": {
            "watermark_text": "",
            "source_attribution_prefix": "Source:",
            "cta_enabled": False,
            "intro_enabled": False,
            "outro_enabled": False,
        },
        "shell_components": recipe.default_shell_components(),
        "ai": deepcopy(default_doc.get("ai")) if isinstance(default_doc.get("ai"), dict) else {},
    }


def load_style_for_render(
    style_path: str | Path | None = None,
    *,
    hyperframes_template: str = "auto",
    genres: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    if is_template_only_style(style_path):
        from .hyperframes_templates import resolve_hyperframes_template

        resolved = resolve_hyperframes_template(hyperframes_template, genres=genres or ())
        recipe_id = str(resolved.get("recipe_module") or resolved["id"])
        return style_from_recipe(recipe_id)
    return load_style(style_path)


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return text or "custom_template"


def _profiles_relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve()))


def _resolve_save_path(label: str, target_path: str | Path | None = None) -> tuple[Path, str]:
    """Return (absolute path, template id) for a brand style write."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    if target_path:
        path = resolve_style_path(target_path)
        if path.parent.resolve() != PROFILES_DIR.resolve():
            raise ValueError("target path must be inside profiles/")
        if not path.name.startswith("custom_") or path.suffix != ".json":
            raise ValueError("can only overwrite custom_*.json brand templates")
        return path, path.stem
    template_id = f"custom_{_slug(label)}"
    return PROFILES_DIR / f"{template_id}.json", template_id


def save_style_template(
    label: str,
    style: dict[str, Any],
    base_style_path: str | Path | None = None,
    target_path: str | Path | None = None,
) -> dict[str, str]:
    clean_label = str(label or "").strip() or "Custom Brand Template"
    payload = deep_merge(load_style(base_style_path), style)
    payload["label"] = clean_label
    path, template_id = _resolve_save_path(clean_label, target_path)
    payload["id"] = template_id
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    relative = _profiles_relative(path)
    return {"id": relative, "label": clean_label, "path": relative}


def save_brand_system_template(
    label: str,
    style: dict[str, Any],
    brand_system: dict[str, Any],
    base_style_path: str | Path | None = None,
    target_path: str | Path | None = None,
) -> dict[str, str]:
    payload = deep_merge(style, {"brand_system": brand_system})
    return save_style_template(label, payload, base_style_path, target_path=target_path)


def _brand_public_id(template_id: str) -> str:
    clean = str(template_id or "").strip()
    if clean.startswith("brand:"):
        return clean
    if not clean.startswith("custom_"):
        clean = f"custom_{_slug(clean)}"
    return f"brand:{clean}"


def resolve_custom_brand_template_path(
    *,
    path: str | Path | None = None,
    template_id: str | None = None,
) -> Path:
    raw_path = str(path or "").strip()
    raw_id = str(template_id or "").strip()
    if raw_path:
        resolved = resolve_style_path(raw_path)
    elif raw_id:
        if raw_id.startswith("brand:"):
            raw_id = raw_id.split(":", 1)[1]
        candidate = PROFILES_DIR / f"{raw_id}.json" if not raw_id.endswith(".json") else PROFILES_DIR / Path(raw_id).name
        resolved = resolve_style_path(candidate)
    else:
        raise ValueError("path or template_id is required")
    if resolved.parent.resolve() != PROFILES_DIR.resolve():
        raise ValueError("only profiles/custom_*.json brand templates can be deleted")
    if not resolved.name.startswith("custom_") or resolved.suffix != ".json":
        raise ValueError("only profiles/custom_*.json brand templates can be deleted")
    if not resolved.exists():
        raise ValueError("brand template not found")
    return resolved


def delete_brand_template(
    *,
    path: str | Path | None = None,
    template_id: str | None = None,
) -> dict[str, str]:
    resolved = resolve_custom_brand_template_path(path=path, template_id=template_id)
    template_slug = resolved.stem
    brand_id = _brand_public_id(template_slug)
    relative = _profiles_relative(resolved)
    resolved.unlink()
    return {
        "deleted": "true",
        "path": relative,
        "template_id": template_slug,
        "brand_id": brand_id,
    }
