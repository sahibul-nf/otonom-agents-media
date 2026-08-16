"""Speech-language detection and YouTube transcript preference helpers."""

from __future__ import annotations

from typing import Any

from .genres import resolve_genre_pack

SUPPORTED_SPEECH_LANGUAGES = frozenset({"id", "en", "ar", "ms", "auto"})
AUTO_LANGUAGE = "auto"

_DEVOTIONAL_TRANSCRIPT_LANGS = ("id", "ms", "ar", "en")
_TECH_FINANCE_TRANSCRIPT_LANGS = ("id", "en")
_GENERAL_TRANSCRIPT_LANGS = ("id", "en")


def normalize_speech_language(value: Any, default: str = AUTO_LANGUAGE) -> str:
    text = str(value or default).strip().lower()
    return text if text in SUPPORTED_SPEECH_LANGUAGES else default


def is_auto_language(value: str | None) -> bool:
    return normalize_speech_language(value or AUTO_LANGUAGE) == AUTO_LANGUAGE


def whisper_language_arg(speech_language: str | None) -> str | None:
    """Return faster-whisper language code, or None to auto-detect from audio."""
    if is_auto_language(speech_language):
        return None
    return normalize_speech_language(speech_language)


def asr_cache_language_tag(speech_language: str | None) -> str:
    return AUTO_LANGUAGE if is_auto_language(speech_language) else normalize_speech_language(speech_language)


def niche_transcript_fallbacks(niche: str = "", profile_id: str = "") -> tuple[str, ...]:
    pack = resolve_genre_pack(profile_id, niche)
    if pack == "devotional":
        return _DEVOTIONAL_TRANSCRIPT_LANGS
    if pack == "tech_finance":
        return _TECH_FINANCE_TRANSCRIPT_LANGS
    return _GENERAL_TRANSCRIPT_LANGS


def parse_transcript_language_input(value: str | list[str] | None) -> list[str]:
    if isinstance(value, list):
        parts = [str(item).strip().lower() for item in value if str(item).strip()]
    else:
        parts = [part.strip().lower() for part in str(value or "").split(",") if part.strip()]
    return [part for part in parts if part in SUPPORTED_SPEECH_LANGUAGES and part != AUTO_LANGUAGE]


def build_transcript_language_list(
    detected_language: str | None,
    *,
    niche: str = "",
    profile_id: str = "",
    explicit: str | list[str] | None = None,
) -> list[str]:
    """Order YouTube caption fetch attempts: detected audio first, then niche fallbacks."""
    if isinstance(explicit, list):
        explicit_list = parse_transcript_language_input(explicit)
        if explicit_list:
            return _dedupe_languages(explicit_list)
    elif explicit is not None:
        text = str(explicit).strip().lower()
        if text and text != AUTO_LANGUAGE:
            explicit_list = parse_transcript_language_input(text)
            if explicit_list:
                return _dedupe_languages(explicit_list)

    ordered: list[str] = []
    if detected_language:
        ordered.append(detected_language)
    for code in niche_transcript_fallbacks(niche, profile_id):
        ordered.append(code)
    return _dedupe_languages(ordered) or ["id", "en"]


def _dedupe_languages(codes: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for code in codes:
        normalized = code.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered
