"""Editorial quality score used to drop weak clips before a video render."""

from __future__ import annotations

import json
from typing import Any

from .decisions import answer_score, answer_yes, jev_available, jev_decide
from .llm import LLMError, call_llm_json
from .post_copy import _available_provider


DEFAULT_MIN_EDITORIAL_SCORE = 80
EDITORIAL_POOL_CAP = 12


def editorial_pool_count(requested: int, min_score: int) -> int:
    requested = max(1, int(requested))
    if int(min_score or 0) <= 0:
        return requested
    return min(EDITORIAL_POOL_CAP, max(requested, requested * 3))


def heuristic_editorial_score(candidate: dict[str, Any]) -> int:
    """Conservative local score. Keyword resonance alone should not clear 80."""
    score = candidate.get("score") if isinstance(candidate.get("score"), dict) else {}
    hook = int(score.get("hook_score") or 40)
    title = " ".join(str(candidate.get("title_hook") or "").lower().split())
    span = " ".join(str(candidate.get("transcript_span") or "").lower().split())
    reason = " ".join(str(candidate.get("viral_reason") or "").lower().split())
    subtitle = " ".join(str(candidate.get("hook_subtitle") or "").lower().split())
    bonus = 0
    if title and title not in span:
        bonus += 18
    if reason and reason != subtitle:
        bonus += 16
    if "?" in str(candidate.get("title_hook") or ""):
        bonus += 6
    return max(0, min(100, int(hook * 0.55) + bonus))


def _llm_editorial(candidate: dict[str, Any], provider: str) -> dict[str, int] | None:
    system_prompt = (
        "You score short-form clip ideas. Return strict JSON only. "
        "Do not rewrite the hook. Scores are integers 0-100."
    )
    user_prompt = json.dumps(
        {
            "task": "Score this clip idea before any video is rendered.",
            "rules": [
                "hook_strength: opinion or conflict in the title, not a transcript slice.",
                "clarity: a viewer can name the point in one sentence.",
                "post_ready: 100 if you would publish it, else below 60.",
                "editorial_score: weighted judgment, not an average of keyword hits.",
            ],
            "title_hook": candidate.get("title_hook"),
            "hook_subtitle": candidate.get("hook_subtitle"),
            "viral_reason": candidate.get("viral_reason"),
            "transcript_span": str(candidate.get("transcript_span") or "")[:1800],
            "required_json_shape": {
                "hook_strength": 0,
                "clarity": 0,
                "post_ready": 0,
                "editorial_score": 0,
            },
        },
        ensure_ascii=False,
    )
    try:
        result = call_llm_json(provider, system_prompt, user_prompt, timeout_seconds=30)
    except (LLMError, ValueError, TypeError):
        return None
    if not isinstance(result, dict):
        return None
    try:
        hook = int(result.get("hook_strength"))
        clarity = int(result.get("clarity"))
        ready = int(result.get("post_ready"))
        overall = int(result.get("editorial_score"))
    except (TypeError, ValueError):
        return None
    return {
        "hook_strength": max(0, min(100, hook)),
        "clarity": max(0, min(100, clarity)),
        "post_ready": max(0, min(100, ready)),
        "editorial_score": max(0, min(100, overall)),
    }


def _jev_editorial(candidate: dict[str, Any]) -> dict[str, int] | None:
    if not jev_available():
        return None
    state = json.dumps(
        {
            "title_hook": candidate.get("title_hook"),
            "hook_subtitle": candidate.get("hook_subtitle"),
            "viral_reason": candidate.get("viral_reason"),
            "transcript_span": str(candidate.get("transcript_span") or "")[:1800],
        },
        ensure_ascii=False,
    )
    answers = jev_decide(
        state,
        {
            "hook_strength": {
                "type": "score",
                "instructions": "Hook strength from 0 to 100. Opinion or conflict, not a raw transcript slice.",
            },
            "clarity": {
                "type": "score",
                "instructions": "How clear the point is, from 0 to 100.",
            },
            "post_ready": {
                "type": "noul",
                "instructions": "This clip is worth posting as a short.",
            },
        },
    )
    if not isinstance(answers, dict):
        return None
    hook = answer_score(answers.get("hook_strength"))
    clarity = answer_score(answers.get("clarity"))
    ready_flag = answer_yes(answers.get("post_ready"))
    if hook is None or clarity is None or ready_flag is None:
        return None
    ready = 100 if ready_flag else 35
    overall = max(0, min(100, int(round(hook * 0.4 + clarity * 0.4 + ready * 0.2))))
    return {
        "hook_strength": hook,
        "clarity": clarity,
        "post_ready": ready,
        "editorial_score": overall,
    }


def score_candidate_editorial(candidate: dict[str, Any], provider: str = "") -> dict[str, int | str]:
    resolved = _available_provider(provider)
    scored = _jev_editorial(candidate)
    source = "jev"
    if scored is None and resolved != "none":
        scored = _llm_editorial(candidate, resolved)
        source = f"llm_{resolved}"
    if scored is None:
        value = heuristic_editorial_score(candidate)
        scored = {
            "hook_strength": value,
            "clarity": value,
            "post_ready": value,
            "editorial_score": value,
        }
        source = "heuristic"
    existing = candidate.get("score") if isinstance(candidate.get("score"), dict) else {}
    candidate["score"] = {**existing, **scored, "editorial_source": source}
    return {"editorial_score": int(scored["editorial_score"]), "editorial_source": source}


def select_editorial_shortlist(
    candidates: list[dict[str, Any]],
    *,
    provider: str = "",
    min_score: int = 0,
    limit: int = 5,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    floor = max(0, min(100, int(min_score or 0)))
    for candidate in candidates:
        score_candidate_editorial(candidate, provider)
    ranked = sorted(
        candidates,
        key=lambda item: int((item.get("score") or {}).get("editorial_score") or 0),
        reverse=True,
    )
    if floor > 0:
        kept = [item for item in ranked if int((item.get("score") or {}).get("editorial_score") or 0) >= floor]
    else:
        kept = ranked
    kept = kept[: max(0, int(limit))]
    return kept, {"considered": len(candidates), "passed": len(kept), "floor": floor}


def public_shortlist_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    score = candidate.get("score") if isinstance(candidate.get("score"), dict) else {}
    curation = candidate.get("curation_metadata") if isinstance(candidate.get("curation_metadata"), dict) else {}
    span = str(candidate.get("transcript_span") or "").strip()
    return {
        "id": candidate.get("id"),
        "title_hook": candidate.get("title_hook"),
        "hook_subtitle": candidate.get("hook_subtitle"),
        "viral_reason": candidate.get("viral_reason"),
        "transcript_excerpt": span[:360],
        "start_ms": candidate.get("start_ms"),
        "end_ms": candidate.get("end_ms"),
        "content_angle": curation.get("content_angle") or "",
        "editorial_score": int(score.get("editorial_score") or 0),
        "editorial_source": score.get("editorial_source") or "",
        "hook_strength": score.get("hook_strength"),
        "clarity": score.get("clarity"),
    }
