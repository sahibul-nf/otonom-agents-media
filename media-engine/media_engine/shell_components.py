"""Optional HyperFrames shell component flags (hook, watermark, source, CTA)."""

from __future__ import annotations

from typing import Any

SHELL_COMPONENT_KEYS = ("hook", "watermark", "source", "cta")

CATEGORY_SHELL_DEFAULTS: dict[str, dict[str, bool]] = {
    "Spiritual": {"hook": False, "watermark": True, "source": False, "cta": True},
    "Data": {"hook": False, "watermark": True, "source": True, "cta": False},
    "News": {"hook": False, "watermark": True, "source": True, "cta": False},
    "Promo": {"hook": False, "watermark": True, "source": False, "cta": True},
    "Podcast": {"hook": False, "watermark": True, "source": False, "cta": True},
    "Official": {"hook": False, "watermark": True, "source": False, "cta": False},
    "Brand": {"hook": False, "watermark": True, "source": False, "cta": True},
}

FALLBACK_SHELL_DEFAULTS: dict[str, bool] = {
    "hook": False,
    "watermark": True,
    "source": False,
    "cta": True,
}


def category_shell_defaults(category: str) -> dict[str, bool]:
    return dict(CATEGORY_SHELL_DEFAULTS.get(str(category or "").strip(), FALLBACK_SHELL_DEFAULTS))


def normalize_shell_components(value: Any, *, category: str = "") -> dict[str, bool]:
    base = category_shell_defaults(category) if category else dict(FALLBACK_SHELL_DEFAULTS)
    if not isinstance(value, dict):
        return base
    merged = dict(base)
    for key in SHELL_COMPONENT_KEYS:
        if key in value:
            merged[key] = bool(value[key])
    return merged


def merge_shell_components(*layers: Any) -> dict[str, bool]:
    merged = dict(FALLBACK_SHELL_DEFAULTS)
    for layer in layers:
        if isinstance(layer, dict):
            for key in SHELL_COMPONENT_KEYS:
                if key in layer:
                    merged[key] = bool(layer[key])
    return merged
