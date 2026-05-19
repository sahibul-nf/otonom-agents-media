"""Due schedule publishing worker for local-first media operations."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .db import DEFAULT_DB, connect, fetch_one, initialize
from .env_loader import load_env_file
from .live_publishers import LivePublishError, publish_live_payload, verify_published_remote
from .publishers import build_payload, create_dry_run_attempt
from .rights import can_publish_candidate
from .scheduler import DEFAULT_TZ, _iso, refresh_due_posts


LEGACY_PERMISSION_ERROR = "permission evidence"


def _loads(value: str | None, fallback: Any) -> Any:
    try:
        data = json.loads(value or "")
        return data if data is not None else fallback
    except (TypeError, json.JSONDecodeError):
        return fallback


def latest_render_job(conn, candidate_id: str) -> dict[str, Any] | None:
    row = fetch_one(
        conn,
        "SELECT * FROM render_jobs WHERE candidate_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
        (candidate_id,),
    )
    return dict(row) if row else None


def already_published(conn, candidate_id: str, platform: str) -> bool:
    row = conn.execute(
        """
        SELECT payload_json
        FROM publish_attempts
        WHERE candidate_id = ?
          AND platform = ?
          AND status = 'published'
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (candidate_id, platform),
    ).fetchone()
    if not row:
        return False
    payload = _loads(row["payload_json"], {}) if isinstance(row["payload_json"], str) else {}
    live = payload.get("live_result") if isinstance(payload, dict) else {}
    remote_id = str((live or {}).get("remote_id") or "")
    return verify_published_remote(platform, remote_id)


def in_retry_backoff(conn, candidate_id: str, platform: str, minutes: int = 10) -> bool:
    # Prevent publish spam when the user clicks "Publish due now" repeatedly or when the worker is restarted.
    row = conn.execute(
        """
        SELECT 1
        FROM publish_attempts
        WHERE candidate_id = ?
          AND platform = ?
          AND status = 'failed'
          AND created_at >= datetime('now', ?)
        LIMIT 1
        """,
        (candidate_id, platform, f"-{max(1, int(minutes))} minutes"),
    ).fetchone()
    return bool(row)


def archive_legacy_permission_attempts(conn) -> int:
    result = conn.execute(
        """
        UPDATE publish_attempts
        SET status = 'legacy_blocked'
        WHERE status IN ('blocked', 'failed')
          AND lower(error) LIKE ?
        """,
        (f"%{LEGACY_PERMISSION_ERROR}%",),
    )
    conn.commit()
    return int(result.rowcount or 0)


def record_publish_attempt(
    conn,
    candidate_id: str,
    platform: str,
    mode: str,
    status: str,
    payload: dict[str, Any],
    error: str = "",
) -> dict[str, Any]:
    attempt = {
        "id": f"pub_{uuid.uuid4().hex[:12]}",
        "candidate_id": candidate_id,
        "platform": platform,
        "mode": mode,
        "status": status,
        "payload_json": json.dumps(payload, ensure_ascii=False),
        "error": error,
    }
    conn.execute(
        """
        INSERT INTO publish_attempts
          (id, candidate_id, platform, mode, status, payload_json, error)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            attempt["id"],
            attempt["candidate_id"],
            attempt["platform"],
            attempt["mode"],
            attempt["status"],
            attempt["payload_json"],
            attempt["error"],
        ),
    )
    conn.commit()
    return attempt


def _notify(message: str) -> None:
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (
        os.environ.get("TELEGRAM_STATUS_CHAT_ID")
        or os.environ.get("TELEGRAM_CHAT_ID")
        or os.environ.get("TELEGRAM_CHANNEL_ID")
        or ""
    ).strip()
    if not token or not chat_id:
        return
    data = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=15).close()
    except (urllib.error.URLError, TimeoutError):
        return


def publish_candidate_platform(
    conn,
    candidate: dict[str, Any],
    source: dict[str, Any],
    target: dict[str, Any],
    render_job: dict[str, Any] | None,
    dry_run: bool = False,
) -> dict[str, Any]:
    platform = target["platform"]
    if already_published(conn, candidate["id"], platform):
        return {"platform": platform, "status": "skipped", "reason": "already posted (verified)"}
    if in_retry_backoff(conn, candidate["id"], platform, minutes=12):
        return {"platform": platform, "status": "cooldown", "reason": "cooldown after recent failure"}

    guard = can_publish_candidate(source, target, candidate)
    payload = build_payload(platform, candidate, render_job)
    payload["dry_run"] = dry_run
    payload["title"] = str(candidate.get("title_hook") or "Short")
    if not guard.allowed:
        attempt = record_publish_attempt(conn, candidate["id"], platform, target["mode"], "blocked", payload, guard.reason)
        return {"platform": platform, "status": "blocked", "error": guard.reason, "attempt_id": attempt["id"]}

    output_path = str(payload.get("video_path") or "")
    if not output_path or not Path(output_path).exists():
        error = "rendered video file is missing"
        attempt = record_publish_attempt(conn, candidate["id"], platform, target["mode"], "failed", payload, error)
        return {"platform": platform, "status": "failed", "error": error, "attempt_id": attempt["id"]}

    if dry_run:
        attempt = create_dry_run_attempt(conn, source, target, candidate, render_job)
        return {"platform": platform, "status": attempt["status"], "attempt_id": attempt["id"], "payload": payload, "error": attempt["error"]}

    try:
        result = publish_live_payload(platform, payload)
    except LivePublishError as exc:
        attempt = record_publish_attempt(conn, candidate["id"], platform, target["mode"], "failed", payload, str(exc))
        return {"platform": platform, "status": "failed", "error": str(exc), "attempt_id": attempt["id"]}

    attempt = record_publish_attempt(
        conn,
        candidate["id"],
        platform,
        target["mode"],
        "published",
        {**payload, "live_result": result},
        "",
    )
    return {"platform": platform, "status": "published", "attempt_id": attempt["id"], **result}


def process_due_publishes(
    db_path: str | Path = DEFAULT_DB,
    env_file: str | Path | None = None,
    profile_id: str = "nourbit",
    now: datetime | None = None,
    limit: int = 5,
    dry_run: bool = False,
    notify: bool = False,
) -> dict[str, Any]:
    if env_file:
        load_env_file(env_file)
    conn = connect(db_path)
    initialize(conn)
    archive_legacy_permission_attempts(conn)
    now = (now or datetime.now(DEFAULT_TZ)).astimezone(DEFAULT_TZ)
    refresh_due_posts(conn, now=now)
    rows = conn.execute(
        """
        SELECT * FROM scheduled_posts
        WHERE profile_id = ?
          AND status IN ('ready_to_publish', 'partial_failed', 'failed', 'publishing')
          AND scheduled_at <= ?
        ORDER BY scheduled_at ASC
        LIMIT ?
        """,
        (profile_id, _iso(now), max(1, limit)),
    ).fetchall()
    processed: list[dict[str, Any]] = []
    for row in rows:
        schedule = dict(row)
        conn.execute(
            "UPDATE scheduled_posts SET status = 'publishing', last_error = '', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (schedule["id"],),
        )
        conn.execute(
            "UPDATE clip_candidates SET status = 'ready_to_publish' WHERE id = ? AND status IN ('scheduled', 'ready_to_publish')",
            (schedule["candidate_id"],),
        )
        conn.commit()
        candidate = fetch_one(conn, "SELECT * FROM clip_candidates WHERE id = ?", (schedule["candidate_id"],))
        if not candidate:
            continue
        candidate = dict(candidate)
        source = fetch_one(conn, "SELECT * FROM source_manifests WHERE id = ?", (candidate["source_id"],))
        render_job = latest_render_job(conn, candidate["id"])
        platforms = _loads(schedule.get("platforms_json"), []) or []
        existing_results = _loads(schedule.get("platform_results_json"), {}) or {}
        platform_results: dict[str, Any] = dict(existing_results)
        for platform in platforms:
            target = fetch_one(
                conn,
                "SELECT * FROM publish_targets WHERE profile_id = ? AND platform = ?",
                (candidate["profile_id"], platform),
            )
            if not source or not target:
                platform_results[platform] = {"platform": platform, "status": "failed", "error": "source or publish target not found"}
                continue
            platform_results[platform] = publish_candidate_platform(
                conn,
                candidate,
                dict(source),
                dict(target),
                render_job,
                dry_run=dry_run,
            )
        statuses = [result.get("status") for result in platform_results.values()]
        published_count = sum(1 for status in statuses if status in {"published", "skipped"})
        failed_count = sum(1 for status in statuses if status in {"failed", "blocked"})
        if dry_run:
            final_status = "ready_to_publish"
        elif published_count == len(platforms) and platforms:
            final_status = "published"
        elif published_count > 0 and failed_count > 0:
            final_status = "partial_failed"
        else:
            final_status = "failed"
        last_error = "; ".join(
            str(result.get("error") or result.get("reason") or "")
            for result in platform_results.values()
            if result.get("status") in {"failed", "blocked"} and (result.get("error") or result.get("reason"))
        )
        published_at = _iso(now) if final_status == "published" else ""
        conn.execute(
            """
            UPDATE scheduled_posts
            SET status = ?, platform_results_json = ?, published_at = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (final_status, json.dumps(platform_results, ensure_ascii=False), published_at, last_error, schedule["id"]),
        )
        if final_status == "published":
            conn.execute("UPDATE clip_candidates SET status = 'published' WHERE id = ?", (candidate["id"],))
        elif final_status in {"partial_failed", "failed"}:
            conn.execute("UPDATE clip_candidates SET status = 'ready_to_publish' WHERE id = ?", (candidate["id"],))
        conn.commit()
        item = {
            "schedule_id": schedule["id"],
            "candidate_id": candidate["id"],
            "title_hook": candidate["title_hook"],
            "status": final_status,
            "platform_results": platform_results,
            "last_error": last_error,
        }
        processed.append(item)
        if notify and not dry_run and final_status in {"published", "partial_failed", "failed"}:
            _notify(f"Otonom Media publish {final_status}: {candidate['title_hook']}")
    conn.close()
    return {
        "status": "ok",
        "dry_run": dry_run,
        "count": len(processed),
        "processed": processed,
    }
