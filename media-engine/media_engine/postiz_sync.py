"""Mirror Otonom schedules onto Postiz and cancel them when the queue changes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from datetime import datetime, timedelta, timezone

from .db import fetch_one
from .postiz_client import (
    PostizError,
    delete_post,
    get_post,
    index_posts_by_id,
    is_postiz_post_id,
    list_posts,
    reconcile_platform_result,
    on_postiz_calendar,
    postiz_api_key,
    publish_video,
    uses_postiz,
)
from .publishers import build_payload
from .rights import can_publish_candidate
from .schedule_publisher import latest_render_job, record_publish_attempt, rollup_schedule_status
from .scheduler import _parse_iso


def _loads(value: Any, fallback: Any) -> Any:
    if isinstance(value, dict) or isinstance(value, list):
        return value
    try:
        data = json.loads(value or "")
        return data if data is not None else fallback
    except (TypeError, json.JSONDecodeError):
        return fallback


def _save_platform_results(conn, schedule_id: str, results: dict[str, Any], last_error: str = "") -> None:
    conn.execute(
        """
        UPDATE scheduled_posts
        SET platform_results_json = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (json.dumps(results, ensure_ascii=False), last_error, schedule_id),
    )
    conn.commit()


def same_schedule_slot(stored: str, slot: str) -> bool:
    left = (stored or "").strip()
    right = (slot or "").strip()
    if not left or not right:
        return False
    if left == right:
        return True
    try:
        return _parse_iso(left).astimezone(timezone.utc) == _parse_iso(right).astimezone(timezone.utc)
    except ValueError:
        return False


def cancel_postiz_results(results: dict[str, Any], profile_id: str | None) -> None:
    for item in results.values():
        if not isinstance(item, dict):
            continue
        remote_id = str(item.get("remote_id") or "").strip()
        if str(item.get("backend") or "") != "postiz" or not remote_id:
            continue
        if not is_postiz_post_id(remote_id):
            continue
        try:
            delete_post(remote_id, profile_id=profile_id)
        except PostizError:
            continue


def cancel_postiz_for_candidate(conn, candidate_id: str) -> None:
    row = fetch_one(conn, "SELECT * FROM scheduled_posts WHERE candidate_id = ?", (candidate_id,))
    if not row:
        return
    schedule = dict(row)
    results = _loads(schedule.get("platform_results_json"), {}) or {}
    if isinstance(results, dict):
        cancel_postiz_results(results, str(schedule.get("profile_id") or "") or None)


def _publish_mapped(
    conn,
    *,
    candidate: dict[str, Any],
    source: dict[str, Any],
    target: dict[str, Any],
    render_job: dict[str, Any] | None,
    post_type: str,
    date_iso: str | None,
) -> dict[str, Any]:
    platform = target["platform"]
    guard = can_publish_candidate(source, target, candidate)
    payload = build_payload(platform, candidate, render_job)
    payload["title"] = str(candidate.get("title_hook") or "Short")
    if not guard.allowed:
        attempt = record_publish_attempt(conn, candidate["id"], platform, target["mode"], "blocked", payload, guard.reason)
        return {"platform": platform, "status": "blocked", "error": guard.reason, "attempt_id": attempt["id"]}
    output_path = str(payload.get("video_path") or "")
    if not output_path or not Path(output_path).exists():
        error = "rendered video file is missing"
        attempt = record_publish_attempt(conn, candidate["id"], platform, target["mode"], "failed", payload, error)
        return {"platform": platform, "status": "failed", "error": error, "attempt_id": attempt["id"]}
    profile_id = str(candidate.get("profile_id") or target.get("profile_id") or "").strip() or None
    result = publish_video(platform, payload, profile_id=profile_id, post_type=post_type, date_iso=date_iso)
    attempt_status = str(result.get("status") or "queued")
    attempt = record_publish_attempt(
        conn,
        candidate["id"],
        platform,
        target["mode"],
        attempt_status,
        {**payload, "live_result": result},
        "",
    )
    return {
        **result,
        "attempt_id": attempt["id"],
        "scheduled_at": date_iso or "",
    }


def sync_schedule_to_postiz(conn, schedule_id: str) -> dict[str, Any]:
    row = fetch_one(conn, "SELECT * FROM scheduled_posts WHERE id = ?", (schedule_id,))
    if not row:
        return {"id": schedule_id, "synced": False, "error": "schedule not found"}
    schedule = dict(row)
    profile_id = str(schedule.get("profile_id") or "").strip()
    platforms = _loads(schedule.get("platforms_json"), []) or []
    existing = _loads(schedule.get("platform_results_json"), {}) or {}
    if not isinstance(existing, dict):
        existing = {}
    candidate_row = fetch_one(conn, "SELECT * FROM clip_candidates WHERE id = ?", (schedule["candidate_id"],))
    if not candidate_row:
        return {"id": schedule_id, "synced": False, "error": "candidate not found"}
    candidate = dict(candidate_row)
    source_row = fetch_one(conn, "SELECT * FROM source_manifests WHERE id = ?", (candidate["source_id"],))
    source = dict(source_row) if source_row else {}
    render_job = latest_render_job(conn, candidate["id"])
    slot = str(schedule.get("scheduled_at") or "")
    date_iso = None
    try:
        date_iso = _parse_iso(slot).isoformat()
    except ValueError:
        date_iso = slot
    results: dict[str, Any] = {}
    errors: list[str] = []
    kept_ids = set()
    for platform in platforms:
        previous = existing.get(platform) if isinstance(existing.get(platform), dict) else {}
        if not uses_postiz(platform, profile_id):
            if on_postiz_calendar(previous):
                cancel_postiz_results({platform: previous}, profile_id)
            results[platform] = {"platform": platform, "status": "pending"}
            continue
        if (
            on_postiz_calendar(previous)
            and str(previous.get("post_type") or "schedule") == "schedule"
            and same_schedule_slot(str(previous.get("scheduled_at") or ""), slot)
        ):
            results[platform] = previous
            kept_ids.add(str(previous.get("remote_id") or ""))
            continue
        if on_postiz_calendar(previous):
            cancel_postiz_results({platform: previous}, profile_id)
        target = fetch_one(
            conn,
            "SELECT * FROM publish_targets WHERE profile_id = ? AND platform = ?",
            (profile_id, platform),
        )
        if not source or not target:
            results[platform] = {"platform": platform, "status": "failed", "error": "source or publish target not found"}
            errors.append(f"{platform}: source or publish target not found")
            continue
        try:
            results[platform] = _publish_mapped(
                conn,
                candidate=candidate,
                source=source,
                target=dict(target),
                render_job=render_job,
                post_type="schedule",
                date_iso=date_iso,
            )
            results[platform]["scheduled_at"] = slot
        except PostizError as exc:
            results[platform] = {"platform": platform, "status": "failed", "backend": "postiz", "error": str(exc)}
            errors.append(f"{platform}: {exc}")
    for platform, previous in existing.items():
        if platform in results:
            continue
        if on_postiz_calendar(previous if isinstance(previous, dict) else None):
            remote = str((previous or {}).get("remote_id") or "")
            if remote not in kept_ids:
                cancel_postiz_results({platform: previous}, profile_id)
    last_error = "; ".join(errors)
    _save_platform_results(conn, schedule_id, results, last_error)
    return {"id": schedule_id, "synced": True, "platform_results": results, "last_error": last_error}


def _rollup_last_error(results: dict[str, Any]) -> str:
    parts: list[str] = []
    for platform, row in results.items():
        if not isinstance(row, dict):
            continue
        if row.get("status") not in {"failed", "blocked"}:
            continue
        message = str(row.get("error") or row.get("reason") or "").strip()
        if message:
            parts.append(f"{platform}: {message}")
    return "; ".join(parts)


def _persist_rollup(conn, schedule: dict[str, Any], results: dict[str, Any]) -> None:
    platforms = _loads(schedule.get("platforms_json"), []) or []
    final_status = rollup_schedule_status(platforms if isinstance(platforms, list) else [], results)
    published_at = str(schedule.get("published_at") or "")
    last_error = _rollup_last_error(results)
    if final_status == "published":
        if not published_at:
            published_at = datetime.now(timezone.utc).isoformat()
        candidate_status = "published"
    elif final_status in {"partial_failed", "failed"}:
        published_at = ""
        candidate_status = "ready_to_publish"
    else:
        published_at = ""
        candidate_status = "scheduled"
        if not any(
            isinstance(row, dict) and row.get("status") in {"failed", "blocked"}
            for row in results.values()
        ):
            last_error = ""
    conn.execute(
        """
        UPDATE scheduled_posts
        SET status = ?, platform_results_json = ?, published_at = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (final_status, json.dumps(results, ensure_ascii=False), published_at, last_error, schedule["id"]),
    )
    conn.execute(
        "UPDATE clip_candidates SET status = ? WHERE id = ?",
        (candidate_status, schedule["candidate_id"]),
    )
    conn.commit()


def _reconcile_list_window(conn, profile_id: str) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    rows = conn.execute(
        "SELECT scheduled_at FROM scheduled_posts WHERE profile_id = ?",
        (profile_id,),
    ).fetchall()
    if not rows:
        return now - timedelta(days=14), now + timedelta(days=30)
    slots = [_parse_iso(str(row["scheduled_at"] or "")).astimezone(timezone.utc) for row in rows]
    start = min(slots) - timedelta(days=2)
    end = max(max(slots), now) + timedelta(days=2)
    return start, end


def reconcile_profile_schedules(conn, profile_id: str) -> None:
    if not str(profile_id or "").strip() or not postiz_api_key(profile_id):
        return
    start, end = _reconcile_list_window(conn, profile_id)
    posts = list_posts(profile_id, start_date=start, end_date=end)
    indexed = index_posts_by_id(posts)
    rows = conn.execute("SELECT * FROM scheduled_posts WHERE profile_id = ?", (profile_id,)).fetchall()
    for row in rows:
        schedule = dict(row)
        existing = _loads(schedule.get("platform_results_json"), {}) or {}
        if not isinstance(existing, dict) or not existing:
            continue
        results: dict[str, Any] = {}
        changed = False
        for platform, previous in existing.items():
            if not isinstance(previous, dict):
                results[platform] = previous
                continue
            remote_id = str(previous.get("remote_id") or "").strip()
            if not remote_id:
                results[platform] = previous
                continue
            remote_post = indexed.get(remote_id)
            if remote_post is None:
                try:
                    remote_post = get_post(remote_id, profile_id=profile_id)
                except PostizError:
                    remote_post = None
            if remote_post is None:
                results[platform] = previous
                continue
            next_row = reconcile_platform_result(previous, remote_post, platform)
            results[platform] = next_row
            if (
                next_row.get("status") != previous.get("status")
                or next_row.get("remote_url") != previous.get("remote_url")
                or next_row.get("error") != previous.get("error")
            ):
                changed = True
        if changed:
            _persist_rollup(conn, schedule, results)
