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


BRAND_STUDIO_CATEGORY_KICKERS = {
    "Spiritual": "Reflection",
    "Promo": "Takeaway",
    "Official": "Story",
    "News": "Brief",
    "Data": "Insight",
    "Podcast": "Moment",
}


def brand_studio_overlay_slots(sample_phrase: str, template_category: str = "Official") -> dict[str, str]:
    """Short hook slots for Brand Studio — never mirror the full caption line."""
    text = " ".join(str(sample_phrase or "").split())
    words = text.split()
    category_kicker = BRAND_STUDIO_CATEGORY_KICKERS.get(template_category, "Takeaway")
    if not words:
        return {
            "kicker": category_kicker,
            "headline": category_kicker,
            "stamp": category_kicker.upper(),
        }
    short_hook = " ".join(words[:3])
    snippet = words[:4]
    mid = max(1, len(snippet) // 2)
    line_a = " ".join(snippet[:mid])
    line_b = " ".join(snippet[mid:]) if len(snippet) > mid else ""
    slots = {
        "kicker": clip_overlay_text(category_kicker, OVERLAY_LIMITS["kicker"]),
        "headline": clip_overlay_text(short_hook, OVERLAY_LIMITS["headline"]),
        "subhead": "",
        "stamp": clip_overlay_text(category_kicker.upper(), OVERLAY_LIMITS["stamp"]),
        "line_a": clip_overlay_text(line_a, OVERLAY_LIMITS["line_a"]),
        "line_b": clip_overlay_text(line_b, OVERLAY_LIMITS["line_b"]),
    }
    return {key: value for key, value in slots.items() if value and not _is_forbidden(value)}


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


def _overlay_matches_title(overlay: dict[str, Any], title: str) -> bool:
    headline = " ".join(str(overlay.get("headline") or "").split()).lower()
    title_norm = " ".join(str(title or "").split()).lower()
    if not headline or not title_norm:
        return False
    if headline == title_norm:
        return True
    title_words = {word for word in title_norm.split() if len(word) > 2}
    headline_words = {word for word in headline.split() if len(word) > 2}
    if not title_words or not headline_words:
        return False
    overlap = len(title_words & headline_words)
    return overlap >= max(1, min(2, len(title_words) // 2))


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
    if isinstance(existing, dict) and not _overlay_matches_title(existing, title):
        existing = None
    merged = merge_overlay_slots(base, existing)
    return merge_overlay_slots(merged, suggestion.get("overlay"))


def resolve_overlay_for_contract(contract: dict[str, Any]) -> dict[str, str]:
    title = str(contract.get("titleHook") or contract.get("title_hook") or "").strip()
    subtitle = str(
        contract.get("hookSubtitle") or contract.get("hook_subtitle") or contract.get("subtitle") or ""
    ).strip()
    base = heuristic_overlay_slots(title, subtitle)
    overlay = contract.get("overlay")
    if isinstance(overlay, dict) and not _overlay_matches_title(overlay, title):
        overlay = None
    return merge_overlay_slots(base, overlay)


def overlay_text(contract: dict[str, Any], *keys: str, default: str = "") -> str:
    slots = resolve_overlay_for_contract(contract)
    for key in keys:
        value = str(slots.get(key) or "").strip()
        if value:
            return value
    return str(default or "").strip()
