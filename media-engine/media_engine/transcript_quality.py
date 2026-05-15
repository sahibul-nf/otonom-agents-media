"""Transcript cleanup for Nourbit-style Indonesian and Arabic terms."""

from __future__ import annotations

import re
from dataclasses import replace
from difflib import get_close_matches
from typing import Iterable


NOURBIT_GLOSSARY = {
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

PROTECTED_TERMS = set(NOURBIT_GLOSSARY.values())


def correct_text_with_glossary(text: str, glossary: dict[str, str] | None = None) -> str:
    glossary = glossary or NOURBIT_GLOSSARY

    def replace_word(match: re.Match[str]) -> str:
        token = match.group(0)
        return glossary.get(token.lower(), token)

    return re.sub(r"[A-Za-z][A-Za-z'’`-]*", replace_word, text)


def correct_word_text(text: str, glossary: dict[str, str] | None = None, fuzzy: bool = True) -> tuple[str, bool]:
    glossary = glossary or NOURBIT_GLOSSARY
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
    if fuzzy and len(core) >= 5:
        matches = get_close_matches(lowered, glossary.keys(), n=1, cutoff=0.84)
        if matches:
            corrected = glossary[matches[0]]
            return f"{prefix}{corrected}{suffix}", corrected != core
    return text, False


def correct_asr_words(words: list[dict], glossary: dict[str, str] | None = None) -> tuple[list[dict], dict]:
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
        "correction_engine": "glossary_fuzzy_v1",
        "correction_count": len(corrections),
        "corrections": corrections[:80],
        "low_confidence_word_count": low_confidence,
    }


def correct_transcript_entries(entries: Iterable, glossary: dict[str, str] | None = None) -> list:
    corrected = []
    for entry in entries:
        text = correct_text_with_glossary(entry.text, glossary)
        corrected.append(replace(entry, text=text))
    return corrected
