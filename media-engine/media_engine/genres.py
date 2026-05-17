"""Content genre options used by curation and dashboard generation."""

from __future__ import annotations

from typing import Any


GENRE_OPTIONS: dict[str, dict[str, str]] = {
    "kajian": {"label": "Kajian", "description": "Religious teaching, reflection, and structured advice."},
    "spiritual_reflection": {"label": "Spiritual reflection", "description": "Heart-softening clips about faith, meaning, and inner life."},
    "story": {"label": "Story", "description": "Narrative moments, examples, anecdotes, or memorable analogies."},
    "advice": {"label": "Advice", "description": "Practical reminders, personal conduct, and daily-life guidance."},
    "social_commentary": {"label": "Social commentary", "description": "Comments on culture, behavior, trends, or public habits."},
    "history": {"label": "History", "description": "Historical facts, figures, places, and lessons."},
    "dua_dzikir": {"label": "Dua and dzikir", "description": "Supplications, remembrance, and devotional practice."},
}

DEFAULT_GENRES = ["kajian", "spiritual_reflection", "advice"]


def normalize_genres(value: Any) -> list[str]:
    if value is None or value == "":
        return list(DEFAULT_GENRES)
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        parts = [str(part).strip() for part in value]
    else:
        parts = []
    seen: set[str] = set()
    genres = []
    for part in parts:
        if part in GENRE_OPTIONS and part not in seen:
            genres.append(part)
            seen.add(part)
    return genres or list(DEFAULT_GENRES)


def genre_options() -> list[dict[str, str]]:
    return [{"id": key, **value} for key, value in GENRE_OPTIONS.items()]


def genre_prompt_phrase(genres: list[str]) -> str:
    labels = [GENRE_OPTIONS[genre]["label"] for genre in normalize_genres(genres)]
    return ", ".join(labels)
