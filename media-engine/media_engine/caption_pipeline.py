"""Production captions: Whisper timing + YouTube text + light LLM polish."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from .asr import asr_cache_path, load_or_create_asr_words
from .caption_composer import compose_caption_groups
from .captions import split_words
from .llm import LLMError, call_llm_json
from .speech_language import AUTO_LANGUAGE, build_transcript_language_list
from .transcript_quality import correct_asr_words
from .youtube_pipeline import TranscriptEntry, fetch_youtube_transcript

UNCERTAIN_THRESHOLD = 0.65
CONFIRMED_CONFIDENCE = 0.92
MAX_LLM_TARGETS = 40
LLM_TOKEN_MAX_WORDS = 3

POLISH_SYSTEM = (
    "You fix Indonesian/Arabic ASR captions. Reply JSON only: "
    '{"replacements":[{"index":0,"text":"word"}]}. '
    "Change only uncertain tokens that are clearly wrong. Keep meaning. "
    "Each text is 1-3 words. Do not invent clauses."
)


def asr_initial_prompt(
    candidate: dict[str, Any] | None = None,
    *,
    niche: str = "",
    source_title: str = "",
    source_channel: str = "",
) -> str:
    payload = candidate or {}
    metadata = payload.get("curation_metadata") if isinstance(payload.get("curation_metadata"), dict) else {}
    parts = [
        str(source_title or metadata.get("source_title") or "").strip(),
        str(source_channel or metadata.get("source_channel") or "").strip(),
        str(niche or "").strip(),
        str(payload.get("title_hook") or "").strip(),
        str(payload.get("transcript_span") or "").strip()[:160],
    ]
    hint = ". ".join(part for part in parts if part)
    return (hint or "Multilingual speech, names, numbers, technical terms").strip()[:400]


def apply_youtube_text(
    whisper_words: list[dict[str, Any]],
    entries: list[TranscriptEntry],
    clip_start_ms: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not whisper_words or not entries:
        return list(whisper_words), {"youtube_replaced": 0, "youtube_cues": len(entries)}
    replaced = 0
    next_words: list[dict[str, Any]] = []
    for word in whisper_words:
        abs_start = clip_start_ms + int(word.get("startMs") or 0)
        abs_end = clip_start_ms + int(word.get("endMs") or abs_start + 80)
        token = _youtube_token_at(entries, abs_start, abs_end)
        item = dict(word)
        if token and _should_take_youtube_token(word, token):
            original = str(word.get("text") or "").strip()
            if token.lower() != original.lower():
                item["text"] = token
                replaced += 1
            item["caption_text_source"] = "youtube"
            item = _mark_confirmed(item)
        next_words.append(item)
    return next_words, {"youtube_replaced": replaced, "youtube_cues": len(entries)}


def polish_uncertain_words(
    words: list[dict[str, Any]],
    provider: str,
    *,
    context: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if provider in {"", "none"} or not words:
        return list(words), {"llm_replacements": 0, "llm_skipped": True}
    targets = [
        index
        for index, word in enumerate(words)
        if isinstance(word.get("confidence"), (int, float)) and float(word["confidence"]) < UNCERTAIN_THRESHOLD
    ][:MAX_LLM_TARGETS]
    if not targets:
        return list(words), {"llm_replacements": 0}
    payload = {
        "context": context[:240],
        "uncertain": [
            {"index": index, "text": str(words[index].get("text") or ""), "window": _context_window(words, index)}
            for index in targets
        ],
    }
    try:
        result = call_llm_json(provider, POLISH_SYSTEM, str(payload), timeout_seconds=30)
    except (LLMError, TypeError, ValueError):
        return list(words), {"llm_replacements": 0, "llm_error": True}
    allowed = set(targets)
    replacements = result.get("replacements") if isinstance(result, dict) else []
    if not isinstance(replacements, list):
        return list(words), {"llm_replacements": 0, "llm_error": True}
    next_words = [dict(word) for word in words]
    applied = 0
    for item in replacements:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        if index not in allowed:
            continue
        text = _safe_token(item.get("text"))
        if not text or text.lower() == str(next_words[index].get("text") or "").strip().lower():
            continue
        next_words[index]["text"] = text
        next_words[index]["caption_text_source"] = "llm"
        next_words[index] = _mark_confirmed(next_words[index])
        applied += 1
    return next_words, {"llm_replacements": applied}


def build_production_captions(
    candidate: dict[str, Any],
    source_clip: str,
    *,
    caption_source: str,
    asr_model: str,
    speech_language: str = AUTO_LANGUAGE,
    style: dict[str, Any] | None = None,
    youtube_url: str = "",
    transcript_languages: str | list[str] | None = None,
    llm_provider: str = "none",
    niche: str = "",
    profile_id: str = "",
) -> dict[str, Any]:
    """Mutate candidate timed captions. Returns pipeline metadata."""
    if caption_source not in {"whisper", "hybrid"}:
        candidate["caption_source"] = caption_source
        return {"skipped": True, "caption_source": caption_source}

    asr_path = asr_cache_path(source_clip, asr_model, speech_language)
    prompt = asr_initial_prompt(candidate, niche=niche)
    words, asr_metadata = load_or_create_asr_words(
        source_clip,
        str(asr_path),
        model_name=asr_model,
        language=speech_language,
        initial_prompt=prompt,
    )
    detected_language = str(asr_metadata.get("detected_language") or asr_metadata.get("language") or "").strip() or None
    transcript_lang_list = build_transcript_language_list(
        detected_language,
        niche=niche,
        profile_id=profile_id,
        explicit=transcript_languages,
    )
    pipeline: dict[str, Any] = {
        "caption_source": caption_source,
        "asr_prompt": prompt,
        "speech_language": speech_language,
        "detected_language": detected_language,
        "transcript_languages": transcript_lang_list,
    }
    if caption_source == "hybrid":
        words, youtube_meta = _try_youtube_text(words, candidate, youtube_url, transcript_lang_list)
        pipeline["youtube"] = youtube_meta
    words, glossary_meta = correct_asr_words(words)
    words = _confirm_glossary_corrections(words, glossary_meta)
    words, llm_meta = polish_uncertain_words(
        words,
        llm_provider,
        context=asr_initial_prompt(candidate, niche=niche),
    )
    pipeline["glossary"] = {"correction_count": glossary_meta.get("correction_count", 0)}
    pipeline["llm"] = llm_meta
    style = style or {}
    captions, composer_metadata = compose_caption_groups(
        words,
        max_words_per_caption=int(style.get("caption", {}).get("max_words_per_caption", 3)),
    )
    low_confidence = _low_confidence_count(words)
    if not captions:
        return pipeline
    candidate["timed_captions"] = captions
    candidate["caption_source"] = caption_source
    candidate["asr_metadata"] = {
        **asr_metadata,
        **glossary_meta,
        "caption_pipeline": pipeline,
        "caption_composer": {**composer_metadata, "low_confidence_word_count": low_confidence},
    }
    candidate["caption_corrections"] = {**glossary_meta, "low_confidence_word_count": low_confidence, **pipeline}
    candidate["score"] = {
        **candidate.get("score", {}),
        "asr_confidence": int(round((composer_metadata.get("avg_word_confidence") or 0.82) * 100)),
        "caption_sync_score": 95 if composer_metadata.get("caption_count", 0) else 0,
    }
    return pipeline


def _try_youtube_text(
    words: list[dict[str, Any]],
    candidate: dict[str, Any],
    youtube_url: str,
    transcript_languages: str | list[str] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url = str(youtube_url or "").strip()
    if not url:
        return words, {"used": False, "reason": "no_url"}
    languages = _language_list(transcript_languages)
    try:
        entries = fetch_youtube_transcript(url, languages=languages)
    except Exception:  # noqa: BLE001 - missing captions must not fail generate
        return words, {"used": False, "reason": "fetch_failed"}
    clip_start = int(candidate.get("start_ms") or 0)
    next_words, meta = apply_youtube_text(words, entries, clip_start)
    meta["used"] = bool(meta.get("youtube_replaced") or meta.get("youtube_cues"))
    return next_words, meta


def _should_take_youtube_token(word: dict[str, Any], token: str) -> bool:
    original = str(word.get("text") or "").strip()
    if not original or token.lower() == original.lower():
        return True
    if _similar_token(original, token):
        return True
    confidence = word.get("confidence")
    return isinstance(confidence, (int, float)) and float(confidence) < UNCERTAIN_THRESHOLD


def _similar_token(left: str, right: str) -> bool:
    a, b = left.lower(), right.lower()
    if a in b or b in a:
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.72


def _youtube_token_at(entries: list[TranscriptEntry], abs_start: int, abs_end: int) -> str | None:
    mid = (abs_start + abs_end) / 2
    for entry in entries:
        if entry.end_ms <= abs_start or entry.start_ms >= abs_end:
            continue
        tokens = split_words(entry.text)
        if not tokens:
            continue
        duration = max(1, entry.end_ms - entry.start_ms)
        rel = (mid - entry.start_ms) / duration
        index = min(len(tokens) - 1, max(0, int(rel * len(tokens))))
        return tokens[index]
    return None


def _confirm_glossary_corrections(words: list[dict[str, Any]], glossary_meta: dict[str, Any]) -> list[dict[str, Any]]:
    changed = {int(item["index"]) for item in glossary_meta.get("corrections") or [] if isinstance(item, dict) and "index" in item}
    if not changed:
        return words
    return [_mark_confirmed(word) if index in changed else word for index, word in enumerate(words)]


def _mark_confirmed(word: dict[str, Any]) -> dict[str, Any]:
    confidence = word.get("confidence")
    next_confidence = CONFIRMED_CONFIDENCE
    if isinstance(confidence, (int, float)):
        next_confidence = max(float(confidence), CONFIRMED_CONFIDENCE)
    return {**word, "confidence": next_confidence}


def _low_confidence_count(words: list[dict[str, Any]]) -> int:
    return sum(
        1
        for word in words
        if isinstance(word.get("confidence"), (int, float)) and float(word["confidence"]) < UNCERTAIN_THRESHOLD
    )


def _context_window(words: list[dict[str, Any]], index: int, radius: int = 6) -> str:
    start = max(0, index - radius)
    end = min(len(words), index + radius + 1)
    return " ".join(str(word.get("text") or "") for word in words[start:end])


def _safe_token(value: Any) -> str:
    text = str(value or "").strip()
    tokens = split_words(text)
    if not tokens or len(tokens) > LLM_TOKEN_MAX_WORDS:
        return ""
    return " ".join(tokens)


def _language_list(value: str | list[str] | None) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value or "id,en").split(",") if part.strip()]
