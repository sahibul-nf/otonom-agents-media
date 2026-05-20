"""Smart/local metadata refresh for reviewed clip candidates."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from .llm import LLMError, call_llm_json
from .scoring import score_candidate_text
from .youtube_pipeline import _subtitle_is_relevant, _title_is_relevant, hook_subtitle_for_span, title_for_span


def _loads(value: str | None) -> dict[str, Any]:
    try:
        data = json.loads(value or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _available_provider(preferred: str = "") -> str:
    candidates = [preferred, "deepseek", "openai"]
    for provider in candidates:
        provider = (provider or "").strip().lower()
        if provider == "deepseek" and os.environ.get("DEEPSEEK_API_KEY"):
            return provider
        if provider == "openai" and os.environ.get("OPENAI_API_KEY"):
            return provider
    return "none"


def _local_metadata(span: str) -> dict[str, str]:
    title = title_for_span(span)
    subtitle = hook_subtitle_for_span(span, title)
    return {
        "title_hook": title,
        "hook_subtitle": subtitle,
        "viral_reason": subtitle,
        "source": "heuristic_span",
    }


def _llm_metadata(span: str, current_title: str, current_subtitle: str, provider: str) -> dict[str, str] | None:
    system_prompt = (
        "You are a short-form Islamic content editor. Return strict JSON only. "
        "Write metadata that is specific to the transcript and never generic."
    )
    user_prompt = json.dumps(
        {
            "task": "Create a precise Indonesian hook title and warm subtitle for this short clip.",
            "rules": [
                "title_hook: 4-8 words, no generic fallback title, match the actual transcript.",
                "hook_subtitle: max 18 words, warm and specific.",
                "viral_reason: one short sentence explaining why this clip works.",
                "Do not invent claims not present in transcript.",
            ],
            "current": {"title_hook": current_title, "hook_subtitle": current_subtitle},
            "transcript_span": span[:2600],
            "required_json_shape": {
                "title_hook": "string",
                "hook_subtitle": "string",
                "viral_reason": "string",
            },
        },
        ensure_ascii=False,
    )
    try:
        result = call_llm_json(provider, system_prompt, user_prompt, timeout_seconds=35)
    except (LLMError, ValueError, TypeError):
        return None
    if not isinstance(result, dict):
        return None
    title = str(result.get("title_hook") or "").strip()
    subtitle = str(result.get("hook_subtitle") or "").strip()
    reason = str(result.get("viral_reason") or "").strip()
    if not _title_is_relevant(title, span) or not _subtitle_is_relevant(subtitle, span):
        return None
    if reason and not _subtitle_is_relevant(reason, span):
        reason = subtitle
    return {
        "title_hook": title,
        "hook_subtitle": subtitle,
        "viral_reason": reason or subtitle,
        "source": f"llm_{provider}",
    }


def refresh_candidate_metadata(conn, candidate_id: str, mode: str = "smart") -> dict[str, Any]:
    if mode not in {"smart", "local"}:
        raise ValueError("mode must be smart or local")
    row = conn.execute("SELECT * FROM clip_candidates WHERE id = ?", (candidate_id,)).fetchone()
    if not row:
        raise ValueError("candidate not found")
    candidate = dict(row)
    span = str(candidate.get("transcript_span") or "").strip()
    if not span:
        raise ValueError("candidate has no transcript span")

    curation = _loads(candidate.get("curation_metadata_json"))
    preferred_provider = str(curation.get("llm_provider") or "")
    metadata = _local_metadata(span)
    if mode == "smart":
        provider = _available_provider(preferred_provider)
        if provider != "none":
            llm_result = _llm_metadata(span, candidate.get("title_hook", ""), candidate.get("hook_subtitle", ""), provider)
            if llm_result:
                metadata = llm_result

    duration_ms = int(candidate["end_ms"]) - int(candidate["start_ms"])
    existing_score = _loads(candidate.get("score_json"))
    score = {
        **existing_score,
        **score_candidate_text(
            span,
            metadata["title_hook"],
            duration_ms,
            rights_risk=True,
            boundary_confidence=int(curation.get("boundary_confidence") or 75),
            opening_strength=int(curation.get("opening_strength") or 70),
        ),
    }
    refreshed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    curation = {
        **curation,
        "metadata_refresh_mode": mode,
        "metadata_refreshed_at": refreshed_at,
        "title_source": metadata["source"],
        "subtitle_source": metadata["source"],
        "reason_source": metadata["source"],
    }
    conn.execute(
        """
        UPDATE clip_candidates
        SET title_hook = ?, hook_subtitle = ?, viral_reason = ?,
            score_json = ?, curation_metadata_json = ?
        WHERE id = ?
        """,
        (
            metadata["title_hook"],
            metadata["hook_subtitle"],
            metadata["viral_reason"],
            json.dumps(score, ensure_ascii=False),
            json.dumps(curation, ensure_ascii=False),
            candidate_id,
        ),
    )
    conn.commit()
    return {
        "candidate_id": candidate_id,
        "title_hook": metadata["title_hook"],
        "hook_subtitle": metadata["hook_subtitle"],
        "viral_reason": metadata["viral_reason"],
        "score": score,
        "curation_metadata": curation,
    }
