"""Resolve package source text from YouTube URLs or chat paste."""

from __future__ import annotations

import re

from .chat_source import sanitize_chat_transcript
from .source_resolve import resolve_youtube_source
from .youtube_pipeline import fetch_youtube_transcript

_YT = re.compile(r"(?:youtube\.com|youtu\.be)", re.I)


def resolve_source_text(kind: str, ref: str) -> tuple[str, dict]:
    kind = (kind or "youtube").strip().lower()
    ref = (ref or "").strip()
    if not ref:
        raise ValueError("source ref is required")

    if kind == "chat":
        text = sanitize_chat_transcript(ref)
        return text, {"kind": "chat", "chars": len(text)}

    if kind in {"youtube", "topic"}:
        if kind == "topic" or not _YT.search(ref):
            return ref, {"kind": "topic", "chars": len(ref)}
        resolved = resolve_youtube_source(ref)
        transcript = resolved.get("transcript") or {}
        text = ""
        if transcript.get("status") == "available":
            try:
                entries = fetch_youtube_transcript(ref, languages=["id", "en"], use_cache=True)
                lines = [e.text.strip() for e in entries if e.text.strip()]
                text = "\n".join(lines)
            except (ValueError, OSError):
                text = ""
        if not text:
            text = str(resolved.get("title") or ref)
        if len(text.strip()) < 40:
            text = f"{resolved.get('title') or ref}\n\n{text}".strip()
        return text[:24000], {
            "kind": "youtube",
            "video_id": resolved.get("video_id"),
            "title": resolved.get("title"),
            "transcript_status": transcript.get("status"),
        }

    raise ValueError(f"unsupported source_kind: {kind}")
