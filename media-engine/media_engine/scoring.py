"""Deterministic clip quality scoring for review ranking."""

from __future__ import annotations

import re
from typing import Any

from .genres import resolve_genre_pack


HOOK_WORDS = frozenset({"kenapa", "rahasia", "jangan", "ternyata", "pernahkah", "inilah", "hati"})

DEVOTIONAL_INTENT_WORDS = frozenset(
    {
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
        "quran",
        "doa",
        "iman",
    }
)

TECH_FINANCE_INTENT_WORDS = frozenset(
    {
        "ai",
        "startup",
        "investor",
        "market",
        "bitcoin",
        "saas",
        "profit",
        "bisnis",
        "teknologi",
        "uang",
        "saham",
        "crypto",
        "unicorn",
        "founder",
        "revenue",
        "margin",
        "inflasi",
        "fed",
        "ipo",
        "valuation",
        "automation",
    }
)

GENERAL_INTENT_WORDS = frozenset(
    {
        "rahasia",
        "tips",
        "fakta",
        "cerita",
        "pelajaran",
        "kesalahan",
        "strategi",
        "cara",
        "alasan",
        "bukti",
        "masalah",
        "solusi",
    }
)

TECH_FINANCE_HOOK_WORDS = frozenset({"fakta", "bukti", "bahaya", "boom", "crash", "profit", "rugi"})
DEVOTIONAL_HOOK_WORDS = frozenset({"hati", "allah", "tenang", "doa"})

SCORING_PACKS: dict[str, dict[str, frozenset[str]]] = {
    "devotional": {
        "intent_words": DEVOTIONAL_INTENT_WORDS,
        "hook_words": HOOK_WORDS | DEVOTIONAL_HOOK_WORDS,
    },
    "tech_finance": {
        "intent_words": TECH_FINANCE_INTENT_WORDS,
        "hook_words": HOOK_WORDS | TECH_FINANCE_HOOK_WORDS,
    },
    "general": {
        "intent_words": GENERAL_INTENT_WORDS,
        "hook_words": HOOK_WORDS,
    },
}

HYGIENE_GATE_PASS = "pass"
HYGIENE_GATE_NEEDS_ATTENTION = "needs_attention"
HYGIENE_GATE_HOLD = "hold"
HYGIENE_GATE_STATUSES = {HYGIENE_GATE_PASS, HYGIENE_GATE_NEEDS_ATTENTION, HYGIENE_GATE_HOLD}

HYGIENE_FLAG_CAPTION_NOISE = "caption_noise"
HYGIENE_FLAG_ABRUPT_BOUNDARY = "abrupt_boundary"
HYGIENE_FLAG_COPYRIGHT_RISK = "copyright_risk"

HYGIENE_CAPTION_HOLD = 55
HYGIENE_CAPTION_ATTENTION = 75
HYGIENE_BOUNDARY_ATTENTION = 70
HYGIENE_BOUNDARY_HOLD = 50

IDEAL_WPM_MIN = 110
IDEAL_WPM_TARGET = 150
IDEAL_WPM_MAX = 180

# Backward-compatible alias used in older tests and docs.
NOURBIT_INTENT_WORDS = DEVOTIONAL_INTENT_WORDS


def resolve_scoring_pack(
    profile_id: str | None = None,
    niche: str | None = None,
    pack_id: str | None = None,
) -> str:
    if pack_id in SCORING_PACKS:
        return pack_id
    resolved = resolve_genre_pack(profile_id, niche)
    return resolved if resolved in SCORING_PACKS else "general"


def scoring_pack_keywords(pack_id: str) -> tuple[frozenset[str], frozenset[str]]:
    pack = SCORING_PACKS.get(pack_id, SCORING_PACKS["general"])
    return pack["intent_words"], pack["hook_words"]


def clamp_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text, re.UNICODE))


def _duration_bonus(
    duration_ms: int,
    ideal_min_ms: int,
    ideal_target_ms: int,
    ideal_max_ms: int,
) -> float:
    if duration_ms < ideal_min_ms:
        return 4 - min(20, (ideal_min_ms - duration_ms) / 1000)
    if duration_ms > ideal_max_ms:
        return 4 - min(20, (duration_ms - ideal_max_ms) / 1000)
    span = max(1, max(ideal_target_ms - ideal_min_ms, ideal_max_ms - ideal_target_ms))
    distance = abs(duration_ms - ideal_target_ms)
    return 28 - min(18, (distance / span) * 18)


def _pacing_bonus(words: int, duration_ms: int, opening_strength: int) -> float:
    minutes = max(duration_ms / 60_000, 0.1)
    wpm = words / minutes
    if wpm < IDEAL_WPM_MIN:
        wpm_bonus = 8 - min(16, (IDEAL_WPM_MIN - wpm) / 4)
    elif wpm > IDEAL_WPM_MAX:
        wpm_bonus = 8 - min(16, (wpm - IDEAL_WPM_MAX) / 5)
    else:
        wpm_distance = abs(wpm - IDEAL_WPM_TARGET)
        wpm_span = max(1, IDEAL_WPM_TARGET - IDEAL_WPM_MIN)
        wpm_bonus = 18 - min(14, (wpm_distance / wpm_span) * 14)
    opening_bonus = (clamp_score(opening_strength) - 50) * 0.24
    return wpm_bonus + opening_bonus


def _caption_confidence_score(text: str) -> int:
    lowered = text.lower()
    return clamp_score(82 - min(24, lowered.count("[music]") * 8 + lowered.count("...") * 3))


def evaluate_hygiene_gate(
    *,
    caption_confidence: int,
    boundary_confidence: int,
    rights_risk: bool = True,
    catastrophic_caption: bool = False,
    explicit_copyright_risk: bool = False,
) -> dict[str, Any]:
    flags: list[str] = []
    if explicit_copyright_risk:
        flags.append(HYGIENE_FLAG_COPYRIGHT_RISK)
    if catastrophic_caption or caption_confidence < HYGIENE_CAPTION_HOLD:
        flags.append(HYGIENE_FLAG_CAPTION_NOISE)
    elif caption_confidence < HYGIENE_CAPTION_ATTENTION:
        flags.append(HYGIENE_FLAG_CAPTION_NOISE)
    if boundary_confidence < HYGIENE_BOUNDARY_HOLD:
        flags.append(HYGIENE_FLAG_ABRUPT_BOUNDARY)
    elif boundary_confidence < HYGIENE_BOUNDARY_ATTENTION:
        flags.append(HYGIENE_FLAG_ABRUPT_BOUNDARY)

    if catastrophic_caption or caption_confidence < HYGIENE_CAPTION_HOLD or explicit_copyright_risk:
        gate_status = HYGIENE_GATE_HOLD
    elif flags:
        gate_status = HYGIENE_GATE_NEEDS_ATTENTION
    else:
        gate_status = HYGIENE_GATE_PASS

    return {
        "gate_status": gate_status,
        "flags": flags,
        "caption_confidence": caption_confidence,
        "boundary_confidence": boundary_confidence,
        "rights_risk": rights_risk,
    }


def score_candidate_text(
    text: str,
    title_hook: str,
    duration_ms: int,
    rights_risk: bool = True,
    ideal_min_ms: int = 45_000,
    ideal_target_ms: int | None = None,
    ideal_max_ms: int = 120_000,
    boundary_confidence: int = 75,
    opening_strength: int = 70,
    profile_id: str | None = None,
    workspace_id: str | None = None,
    niche: str | None = None,
    pack_id: str | None = None,
    catastrophic_caption: bool = False,
) -> dict[str, int | str | list[str]]:
    pack = resolve_scoring_pack(workspace_id or profile_id, niche, pack_id)
    intent_words, hook_words = scoring_pack_keywords(pack)
    lowered = text.lower()
    title_lowered = title_hook.lower()
    words = max(1, word_count(text))
    keyword_hits = sum(lowered.count(word) for word in intent_words)
    hook_hits = sum(1 for word in hook_words if word in title_lowered)
    ideal_target_ms = ideal_target_ms or int((ideal_min_ms + ideal_max_ms) / 2)

    hook_score = clamp_score(45 + hook_hits * 12 + (10 if 4 <= word_count(title_hook) <= 8 else 0) + (8 if "?" in title_hook else 0))
    resonance_score = clamp_score(42 + min(30, keyword_hits * 4) + min(18, words / 18))
    context_score = clamp_score(50 + min(30, words / 14) + (10 if any(mark in text for mark in ".?!") else 0))
    duration_bonus = _duration_bonus(duration_ms, ideal_min_ms, ideal_target_ms, ideal_max_ms)
    pacing_bonus = _pacing_bonus(words, duration_ms, opening_strength)
    pacing_score = clamp_score(45 + duration_bonus + pacing_bonus + min(12, keyword_hits))
    retention_score = clamp_score((pacing_score * 0.62) + (resonance_score * 0.38))
    caption_confidence = _caption_confidence_score(text)
    rights_risk_score = 35 if rights_risk else 90
    hygiene = evaluate_hygiene_gate(
        caption_confidence=caption_confidence,
        boundary_confidence=clamp_score(boundary_confidence),
        rights_risk=rights_risk,
        catastrophic_caption=catastrophic_caption,
    )
    performance_score = clamp_score(
        hook_score * 0.35
        + pacing_score * 0.30
        + resonance_score * 0.20
        + context_score * 0.15
    )
    viral_score = resonance_score
    return {
        "scoring_pack": pack,
        "hook_score": hook_score,
        "pacing_score": pacing_score,
        "resonance_score": resonance_score,
        "context_score": context_score,
        "retention_score": retention_score,
        "viral_score": viral_score,
        "caption_confidence": caption_confidence,
        "rights_risk_score": rights_risk_score,
        "performance_score": performance_score,
        "overall_score": performance_score,
        "hygiene_gate": hygiene["gate_status"],
        "hygiene_flags": hygiene["flags"],
    }


def score_candidate(
    candidate: dict[str, Any],
    rights_risk: bool = True,
    profile_id: str | None = None,
    workspace_id: str | None = None,
    niche: str | None = None,
) -> dict[str, int | str | list[str]]:
    resolved_workspace = workspace_id or profile_id or str(candidate.get("profile_id") or "")
    resolved_niche = niche or str(candidate.get("niche") or "")
    curation = candidate.get("curation_metadata") if isinstance(candidate.get("curation_metadata"), dict) else {}
    return score_candidate_text(
        str(candidate.get("transcript_span", "")),
        str(candidate.get("title_hook", "")),
        int(candidate["end_ms"]) - int(candidate["start_ms"]),
        rights_risk=rights_risk,
        boundary_confidence=int(curation.get("boundary_confidence") or 75),
        opening_strength=int(curation.get("opening_strength") or 70),
        workspace_id=resolved_workspace or None,
        niche=resolved_niche or None,
    )
