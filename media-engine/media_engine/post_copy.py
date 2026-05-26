"""Post captions and hashtag templates for social publishing payloads."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from .llm import LLMError, call_llm_json


MAX_POST_COPY_CHARS = 400
MAX_POST_COPY_HASHTAGS = 5

DEFAULT_HASHTAGS = [
    "#ShortClips",
    "#DailyReminder",
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


def _available_provider(preferred: str = "") -> str:
    candidates = [preferred, "deepseek", "openai", "groq"]
    for provider in candidates:
        provider = (provider or "").strip().lower()
        if provider == "deepseek" and os.environ.get("DEEPSEEK_API_KEY"):
            return provider
        if provider == "openai" and os.environ.get("OPENAI_API_KEY"):
            return provider
        if provider == "groq" and os.environ.get("GROQ_API_KEY"):
            return provider
    return "none"


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
    source_attribution: str = "Source: Channel clip",
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
    hashtags = " ".join(DEFAULT_HASHTAGS[:MAX_POST_COPY_HASHTAGS])
    lines = [
        title,
        subtitle,
        source_attribution,
        hashtags,
    ]
    return _compact_lines(lines, min(PLATFORM_LIMITS.get(platform, MAX_POST_COPY_CHARS), MAX_POST_COPY_CHARS))


def _local_generated_post_caption(candidate: dict[str, Any], render_job: dict[str, Any] | None = None) -> str:
    title = str(candidate.get("title_hook") or "").strip()
    subtitle = (
        str(candidate.get("hook_subtitle") or "").strip()
        or _render_subtitle(render_job)
        or str(candidate.get("viral_reason") or "").strip()
    )
    span = str(candidate.get("transcript_span") or "").strip()
    excerpt_words = [word.strip(".,!?;:()[]{}\"'“”‘’") for word in span.split() if len(word.strip(".,!?;:()[]{}\"'“”‘’")) > 3]
    excerpt = " ".join(excerpt_words[:14])
    body = title
    if subtitle:
        body = f"{title}\n\n{subtitle}"
    if excerpt and excerpt.lower() not in body.lower():
        body = f"{body}\n\n{excerpt}..."
    return sanitize_post_caption(f"{body}\n\n{' '.join(DEFAULT_HASHTAGS[:MAX_POST_COPY_HASHTAGS])}")


def generate_post_caption(
    candidate: dict[str, Any],
    render_job: dict[str, Any] | None = None,
    preferred_provider: str = "",
) -> dict[str, str | int]:
    """Generate short social post copy with LLM-only output."""
    metadata = _candidate_metadata(candidate)
    provider = _available_provider(preferred_provider or str(metadata.get("llm_provider") or ""))
    if provider == "none":
        raise LLMError("post copy generation failed: no LLM provider key available")

    system_prompt = (
        "You are a social video copywriter for short Islamic reminder clips. "
        "Return strict JSON only. Do not invent claims outside the transcript."
    )
    user_prompt = json.dumps(
        {
            "task": "Write a warm Indonesian post caption for this short-form video.",
            "rules": [
                "post_caption must be under 400 characters after hashtags.",
                "Use at most 5 hashtags.",
                "Do not mention platform mechanics, AI, or automation.",
                "Use the title/subtitle as context, but match the transcript content.",
                "Keep it sincere, not salesy.",
            ],
            "title_hook": str(candidate.get("title_hook") or "").strip(),
            "hook_subtitle": str(candidate.get("hook_subtitle") or "").strip(),
            "viral_reason": str(candidate.get("viral_reason") or "").strip(),
            "transcript_span": str(candidate.get("transcript_span") or "")[:2400],
            "suggested_hashtags": DEFAULT_HASHTAGS[:MAX_POST_COPY_HASHTAGS],
            "required_json_shape": {"post_caption": "string"},
        },
        ensure_ascii=False,
    )
    result = call_llm_json(provider, system_prompt, user_prompt, timeout_seconds=35)
    if not isinstance(result, dict):
        raise LLMError("post copy generation failed: LLM response is not JSON object")
    caption = sanitize_post_caption(str(result.get("post_caption") or ""))
    if not caption:
        raise LLMError("post copy generation failed: empty post_caption")
    source = f"llm_{provider}"

    return {
        "post_caption": caption,
        "source": source,
        "char_count": len(caption),
        "hashtag_count": caption.count("#"),
    }
