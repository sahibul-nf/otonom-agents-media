"""Assisted autonomy settings and quality gates."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

from .scheduler import DEFAULT_TZ


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


def evaluate_quality_gate(
    candidate: dict[str, Any],
    settings: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    score = candidate.get("score") or {}
    metadata = candidate.get("curation_metadata") or {}
    asr = candidate.get("asr_metadata") or {}
    overall = int(score.get("overall_score") or 0)
    hook = int(score.get("hook_score") or 0)
    caption = int(score.get("asr_confidence") or score.get("caption_confidence") or 0)
    boundary = int(metadata.get("boundary_confidence") or 0)
    low_confidence_words = int(asr.get("caption_composer", {}).get("low_confidence_word_count") or asr.get("low_confidence_word_count") or 0)
    checks = {
        "overall": overall >= int(settings["overall_threshold"]),
        "hook": hook >= int(settings["hook_threshold"]),
        "caption": caption >= int(settings["caption_threshold"]),
        "boundary": boundary >= int(settings["boundary_threshold"]),
        "low_confidence_words": low_confidence_words <= 4,
    }
    passed = all(checks.values())
    mode = settings.get("autonomy_mode", AUTONOMY_ASSISTED)
    deadline = ""
    if passed and mode == AUTONOMY_ASSISTED:
        deadline = _iso(_now(now) + timedelta(hours=int(settings["review_grace_hours"])))
    elif passed and mode == AUTONOMY_FULL:
        # Full autonomy schedules as soon as process_due_auto_schedule runs.
        deadline = _iso(_now(now))
    status = "rendered"
    if mode == AUTONOMY_OFF:
        status = "rendered"
    elif not checks["caption"] or not checks["low_confidence_words"]:
        status = "held"
    elif passed:
        status = STATUS_PENDING_AUTO_SCHEDULE
    return {
        "passed": passed,
        "status": status,
        "review_deadline_at": deadline,
        "checks": checks,
        "scores": {
            "overall": overall,
            "hook": hook,
            "caption": caption,
            "boundary": boundary,
            "low_confidence_words": low_confidence_words,
        },
        "settings": {
            "autonomy_mode": mode,
            "review_grace_hours": int(settings["review_grace_hours"]),
            "auto_schedule_enabled": bool(settings["auto_schedule_enabled"]),
        },
    }
