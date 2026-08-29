"""Caption timing helpers for word-aligned short-form overlays."""

from __future__ import annotations

import re
from typing import Any, Protocol


class TranscriptLike(Protocol):
    start_ms: int
    end_ms: int
    text: str


FILLER_WORDS = {"eee", "ee", "em", "emm", "anu"}
MIN_WORD_DURATION_MS = 80


def split_words(text: str) -> list[str]:
    return [word for word in re.split(r"\s+", text.strip()) if word]


def should_keep_word(word: str, remove_filler_words: bool) -> bool:
    if not remove_filler_words:
        return True
    normalized = re.sub(r"[^a-zA-Z0-9]", "", word).lower()
    return normalized not in FILLER_WORDS


def build_word_timeline(
    entries: list[TranscriptLike],
    clip_start_ms: int,
    clip_end_ms: int,
    remove_filler_words: bool = False,
) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for entry in entries:
        if entry.end_ms <= clip_start_ms or entry.start_ms >= clip_end_ms:
            continue
        raw_words = [word for word in split_words(entry.text) if should_keep_word(word, remove_filler_words)]
        if not raw_words:
            continue
        entry_start = max(entry.start_ms, clip_start_ms)
        entry_end = min(entry.end_ms, clip_end_ms)
        entry_duration = max(1, entry_end - entry_start)
        slot = max(1, entry_duration // len(raw_words))
        for index, word in enumerate(raw_words):
            start = entry_start + index * slot
            end = entry_start + (index + 1) * slot if index < len(raw_words) - 1 else entry_end
            if start >= entry_end:
                continue
            words.append(
                {
                    "text": word,
                    "startMs": max(0, start - clip_start_ms),
                    "endMs": max(0, max(start + 80, min(entry_end, end)) - clip_start_ms),
                }
            )
    return normalize_word_timeline(words)


def normalize_word_timeline(
    words: list[dict[str, Any]],
    duration_ms: int | None = None,
    min_duration_ms: int = MIN_WORD_DURATION_MS,
) -> list[dict[str, Any]]:
    clean_words = []
    for index, word in enumerate(words):
        text = str(word.get("text", "")).strip()
        if not text:
            continue
        try:
            start_ms = int(word.get("startMs", 0))
            end_ms = int(word.get("endMs", start_ms + min_duration_ms))
        except (TypeError, ValueError):
            continue
        clean_words.append(
            {
                **word,
                "text": text,
                "startMs": max(0, start_ms),
                "endMs": max(0, end_ms),
                "_sourceIndex": index,
            }
        )
    if not clean_words:
        return []

    clean_words.sort(key=lambda word: (word["startMs"], word["endMs"], word["_sourceIndex"]))
    normalized: list[dict[str, Any]] = []
    previous_start: int | None = None
    for word in clean_words:
        start_ms = word["startMs"]
        if previous_start is not None and start_ms <= previous_start:
            start_ms = previous_start + min_duration_ms
        if duration_ms is not None and start_ms >= duration_ms:
            continue
        end_ms = max(start_ms + min_duration_ms, word["endMs"])
        if duration_ms is not None:
            end_ms = min(duration_ms, end_ms)
        if end_ms <= start_ms:
            continue
        word = {key: value for key, value in word.items() if key != "_sourceIndex"}
        word["startMs"] = start_ms
        word["endMs"] = end_ms
        normalized.append(word)
        previous_start = start_ms

    for index, word in enumerate(normalized[:-1]):
        next_start = normalized[index + 1]["startMs"]
        if word["endMs"] > next_start:
            word["endMs"] = next_start
    return [word for word in normalized if word["endMs"] > word["startMs"]]


def _shift_caption_group(caption: dict[str, Any], shift_ms: int) -> dict[str, Any]:
    if shift_ms <= 0:
        return caption
    shifted = dict(caption)
    for key in ("startMs", "endMs", "timestampMs"):
        if key in shifted:
            shifted[key] = max(0, int(shifted[key]) - shift_ms)
    words = shifted.get("words")
    if isinstance(words, list):
        shifted["words"] = [
            {
                **word,
                "startMs": max(0, int(word.get("startMs", 0)) - shift_ms),
                "endMs": max(0, int(word.get("endMs", 0)) - shift_ms),
            }
            for word in words
            if isinstance(word, dict)
        ]
    return shifted


def _first_spoken_ms(captions: list[dict[str, Any]]) -> int | None:
    starts: list[int] = []
    for caption in captions:
        words = caption.get("words")
        if isinstance(words, list) and words:
            for word in words:
                if not isinstance(word, dict):
                    continue
                try:
                    starts.append(int(word.get("startMs", 0)))
                except (TypeError, ValueError):
                    continue
        try:
            starts.append(int(caption.get("startMs", 0)))
        except (TypeError, ValueError):
            continue
    return min(starts) if starts else None


def _captions_last_ms(captions: list[dict[str, Any]]) -> int:
    last_ms = 0
    for caption in captions:
        words = caption.get("words")
        if isinstance(words, list) and words:
            for word in words:
                if not isinstance(word, dict):
                    continue
                try:
                    last_ms = max(last_ms, int(word.get("endMs", 0)))
                except (TypeError, ValueError):
                    continue
        try:
            last_ms = max(last_ms, int(caption.get("endMs", 0)))
        except (TypeError, ValueError):
            continue
    return last_ms


def captions_timeline_uses_source_offset(captions: list[dict[str, Any]], clip_start_ms: int) -> bool:
    """True when caption timestamps look absolute to the long-form source, not clip-relative."""
    first_ms = _first_spoken_ms(captions)
    clip_start = max(0, int(clip_start_ms or 0))
    if first_ms is None or clip_start < 1000:
        return False
    return first_ms >= clip_start - 1000


def rebase_captions_to_clip_zero(captions: list[dict[str, Any]], clip_start_ms: int) -> list[dict[str, Any]]:
    shift = max(0, int(clip_start_ms or 0))
    if shift <= 0:
        return list(captions)
    return [_shift_caption_group(caption, shift) for caption in captions]


def align_caption_timeline_start(
    captions: list[dict[str, Any]],
    *,
    max_leading_pad_ms: int = 120,
    shift_threshold_ms: int = 450,
) -> list[dict[str, Any]]:
    """Pull captions earlier when the first spoken word starts noticeably after t=0."""
    if not captions:
        return []
    first_ms = _first_spoken_ms(captions)
    if first_ms is None or first_ms <= shift_threshold_ms:
        return captions
    shift = first_ms - max_leading_pad_ms
    return [_shift_caption_group(caption, shift) for caption in captions]


def captions_out_of_sync(
    captions: list[dict[str, Any]],
    video_ms: int,
    *,
    clip_start_ms: int = 0,
) -> bool:
    """Detect captions that no longer match the trimmed source media timeline."""
    if not captions:
        return video_ms > 0
    if video_ms <= 0:
        return False
    if captions_timeline_uses_source_offset(captions, clip_start_ms):
        return False
    last_ms = _captions_last_ms(captions)
    if last_ms > video_ms + 2000:
        return True
    first_ms = _first_spoken_ms(captions) or 0
    if video_ms >= 15_000 and first_ms > min(10_000, int(video_ms * 0.35)):
        return True
    if video_ms >= 15_000 and len(captions) >= 3 and last_ms < video_ms - 12_000:
        return True
    return False


def normalize_caption_timeline_for_render(
    captions: list[dict[str, Any]],
    *,
    clip_start_ms: int = 0,
    video_duration_ms: int | None = None,
    max_leading_pad_ms: int = 120,
    shift_threshold_ms: int = 450,
) -> list[dict[str, Any]]:
    """Rebase absolute source timestamps to clip zero, then trim leading dead air."""
    if not captions:
        return []
    rebased = captions
    if captions_timeline_uses_source_offset(captions, clip_start_ms):
        rebased = rebase_captions_to_clip_zero(captions, clip_start_ms)
    return align_caption_timeline_start(
        rebased,
        max_leading_pad_ms=max_leading_pad_ms,
        shift_threshold_ms=shift_threshold_ms,
    )


def normalize_caption_groups(
    captions: list[dict[str, Any]],
    max_words_per_caption: int = 3,
    duration_ms: int | None = None,
) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for caption in captions:
        caption_words = caption.get("words") or []
        if caption_words:
            words.extend(caption_words)
            continue
        tokens = split_words(str(caption.get("text", "")))
        if not tokens:
            continue
        start_ms = int(caption.get("startMs", 0))
        end_ms = int(caption.get("endMs", start_ms + len(tokens) * 260))
        slot = max(MIN_WORD_DURATION_MS, (end_ms - start_ms) // max(1, len(tokens)))
        for index, token in enumerate(tokens):
            words.append(
                {
                    "text": token,
                    "startMs": start_ms + index * slot,
                    "endMs": min(end_ms, start_ms + (index + 1) * slot),
                }
            )
    return group_word_captions(
        normalize_word_timeline(words, duration_ms=duration_ms),
        max_words_per_caption=max_words_per_caption,
    )


def group_word_captions(
    words: list[dict[str, Any]],
    max_words_per_caption: int = 3,
    min_duration_ms: int = 320,
) -> list[dict[str, Any]]:
    if not words:
        return []
    groups: list[dict[str, Any]] = []
    clean_words = normalize_word_timeline(words)
    if not clean_words:
        return []
    for index in range(0, len(clean_words), max(1, max_words_per_caption)):
        group_words = clean_words[index : index + max(1, max_words_per_caption)]
        start_ms = group_words[0]["startMs"]
        end_ms = max(group_words[-1]["endMs"], start_ms + min_duration_ms)
        groups.append(
            {
                "text": " ".join(word["text"] for word in group_words),
                "startMs": start_ms,
                "endMs": end_ms,
                "timestampMs": start_ms,
                "confidence": None,
                "words": group_words,
            }
        )
    for index, group in enumerate(groups[:-1]):
        next_start = groups[index + 1]["startMs"]
        if next_start > group["startMs"]:
            group["endMs"] = next_start
    return groups


def build_fallback_caption_segments(
    transcript_span: str,
    duration_ms: int,
    max_words_per_caption: int = 3,
) -> list[dict[str, Any]]:
    tokens = split_words(transcript_span)
    if not tokens:
        return []
    word_slot = max(260, duration_ms // len(tokens))
    words = [
        {
            "text": token,
            "startMs": index * word_slot,
            "endMs": min(duration_ms, (index + 1) * word_slot),
        }
        for index, token in enumerate(tokens)
    ]
    return group_word_captions(words, max_words_per_caption=max_words_per_caption)
