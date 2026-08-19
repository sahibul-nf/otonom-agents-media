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
