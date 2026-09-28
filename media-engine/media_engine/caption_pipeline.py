"""Production captions: Whisper timing + YouTube text + contextual LLM reconstruction."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from .asr import asr_cache_path, load_or_create_asr_words
from .caption_composer import compose_caption_groups
from .caption_edits import merge_caption_corrections
from .captions import split_words
from .genres import resolve_genre_pack
from .llm import LLMError, call_llm_json
from .silence_trim import parse_keep_segments, probe_duration_ms, untrim_time_ms
from .speech_language import AUTO_LANGUAGE, build_transcript_language_list
from .transcript_quality import (
    correct_asr_words,
    domain_vocabulary_hint,
    resolve_glossary,
    resolve_phrase_glossary,
)
from .youtube_pipeline import TranscriptEntry, fetch_youtube_transcript

UNCERTAIN_THRESHOLD = 0.65
CONFIRMED_CONFIDENCE = 0.92
HIGH_CONFIDENCE_STRICT_RATIO = 0.85
MAX_LLM_TARGETS = 40
LLM_TOKEN_MAX_WORDS = 3
MAX_TOKEN_LENGTH_RATIO = 2.5

_POLISH_DOMAINS = {
    "devotional": "Indonesian and Arabic Islamic devotional speech",
    "tech_finance": "Indonesian and English tech, finance, and business speech",
    "general": "Indonesian and English mixed short-form speech",
}


def build_reconstruct_system_prompt(
    *,
    detected_language: str | None = None,
    niche: str = "",
    profile_id: str = "",
) -> str:
    pack = resolve_genre_pack(profile_id, niche)
    domain = _POLISH_DOMAINS.get(pack, _POLISH_DOMAINS["general"])
    language_hint = (detected_language or "auto-detected").strip() or "auto-detected"
    return (
        f"You clean {domain} ASR captions (spoken language: {language_hint}). Reply JSON only: "
        '{"text":"..."}. Fix spelling and niche terminology, remove repeated stutters/disfluencies, '
        "add natural punctuation and capitalization. Keep the speaker's words and word order. "
        "Do not replace spoken phrases with title, kicker, or synonym rewrites. "
        "Never insert names, titles, or glossary terms that are not already in raw_transcript. "
        "Ignore any vocabulary lists; they are not spoken text."
    )


def build_polish_system_prompt(
    *,
    detected_language: str | None = None,
    niche: str = "",
    profile_id: str = "",
) -> str:
    pack = resolve_genre_pack(profile_id, niche)
    domain = _POLISH_DOMAINS.get(pack, _POLISH_DOMAINS["general"])
    language_hint = (detected_language or "auto-detected").strip() or "auto-detected"
    return (
        f"You fix {domain} ASR captions (spoken language: {language_hint}). Reply JSON only: "
        '{"replacements":[{"index":0,"text":"word"}]}. '
        "Change only uncertain tokens that are clearly wrong. Keep meaning and timing words short. "
        "Each text is 1-3 words. Do not invent clauses."
    )


def asr_initial_prompt(
    candidate: dict[str, Any] | None = None,
    *,
    niche: str = "",
    source_title: str = "",
    source_channel: str = "",
    profile_id: str = "",
) -> str:
    payload = candidate or {}
    metadata = payload.get("curation_metadata") if isinstance(payload.get("curation_metadata"), dict) else {}
    parts = [
        str(source_title or metadata.get("source_title") or "").strip(),
        str(source_channel or metadata.get("source_channel") or "").strip(),
        str(niche or "").strip(),
        str(payload.get("title_hook") or "").strip(),
        str(payload.get("transcript_span") or "").strip()[:160],
        domain_vocabulary_hint(profile_id or str(payload.get("profile_id") or ""), niche),
    ]
    hint = ". ".join(part for part in parts if part)
    return (hint or "Multilingual speech, names, numbers, technical terms").strip()[:500]


def reconstruct_llm_context(
    candidate: dict[str, Any] | None = None,
    *,
    source_title: str = "",
) -> str:
    """Short clip hint for reconstruct — no domain vocabulary dump (that leaks into captions)."""
    payload = candidate or {}
    metadata = payload.get("curation_metadata") if isinstance(payload.get("curation_metadata"), dict) else {}
    parts = [
        str(source_title or metadata.get("source_title") or "").strip(),
        str(payload.get("title_hook") or "").strip(),
        str(payload.get("transcript_span") or "").strip()[:160],
    ]
    return ". ".join(part for part in parts if part)[:320]


def apply_youtube_text(
    whisper_words: list[dict[str, Any]],
    entries: list[TranscriptEntry],
    clip_start_ms: int,
    *,
    keep_segments: list[tuple[int, int]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not whisper_words or not entries:
        return list(whisper_words), {"youtube_replaced": 0, "youtube_cues": len(entries)}
    replaced = 0
    skipped = 0
    next_words: list[dict[str, Any]] = []
    for index, word in enumerate(whisper_words):
        rel_start = int(word.get("startMs") or 0)
        rel_end = int(word.get("endMs") or rel_start + 80)
        if keep_segments:
            rel_start = untrim_time_ms(rel_start, keep_segments)
            rel_end = untrim_time_ms(rel_end, keep_segments)
        abs_start = clip_start_ms + rel_start
        abs_end = clip_start_ms + max(rel_end, rel_start + 80)
        token, entry_tokens, token_index = _youtube_token_context(entries, abs_start, abs_end)
        item = dict(word)
        if token and _should_take_youtube_token(word, token, whisper_words, index, entry_tokens, token_index):
            original = str(word.get("text") or "").strip()
            if token.lower() != original.lower():
                item["text"] = token
                replaced += 1
            item["caption_text_source"] = "youtube"
            item = _mark_confirmed(item)
        elif token:
            skipped += 1
        next_words.append(item)
    return next_words, {"youtube_replaced": replaced, "youtube_skipped": skipped, "youtube_cues": len(entries)}


def polish_uncertain_words(
    words: list[dict[str, Any]],
    provider: str,
    *,
    context: str = "",
    detected_language: str | None = None,
    niche: str = "",
    profile_id: str = "",
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
    system_prompt = build_polish_system_prompt(
        detected_language=detected_language,
        niche=niche,
        profile_id=profile_id,
    )
    try:
        result = call_llm_json(provider, system_prompt, str(payload), timeout_seconds=30)
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


def reconstruct_timed_captions_llm(
    words: list[dict[str, Any]],
    provider: str,
    *,
    context: str = "",
    detected_language: str | None = None,
    niche: str = "",
    profile_id: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if provider in {"", "none"} or not words:
        return list(words), {"llm_reconstructed": False, "llm_skipped": True}
    raw_text = " ".join(str(word.get("text") or "").strip() for word in words if str(word.get("text") or "").strip())
    if not raw_text:
        return list(words), {"llm_reconstructed": False, "llm_skipped": True}
    payload = {"raw_transcript": raw_text[:4000]}
    hint = str(context or "").strip()[:320]
    if hint:
        payload["clip_title"] = hint
    system_prompt = build_reconstruct_system_prompt(
        detected_language=detected_language,
        niche=niche,
        profile_id=profile_id,
    )
    try:
        result = call_llm_json(provider, system_prompt, str(payload), timeout_seconds=45)
    except (LLMError, TypeError, ValueError):
        return list(words), {"llm_reconstructed": False, "llm_error": True}
    cleaned = str(result.get("text") or "").strip() if isinstance(result, dict) else ""
    if not cleaned:
        return list(words), {"llm_reconstructed": False, "llm_error": True}
    if not reconstructed_text_is_grounded(raw_text, cleaned):
        return list(words), {
            "llm_reconstructed": False,
            "llm_rejected_ungrounded": True,
            "llm_output_preview": cleaned[:240],
        }
    aligned = align_words_to_reconstructed_text(words, cleaned)
    removed = max(0, len(words) - len(aligned))
    return aligned, {
        "llm_reconstructed": True,
        "llm_removed_words": removed,
        "llm_output_preview": cleaned[:240],
        "llm_word_count": len(aligned),
    }


def align_words_to_reconstructed_text(
    original_words: list[dict[str, Any]],
    reconstructed_text: str,
) -> list[dict[str, Any]]:
    recon_tokens = split_words(reconstructed_text)
    if not recon_tokens:
        return list(original_words)
    aligned: list[dict[str, Any]] = []
    orig_index = 0
    prefix_kept = False
    for recon_token in recon_tokens:
        recon_norm = _normalize_align_token(recon_token)
        if not recon_norm and not _is_punctuation_only(recon_token):
            continue
        if _is_punctuation_only(recon_token) and aligned:
            aligned[-1]["text"] = f"{aligned[-1]['text']}{recon_token}"
            continue
        best_index: int | None = None
        best_ratio = 0.0
        search_end = min(len(original_words), orig_index + 8)
        for candidate_index in range(orig_index, search_end):
            orig_norm = _normalize_align_token(str(original_words[candidate_index].get("text") or ""))
            if not orig_norm:
                continue
            ratio = SequenceMatcher(None, orig_norm, recon_norm).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_index = candidate_index
        if best_index is None or best_ratio < 0.6:
            continue
        if not prefix_kept:
            aligned.extend(dict(word) for word in original_words[:best_index])
            prefix_kept = True
        item = dict(original_words[best_index])
        item["text"] = recon_token
        item["caption_text_source"] = "llm_reconstruct"
        aligned.append(item)
        orig_index = best_index + 1
    if orig_index < len(original_words):
        aligned.extend(dict(word) for word in original_words[orig_index:])
    return aligned if aligned else list(original_words)


def reconstructed_text_is_grounded(raw_text: str, cleaned_text: str) -> bool:
    raw_tokens = [_normalize_align_token(token) for token in split_words(raw_text)]
    raw_tokens = [token for token in raw_tokens if token]
    if not raw_tokens:
        return True
    for token in split_words(cleaned_text):
        norm = _normalize_align_token(token)
        if len(norm) < 5:
            continue
        if any(SequenceMatcher(None, norm, original).ratio() >= 0.62 for original in raw_tokens):
            continue
        return False
    return True


def flatten_caption_segments_to_words(captions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for caption in captions:
        timed_words = caption.get("words")
        if isinstance(timed_words, list) and timed_words:
            for word in timed_words:
                text = str(word.get("text") or "").strip()
                if not text:
                    continue
                start_ms = int(word.get("startMs", caption.get("startMs", 0)) or 0)
                end_ms = int(word.get("endMs", caption.get("endMs", start_ms + 40)) or start_ms + 40)
                words.append({**word, "text": text, "startMs": start_ms, "endMs": max(start_ms + 40, end_ms)})
            continue
        text = str(caption.get("text") or "").strip()
        if not text:
            continue
        start_ms = int(caption.get("startMs", 0) or 0)
        end_ms = int(caption.get("endMs", start_ms + 40) or start_ms + 40)
        tokens = split_words(text)
        if not tokens:
            continue
        duration = max(40, end_ms - start_ms)
        step = max(40, duration // len(tokens))
        for index, token in enumerate(tokens):
            token_start = start_ms + index * step
            token_end = end_ms if index == len(tokens) - 1 else min(end_ms, token_start + step)
            words.append({"text": token, "startMs": token_start, "endMs": max(token_start + 40, token_end)})
    return words


def polish_caption_words(
    words: list[dict[str, Any]],
    *,
    llm_provider: str = "none",
    niche: str = "",
    profile_id: str = "",
    profile: dict[str, Any] | None = None,
    context: str = "",
    detected_language: str | None = None,
    max_words_per_caption: int = 3,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    glossary = resolve_glossary(profile_id=profile_id, niche=niche, profile=profile)
    phrase_glossary = resolve_phrase_glossary(profile_id=profile_id, niche=niche, profile=profile)
    words, glossary_meta = correct_asr_words(words, glossary=glossary, phrase_glossary=phrase_glossary)
    pipeline: dict[str, Any] = {"glossary": glossary_meta}
    if llm_provider not in {"", "none"}:
        words, llm_meta = reconstruct_timed_captions_llm(
            words,
            llm_provider,
            context=context,
            detected_language=detected_language,
            niche=niche,
            profile_id=profile_id,
        )
        pipeline["llm"] = llm_meta
    else:
        words, llm_meta = polish_uncertain_words(
            words,
            llm_provider,
            context=context,
            detected_language=detected_language,
            niche=niche,
            profile_id=profile_id,
        )
        pipeline["llm"] = llm_meta
    captions, composer_metadata = compose_caption_groups(words, max_words_per_caption=max_words_per_caption, glossary=glossary)
    pipeline["composer"] = composer_metadata
    return captions, pipeline


def polish_candidate_captions(
    candidate: dict[str, Any],
    captions: list[dict[str, Any]],
    *,
    llm_provider: str = "deepseek",
    niche: str = "",
    profile_id: str = "",
    profile: dict[str, Any] | None = None,
    max_words_per_caption: int = 3,
) -> dict[str, Any]:
    words = flatten_caption_segments_to_words(captions)
    if not words:
        raise ValueError("no caption words available to polish")
    metadata = candidate.get("curation_metadata") if isinstance(candidate.get("curation_metadata"), dict) else {}
    asr_metadata = candidate.get("asr_metadata") if isinstance(candidate.get("asr_metadata"), dict) else {}
    detected_language = str(asr_metadata.get("detected_language") or asr_metadata.get("language") or "").strip() or None
    context = reconstruct_llm_context(candidate, source_title=str(metadata.get("source_title") or ""))
    polished_captions, pipeline = polish_caption_words(
        words,
        llm_provider=llm_provider,
        niche=niche,
        profile_id=profile_id,
        profile=profile,
        context=context,
        detected_language=detected_language,
        max_words_per_caption=max_words_per_caption,
    )
    existing = candidate.get("caption_corrections") if isinstance(candidate.get("caption_corrections"), dict) else {}
    corrections = merge_caption_corrections(existing, polished_captions)
    corrections["ai_polish"] = True
    corrections["ai_polish_pipeline"] = pipeline
    return {
        "captions": polished_captions,
        "caption_corrections": corrections,
        "pipeline": pipeline,
    }


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
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mutate candidate timed captions. Returns pipeline metadata."""
    if caption_source not in {"whisper", "hybrid"}:
        candidate["caption_source"] = caption_source
        return {"skipped": True, "caption_source": caption_source}

    glossary = resolve_glossary(profile_id=profile_id, niche=niche, profile=profile)
    phrase_glossary = resolve_phrase_glossary(profile_id=profile_id, niche=niche, profile=profile)
    asr_path = asr_cache_path(source_clip, asr_model, speech_language)
    prompt = asr_initial_prompt(candidate, niche=niche, profile_id=profile_id)
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
        "glossary_pack": resolve_genre_pack(profile_id, niche),
    }
    if caption_source == "hybrid":
        words, youtube_meta = _try_youtube_text(words, candidate, youtube_url, transcript_lang_list)
        pipeline["youtube"] = youtube_meta
    words, glossary_meta = correct_asr_words(words, glossary=glossary, phrase_glossary=phrase_glossary)
    words = _confirm_glossary_corrections(words, glossary_meta)
    if llm_provider not in {"", "none"}:
        words, llm_meta = reconstruct_timed_captions_llm(
            words,
            llm_provider,
            context=reconstruct_llm_context(candidate),
            detected_language=detected_language,
            niche=niche,
            profile_id=profile_id,
        )
    else:
        words, llm_meta = polish_uncertain_words(
            words,
            llm_provider,
            context=reconstruct_llm_context(candidate),
            detected_language=detected_language,
            niche=niche,
            profile_id=profile_id,
        )
    pipeline["glossary"] = {"correction_count": glossary_meta.get("correction_count", 0)}
    pipeline["llm"] = llm_meta
    style = style or {}
    captions, composer_metadata = compose_caption_groups(
        words,
        max_words_per_caption=int(style.get("caption", {}).get("max_words_per_caption", 3)),
        glossary=glossary,
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
        "caption_sync_score": compute_caption_sync_score(words, video_ms=_source_duration_ms(source_clip)),
    }
    return pipeline


def compute_caption_sync_score(
    words: list[dict[str, Any]],
    *,
    video_ms: int = 0,
) -> int:
    if not words:
        return 0
    starts = []
    ends = []
    for word in words:
        try:
            starts.append(int(word.get("startMs") or 0))
            ends.append(int(word.get("endMs") or 0))
        except (TypeError, ValueError):
            continue
    if not starts or not ends:
        return 0
    first_ms = min(starts)
    last_ms = max(ends)
    score = 100
    if first_ms > 450:
        score -= min(50, int((first_ms - 450) / 150))
    if video_ms > 0:
        if last_ms > video_ms + 1500:
            score -= min(20, int((last_ms - video_ms) / 500))
        trailing = video_ms - last_ms
        if video_ms >= 15_000 and trailing > 8000:
            score -= min(20, int(trailing / 1000))
    return max(0, min(100, score))


def _source_duration_ms(source_clip: str) -> int:
    try:
        return int(probe_duration_ms(source_clip) or 0)
    except Exception:  # noqa: BLE001 - scoring must not fail caption build
        return 0


def _youtube_keep_segments(candidate: dict[str, Any]) -> tuple[list[tuple[int, int]] | None, str]:
    trim = candidate.get("silence_trim") if isinstance(candidate.get("silence_trim"), dict) else {}
    segments = parse_keep_segments(trim.get("keep_segments"))
    if trim.get("skipped") == "already_trimmed" and not segments:
        return None, "silence_trim_timeline_unknown"
    if trim.get("changed"):
        if not segments:
            return None, "silence_trim_timeline_unknown"
        return segments, ""
    return None, ""


def _try_youtube_text(
    words: list[dict[str, Any]],
    candidate: dict[str, Any],
    youtube_url: str,
    transcript_languages: str | list[str] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url = str(youtube_url or "").strip()
    if not url:
        return words, {"used": False, "reason": "no_url"}
    keep_segments, skip_reason = _youtube_keep_segments(candidate)
    if skip_reason:
        return words, {"used": False, "reason": skip_reason}
    languages = _language_list(transcript_languages)
    try:
        entries = fetch_youtube_transcript(url, languages=languages)
    except Exception:  # noqa: BLE001 - missing captions must not fail generate
        return words, {"used": False, "reason": "fetch_failed"}
    clip_start = int(candidate.get("start_ms") or 0)
    next_words, meta = apply_youtube_text(
        words,
        entries,
        clip_start,
        keep_segments=keep_segments,
    )
    meta["used"] = bool(meta.get("youtube_replaced") or meta.get("youtube_cues"))
    return next_words, meta


def _should_take_youtube_token(
    word: dict[str, Any],
    token: str,
    whisper_words: list[dict[str, Any]],
    word_index: int,
    entry_tokens: list[str],
    token_index: int,
) -> bool:
    original = str(word.get("text") or "").strip()
    if not original:
        return False
    if token.lower() == original.lower():
        return True
    confidence = word.get("confidence")
    confidence_value = float(confidence) if isinstance(confidence, (int, float)) else 0.0
    ratio = SequenceMatcher(None, original.lower(), token.lower()).ratio()
    similar = _similar_token(original, token)
    if confidence_value >= UNCERTAIN_THRESHOLD:
        return similar and ratio >= HIGH_CONFIDENCE_STRICT_RATIO
    if not _length_sane(original, token) and ratio < HIGH_CONFIDENCE_STRICT_RATIO:
        return False
    if not _youtube_anchors_align(whisper_words, word_index, entry_tokens, token_index):
        return False
    return similar


def _similar_token(left: str, right: str) -> bool:
    a, b = left.lower(), right.lower()
    if a in b or b in a:
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.72


def _length_sane(left: str, right: str) -> bool:
    left_len = len(left.strip())
    right_len = len(right.strip())
    if left_len == 0 or right_len == 0:
        return False
    return max(left_len, right_len) / min(left_len, right_len) <= MAX_TOKEN_LENGTH_RATIO


def _youtube_anchors_align(
    whisper_words: list[dict[str, Any]],
    word_index: int,
    entry_tokens: list[str],
    token_index: int,
) -> bool:
    if token_index < 0 or not entry_tokens:
        return True
    if token_index > 0 and word_index > 0:
        prev_whisper = str(whisper_words[word_index - 1].get("text") or "").strip()
        prev_youtube = entry_tokens[token_index - 1]
        prev_conf = whisper_words[word_index - 1].get("confidence")
        if prev_whisper and isinstance(prev_conf, (int, float)) and float(prev_conf) >= UNCERTAIN_THRESHOLD:
            if not _similar_token(prev_whisper, prev_youtube):
                return False
    if token_index < len(entry_tokens) - 1 and word_index < len(whisper_words) - 1:
        next_whisper = str(whisper_words[word_index + 1].get("text") or "").strip()
        next_youtube = entry_tokens[token_index + 1]
        next_conf = whisper_words[word_index + 1].get("confidence")
        if next_whisper and isinstance(next_conf, (int, float)) and float(next_conf) >= UNCERTAIN_THRESHOLD:
            if not _similar_token(next_whisper, next_youtube):
                return False
    return True


def _youtube_token_context(
    entries: list[TranscriptEntry],
    abs_start: int,
    abs_end: int,
) -> tuple[str | None, list[str], int]:
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
        return tokens[index], tokens, index
    return None, [], -1


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


def _normalize_align_token(text: str) -> str:
    return re.sub(r"[^\w']+", "", text.lower())


def _is_punctuation_only(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and not re.search(r"[A-Za-z0-9]", stripped)


def _language_list(value: str | list[str] | None) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value or "id,en").split(",") if part.strip()]
