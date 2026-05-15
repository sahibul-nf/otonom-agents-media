"""Manual caption edit helpers for review workflows."""

from __future__ import annotations

from typing import Any


MAX_CAPTION_SEGMENTS = 500
MAX_CAPTION_TEXT_LENGTH = 220


def normalize_edited_captions(captions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate and normalize edited caption text while preserving timing."""
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
        normalized.append(
            {
                "text": text,
                "startMs": start_ms,
                "endMs": end_ms,
                "timestampMs": start_ms,
                "manualIndex": index,
            }
        )
        previous_end = end_ms
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
