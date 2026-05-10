"""Transcript cleanup for Nourbit-style Indonesian and Arabic terms."""

from __future__ import annotations

import re
from dataclasses import replace
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


def correct_text_with_glossary(text: str, glossary: dict[str, str] | None = None) -> str:
    glossary = glossary or NOURBIT_GLOSSARY

    def replace_word(match: re.Match[str]) -> str:
        token = match.group(0)
        return glossary.get(token.lower(), token)

    return re.sub(r"[A-Za-z][A-Za-z'’`-]*", replace_word, text)


def correct_transcript_entries(entries: Iterable, glossary: dict[str, str] | None = None) -> list:
    corrected = []
    for entry in entries:
        text = correct_text_with_glossary(entry.text, glossary)
        corrected.append(replace(entry, text=text))
    return corrected
