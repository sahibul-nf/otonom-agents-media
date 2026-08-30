"""Smart/local metadata refresh for reviewed clip candidates."""

from __future__ import annotations

import json
import os
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .genres import resolve_genre_pack, uses_devotional_tone, workspace_curation_context
from .llm import LLMError, call_llm_json
from .overlay_copy import overlay_slots_for_candidate
from .scoring import score_candidate_text
from .youtube_pipeline import _subtitle_is_relevant, _title_is_relevant, hook_subtitle_for_span, title_for_span


@dataclass(frozen=True)
class WorkspaceContext:
    """Brand/workspace scope for metadata and scoring.

    Maps to ``media_profiles.id`` and ``clip_candidates.profile_id`` in SQLite.
    This is not an end-user login account; future auth would introduce a
    separate ``user_id`` that owns one or more workspaces.
    """

    workspace_id: str
    niche: str = ""
    name: str = ""


def _loads(value: str | None) -> dict[str, Any]:
    try:
        data = json.loads(value or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _resolve_workspace_context(
    candidate: dict[str, Any],
    *,
    workspace_id: str = "",
    profile_id: str = "",
    niche: str = "",
    workspace_name: str = "",
) -> WorkspaceContext:
    if profile_id and not workspace_id:
        warnings.warn(
            "profile_id is deprecated in metadata_refresh; use workspace_id instead.",
            DeprecationWarning,
            stacklevel=3,
        )
    resolved_id = (workspace_id or profile_id or str(candidate.get("profile_id") or "")).strip()
    return WorkspaceContext(workspace_id=resolved_id, niche=niche, name=workspace_name)


def available_metadata_provider(preferred: str = "") -> str:
    candidates = [preferred, "deepseek", "openai"]
    for provider in candidates:
        provider = (provider or "").strip().lower()
        if provider == "deepseek" and os.environ.get("DEEPSEEK_API_KEY"):
            return provider
        if provider == "openai" and os.environ.get("OPENAI_API_KEY"):
            return provider
    return "none"


def metadata_editor_system_prompt(
    *,
    workspace_id: str = "",
    niche: str = "",
    workspace_name: str = "",
    profile_id: str = "",
) -> str:
    resolved_workspace_id = workspace_id or profile_id
    if uses_devotional_tone(profile_id=resolved_workspace_id, niche=niche):
        role = "short-form Islamic content editor"
        tone = "warm, reflective Indonesian suited to faith-based clips"
    elif resolve_genre_pack(resolved_workspace_id, niche) == "tech_finance":
        role = "short-form tech and finance content editor"
        tone = "clear, opinionated Indonesian suited to tech and finance edutainment"
    else:
        role = "short-form video content editor"
        tone = "clear, engaging Indonesian that matches the workspace niche"
    base = (
        f"You are a {role}. Return strict JSON only. "
        "Write metadata that is specific to the transcript and never generic. "
        f"Tone: {tone}."
    )
    context = workspace_curation_context(workspace_name, niche)
    if context:
        base += f" {context}"
    return base


def _local_metadata(span: str) -> dict[str, str]:
    title = title_for_span(span)
    subtitle = hook_subtitle_for_span(span, title)
    return {
        "title_hook": title,
        "hook_subtitle": subtitle,
        "viral_reason": subtitle,
        "source": "heuristic_span",
    }


def _llm_metadata(
    span: str,
    current_title: str,
    current_subtitle: str,
    provider: str,
    workspace: WorkspaceContext,
) -> dict[str, str] | None:
    system_prompt = metadata_editor_system_prompt(
        workspace_id=workspace.workspace_id,
        niche=workspace.niche,
        workspace_name=workspace.name,
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


def needs_metadata_enrichment(candidate: dict[str, Any]) -> bool:
    curation = candidate.get("curation_metadata")
    if not isinstance(curation, dict):
        return True
    title_source = str(curation.get("title_source") or "")
    subtitle_source = str(curation.get("subtitle_source") or "")
    if title_source.startswith("llm") and subtitle_source.startswith("llm"):
        return False
    return title_source in {"", "heuristic_span"} or subtitle_source in {"", "heuristic_span"}


def _apply_metadata_to_candidate(
    candidate: dict[str, Any],
    metadata: dict[str, str],
    workspace: WorkspaceContext,
) -> None:
    candidate["title_hook"] = metadata["title_hook"]
    candidate["hook_subtitle"] = metadata["hook_subtitle"]
    candidate["viral_reason"] = metadata["viral_reason"]
    curation = candidate.get("curation_metadata")
    if not isinstance(curation, dict):
        curation = {}
    source = metadata["source"]
    curation.pop("overlay_slots", None)
    candidate["curation_metadata"] = curation
    fresh_overlay = overlay_slots_for_candidate(candidate)
    curation = {
        **curation,
        "title_source": source,
        "subtitle_source": source,
        "reason_source": source,
        "overlay_slots": fresh_overlay,
        "metadata_enriched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    candidate["curation_metadata"] = curation
    candidate["overlay_slots"] = fresh_overlay
    duration_ms = int(candidate["end_ms"]) - int(candidate["start_ms"])
    existing_score = candidate.get("score") if isinstance(candidate.get("score"), dict) else {}
    candidate["score"] = {
        **existing_score,
        **score_candidate_text(
            str(candidate.get("transcript_span") or ""),
            metadata["title_hook"],
            duration_ms,
            rights_risk=True,
            boundary_confidence=int(curation.get("boundary_confidence") or 75),
            opening_strength=int(curation.get("opening_strength") or 70),
            workspace_id=workspace.workspace_id,
            niche=workspace.niche,
        ),
    }


def enrich_candidate_metadata(
    candidate: dict[str, Any],
    *,
    llm_provider: str = "",
    workspace_id: str = "",
    niche: str = "",
    workspace_name: str = "",
    profile_id: str = "",
) -> dict[str, Any]:
    """Upgrade hook copy on an in-memory candidate before render or insert."""
    workspace = _resolve_workspace_context(
        candidate,
        workspace_id=workspace_id,
        profile_id=profile_id,
        niche=niche,
        workspace_name=workspace_name,
    )
    if not needs_metadata_enrichment(candidate):
        return candidate
    span = str(candidate.get("transcript_span") or "").strip()
    if not span:
        return candidate

    curation = candidate.get("curation_metadata") if isinstance(candidate.get("curation_metadata"), dict) else {}
    preferred = llm_provider or str(curation.get("llm_provider") or "")
    provider = available_metadata_provider(preferred)
    metadata = None
    if provider != "none":
        metadata = _llm_metadata(
            span,
            str(candidate.get("title_hook") or ""),
            str(candidate.get("hook_subtitle") or ""),
            provider,
            workspace,
        )
    if not metadata:
        metadata = _local_metadata(span)
    _apply_metadata_to_candidate(candidate, metadata, workspace)
    return candidate


def enrich_candidates_metadata(
    candidates: list[dict[str, Any]],
    *,
    llm_provider: str = "",
    workspace_id: str = "",
    niche: str = "",
    workspace_name: str = "",
    profile_id: str = "",
) -> list[dict[str, Any]]:
    return [
        enrich_candidate_metadata(
            candidate,
            llm_provider=llm_provider,
            workspace_id=workspace_id or profile_id or str(candidate.get("profile_id") or ""),
            niche=niche,
            workspace_name=workspace_name,
        )
        for candidate in candidates
    ]


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

    workspace = _resolve_workspace_context(candidate)
    profile = conn.execute(
        "SELECT niche, name FROM media_profiles WHERE id = ?",
        (workspace.workspace_id,),
    ).fetchone()
    if profile:
        workspace = WorkspaceContext(
            workspace_id=workspace.workspace_id,
            niche=str(profile["niche"] or ""),
            name=str(profile["name"] or ""),
        )

    curation = _loads(candidate.get("curation_metadata_json"))
    preferred_provider = str(curation.get("llm_provider") or "")
    metadata: dict[str, str] | None = None
    if mode == "smart":
        provider = available_metadata_provider(preferred_provider)
        if provider == "none":
            raise ValueError("metadata refresh failed: no LLM provider key available (set OPENAI_API_KEY or DEEPSEEK_API_KEY)")
        llm_result = _llm_metadata(
            span,
            candidate.get("title_hook", ""),
            candidate.get("hook_subtitle", ""),
            provider,
            workspace,
        )
        if not llm_result:
            raise ValueError("metadata refresh failed: LLM output is invalid or not relevant to transcript")
        metadata = llm_result
    else:
        metadata = _local_metadata(span)

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
            workspace_id=workspace.workspace_id,
            niche=workspace.niche,
        ),
    }
    refreshed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    scratch = {
        "title_hook": metadata["title_hook"],
        "hook_subtitle": metadata["hook_subtitle"],
        "curation_metadata": curation,
    }
    fresh_overlay = overlay_slots_for_candidate(scratch)
    curation = {
        **curation,
        "metadata_refresh_mode": mode,
        "metadata_refreshed_at": refreshed_at,
        "title_source": metadata["source"],
        "subtitle_source": metadata["source"],
        "reason_source": metadata["source"],
        "overlay_slots": fresh_overlay,
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
        "overlay_slots": fresh_overlay,
    }
