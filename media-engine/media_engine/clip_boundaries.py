"""Manual boundary editing for reviewed clips."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .costs import estimate_clip_cost
from .scoring import score_candidate_text

MIN_BOUNDARY_MS = 20_000
MAX_BOUNDARY_MS = 180_000


def _loads(value: str | None) -> dict[str, Any]:
    try:
        data = json.loads(value or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def update_clip_boundary(conn, candidate_id: str, start_ms: int, end_ms: int) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM clip_candidates WHERE id = ?", (candidate_id,)).fetchone()
    if not row:
        raise ValueError("candidate not found")
    candidate = dict(row)
    if candidate.get("status") == "published":
        raise ValueError("published clips cannot be boundary edited")
    if end_ms <= start_ms:
        raise ValueError("end time must be after start time")
    duration_ms = end_ms - start_ms
    if duration_ms < MIN_BOUNDARY_MS or duration_ms > MAX_BOUNDARY_MS:
        raise ValueError("clip duration must stay between 20 seconds and 3 minutes")

    curation = _loads(candidate.get("curation_metadata_json"))
    score = {
        **_loads(candidate.get("score_json")),
        **score_candidate_text(
            str(candidate.get("transcript_span") or ""),
            str(candidate.get("title_hook") or ""),
            duration_ms,
            rights_risk=True,
            boundary_confidence=72,
            opening_strength=int(curation.get("opening_strength") or 70),
            profile_id=str(candidate.get("profile_id") or ""),
        ),
    }
    cost = estimate_clip_cost(
        duration_ms,
        llm_provider=str(_loads(candidate.get("cost_json")).get("llm_provider") or curation.get("llm_provider") or "none"),
        caption_source=str(candidate.get("caption_source") or "youtube"),
        renderer=str(_loads(candidate.get("cost_json")).get("renderer") or "remotion"),
    )
    corrections = _loads(candidate.get("caption_corrections_json"))
    if corrections.get("manual_edit") or corrections.get("edited_captions"):
        corrections["manual_edit_stale"] = True
        corrections["manual_edit_stale_reason"] = "boundary_changed"

    edited_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    curation = {
        **curation,
        "boundary_source": "manual_edit",
        "boundary_edited_at": edited_at,
        "manual_start_ms": start_ms,
        "manual_end_ms": end_ms,
        "selected_duration_ms": duration_ms,
        "boundary_confidence": 72,
    }
    next_status = candidate.get("status") or "held"
    if next_status in {"approved", "scheduled", "ready_to_publish", "pending_auto_schedule"}:
        next_status = "held"
    conn.execute("DELETE FROM scheduled_posts WHERE candidate_id = ?", (candidate_id,))
    conn.execute(
        """
        UPDATE clip_candidates
        SET start_ms = ?, end_ms = ?, score_json = ?, cost_json = ?,
            curation_metadata_json = ?, caption_corrections_json = ?,
            status = ?, review_deadline_at = ''
        WHERE id = ?
        """,
        (
            start_ms,
            end_ms,
            json.dumps(score, ensure_ascii=False),
            json.dumps(cost, ensure_ascii=False),
            json.dumps(curation, ensure_ascii=False),
            json.dumps(corrections, ensure_ascii=False),
            next_status,
            candidate_id,
        ),
    )
    conn.commit()
    return {
        "candidate_id": candidate_id,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "duration_ms": duration_ms,
        "status": next_status,
        "score": score,
        "cost": cost,
        "curation_metadata": curation,
        "caption_corrections": corrections,
    }
