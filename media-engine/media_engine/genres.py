"""Industry-standard content angles. Niche lives on the workspace, not on chips."""

from __future__ import annotations

from typing import Any


GENRE_AUTO = "auto"

GENRE_OPTIONS: dict[str, dict[str, str]] = {
    "story": {"label": "Story", "description": "Narrative moments, examples, anecdotes, or memorable analogies."},
    "advice": {"label": "Advice", "description": "Practical reminders and takeaways the viewer can use."},
    "opinion": {"label": "Opinion", "description": "A clear take, not a recap — story plus stance."},
    "explainer": {"label": "Explainer", "description": "Teach one idea cleanly for a short-form cut."},
    "social_commentary": {"label": "Commentary", "description": "Culture, behavior, trends, or public habits."},
    "history": {"label": "History", "description": "Backstory, timeline, or a lesson from the past."},
    "tutorial": {"label": "Tutorial", "description": "Steps, how-to, or a process the viewer can follow."},
    # Legacy ids still parse so old jobs/CLI strings do not break.
    "kajian": {"label": "Kajian", "description": "Religious teaching, reflection, and structured advice."},
    "spiritual_reflection": {"label": "Spiritual reflection", "description": "Heart-softening clips about faith, meaning, and inner life."},
    "dua_dzikir": {"label": "Dua and dzikir", "description": "Supplications, remembrance, and devotional practice."},
    "markets": {"label": "Markets", "description": "Markets, investing, macro, and money-flow moments."},
    "tech_ai": {"label": "Tech & AI", "description": "Technology, AI, and builder-tool moments."},
    "business_impact": {"label": "Business impact", "description": "What a tech or market shift means for operators."},
}

UNIVERSAL_CATALOG = ("story", "advice", "opinion", "explainer", "social_commentary", "history", "tutorial")

GENRE_PACKS: dict[str, dict[str, Any]] = {
    "devotional": {
        "label": "Devotional",
        "defaults": ("story", "advice", "social_commentary"),
    },
    "tech_finance": {
        "label": "Tech & finance",
        "defaults": ("advice", "opinion", "explainer"),
    },
    "general": {
        "label": "General",
        "defaults": ("story", "advice", "social_commentary"),
    },
}

DEVOTIONAL_GENRE_IDS = frozenset({"kajian", "spiritual_reflection", "dua_dzikir"})
_DEVOTIONAL_HINTS = ("islam", "kajian", "spiritual", "religi", "nourbit", "dakwah", "quran", "muslim", "devotional")
_TECH_FINANCE_HINTS = (
    "tech",
    "finance",
    "market",
    "ai",
    "saas",
    "investor",
    "builder",
    "crypto",
    "startup",
    "bisnis",
    "business",
    "techtalk",
    "fintech",
)

DEFAULT_PACK = "general"
DEFAULT_GENRES = list(GENRE_PACKS[DEFAULT_PACK]["defaults"])


def resolve_genre_pack(profile_id: str | None = None, niche: str | None = None) -> str:
    pid = (profile_id or "").strip().lower()
    blob = f"{pid} {niche or ''}".lower()
    if pid == "nourbit" or any(hint in blob for hint in _DEVOTIONAL_HINTS):
        return "devotional"
    if any(hint in blob for hint in _TECH_FINANCE_HINTS):
        return "tech_finance"
    return DEFAULT_PACK


def pack_defaults(pack_id: str | None = None, profile_id: str | None = None, niche: str | None = None) -> list[str]:
    pack = pack_id if pack_id in GENRE_PACKS else resolve_genre_pack(profile_id, niche)
    return list(GENRE_PACKS[pack]["defaults"])


def genres_is_auto(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() == GENRE_AUTO
    if isinstance(value, (list, tuple, set)):
        return any(str(part).strip().lower() == GENRE_AUTO for part in value)
    return False


def _parse_genre_parts(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        parts = [str(part).strip() for part in value]
    else:
        return []
    if any(part.lower() == GENRE_AUTO for part in parts):
        return [GENRE_AUTO]
    seen: set[str] = set()
    genres: list[str] = []
    for part in parts:
        if part in GENRE_OPTIONS and part not in seen:
            genres.append(part)
            seen.add(part)
    return genres


def normalize_genres(
    value: Any,
    profile_id: str | None = None,
    niche: str | None = None,
    pack_id: str | None = None,
) -> list[str]:
    if genres_is_auto(value):
        return [GENRE_AUTO]
    known = _parse_genre_parts(value)
    if known:
        return known
    return pack_defaults(pack_id, profile_id, niche)


def genre_options(
    pack_id: str | None = None,
    profile_id: str | None = None,
    niche: str | None = None,
) -> list[dict[str, str]]:
    del pack_id, profile_id, niche
    return [{"id": key, **GENRE_OPTIONS[key]} for key in UNIVERSAL_CATALOG]


def genre_catalog(
    pack_id: str | None = None,
    profile_id: str | None = None,
    niche: str | None = None,
) -> dict[str, Any]:
    pack = pack_id if pack_id in GENRE_PACKS else resolve_genre_pack(profile_id, niche)
    meta = GENRE_PACKS[pack]
    return {
        "pack": pack,
        "pack_label": meta["label"],
        "defaults": [GENRE_AUTO],
        "supports_auto": True,
        "options": genre_options(),
    }


def genre_prompt_phrase(genres: list[str]) -> str:
    if genres_is_auto(genres):
        return ""
    labels = [GENRE_OPTIONS[genre]["label"] for genre in genres if genre in GENRE_OPTIONS]
    return ", ".join(labels)


def genre_catalog_labels() -> str:
    return ", ".join(GENRE_OPTIONS[key]["label"] for key in UNIVERSAL_CATALOG)


def uses_devotional_tone(
    genres: list[str] | None = None,
    profile_id: str | None = None,
    niche: str | None = None,
) -> bool:
    if DEVOTIONAL_GENRE_IDS.intersection(genres or []):
        return True
    return resolve_genre_pack(profile_id, niche) == "devotional"


def workspace_curation_context(workspace_name: str | None = None, niche: str | None = None) -> str:
    name = (workspace_name or "").strip()
    niche_text = (niche or "").strip()
    parts: list[str] = []
    if name:
        parts.append(f"Workspace: {name}.")
    if niche_text:
        parts.append(f"Niche: {niche_text}.")
    if not parts:
        return ""
    parts.append("Match this workspace's niche and brand voice when picking moments.")
    return " ".join(parts)
