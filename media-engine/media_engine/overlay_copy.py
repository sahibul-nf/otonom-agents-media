"""Clip-specific HyperFrames overlay slots (not gallery dummy copy)."""

from __future__ import annotations

from typing import Any

OVERLAY_KEYS = ("kicker", "headline", "subhead", "stamp", "line_a", "line_b")
OVERLAY_LIMITS = {
    "kicker": 28,
    "headline": 56,
    "subhead": 80,
    "stamp": 22,
    "line_a": 32,
    "line_b": 32,
}

# Catalog sample strings that must never ship on a production clip overlay.
FORBIDDEN_OVERLAY_COPY = frozenset(
    {
        "more clarity",
        "mustard mode",
        "level up",
        "boost your business",
        "add captions",
        "in seconds",
        "more views?",
        "say it louder",
        "how to build anything",
        "seize the future",
        "remember the consistency",
        "creative",
        "lessons",
        "emphasis",
        "guidelines",
        "play mode",
        "cyber",
        "volt",
        "bloom",
        "make it pop",
        "training",
        "archive",
        "pro",
        "$29",
        "idea",
        "ship",
        "hook",
        "now",
        "fast",
        "simple",
        "start",
        "decide",
        "result",
    }
)


def clip_overlay_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip(" ,;:-") + "…"


def _is_forbidden(text: str) -> bool:
    return text.lower().strip(" .!?'\"") in FORBIDDEN_OVERLAY_COPY


def heuristic_overlay_slots(title_hook: str, hook_subtitle: str = "") -> dict[str, str]:
    hook = " ".join(str(title_hook or "").split())
    sub = " ".join(str(hook_subtitle or "").split())
    words = hook.split()
    kicker = words[0] if words else ""
    stamp = kicker.upper() if kicker else ""
    mid = max(1, (len(words) + 1) // 2)
    line_a = " ".join(words[:mid])
    line_b = " ".join(words[mid:]) or sub
    slots = {
        "kicker": clip_overlay_text(kicker, OVERLAY_LIMITS["kicker"]),
        "headline": clip_overlay_text(hook, OVERLAY_LIMITS["headline"]),
        "subhead": clip_overlay_text(sub, OVERLAY_LIMITS["subhead"]),
        "stamp": clip_overlay_text(stamp, OVERLAY_LIMITS["stamp"]),
        "line_a": clip_overlay_text(line_a, OVERLAY_LIMITS["line_a"]),
        "line_b": clip_overlay_text(line_b, OVERLAY_LIMITS["line_b"]),
    }
    return {key: value for key, value in slots.items() if value and not _is_forbidden(value)}


def merge_overlay_slots(base: dict[str, str], override: Any) -> dict[str, str]:
    merged = dict(base)
    if not isinstance(override, dict):
        return merged
    for key in OVERLAY_KEYS:
        raw = clip_overlay_text(override.get(key), OVERLAY_LIMITS[key])
        if not raw or _is_forbidden(raw):
            continue
        merged[key] = raw
    return merged


def overlay_slots_for_candidate(
    candidate: dict[str, Any],
    llm_suggestion: dict[str, Any] | None = None,
) -> dict[str, str]:
    title = str(candidate.get("title_hook") or candidate.get("titleHook") or "").strip()
    subtitle = str(
        candidate.get("hook_subtitle")
        or candidate.get("hookSubtitle")
        or candidate.get("subtitle")
        or ""
    ).strip()
    base = heuristic_overlay_slots(title, subtitle)
    suggestion = llm_suggestion if isinstance(llm_suggestion, dict) else {}
    existing = candidate.get("overlay_slots")
    if not isinstance(existing, dict):
        meta = candidate.get("curation_metadata")
        existing = meta.get("overlay_slots") if isinstance(meta, dict) else None
    merged = merge_overlay_slots(base, existing)
    return merge_overlay_slots(merged, suggestion.get("overlay"))


def resolve_overlay_for_contract(contract: dict[str, Any]) -> dict[str, str]:
    title = str(contract.get("titleHook") or contract.get("title_hook") or "").strip()
    subtitle = str(
        contract.get("hookSubtitle") or contract.get("hook_subtitle") or contract.get("subtitle") or ""
    ).strip()
    base = heuristic_overlay_slots(title, subtitle)
    return merge_overlay_slots(base, contract.get("overlay"))


def overlay_text(contract: dict[str, Any], *keys: str, default: str = "") -> str:
    slots = resolve_overlay_for_contract(contract)
    for key in keys:
        value = str(slots.get(key) or "").strip()
        if value:
            return value
    return str(default or "").strip()
