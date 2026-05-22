"""Post captions and hashtag templates for social publishing payloads."""

from __future__ import annotations

import json
import re
from typing import Any


MAX_POST_COPY_CHARS = 400
MAX_POST_COPY_HASHTAGS = 5

NOURBIT_HASHTAGS = [
    "#Nourbit",
    "#NourbitClips",
    "#KajianIslam",
    "#NasihatHati",
    "#Dzikir",
    "#Tasawuf",
    "#IslamicReminder",
]

PLATFORM_LIMITS = {
    "telegram_channel": 1024,
    "tiktok": 2200,
}


HASHTAG_RE = re.compile(r"(?<!\w)#[\w\u00c0-\u024f\u0600-\u06ff_]+", re.UNICODE)


def _render_subtitle(render_job: dict[str, Any] | None) -> str:
    if not render_job:
        return ""
    try:
        metadata = json.loads(render_job.get("metadata_json") or "{}")
    except json.JSONDecodeError:
        return ""
    return str(metadata.get("subtitle") or "").strip()


def _candidate_metadata(candidate: dict[str, Any]) -> dict[str, Any]:
    metadata = candidate.get("curation_metadata")
    if isinstance(metadata, dict):
        return metadata
    try:
        parsed = json.loads(str(candidate.get("curation_metadata_json") or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _split_hashtags(text: str) -> tuple[str, list[str]]:
    hashtags: list[str] = []

    def collect(match: re.Match[str]) -> str:
        tag = match.group(0)
        if tag not in hashtags:
            hashtags.append(tag)
        return ""

    body = HASHTAG_RE.sub(collect, text)
    return body, hashtags


def sanitize_post_caption(text: str, limit: int = MAX_POST_COPY_CHARS, max_hashtags: int = MAX_POST_COPY_HASHTAGS) -> str:
    """Normalize user/edit generated post copy for short-form platform reuse."""
    normalized = re.sub(r"[ \t]+", " ", str(text or "").replace("\r\n", "\n").replace("\r", "\n"))
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    body, hashtags = _split_hashtags(normalized)
    body = "\n".join(line.strip() for line in body.splitlines()).strip()
    hashtags = hashtags[:max_hashtags]
    hashtag_line = " ".join(hashtags)
    if hashtag_line and len(hashtag_line) > limit:
        hashtag_line = " ".join(hashtags[:1])[:limit].rstrip()
    if hashtag_line:
        body_limit = max(0, limit - len(hashtag_line) - 2)
        if len(body) > body_limit:
            suffix = "..."
            body = body[: max(0, body_limit - len(suffix))].rstrip() + suffix
        return f"{body}\n\n{hashtag_line}".strip()
    if len(body) > limit:
        body = body[: max(0, limit - 3)].rstrip() + "..."
    return body.strip()


def _compact_lines(lines: list[str], limit: int | None = None) -> str:
    text = "\n\n".join(line.strip() for line in lines if line and line.strip())
    if limit is None or len(text) <= limit:
        return sanitize_post_caption(text)
    hashtags = lines[-1] if lines else ""
    room = max(0, limit - len(hashtags) - 5)
    body = "\n\n".join(lines[:-1]).strip()
    return sanitize_post_caption(f"{body[:room].rstrip()}...\n\n{hashtags}", limit)


def build_post_caption(
    candidate: dict[str, Any],
    render_job: dict[str, Any] | None = None,
    platform: str = "",
    source_attribution: str = "Source: Ribath Nouraniyyah Hasyimiyyah",
) -> str:
    metadata = _candidate_metadata(candidate)
    override = str(metadata.get("post_caption_override") or "").strip()
    if override:
        return sanitize_post_caption(override, PLATFORM_LIMITS.get(platform, MAX_POST_COPY_CHARS))

    title = str(candidate.get("title_hook") or "").strip()
    subtitle = (
        str(candidate.get("hook_subtitle") or "").strip()
        or _render_subtitle(render_job)
        or str(candidate.get("viral_reason") or "").strip()
    )
    hashtags = " ".join(NOURBIT_HASHTAGS[:MAX_POST_COPY_HASHTAGS])
    lines = [
        title,
        subtitle,
        source_attribution,
        hashtags,
    ]
    return _compact_lines(lines, min(PLATFORM_LIMITS.get(platform, MAX_POST_COPY_CHARS), MAX_POST_COPY_CHARS))
