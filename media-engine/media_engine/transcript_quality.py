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
    "balasya": "bala syahidna",
    "hadrah": "hadrah",
    "rububiyah": "rububiyah",
    "mentakbir": "mentadbir",
    "marbu": "al-marbub",
    "makrifatullah": "makrifatullah",
    "kerenanya": "karenanya",
}

DEVOTIONAL_PHRASE_GLOSSARY = {
    "mentakbir kena cinta": "mentadbir karena cinta",
    "mentadbir kena cinta": "mentadbir karena cinta",
    "alastu bi rabbikum": "alastu bi rabbikum",
    "alastu bi rabikum": "alastu bi rabbikum",
    "bala syahidna": "bala syahidna",
    "bala syahidnaa": "bala syahidna",
    "hadrah rububiyah": "hadrah rububiyah",
    "hadrat rububiyah": "hadrah rububiyah",
    "al marbu": "al-marbub",
    "al marbub": "al-marbub",
    "nur muhammad": "nur Muhammad",
    "makrifatullah": "makrifatullah",
    "oleh kerenanya": "oleh karenanya",
    "bukan ke aku ini": "bukankah Aku ini",
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

TECH_FINANCE_PHRASE_GLOSSARY = {
    "burn rate": "burn rate",
    "burnrate": "burn rate",
    "product market fit": "product-market fit",
    "product-market fit": "product-market fit",
    "run way": "runway",
    "valu ation": "valuation",
    "venture capital": "venture capital",
    "open ai": "OpenAI",
    "chat gpt": "ChatGPT",
}

GENERAL_GLOSSARY: dict[str, str] = {}

PACK_GLOSSARIES: dict[str, dict[str, str]] = {
    "devotional": DEVOTIONAL_GLOSSARY,
    "tech_finance": TECH_FINANCE_GLOSSARY,
    "general": GENERAL_GLOSSARY,
}

PACK_PHRASE_GLOSSARIES: dict[str, dict[str, str]] = {
    "devotional": DEVOTIONAL_PHRASE_GLOSSARY,
    "tech_finance": TECH_FINANCE_PHRASE_GLOSSARY,
    "general": {},
}

_DOMAIN_VOCABULARY_HINTS: dict[str, str] = {
    "devotional": (
        "Allah, Rasulullah, dzikir, qalbu, sholawat, istighfar, ma'rifat, taubat, syukur, "
        "alastu bi rabbikum, bala syahidna, hadrah rububiyah, al-marbub, mentadbir, makrifatullah, nur Muhammad"
    ),
    "tech_finance": (
        "Bitcoin, Ethereum, SaaS, OpenAI, ChatGPT, Nvidia, burn rate, product-market fit, "
        "runway, valuation, venture capital, FOMC, GDP, CPI, IPO, ETF"
    ),
    "general": "Indonesian and English mixed speech, names, numbers, technical terms",
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


def resolve_phrase_glossary(
    profile_id: str = "",
    niche: str = "",
    profile: dict[str, Any] | None = None,
) -> dict[str, str]:
    pack = resolve_genre_pack(profile_id, niche)
    phrases = dict(PACK_PHRASE_GLOSSARIES.get(pack, {}))
    custom = _custom_glossary(profile_id, profile)
    for key, value in custom.items():
        if " " in key:
            phrases[key] = value
    return phrases


def domain_vocabulary_hint(profile_id: str = "", niche: str = "") -> str:
    pack = resolve_genre_pack(profile_id, niche)
    return _DOMAIN_VOCABULARY_HINTS.get(pack, _DOMAIN_VOCABULARY_HINTS["general"])


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


def _normalize_phrase_key(text: str) -> str:
    return " ".join(part.lower() for part in re.split(r"\s+", text.strip()) if part)


def _phrase_patterns(phrase_glossary: dict[str, str]) -> list[tuple[str, str, int]]:
    patterns: list[tuple[str, str, int]] = []
    for wrong, correct in phrase_glossary.items():
        tokens = [token for token in _normalize_phrase_key(wrong).split() if token]
        if len(tokens) < 2:
            continue
        patterns.append((wrong, correct, len(tokens)))
    patterns.sort(key=lambda item: item[2], reverse=True)
    return patterns


def apply_phrase_glossary(words: list[dict], phrase_glossary: dict[str, str] | None = None) -> tuple[list[dict], list[dict]]:
    phrase_glossary = phrase_glossary or {}
    if not words or not phrase_glossary:
        return list(words), []
    patterns = _phrase_patterns(phrase_glossary)
    if not patterns:
        return list(words), []
    corrected_words = [dict(word) for word in words]
    corrections: list[dict[str, Any]] = []
    index = 0
    while index < len(corrected_words):
        matched = False
        for wrong, correct, size in patterns:
            if index + size > len(corrected_words):
                continue
            window = " ".join(str(corrected_words[index + offset].get("text", "")).strip() for offset in range(size))
            if _normalize_phrase_key(window) != _normalize_phrase_key(wrong):
                continue
            replacement_tokens = correct.split()
            if len(replacement_tokens) == size:
                for offset, token in enumerate(replacement_tokens):
                    corrected_words[index + offset]["text"] = token
            else:
                start_ms = int(corrected_words[index].get("startMs") or 0)
                end_ms = int(corrected_words[index + size - 1].get("endMs") or start_ms + 40)
                chunk = corrected_words[index : index + size]
                replacement_words = _split_phrase_timing(chunk, replacement_tokens, start_ms, end_ms)
                corrected_words[index : index + size] = replacement_words
            corrections.append({"index": index, "from": window, "to": correct})
            index += len(replacement_tokens) if len(replacement_tokens) != size else size
            matched = True
            break
        if not matched:
            index += 1
    return corrected_words, corrections


def _split_phrase_timing(
    original_chunk: list[dict],
    replacement_tokens: list[str],
    start_ms: int,
    end_ms: int,
) -> list[dict]:
    if not replacement_tokens:
        return []
    duration = max(40, end_ms - start_ms)
    step = max(40, duration // len(replacement_tokens))
    base = dict(original_chunk[0]) if original_chunk else {"startMs": start_ms, "endMs": end_ms}
    replacement_words: list[dict] = []
    for offset, token in enumerate(replacement_tokens):
        word_start = start_ms + offset * step
        word_end = end_ms if offset == len(replacement_tokens) - 1 else min(end_ms, word_start + step)
        replacement_words.append({**base, "text": token, "startMs": word_start, "endMs": max(word_start + 40, word_end)})
    return replacement_words


def correct_asr_words(words: list[dict], glossary: dict[str, str] | None = None, phrase_glossary: dict[str, str] | None = None) -> tuple[list[dict], dict]:
    glossary = glossary or resolve_glossary()
    phrase_corrected, phrase_corrections = apply_phrase_glossary(words, phrase_glossary)
    corrected_words = []
    corrections = list(phrase_corrections)
    low_confidence = 0
    for index, word in enumerate(phrase_corrected):
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
        "correction_engine": "glossary_pack_v3",
        "correction_count": len(corrections),
        "corrections": corrections[:80],
        "phrase_correction_count": len(phrase_corrections),
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
