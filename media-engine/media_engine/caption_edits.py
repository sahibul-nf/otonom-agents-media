"""Manual caption edit helpers for review workflows."""

from __future__ import annotations

from typing import Any


MAX_CAPTION_SEGMENTS = 500
MAX_CAPTION_TEXT_LENGTH = 220


def normalize_edited_captions(captions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate and normalize edited caption text while preserving timing (and words when present)."""
    normalized: list[dict[str, Any]] = []
    previous_end = 0
    for index, caption in enumerate(captions[:MAX_CAPTION_SEGMENTS]):
        text = " ".join(str(caption.get("text") or "").split())
        start_ms = int(caption.get("startMs", caption.get("timestampMs", previous_end)) or 0)
        end_ms = int(caption.get("endMs", start_ms) or start_ms)
        if not text or end_ms <= start_ms:
            continue
        if start_ms < previous_end:
            start_ms = previous_end
        if end_ms <= start_ms:
            continue
        text = text[:MAX_CAPTION_TEXT_LENGTH].strip()
        entry: dict[str, Any] = {
            "text": text,
            "startMs": start_ms,
            "endMs": end_ms,
            "timestampMs": start_ms,
            "manualIndex": index,
        }
        words_in = caption.get("words")
        if isinstance(words_in, list) and words_in:
            words_out: list[dict[str, Any]] = []
            for word in words_in:
                word_text = " ".join(str(word.get("text") or "").split())
                if not word_text:
                    continue
                w_start = int(word.get("startMs", start_ms) or start_ms)
                w_end = int(word.get("endMs", w_start) or w_start)
                if w_end <= w_start:
                    w_end = w_start + 40
                words_out.append({**word, "text": word_text[:80], "startMs": w_start, "endMs": w_end})
            if words_out:
                word_span_end = max(words_out[-1]["endMs"], entry["startMs"] + 40)
                caption_span = end_ms - start_ms
                # Drop orphan word timings that do not cover the edited caption span.
                if word_span_end >= end_ms - 80 or caption_span < 500:
                    entry["words"] = words_out
                    entry["startMs"] = words_out[0]["startMs"]
                    entry["endMs"] = word_span_end
                    entry["timestampMs"] = entry["startMs"]
        normalized.append(entry)
        previous_end = int(entry["endMs"])
    if not normalized:
        raise ValueError("at least one valid caption segment is required")
    return normalized


def merge_caption_corrections(existing: dict[str, Any], captions: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = normalize_edited_captions(captions)
    return {
        **existing,
        "manual_edit": True,
        "edited_captions": normalized,
        "edited_caption_count": len(normalized),
    }
