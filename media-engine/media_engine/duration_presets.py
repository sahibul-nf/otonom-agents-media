"""Niche-aware duration presets for short-form candidate selection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DurationPreset:
    id: str
    label: str
    min_ms: int
    target_ms: int
    max_ms: int
    intent: str


DURATION_PRESETS: dict[str, DurationPreset] = {
    "quick_hit": DurationPreset(
        id="quick_hit",
        label="Quick Hit",
        min_ms=20_000,
        target_ms=38_000,
        max_ms=60_000,
        intent="Fast punchy clips for news, sports, facts, quotes, and visual-driven moments.",
    ),
    "standard_short": DurationPreset(
        id="standard_short",
        label="Standard Short",
        min_ms=35_000,
        target_ms=65_000,
        max_ms=90_000,
        intent="Balanced clips for explainers, tech updates, and one clear takeaway.",
    ),
    "deep_context": DurationPreset(
        id="deep_context",
        label="Deep Context",
        min_ms=45_000,
        target_ms=95_000,
        max_ms=120_000,
        intent="Meaning-first clips for kajian, podcast, reflection, and story-based content.",
    ),
    "platform_max": DurationPreset(
        id="platform_max",
        label="Platform Max",
        min_ms=90_000,
        target_ms=150_000,
        max_ms=180_000,
        intent="Longer shorts where YouTube/TikTok retention can support deeper context.",
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


def duration_prompt_phrase(preset: DurationPreset) -> str:
    min_s = preset.min_ms // 1000
    max_s = preset.max_ms // 1000
    return f"{min_s}-{max_s} detik ({preset.label}: {preset.intent})"
