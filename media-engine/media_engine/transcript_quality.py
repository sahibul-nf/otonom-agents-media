"""Transcript cleanup with workspace/niche-aware glossaries."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Iterable

from .genres import resolve_genre_pack

_PROFILES_DIR = Path(__file__).resolve().parents[1] / "profiles"

DEVOTIONAL_GLOSSARY = {
    "alloh": "Allah",
    "aloh": "Allah",
    "allahh": "Allah",
    "dzikir": "dzikir",
    "zikir": "zikir",
    "dikir": "dzikir",
    "jikir": "dzikir",
    "qalbu": "qalbu",
    "kalbu": "qalbu",
    "qolbu": "qalbu",
    "sholawat": "sholawat",
    "salawat": "sholawat",
    "ma'rifat": "ma'rifat",
    "makrifat": "ma'rifat",
    "marifat": "ma'rifat",
    "istighfar": "istighfar",
    "istigfar": "istighfar",
    "rasulullah": "Rasulullah",
    "rosulullah": "Rasulullah",
    "subhanallah": "subhanallah",
    "alhamdulillah": "alhamdulillah",
    "bismillah": "bismillah",
    "insyaallah": "insya Allah",
    "inshaallah": "insya Allah",
}

TECH_FINANCE_GLOSSARY = {
    "bitkon": "Bitcoin",
    "bitcoinn": "Bitcoin",
    "etherium": "Ethereum",
    "ethereun": "Ethereum",
    "nvidia": "Nvidia",
    "nvda": "NVDA",
    "saas": "SaaS",
    "open ai": "OpenAI",
    "openai": "OpenAI",
    "chat gpt": "ChatGPT",
    "chatgpt": "ChatGPT",
    "fomc": "FOMC",
    "gdp": "GDP",
    "cpi": "CPI",
    "ipo": "IPO",
    "etf": "ETF",
    "fed": "Fed",
    "ai": "AI",
}

GENERAL_GLOSSARY: dict[str, str] = {}

PACK_GLOSSARIES: dict[str, dict[str, str]] = {
    "devotional": DEVOTIONAL_GLOSSARY,
    "tech_finance": TECH_FINANCE_GLOSSARY,
    "general": GENERAL_GLOSSARY,
}

# Backward-compatible alias used by older imports/tests.
NOURBIT_GLOSSARY = DEVOTIONAL_GLOSSARY
PROTECTED_TERMS = set(DEVOTIONAL_GLOSSARY.values()) | set(TECH_FINANCE_GLOSSARY.values())


def resolve_glossary(
    profile_id: str = "",
    niche: str = "",
    profile: dict[str, Any] | None = None,
) -> dict[str, str]:
    pack = resolve_genre_pack(profile_id, niche)
    glossary = dict(PACK_GLOSSARIES.get(pack, GENERAL_GLOSSARY))
    glossary.update(_custom_glossary(profile_id, profile))
    return glossary


def _custom_glossary(profile_id: str, profile: dict[str, Any] | None) -> dict[str, str]:
    custom: dict[str, str] = {}
    for source in (profile, _profile_json(profile_id)):
        if not isinstance(source, dict):
            continue
        raw = source.get("caption_glossary") or source.get("glossary")
        if isinstance(raw, dict):
            custom.update({str(key).strip().lower(): str(value).strip() for key, value in raw.items() if str(key).strip() and str(value).strip()})
    return custom


def _profile_json(profile_id: str) -> dict[str, Any] | None:
    slug = (profile_id or "").strip()
    if not slug:
        return None
    path = _PROFILES_DIR / f"{slug}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def correct_text_with_glossary(text: str, glossary: dict[str, str] | None = None) -> str:
    glossary = glossary or resolve_glossary()

    def replace_word(match: re.Match[str]) -> str:
        token = match.group(0)
        return glossary.get(token.lower(), token)

    return re.sub(r"[A-Za-z][A-Za-z'’`-]*", replace_word, text)


def correct_word_text(text: str, glossary: dict[str, str] | None = None, fuzzy: bool = True) -> tuple[str, bool]:
    glossary = glossary or resolve_glossary()
    stripped = text.strip()
    prefix = stripped[: len(stripped) - len(stripped.lstrip(".,!?;:()[]{}\"'“”‘’"))]
    suffix = stripped[len(stripped.rstrip(".,!?;:()[]{}\"'“”‘’")) :]
    core = stripped[len(prefix) : len(stripped) - len(suffix) if suffix else len(stripped)]
    if not core:
        return text, False
    lowered = core.lower()
    if lowered in glossary:
        corrected = glossary[lowered]
        return f"{prefix}{corrected}{suffix}", corrected != core
    if fuzzy and len(core) >= 5 and glossary:
        matches = get_close_matches(lowered, glossary.keys(), n=1, cutoff=0.84)
        if matches:
            corrected = glossary[matches[0]]
            return f"{prefix}{corrected}{suffix}", corrected != core
    return text, False


def correct_asr_words(words: list[dict], glossary: dict[str, str] | None = None) -> tuple[list[dict], dict]:
    glossary = glossary or resolve_glossary()
    corrected_words = []
    corrections = []
    low_confidence = 0
    for index, word in enumerate(words):
        original = str(word.get("text", ""))
        corrected, changed = correct_word_text(original, glossary)
        confidence = word.get("confidence")
        if isinstance(confidence, (int, float)) and confidence < 0.65:
            low_confidence += 1
        item = {**word, "text": corrected}
        corrected_words.append(item)
        if changed:
            corrections.append({"index": index, "from": original, "to": corrected})
    return corrected_words, {
        "correction_engine": "glossary_pack_v2",
        "correction_count": len(corrections),
        "corrections": corrections[:80],
        "low_confidence_word_count": low_confidence,
        "glossary_size": len(glossary),
    }


def correct_transcript_entries(entries: Iterable, glossary: dict[str, str] | None = None) -> list:
    glossary = glossary or resolve_glossary()
    corrected = []
    for entry in entries:
        text = correct_text_with_glossary(entry.text, glossary)
        corrected.append(replace(entry, text=text))
    return corrected
