"""Post captions and hashtag templates for social publishing payloads."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .genres import resolve_genre_pack
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

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"
SOURCES_DIR = Path(__file__).resolve().parent.parent / "sources"

HASHTAG_RE = re.compile(r"(?<!\w)#[\w\u00c0-\u024f\u0600-\u06ff_]+", re.UNICODE)

SOURCE_ATTRIBUTION_PLACEHOLDER = "Source: Channel clip"
_ATTRIBUTION_LINE = re.compile(r"(?i)^(source|sumber)\s*:\s*(.+)$")
_GENERIC_ATTRIBUTION_TAIL = re.compile(
    r"(?i)^(channel(?:\s+clip)?|youtube(?:\s+(?:clip|video|kajian))?|klip(?:\s+\S+){0,6}|kajian(?:\s+\S+){0,6}|video(?:\s+clip)?)$"
)


def format_source_attribution(channel: str, prefix: str = "Source:") -> str:
    name = str(channel or "").strip()
    if not name:
        return ""
    pref = str(prefix or "Source:").strip() or "Source:"
    if pref.endswith(":"):
        return f"{pref} {name}"
    return f"{pref}: {name}"


def _attribution_tail(value: str) -> str:
    match = _ATTRIBUTION_LINE.match(str(value or "").strip())
    if not match:
        return ""
    return " ".join(match.group(2).split())


def is_placeholder_source_attribution(value: str, channel: str = "") -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if text.casefold() in {
        SOURCE_ATTRIBUTION_PLACEHOLDER.casefold(),
        "source: channel",
        "source: channel clip",
    }:
        return True
    tail = _attribution_tail(text)
    if not tail:
        return False
    resolved = " ".join(str(channel or "").split())
    if resolved and tail.casefold() == resolved.casefold():
        return False
    return bool(_GENERIC_ATTRIBUTION_TAIL.match(tail)) or tail.casefold() in {
        "channel clip",
        "klip kajian youtube",
        "klip youtube",
        "kajian youtube",
    }


def _channel_from_candidate(candidate: dict[str, Any] | None) -> str:
    if not isinstance(candidate, dict):
        return ""
    source = candidate.get("source")
    if isinstance(source, dict):
        channel = str(source.get("channel") or "").strip()
        if channel:
            return channel
    render = candidate.get("render_metadata")
    if isinstance(render, dict):
        attr = str(render.get("sourceAttribution") or "").strip()
        if attr and not is_placeholder_source_attribution(attr):
            return attr.removeprefix("Source:").strip()
    return ""


def _usable_source_attribution(raw: str, candidate: dict[str, Any] | None = None) -> str:
    text = str(raw or "").strip()
    if text and not is_placeholder_source_attribution(text):
        return text
    channel = _channel_from_candidate(candidate)
    return format_source_attribution(channel)


@dataclass(frozen=True)
class PostCopyContext:
    profile_id: str = ""
    workspace_name: str = ""
    niche: str = ""
    cta_text: str = ""
    source_attribution: str = ""
    attribution_rule: str = ""


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _workspace_hashtag(workspace_name: str) -> str:
    parts = [part.strip() for part in (workspace_name or "").split() if part.strip()]
    if not parts:
        return ""
    token = re.sub(r"[^\w]", "", parts[0])
    if not token:
        return ""
    return f"#{token}"


def default_hashtags_for_context(context: PostCopyContext | None = None) -> list[str]:
    ctx = context or PostCopyContext()
    pack = resolve_genre_pack(ctx.profile_id, ctx.niche)
    workspace_tag = _workspace_hashtag(ctx.workspace_name)
    if pack == "devotional":
        tags = ["#ShortClips", "#KajianIslam", "#NasihatHati", "#Dzikir", "#IslamicReminder"]
    elif pack == "tech_finance":
        tags = ["#ShortClips", "#TechTalk", "#TechFinance", "#AI", "#Business"]
    else:
        tags = ["#ShortClips", "#DailyReminder", "#CreatorTips", "#ShortForm", "#Content"]
    if workspace_tag and workspace_tag not in tags:
        tags.insert(1, workspace_tag)
    return tags[:MAX_POST_COPY_HASHTAGS]


def resolve_post_copy_context(
    *,
    profile_id: str = "",
    profile: dict[str, Any] | None = None,
    source: dict[str, Any] | None = None,
    workspace_name: str = "",
    niche: str = "",
    source_id: str = "",
) -> PostCopyContext:
    profile_payload = profile if isinstance(profile, dict) else _load_json(PROFILES_DIR / f"{profile_id}.json")
    source_payload = source if isinstance(source, dict) else None
    if source_payload is None and source_id:
        source_payload = _load_json(SOURCES_DIR / f"{source_id}.json")
        if source_payload is None and profile_id and "_" in source_id:
            tail = source_id.split("_", 1)[1]
            source_payload = _load_json(SOURCES_DIR / f"{profile_id}_{tail}.json")

    resolved_name = (workspace_name or str((profile_payload or {}).get("name") or "")).strip()
    resolved_niche = (niche or str((profile_payload or {}).get("niche") or "")).strip()
    cta_text = str((profile_payload or {}).get("cta_text") or "").strip()
    attribution_rule = str((source_payload or {}).get("attribution_rule") or "").strip()
    channel = str((source_payload or {}).get("channel") or (source_payload or {}).get("label") or "").strip()
    if not channel:
        channel = _channel_from_candidate({"source": source_payload} if source_payload else {})
    source_attribution = format_source_attribution(channel)
    return PostCopyContext(
        profile_id=profile_id,
        workspace_name=resolved_name,
        niche=resolved_niche,
        cta_text=cta_text,
        source_attribution=source_attribution,
        attribution_rule=attribution_rule,
    )


def _context_from_candidate(candidate: dict[str, Any]) -> PostCopyContext:
    source = candidate.get("source") if isinstance(candidate.get("source"), dict) else None
    return resolve_post_copy_context(
        profile_id=str(candidate.get("profile_id") or ""),
        source_id=str(candidate.get("source_id") or ""),
        source=source,
    )


def caption_char_limit(platform: str = "") -> int:
    cleaned = (platform or "").strip().lower()
    if cleaned:
        return PLATFORM_LIMITS.get(cleaned, MAX_POST_COPY_CHARS)
    return MAX_POST_COPY_CHARS


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


def _write_candidate_metadata(candidate: dict[str, Any], metadata: dict[str, Any]) -> None:
    candidate["curation_metadata"] = metadata
    candidate["curation_metadata_json"] = json.dumps(metadata, ensure_ascii=False)


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


def _fit_text(text: str, limit: int) -> str:
    """Shorten at a sentence or word boundary. Do not append an ellipsis."""
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    window = cleaned[:limit]
    best = -1
    for mark in (". ", "! ", "? ", ".\n", "!\n", "?\n"):
        index = window.rfind(mark)
        if index > best:
            best = index
    if best >= int(limit * 0.45):
        end = best + (2 if window[best : best + 2] in {". ", "! ", "? "} else 1)
        return window[:end].strip()
    space = window.rfind(" ")
    if space >= int(limit * 0.5):
        return window[:space].rstrip(" ,;:-")
    return window.rstrip()


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
        body = _fit_text(body, body_limit)
        return f"{body}\n\n{hashtag_line}".strip()
    return _fit_text(body, limit)


def strip_unresolved_attribution(text: str, channel: str = "") -> str:
    kept: list[str] = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if _ATTRIBUTION_LINE.match(stripped) and is_placeholder_source_attribution(stripped, channel):
            continue
        if re.search(r"(?i)\b(source|sumber):\s*channel(?:\s+clip)?\b", stripped):
            continue
        kept.append(line)
    cleaned = "\n".join(kept)
    cleaned = re.sub(r"(?i)\b(source|sumber):\s*channel(?:\s+clip)?\b", "", cleaned)
    return sanitize_post_caption(cleaned)


def _strip_placeholder_attribution(text: str, channel: str = "") -> str:
    return strip_unresolved_attribution(text, channel)


def _compact_lines(lines: list[str], limit: int | None = None) -> str:
    text = "\n\n".join(line.strip() for line in lines if line and line.strip())
    if limit is None or len(text) <= limit:
        return sanitize_post_caption(text, limit or MAX_POST_COPY_CHARS)
    hashtags = lines[-1] if lines else ""
    room = max(0, limit - len(hashtags) - 2)
    body = "\n\n".join(lines[:-1]).strip()
    return sanitize_post_caption(f"{_fit_text(body, room)}\n\n{hashtags}", limit)


def build_post_caption(
    candidate: dict[str, Any],
    render_job: dict[str, Any] | None = None,
    platform: str = "",
    source_attribution: str = "",
    context: PostCopyContext | None = None,
) -> str:
    limit = caption_char_limit(platform)
    metadata = _candidate_metadata(candidate)
    override = str(metadata.get("post_caption_override") or "").strip()
    if override:
        return sanitize_post_caption(_strip_placeholder_attribution(override), limit)

    ctx = context or _context_from_candidate(candidate)
    attribution = _usable_source_attribution(source_attribution or ctx.source_attribution, candidate)
    title = str(candidate.get("title_hook") or "").strip()
    subtitle = (
        str(candidate.get("hook_subtitle") or "").strip()
        or _render_subtitle(render_job)
        or str(candidate.get("viral_reason") or "").strip()
    )
    hashtags = " ".join(default_hashtags_for_context(ctx))
    lines = [title, subtitle]
    if attribution:
        lines.append(attribution)
    lines.append(hashtags)
    return _compact_lines(lines, limit)


def _local_generated_post_caption(
    candidate: dict[str, Any],
    render_job: dict[str, Any] | None = None,
    context: PostCopyContext | None = None,
) -> str:
    ctx = context or _context_from_candidate(candidate)
    title = str(candidate.get("title_hook") or "").strip()
    subtitle = (
        str(candidate.get("hook_subtitle") or "").strip()
        or _render_subtitle(render_job)
        or str(candidate.get("viral_reason") or "").strip()
    )
    body = title
    if subtitle:
        body = f"{title}\n\n{subtitle}"
    if ctx.cta_text and ctx.cta_text.lower() not in body.lower():
        body = f"{body}\n\n{ctx.cta_text}"
    attribution = _usable_source_attribution(ctx.source_attribution, candidate)
    if attribution:
        body = f"{body}\n\n{attribution}"
    hashtags = " ".join(default_hashtags_for_context(ctx))
    return sanitize_post_caption(f"{body}\n\n{hashtags}")


def generate_post_caption(
    candidate: dict[str, Any],
    render_job: dict[str, Any] | None = None,
    preferred_provider: str = "",
    context: PostCopyContext | None = None,
) -> dict[str, str | int]:
    """Generate short social post copy with LLM output and heuristic fallback."""
    metadata = _candidate_metadata(candidate)
    ctx = context or _context_from_candidate(candidate)
    provider = _available_provider(preferred_provider or str(metadata.get("llm_provider") or ""))
    if provider == "none":
        raise LLMError("post copy generation failed: no LLM provider key available")

    devotional = resolve_genre_pack(ctx.profile_id, ctx.niche) == "devotional"
    role = "social video copywriter for short Islamic reminder clips" if devotional else "social video copywriter for short-form edutainment"
    system_prompt = (
        f"You are a {role}. Return strict JSON only. Do not invent claims outside the transcript."
    )
    suggested_hashtags = default_hashtags_for_context(ctx)
    rules = [
        "post_caption must be under 400 characters after hashtags for short-form platforms.",
        "Use at most 5 hashtags.",
        "Do not mention platform mechanics, AI, or automation.",
        "Use the title/subtitle as context, but match the transcript content.",
        "Keep it sincere, not salesy.",
    ]
    if ctx.workspace_name:
        rules.append(f"Mention or echo the workspace brand ({ctx.workspace_name}) naturally when it fits.")
    if ctx.cta_text:
        rules.append(f"End with this CTA when space allows: {ctx.cta_text}")
    if ctx.attribution_rule:
        rules.append(f"Follow this attribution rule: {ctx.attribution_rule}")
    elif ctx.source_attribution and not is_placeholder_source_attribution(ctx.source_attribution):
        rules.append(f"Include a short source line like: {ctx.source_attribution}")
    else:
        rules.append(
            "Do not invent a source line. Never write 'Source: Channel clip', 'Sumber: klip kajian YouTube', or any generic Sumber/Source line."
        )
    rules.append("If the caption must be shortened, end on a complete sentence. Do not end with an ellipsis.")

    user_prompt = json.dumps(
        {
            "task": "Write a warm Indonesian post caption for this short-form video.",
            "rules": rules,
            "workspace_name": ctx.workspace_name,
            "niche": ctx.niche,
            "title_hook": str(candidate.get("title_hook") or "").strip(),
            "hook_subtitle": str(candidate.get("hook_subtitle") or "").strip(),
            "viral_reason": str(candidate.get("viral_reason") or "").strip(),
            "transcript_span": str(candidate.get("transcript_span") or "")[:2400],
            "suggested_hashtags": suggested_hashtags,
            "required_json_shape": {"post_caption": "string"},
        },
        ensure_ascii=False,
    )
    try:
        result = call_llm_json(provider, system_prompt, user_prompt, timeout_seconds=35)
    except LLMError:
        caption = _local_generated_post_caption(candidate, render_job, ctx)
        return {
            "post_caption": caption,
            "source": "heuristic_local",
            "char_count": len(caption),
            "hashtag_count": caption.count("#"),
        }
    if not isinstance(result, dict):
        raise LLMError("post copy generation failed: LLM response is not JSON object")
    caption = sanitize_post_caption(str(result.get("post_caption") or ""))
    channel = _channel_from_candidate(candidate) or _attribution_tail(ctx.source_attribution)
    caption = _strip_placeholder_attribution(caption, channel)
    if not caption:
        caption = _local_generated_post_caption(candidate, render_job, ctx)
        return {
            "post_caption": caption,
            "source": "heuristic_local",
            "char_count": len(caption),
            "hashtag_count": caption.count("#"),
        }
    source = f"llm_{provider}"

    return {
        "post_caption": caption,
        "source": source,
        "char_count": len(caption),
        "hashtag_count": caption.count("#"),
    }


def enrich_post_copy_for_candidate(
    candidate: dict[str, Any],
    *,
    profile_id: str = "",
    workspace_name: str = "",
    niche: str = "",
    profile: dict[str, Any] | None = None,
    source: dict[str, Any] | None = None,
    preferred_provider: str = "",
) -> dict[str, Any]:
    metadata = _candidate_metadata(candidate)
    if str(metadata.get("post_caption_override") or "").strip():
        return candidate
    ctx = resolve_post_copy_context(
        profile_id=profile_id or str(candidate.get("profile_id") or ""),
        profile=profile,
        source=source,
        workspace_name=workspace_name,
        niche=niche,
        source_id=str(candidate.get("source_id") or ""),
    )
    provider = _available_provider(preferred_provider or str(metadata.get("llm_provider") or ""))
    if provider == "none":
        caption = _local_generated_post_caption(candidate, context=ctx)
        metadata = {
            **metadata,
            "post_caption_override": caption,
            "post_caption_source": "heuristic_local",
        }
        _write_candidate_metadata(candidate, metadata)
        return candidate
    try:
        result = generate_post_caption(candidate, preferred_provider=preferred_provider, context=ctx)
    except LLMError:
        caption = _local_generated_post_caption(candidate, context=ctx)
        metadata = {
            **metadata,
            "post_caption_override": caption,
            "post_caption_source": "heuristic_local",
        }
        _write_candidate_metadata(candidate, metadata)
        return candidate
    metadata = {
        **metadata,
        "post_caption_override": result["post_caption"],
        "post_caption_source": result["source"],
    }
    _write_candidate_metadata(candidate, metadata)
    return candidate


def enrich_candidates_post_copy(
    candidates: list[dict[str, Any]],
    *,
    llm_provider: str = "",
    profile_id: str = "",
    niche: str = "",
    workspace_name: str = "",
    profile: dict[str, Any] | None = None,
    source: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return [
        enrich_post_copy_for_candidate(
            candidate,
            profile_id=profile_id or str(candidate.get("profile_id") or ""),
            workspace_name=workspace_name,
            niche=niche,
            profile=profile,
            source=source,
            preferred_provider=llm_provider,
        )
        for candidate in candidates
    ]
