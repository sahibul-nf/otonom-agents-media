"""Recommend content angles from a resolved source before the user generates clips."""

from __future__ import annotations

import json
from typing import Any

from .decisions import answer_choice, jev_available, jev_decide
from .genres import GENRE_OPTIONS, UNIVERSAL_CATALOG
from .llm import LLMError, call_llm_json
from .post_copy import _available_provider


ANGLE_HINTS: dict[str, tuple[str, ...]] = {
    "story": ("cerita", "waktu", "pernah", "tiba-tiba", "contoh"),
    "advice": ("sebaiknya", "jangan", "lakukan", "tips", "cara"),
    "opinion": ("menurut", "salah", "seharusnya", "masalahnya", "saya pikir"),
    "explainer": ("artinya", "adalah", "mengapa", "bagaimana", "berarti"),
    "social_commentary": ("orang", "masyarakat", "kebiasaan", "tren", "budaya"),
    "history": ("dulu", "sejarah", "tahun", "awal", "berawal"),
    "tutorial": ("langkah", "pertama", "ikuti", "tutorial", "step"),
}


def cheap_caption_excerpt(video_id: str, limit: int = 900) -> str:
    """YouTube captions only. Never starts Whisper."""
    video_id = (video_id or "").strip()
    if not video_id:
        return ""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return ""
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=["id", "en"])
    except Exception:  # noqa: BLE001 — missing captions should not block the form
        return ""
    texts: list[str] = []
    for item in list(fetched)[:40]:
        text = getattr(item, "text", None)
        if text is None and isinstance(item, dict):
            text = item.get("text")
        if text:
            texts.append(str(text).strip())
    return " ".join(part for part in texts if part)[:limit]


def _heuristic_angles(title: str, description: str, excerpt: str) -> list[dict[str, str]]:
    blob = f"{title} {description} {excerpt}".lower()
    ranked: list[tuple[int, str]] = []
    for angle_id in UNIVERSAL_CATALOG:
        hits = sum(1 for hint in ANGLE_HINTS.get(angle_id, ()) if hint in blob)
        ranked.append((hits, angle_id))
    ranked.sort(key=lambda item: item[0], reverse=True)
    picked = [angle_id for hits, angle_id in ranked if hits > 0][:3]
    if not picked:
        picked = ["explainer", "opinion", "advice"]
    recommendations = []
    for angle_id in picked:
        label = GENRE_OPTIONS[angle_id]["label"]
        recommendations.append(
            {
                "id": angle_id,
                "label": label,
                "reason": f"Cuplikan sumber paling dekat dengan sudut {label.lower()}.",
            }
        )
    return recommendations


def _llm_angles(title: str, description: str, excerpt: str, provider: str) -> list[dict[str, str]] | None:
    catalog = [{"id": key, "label": GENRE_OPTIONS[key]["label"], "description": GENRE_OPTIONS[key]["description"]} for key in UNIVERSAL_CATALOG]
    system_prompt = "You recommend content angles for a short-form cut. Return strict JSON only."
    user_prompt = json.dumps(
        {
            "task": "Pick 1 to 3 content angles that fit this source.",
            "catalog": catalog,
            "title": title,
            "description": description[:600],
            "excerpt": excerpt[:1200],
            "required_json_shape": {"angles": [{"id": "opinion", "reason": "one sentence"}]},
        },
        ensure_ascii=False,
    )
    try:
        result = call_llm_json(provider, system_prompt, user_prompt, timeout_seconds=25)
    except (LLMError, ValueError, TypeError):
        return None
    raw = result.get("angles") if isinstance(result, dict) else None
    if not isinstance(raw, list):
        return None
    recommendations = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        angle_id = str(item.get("id") or "").strip().lower()
        if angle_id not in GENRE_OPTIONS:
            continue
        recommendations.append(
            {
                "id": angle_id,
                "label": GENRE_OPTIONS[angle_id]["label"],
                "reason": str(item.get("reason") or "").strip() or GENRE_OPTIONS[angle_id]["description"],
            }
        )
        if len(recommendations) >= 3:
            break
    return recommendations or None


def _jev_angles(title: str, description: str, excerpt: str) -> list[dict[str, str]] | None:
    if not jev_available():
        return None
    state = json.dumps({"title": title, "description": description[:600], "excerpt": excerpt[:1200]}, ensure_ascii=False)
    answers = jev_decide(
        state,
        {
            "angle": {
                "type": "choice",
                "options": list(UNIVERSAL_CATALOG),
                "instructions": "Best content angle id for cutting this source into a short.",
            }
        },
    )
    if not isinstance(answers, dict):
        return None
    angle_id = answer_choice(answers.get("angle")).lower()
    if angle_id not in GENRE_OPTIONS:
        return None
    return [
        {
            "id": angle_id,
            "label": GENRE_OPTIONS[angle_id]["label"],
            "reason": f"Jev memilih {GENRE_OPTIONS[angle_id]['label']} untuk sumber ini.",
        }
    ]


def recommend_content_angles(
    *,
    title: str = "",
    description: str = "",
    excerpt: str = "",
    provider: str = "",
) -> dict[str, Any]:
    resolved = _available_provider(provider)
    source = "heuristic"
    angles = _jev_angles(title, description, excerpt)
    if angles:
        source = "jev"
    elif resolved != "none":
        angles = _llm_angles(title, description, excerpt, resolved)
        if angles:
            source = f"llm_{resolved}"
    if not angles:
        angles = _heuristic_angles(title, description, excerpt)
        source = "heuristic"
    return {"angles": angles, "source": source}
