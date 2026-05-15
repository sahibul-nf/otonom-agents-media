"""Niche-aware duration presets for short-form candidate selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DurationPreset:
    id: str
    label: str
    min_ms: int
    target_ms: int
    max_ms: int
    intent: str
    best_for: str


DURATION_PRESETS: dict[str, DurationPreset] = {
    "quick_hit": DurationPreset(
        id="quick_hit",
        label="Quick Hit",
        min_ms=20_000,
        target_ms=38_000,
        max_ms=60_000,
        intent="Fast punchy clips for news, sports, facts, quotes, and visual-driven moments.",
        best_for="News, sports, quotes",
    ),
    "standard_short": DurationPreset(
        id="standard_short",
        label="Standard Short",
        min_ms=35_000,
        target_ms=65_000,
        max_ms=90_000,
        intent="Balanced clips for explainers, tech updates, and one clear takeaway.",
        best_for="Tech, explainers",
    ),
    "deep_context": DurationPreset(
        id="deep_context",
        label="Deep Context",
        min_ms=45_000,
        target_ms=95_000,
        max_ms=120_000,
        intent="Meaning-first clips for kajian, podcast, reflection, and story-based content.",
        best_for="Podcasts, lectures",
    ),
    "platform_max": DurationPreset(
        id="platform_max",
        label="Platform Max",
        min_ms=90_000,
        target_ms=150_000,
        max_ms=180_000,
        intent="Longer shorts where YouTube/TikTok retention can support deeper context.",
        best_for="Deep dives",
    ),
}

ALIASES = {
    "30-60s": "quick_hit",
    "45-120s": "deep_context",
    "60-90s": "standard_short",
    "quick": "quick_hit",
    "standard": "standard_short",
    "deep": "deep_context",
    "max": "platform_max",
}


def resolve_duration_preset(value: str | None) -> DurationPreset:
    key = (value or "deep_context").strip()
    key = ALIASES.get(key, key)
    return DURATION_PRESETS.get(key, DURATION_PRESETS["deep_context"])


def duration_preset_options() -> list[dict[str, Any]]:
    options = []
    for preset in DURATION_PRESETS.values():
        options.append(
            {
                "id": preset.id,
                "label": preset.label,
                "min_ms": preset.min_ms,
                "target_ms": preset.target_ms,
                "max_ms": preset.max_ms,
                "range_label": f"{preset.min_ms // 1000}-{preset.max_ms // 1000}s",
                "detail": f"{preset.min_ms // 1000}-{preset.max_ms // 1000}s · {preset.best_for}",
                "intent": preset.intent,
                "best_for": preset.best_for,
            }
        )
    return options


def duration_prompt_phrase(preset: DurationPreset) -> str:
    min_s = preset.min_ms // 1000
    max_s = preset.max_ms // 1000
    return f"{min_s}-{max_s} detik ({preset.label}: {preset.intent})"
