"""Post captions and hashtag templates for social publishing payloads."""

from __future__ import annotations

import json
from typing import Any


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


def _render_subtitle(render_job: dict[str, Any] | None) -> str:
    if not render_job:
        return ""
    try:
        metadata = json.loads(render_job.get("metadata_json") or "{}")
    except json.JSONDecodeError:
        return ""
    return str(metadata.get("subtitle") or "").strip()


def _compact_lines(lines: list[str], limit: int | None = None) -> str:
    text = "\n\n".join(line.strip() for line in lines if line and line.strip())
    if limit is None or len(text) <= limit:
        return text
    hashtags = lines[-1] if lines else ""
    room = max(0, limit - len(hashtags) - 5)
    body = "\n\n".join(lines[:-1]).strip()
    return f"{body[:room].rstrip()}...\n\n{hashtags}".strip()


def build_post_caption(
    candidate: dict[str, Any],
    render_job: dict[str, Any] | None = None,
    platform: str = "",
    source_attribution: str = "Source: Ribath Nouraniyyah Hasyimiyyah",
) -> str:
    title = str(candidate.get("title_hook") or "").strip()
    subtitle = _render_subtitle(render_job) or str(candidate.get("viral_reason") or "").strip()
    hashtags = " ".join(NOURBIT_HASHTAGS)
    lines = [
        title,
        subtitle,
        source_attribution,
        hashtags,
    ]
    return _compact_lines(lines, PLATFORM_LIMITS.get(platform))
