"""Assisted autonomy settings and quality gates."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

from .scheduler import DEFAULT_TZ, process_due_auto_schedule
from .scoring import (
    HYGIENE_GATE_HOLD,
    HYGIENE_GATE_NEEDS_ATTENTION,
    HYGIENE_GATE_PASS,
    evaluate_hygiene_gate,
)


AUTONOMY_OFF = "off"
AUTONOMY_ASSISTED = "assisted"
AUTONOMY_FULL = "full"
AUTONOMY_MODES = {AUTONOMY_OFF, AUTONOMY_ASSISTED, AUTONOMY_FULL}

STATUS_PENDING_AUTO_SCHEDULE = "pending_auto_schedule"
STATUS_REJECTED = "rejected"

DEFAULT_SETTINGS = {
    "autonomy_mode": AUTONOMY_ASSISTED,
    "review_grace_hours": 12,
    "auto_schedule_enabled": 1,
    "overall_threshold": 82,
    "hook_threshold": 80,
    "caption_threshold": 90,
    "boundary_threshold": 80,
}

# Caption hold vs auto-schedule (#70). Whisper token probability < 0.65 is common
# on 1–3 min Indonesian/Arabic speech (dozens of words). That is not a render
# failure. Review is Approve/skip the clip — not per-word caption QA.
# Hold only when captions are unusable. Auto-schedule still needs high scores.
CATASTROPHIC_CAPTION_AVG = 55
CATASTROPHIC_LOW_WORD_RATIO = 0.40
AUTO_SCHEDULE_LOW_WORD_RATIO = 0.08
MANUAL_HOLD_REASON = "manual"


def _now(now: datetime | None = None) -> datetime:
    value = now or datetime.now(DEFAULT_TZ)
    return value.astimezone(DEFAULT_TZ) if value.tzinfo else value.replace(tzinfo=DEFAULT_TZ)


def _iso(value: datetime) -> str:
    return value.astimezone(DEFAULT_TZ).isoformat(timespec="minutes")


def get_autonomy_settings(conn: sqlite3.Connection, profile_id: str = "nourbit") -> dict[str, Any]:
    row = conn.execute("SELECT * FROM autonomy_settings WHERE profile_id = ?", (profile_id,)).fetchone()
    if not row:
        conn.execute(
            """
            INSERT OR IGNORE INTO autonomy_settings
              (profile_id, autonomy_mode, review_grace_hours, auto_schedule_enabled,
               overall_threshold, hook_threshold, caption_threshold, boundary_threshold)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                DEFAULT_SETTINGS["autonomy_mode"],
                DEFAULT_SETTINGS["review_grace_hours"],
                DEFAULT_SETTINGS["auto_schedule_enabled"],
                DEFAULT_SETTINGS["overall_threshold"],
                DEFAULT_SETTINGS["hook_threshold"],
                DEFAULT_SETTINGS["caption_threshold"],
                DEFAULT_SETTINGS["boundary_threshold"],
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM autonomy_settings WHERE profile_id = ?", (profile_id,)).fetchone()
    return dict(row)


def update_autonomy_settings(conn: sqlite3.Connection, profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    current = get_autonomy_settings(conn, profile_id)
    mode = str(payload.get("autonomy_mode", current["autonomy_mode"]))
    if mode not in AUTONOMY_MODES:
        raise ValueError("autonomy_mode must be off, assisted, or full")
    values = {
        "autonomy_mode": mode,
        "review_grace_hours": _int_range(payload.get("review_grace_hours", current["review_grace_hours"]), 1, 168),
        "auto_schedule_enabled": int(bool(payload.get("auto_schedule_enabled", current["auto_schedule_enabled"]))),
        "overall_threshold": _int_range(payload.get("overall_threshold", current["overall_threshold"]), 0, 100),
        "hook_threshold": _int_range(payload.get("hook_threshold", current["hook_threshold"]), 0, 100),
        "caption_threshold": _int_range(payload.get("caption_threshold", current["caption_threshold"]), 0, 100),
        "boundary_threshold": _int_range(payload.get("boundary_threshold", current["boundary_threshold"]), 0, 100),
    }
    conn.execute(
        """
        INSERT INTO autonomy_settings
          (profile_id, autonomy_mode, review_grace_hours, auto_schedule_enabled,
           overall_threshold, hook_threshold, caption_threshold, boundary_threshold)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(profile_id) DO UPDATE SET
          autonomy_mode = excluded.autonomy_mode,
          review_grace_hours = excluded.review_grace_hours,
          auto_schedule_enabled = excluded.auto_schedule_enabled,
          overall_threshold = excluded.overall_threshold,
          hook_threshold = excluded.hook_threshold,
          caption_threshold = excluded.caption_threshold,
          boundary_threshold = excluded.boundary_threshold,
          updated_at = CURRENT_TIMESTAMP
        """,
        (
            profile_id,
            values["autonomy_mode"],
            values["review_grace_hours"],
            values["auto_schedule_enabled"],
            values["overall_threshold"],
            values["hook_threshold"],
            values["caption_threshold"],
            values["boundary_threshold"],
        ),
    )
    conn.commit()
    return get_autonomy_settings(conn, profile_id)


def _int_range(value: Any, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return min(max(parsed, minimum), maximum)


def candidate_dedupe_key(title_hook: str, transcript_span: str = "") -> str:
    words = re.findall(r"[a-zA-Z0-9']+", f"{transcript_span[:360]}".lower())
    stop = {"yang", "dan", "atau", "dengan", "untuk", "dari", "ini", "itu", "kita", "allah"}
    key_words = [word for word in words if word not in stop][:18]
    if not key_words:
        key_words = re.findall(r"[a-zA-Z0-9']+", title_hook.lower())[:8]
    return " ".join(key_words)


def token_jaccard(left: str, right: str) -> float:
    stop = {"yang", "dan", "atau", "dengan", "untuk", "dari", "ini", "itu", "kita", "allah", "adalah", "akan"}
    left_tokens = {token for token in re.findall(r"[a-zA-Z0-9']+", left.lower()) if token not in stop}
    right_tokens = {token for token in re.findall(r"[a-zA-Z0-9']+", right.lower()) if token not in stop}
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def text_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.lower().strip(), right.lower().strip()).ratio()


def is_duplicate_candidate(candidate: dict[str, Any], selected: list[dict[str, Any]], threshold: float = 0.82) -> bool:
    key = candidate_dedupe_key(str(candidate.get("title_hook", "")), str(candidate.get("transcript_span", "")))
    for existing in selected:
        existing_key = str(existing.get("dedupe_key") or candidate_dedupe_key(str(existing.get("title_hook", "")), str(existing.get("transcript_span", ""))))
        key_similarity = text_similarity(key, existing_key)
        title_similarity = text_similarity(str(candidate.get("title_hook", "")), str(existing.get("title_hook", "")))
        transcript_similarity = text_similarity(str(candidate.get("transcript_span", ""))[:600], str(existing.get("transcript_span", ""))[:600])
        token_similarity = token_jaccard(str(candidate.get("transcript_span", ""))[:900], str(existing.get("transcript_span", ""))[:900])
        if key_similarity >= 0.94:
            return True
        if token_similarity >= 0.72:
            return True
        if title_similarity >= 0.9 and transcript_similarity >= threshold:
            return True
    candidate["dedupe_key"] = key
    return False


def _json_obj(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _asr_word_stats(asr: dict[str, Any]) -> tuple[int, int, float]:
    composer = asr.get("caption_composer") if isinstance(asr.get("caption_composer"), dict) else {}
    low = int(composer.get("low_confidence_word_count") or asr.get("low_confidence_word_count") or 0)
    words = int(composer.get("word_count") or asr.get("word_count") or 0)
    ratio = (low / words) if words else 0.0
    return low, words, ratio


def caption_hold_reason(caption: int, word_count: int, low_ratio: float) -> str:
    """Empty unless captions are unusable (catastrophic ASR), not routine Whisper doubt."""
    if caption > 0 and caption < CATASTROPHIC_CAPTION_AVG:
        return "catastrophic_asr"
    if word_count > 0 and low_ratio > CATASTROPHIC_LOW_WORD_RATIO:
        return "catastrophic_uncertain_ratio"
    return ""


def _resolve_hygiene_gate(
    score: dict[str, Any],
    metadata: dict[str, Any],
    *,
    caption: int,
    boundary: int,
    hold_reason: str,
    rights_risk: bool,
) -> dict[str, Any]:
    gate_status = str(score.get("hygiene_gate") or "")
    flags = score.get("hygiene_flags")
    if gate_status in {HYGIENE_GATE_PASS, HYGIENE_GATE_NEEDS_ATTENTION, HYGIENE_GATE_HOLD} and isinstance(flags, list):
        return {"gate_status": gate_status, "flags": [str(flag) for flag in flags]}
    hygiene = evaluate_hygiene_gate(
        caption_confidence=caption,
        boundary_confidence=boundary,
        rights_risk=rights_risk,
        catastrophic_caption=bool(hold_reason),
        explicit_copyright_risk=rights_risk,
    )
    return hygiene


def _hygiene_allows_autonomy(gate_status: str, mode: str) -> bool:
    if gate_status == HYGIENE_GATE_HOLD:
        return False
    if gate_status == HYGIENE_GATE_NEEDS_ATTENTION:
        return mode in {AUTONOMY_ASSISTED, AUTONOMY_FULL}
    return gate_status == HYGIENE_GATE_PASS


def evaluate_quality_gate(
    candidate: dict[str, Any],
    settings: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    score = candidate.get("score") or {}
    metadata = candidate.get("curation_metadata") or {}
    asr = candidate.get("asr_metadata") or {}
    performance = int(score.get("performance_score") or score.get("overall_score") or 0)
    hook = int(score.get("hook_score") or 0)
    caption = int(score.get("asr_confidence") or score.get("caption_confidence") or 0)
    boundary = int(metadata.get("boundary_confidence") or 0)
    low_confidence_words, word_count, low_ratio = _asr_word_stats(asr)
    low_words_ok = True if word_count <= 0 else low_ratio <= AUTO_SCHEDULE_LOW_WORD_RATIO
    hold_reason = caption_hold_reason(caption, word_count, low_ratio)
    risk_flags = candidate.get("risk_flags") if isinstance(candidate.get("risk_flags"), list) else []
    risk_blob = " ".join(str(flag) for flag in risk_flags).lower()
    explicit_copyright_risk = "copyright" in risk_blob or "rights" in risk_blob
    hygiene = _resolve_hygiene_gate(
        score,
        metadata,
        caption=caption,
        boundary=boundary,
        hold_reason=hold_reason,
        rights_risk=explicit_copyright_risk,
    )
    hygiene_status = str(hygiene["gate_status"])
    hygiene_flags = list(hygiene.get("flags") or [])
    mode = settings.get("autonomy_mode", AUTONOMY_ASSISTED)
    hygiene_ok = _hygiene_allows_autonomy(hygiene_status, mode)
    if mode == AUTONOMY_FULL:
        hygiene_ok = hygiene_status == HYGIENE_GATE_PASS and not hold_reason
    checks = {
        "performance": performance >= int(settings["overall_threshold"]),
        "overall": performance >= int(settings["overall_threshold"]),
        "hook": hook >= int(settings["hook_threshold"]),
        "caption": caption >= int(settings["caption_threshold"]),
        "boundary": boundary >= int(settings["boundary_threshold"]),
        "hygiene_gate": hygiene_ok,
        "low_confidence_words": low_words_ok,
        "captions_usable": not hold_reason,
    }
    performance_passed = checks["performance"] and checks["hook"] and checks["low_confidence_words"] and checks["captions_usable"]
    passed = performance_passed and hygiene_ok
    deadline = ""
    if passed and mode == AUTONOMY_ASSISTED:
        deadline = _iso(_now(now) + timedelta(hours=int(settings["review_grace_hours"])))
    elif passed and mode == AUTONOMY_FULL:
        deadline = _iso(_now(now))
    status = "rendered"
    if mode == AUTONOMY_OFF:
        status = "rendered"
    elif hold_reason or hygiene_status == HYGIENE_GATE_HOLD:
        status = "held"
    elif passed:
        status = STATUS_PENDING_AUTO_SCHEDULE
    return {
        "passed": passed,
        "status": status,
        "hold_reason": hold_reason,
        "review_deadline_at": deadline,
        "auto_qualified": passed and mode != AUTONOMY_OFF and not hold_reason,
        "checks": checks,
        "hygiene_gate": hygiene_status,
        "hygiene_flags": hygiene_flags,
        "scores": {
            "performance": performance,
            "overall": performance,
            "hook": hook,
            "caption": caption,
            "boundary": boundary,
            "viral": int(score.get("viral_score") or score.get("resonance_score") or 0),
            "resonance": int(score.get("resonance_score") or score.get("viral_score") or 0),
            "pacing": int(score.get("pacing_score") or 0),
            "retention": int(score.get("retention_score") or 0),
            "low_confidence_words": low_confidence_words,
            "word_count": word_count,
            "low_word_ratio": round(low_ratio, 3),
        },
        "thresholds": {
            "overall": int(settings["overall_threshold"]),
            "performance": int(settings["overall_threshold"]),
            "hook": int(settings["hook_threshold"]),
            "caption": int(settings["caption_threshold"]),
            "boundary": int(settings["boundary_threshold"]),
        },
        "settings": {
            "autonomy_mode": mode,
            "review_grace_hours": int(settings["review_grace_hours"]),
            "auto_schedule_enabled": bool(settings["auto_schedule_enabled"]),
            "overall_threshold": int(settings["overall_threshold"]),
            "hook_threshold": int(settings["hook_threshold"]),
            "caption_threshold": int(settings["caption_threshold"]),
            "boundary_threshold": int(settings["boundary_threshold"]),
        },
    }


def apply_autonomy_gate_to_candidate(
    candidate: dict[str, Any],
    settings: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate the quality gate and mirror results on an in-memory candidate."""
    gate = evaluate_quality_gate(candidate, settings, now=now)
    candidate["quality_gate"] = gate
    candidate["review_deadline_at"] = gate.get("review_deadline_at", "")
    protected_statuses = {"approved", "scheduled", "ready_to_publish", "published"}
    if candidate.get("status") not in protected_statuses:
        candidate["status"] = gate.get("status", "rendered")
    return gate


def maybe_immediate_auto_schedule(
    conn: sqlite3.Connection,
    candidate_id: str,
    profile_id: str,
    gate: dict[str, Any],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Schedule immediately when full autonomy passes the gate."""
    settings = gate.get("settings") or {}
    if not gate.get("passed"):
        return []
    if settings.get("autonomy_mode") != AUTONOMY_FULL:
        return []
    if not settings.get("auto_schedule_enabled"):
        return []
    if gate.get("status") != STATUS_PENDING_AUTO_SCHEDULE:
        return []
    return process_due_auto_schedule(conn, profile_id=profile_id, now=_now(now) + timedelta(seconds=1))


def finalize_candidate_autonomy(
    conn: sqlite3.Connection,
    candidate: dict[str, Any],
    profile_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Apply the gate to an in-memory candidate before persistence."""
    settings = get_autonomy_settings(conn, profile_id)
    return apply_autonomy_gate_to_candidate(candidate, settings, now=now)


def complete_autonomy_after_persist(
    conn: sqlite3.Connection,
    candidate: dict[str, Any],
    profile_id: str,
    gate: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Auto-schedule immediately in full autonomy mode after the candidate row is saved."""
    resolved_gate = gate or candidate.get("quality_gate") or {}
    scheduled = maybe_immediate_auto_schedule(conn, str(candidate["id"]), profile_id, resolved_gate, now=now)
    if scheduled:
        candidate["status"] = "scheduled"
        resolved_gate["auto_scheduled"] = scheduled
        candidate["quality_gate"] = resolved_gate
    return scheduled


def reconcile_caption_holds(conn: sqlite3.Connection) -> int:
    """Release clips held only by the old absolute 4-word caption cap."""
    rows = conn.execute(
        """
        SELECT id, profile_id, caption_source, score_json, asr_metadata_json,
               curation_metadata_json
        FROM clip_candidates
        WHERE status = 'held'
        """
    ).fetchall()
    updated = 0
    settings_by_profile: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = dict(row)
        metadata = _json_obj(item.get("curation_metadata_json"))
        if metadata.get("hold_reason") == MANUAL_HOLD_REASON:
            continue
        if str(item.get("caption_source") or "") in {"explainer", "ingest_longform"}:
            continue
        profile_id = str(item.get("profile_id") or "nourbit")
        if profile_id not in settings_by_profile:
            settings_by_profile[profile_id] = get_autonomy_settings(conn, profile_id)
        gate = evaluate_quality_gate(
            {
                "score": _json_obj(item.get("score_json")),
                "curation_metadata": metadata,
                "asr_metadata": _json_obj(item.get("asr_metadata_json")),
            },
            settings_by_profile[profile_id],
        )
        if gate["status"] == "held":
            continue
        conn.execute(
            """
            UPDATE clip_candidates
            SET status = ?, quality_gate_json = ?, review_deadline_at = ?
            WHERE id = ?
            """,
            (
                gate["status"],
                json.dumps(gate, ensure_ascii=False),
                gate.get("review_deadline_at") or "",
                item["id"],
            ),
        )
        updated += 1
    if updated:
        conn.commit()
    return updated
