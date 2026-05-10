"""Render style profiles for SaaS-like configurable short templates."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .db import ROOT


DEFAULT_STYLE_PATH = ROOT / "profiles" / "nourbit_opus_style.json"


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
    override_path = Path(style_path)
    override = json.loads(override_path.read_text(encoding="utf-8"))
    return deep_merge(base, override)
