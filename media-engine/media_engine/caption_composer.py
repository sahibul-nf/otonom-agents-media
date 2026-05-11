"""Editorial caption composition from word-level timestamps."""

from __future__ import annotations

from typing import Any

from .captions import normalize_word_timeline
from .transcript_quality import correct_text_with_glossary


KEYWORD_HIGHLIGHTS = {"allah", "hati", "dzikir", "zikir", "tenang", "taubat", "syukur", "rasulullah"}
FILLERS = {"eee", "ee", "em", "emm", "anu"}


def clean_caption_word(word: dict[str, Any], remove_fillers: bool = True) -> dict[str, Any] | None:
    text = correct_text_with_glossary(str(word.get("text", "")).strip())
    if not text:
        return None
    normalized = "".join(ch for ch in text.lower() if ch.isalnum())
    if remove_fillers and normalized in FILLERS:
        return None
    return {**word, "text": text}


def compose_caption_groups(
    words: list[dict[str, Any]],
    max_words_per_caption: int = 3,
    max_gap_ms: int = 520,
    max_duration_ms: int = 2200,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    clean_words = [clean_caption_word(word) for word in normalize_word_timeline(words)]
    clean_words = [word for word in clean_words if word is not None]
    groups: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []

    for word in clean_words:
        gap = word["startMs"] - current[-1]["endMs"] if current else 0
        duration = word["endMs"] - current[0]["startMs"] if current else 0
        should_flush = bool(current) and (
            len(current) >= max_words_per_caption or gap > max_gap_ms or duration > max_duration_ms
        )
        if should_flush:
            groups.append(build_caption_group(current))
            current = []
        current.append(word)
    if current:
        groups.append(build_caption_group(current))

    for index, group in enumerate(groups[:-1]):
        group["endMs"] = min(group["endMs"], groups[index + 1]["startMs"])

    total_word_ms = sum(max(0, word["endMs"] - word["startMs"]) for word in clean_words)
    covered_ms = sum(max(0, group["endMs"] - group["startMs"]) for group in groups)
    confidence_values = [word.get("confidence") for word in clean_words if isinstance(word.get("confidence"), (int, float))]
    avg_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else None
    metadata = {
        "engine": "caption_composer_v1",
        "word_count": len(clean_words),
        "caption_count": len(groups),
        "coverage_ratio": round(covered_ms / total_word_ms, 3) if total_word_ms else 0,
        "avg_word_confidence": round(avg_confidence, 3) if avg_confidence is not None else None,
    }
    return groups, metadata


def build_caption_group(words: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "text": " ".join(word["text"] for word in words),
        "startMs": words[0]["startMs"],
        "endMs": words[-1]["endMs"],
        "timestampMs": words[0]["startMs"],
        "confidence": average_confidence(words),
        "words": [
            {
                **word,
                "highlight": "".join(ch for ch in word["text"].lower() if ch.isalnum()) in KEYWORD_HIGHLIGHTS,
            }
            for word in words
        ],
    }


def average_confidence(words: list[dict[str, Any]]) -> float | None:
    values = [word.get("confidence") for word in words if isinstance(word.get("confidence"), (int, float))]
    return round(sum(values) / len(values), 3) if values else None
