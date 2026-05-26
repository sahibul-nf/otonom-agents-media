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


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return text or "custom_template"


def save_style_template(label: str, style: dict[str, Any], base_style_path: str | Path | None = None) -> dict[str, str]:
    clean_label = str(label or "").strip() or "Custom Brand Template"
    payload = deep_merge(load_style(base_style_path), style)
    payload["label"] = clean_label
    template_id = f"custom_{_slug(clean_label)}"
    payload["id"] = template_id
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = PROFILES_DIR / f"{template_id}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    relative = str(path.relative_to(ROOT))
    return {"id": relative, "label": clean_label, "path": relative}


def save_brand_system_template(
    label: str,
    style: dict[str, Any],
    brand_system: dict[str, Any],
    base_style_path: str | Path | None = None,
) -> dict[str, str]:
    payload = deep_merge(style, {"brand_system": brand_system})
    return save_style_template(label, payload, base_style_path)
