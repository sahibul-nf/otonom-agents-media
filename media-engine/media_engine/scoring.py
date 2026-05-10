"""Deterministic clip quality scoring for review ranking."""

from __future__ import annotations

import re
from typing import Any


HOOK_WORDS = {"kenapa", "rahasia", "jangan", "ternyata", "pernahkah", "inilah", "hati"}
NOURBIT_INTENT_WORDS = {
    "allah",
    "hati",
    "dzikir",
    "zikir",
    "ibadah",
    "taubat",
    "syukur",
    "akhirat",
    "dunia",
    "tenang",
    "kesepian",
    "rasulullah",
}


def clamp_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text, re.UNICODE))


def score_candidate_text(text: str, title_hook: str, duration_ms: int, rights_risk: bool = True) -> dict[str, int]:
    lowered = text.lower()
    title_lowered = title_hook.lower()
    words = max(1, word_count(text))
    keyword_hits = sum(lowered.count(word) for word in NOURBIT_INTENT_WORDS)
    hook_hits = sum(1 for word in HOOK_WORDS if word in title_lowered)
    duration_seconds = duration_ms / 1000

    viral_score = clamp_score(42 + min(30, keyword_hits * 4) + min(18, words / 18) + (10 if "?" in title_hook else 0))
    hook_score = clamp_score(45 + hook_hits * 12 + (10 if 4 <= word_count(title_hook) <= 8 else 0))
    context_score = clamp_score(50 + min(30, words / 14) + (10 if any(mark in text for mark in ".?!") else 0))
    retention_score = clamp_score(45 + (25 if 45 <= duration_seconds <= 120 else 5) + min(20, keyword_hits * 2))
    caption_confidence = clamp_score(82 - min(24, lowered.count("[music]") * 8 + lowered.count("...") * 3))
    rights_risk_score = 35 if rights_risk else 90
    overall_score = clamp_score(
        viral_score * 0.26
        + hook_score * 0.2
        + context_score * 0.18
        + retention_score * 0.18
        + caption_confidence * 0.12
        + rights_risk_score * 0.06
    )
    return {
        "viral_score": viral_score,
        "hook_score": hook_score,
        "context_score": context_score,
        "retention_score": retention_score,
        "caption_confidence": caption_confidence,
        "rights_risk_score": rights_risk_score,
        "overall_score": overall_score,
    }


def score_candidate(candidate: dict[str, Any], rights_risk: bool = True) -> dict[str, int]:
    return score_candidate_text(
        str(candidate.get("transcript_span", "")),
        str(candidate.get("title_hook", "")),
        int(candidate["end_ms"]) - int(candidate["start_ms"]),
        rights_risk=rights_risk,
    )
