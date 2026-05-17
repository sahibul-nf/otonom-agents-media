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
    "auto": DurationPreset(
        id="auto",
        label="Auto (0-3 min)",
        min_ms=20_000,
        target_ms=90_000,
        max_ms=180_000,
        intent="Let the engine choose the best short length up to three minutes based on context and retention.",
        best_for="General use",
    ),
    "under_30s": DurationPreset(
        id="under_30s",
        label="Under 30s",
        min_ms=8_000,
        target_ms=22_000,
        max_ms=30_000,
        intent="Very short clips for punchy quotes, fast facts, and high-velocity hooks.",
        best_for="Hooks, quotes",
    ),
    "seconds_30_60": DurationPreset(
        id="seconds_30_60",
        label="30s - 60s",
        min_ms=30_000,
        target_ms=45_000,
        max_ms=60_000,
        intent="Compact clips for one strong idea with enough room for setup and payoff.",
        best_for="Short ideas",
    ),
    "minutes_1_3": DurationPreset(
        id="minutes_1_3",
        label="1 - 3 min",
        min_ms=60_000,
        target_ms=110_000,
        max_ms=180_000,
        intent="Longer short-form clips for deeper context, stories, lectures, and reflective moments.",
        best_for="Context clips",
    ),
    "minutes_3_plus": DurationPreset(
        id="minutes_3_plus",
        label="3+ min",
        min_ms=180_000,
        target_ms=240_000,
        max_ms=360_000,
        intent="Extended clips for platforms or niches where longer context is worth the retention tradeoff.",
        best_for="Extended context",
    ),
}

ALIASES = {
    "custom": "auto",
    "30-60s": "seconds_30_60",
    "45-120s": "minutes_1_3",
    "60-90s": "minutes_1_3",
    "quick": "under_30s",
    "quick_hit": "seconds_30_60",
    "standard": "seconds_30_60",
    "standard_short": "seconds_30_60",
    "deep": "minutes_1_3",
    "deep_context": "minutes_1_3",
    "max": "minutes_1_3",
    "platform_max": "minutes_1_3",
    "under30": "under_30s",
    "30_60": "seconds_30_60",
    "1_3": "minutes_1_3",
    "3plus": "minutes_3_plus",
    "manual": "auto",
}


def resolve_duration_preset(value: str | None) -> DurationPreset:
    key = (value or "auto").strip()
    key = ALIASES.get(key, key)
    return DURATION_PRESETS.get(key, DURATION_PRESETS["auto"])


def custom_duration_preset(min_seconds: int | None, max_seconds: int | None) -> DurationPreset:
    min_s = 20 if min_seconds is None else int(min_seconds)
    max_s = 180 if max_seconds is None else int(max_seconds)
    if min_s < 0:
        raise ValueError("clip_min_seconds must be at least 0")
    if max_s > 600:
        raise ValueError("clip_max_seconds must be at most 600")
    if min_s > max_s:
        raise ValueError("clip_min_seconds must be less than or equal to clip_max_seconds")
    target_s = min(max((min_s + max_s) // 2, min_s), max_s)
    return DurationPreset(
        id="custom",
        label="Custom Range",
        min_ms=min_s * 1000,
        target_ms=target_s * 1000,
        max_ms=max_s * 1000,
        intent=f"User-defined {min_s}-{max_s} second batch guardrail.",
        best_for="Custom batch",
    )


def resolve_duration_strategy(value: str | None, min_seconds: int | None = None, max_seconds: int | None = None) -> DurationPreset:
    if min_seconds is not None or max_seconds is not None or (value or "").strip() == "custom":
        return custom_duration_preset(min_seconds, max_seconds)
    return resolve_duration_preset(value)


def duration_preset_options() -> list[dict[str, Any]]:
    options = []
    for preset in DURATION_PRESETS.values():
        range_label = {
            "auto": "0-3 min",
            "under_30s": "Under 30s",
            "seconds_30_60": "30s-60s",
            "minutes_1_3": "1-3 min",
            "minutes_3_plus": "3+ min",
        }.get(preset.id, f"{preset.min_ms // 1000}-{preset.max_ms // 1000}s")
        options.append(
            {
                "id": preset.id,
                "label": preset.label,
                "min_ms": preset.min_ms,
                "target_ms": preset.target_ms,
                "max_ms": preset.max_ms,
                "range_label": range_label,
                "detail": f"{range_label} · {preset.best_for}",
                "intent": preset.intent,
                "best_for": preset.best_for,
            }
        )
    return options


def duration_prompt_phrase(preset: DurationPreset) -> str:
    min_s = preset.min_ms // 1000
    max_s = preset.max_ms // 1000
    return f"{min_s}-{max_s} detik ({preset.label}: {preset.intent})"
