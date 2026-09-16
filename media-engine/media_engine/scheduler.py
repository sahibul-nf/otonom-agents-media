"""Queue-only scheduling helpers for approved short-form clips."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .publish_delivery import (
    ALL_DELIVERY_PLATFORMS,
    candidate_orientation_for_id,
    filter_platforms_for_orientation,
)

DEFAULT_DELIVERY_PLATFORMS = list(ALL_DELIVERY_PLATFORMS)
DEFAULT_TZ = ZoneInfo("Asia/Jakarta")
DEFAULT_SLOTS = (time(9, 0), time(19, 30))
SCHEDULED_PUBLISH = "scheduled_publish"


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=DEFAULT_TZ)
    return parsed.astimezone(DEFAULT_TZ)


def _iso(value: datetime) -> str:
    return value.astimezone(DEFAULT_TZ).isoformat(timespec="minutes")


def refresh_due_posts(conn: sqlite3.Connection, now: datetime | None = None) -> None:
    now = now or datetime.now(DEFAULT_TZ)
    rows = conn.execute(
        "SELECT id, candidate_id, scheduled_at FROM scheduled_posts WHERE status = 'scheduled'"
    ).fetchall()
    for row in rows:
        if _parse_iso(row["scheduled_at"]) <= now:
            conn.execute(
                "UPDATE scheduled_posts SET status = 'ready_to_publish', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (row["id"],),
            )
            conn.execute(
                "UPDATE clip_candidates SET status = 'ready_to_publish' WHERE id = ? AND status = 'scheduled'",
                (row["candidate_id"],),
            )
    stale_rows = conn.execute(
        "SELECT id, candidate_id, updated_at FROM scheduled_posts WHERE status = 'publishing'"
    ).fetchall()
    for row in stale_rows:
        updated_at = row["updated_at"] or ""
        try:
            parsed = datetime.fromisoformat(updated_at).replace(tzinfo=DEFAULT_TZ)
        except ValueError:
            parsed = now - timedelta(hours=1)
        if now - parsed >= timedelta(minutes=20):
            conn.execute(
                """
                UPDATE scheduled_posts
                SET status = 'ready_to_publish',
                    last_error = 'publish worker stalled; ready to retry',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (row["id"],),
            )
            conn.execute(
                "UPDATE clip_candidates SET status = 'ready_to_publish' WHERE id = ? AND status = 'publishing'",
                (row["candidate_id"],),
            )
    conn.commit()


def list_scheduled_posts(conn: sqlite3.Connection, profile_id: str = "nourbit") -> list[dict]:
    refresh_due_posts(conn)
    try:
        from .postiz_sync import reconcile_profile_schedules

        reconcile_profile_schedules(conn, profile_id)
    except Exception:
        pass
    rows = conn.execute(
        """
        SELECT s.*, c.title_hook, c.viral_reason, c.start_ms, c.end_ms, c.status AS candidate_status,
               r.output_path
        FROM scheduled_posts s
        JOIN clip_candidates c ON c.id = s.candidate_id
        LEFT JOIN render_jobs r ON r.id = (
          SELECT r2.id
          FROM render_jobs r2
          WHERE r2.candidate_id = c.id
          ORDER BY r2.created_at DESC, r2.id DESC
          LIMIT 1
        )
        WHERE s.profile_id = ?
        ORDER BY s.scheduled_at ASC
        """,
        (profile_id,),
    ).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["platforms"] = json.loads(item.get("platforms_json") or "[]")
        try:
            platform_results = json.loads(item.get("platform_results_json") or "{}")
        except json.JSONDecodeError:
            platform_results = {}
        item["platform_results"] = {
            platform: result
            for platform, result in platform_results.items()
            if "permission evidence" not in str(result.get("error") or result.get("reason") or "").lower()
        }
        if "permission evidence" in str(item.get("last_error") or "").lower():
            item["last_error"] = ""
        results.append(item)
    return results


def next_available_slot(
    conn: sqlite3.Connection,
    profile_id: str = "nourbit",
    now: datetime | None = None,
    slots: tuple[time, ...] = DEFAULT_SLOTS,
) -> datetime:
    now = now or datetime.now(DEFAULT_TZ)
    now = now.astimezone(DEFAULT_TZ)
    used = {
        _parse_iso(row["scheduled_at"]).replace(second=0, microsecond=0)
        for row in conn.execute(
            "SELECT scheduled_at FROM scheduled_posts WHERE profile_id = ? AND status IN ('scheduled', 'ready_to_publish')",
            (profile_id,),
        )
    }
    for day_offset in range(0, 90):
        day = now.date() + timedelta(days=day_offset)
        for slot in slots:
            candidate = datetime.combine(day, slot, DEFAULT_TZ)
            if candidate <= now or candidate in used:
                continue
            return candidate
    raise RuntimeError("no schedule slot available in the next 90 days")


def enabled_delivery_platforms(conn: sqlite3.Connection, profile_id: str, now: datetime | None = None) -> list[str]:
    """Return enabled publish platforms that still have daily capacity today."""
    now = now or datetime.now(DEFAULT_TZ)
    now = now.astimezone(DEFAULT_TZ)
    day_start = datetime.combine(now.date(), time(0, 0), DEFAULT_TZ)
    day_end = day_start + timedelta(days=1)
    targets = conn.execute(
        """
        SELECT platform, daily_cap, enabled, mode
        FROM publish_targets
        WHERE profile_id = ?
        ORDER BY platform ASC
        """,
        (profile_id,),
    ).fetchall()
    if not targets:
        return DEFAULT_DELIVERY_PLATFORMS.copy()

    scheduled_rows = conn.execute(
        """
        SELECT platforms_json FROM scheduled_posts
        WHERE profile_id = ?
          AND status IN ('scheduled', 'ready_to_publish', 'publishing', 'published')
          AND scheduled_at >= ? AND scheduled_at < ?
        """,
        (profile_id, _iso(day_start), _iso(day_end)),
    ).fetchall()
    counts: dict[str, int] = {}
    for row in scheduled_rows:
        try:
            platforms = json.loads(row["platforms_json"] or "[]")
        except json.JSONDecodeError:
            platforms = []
        for platform in platforms:
            counts[platform] = counts.get(platform, 0) + 1

    selected: list[str] = []
    for row in targets:
        if "enabled" in row.keys() and not int(row["enabled"] or 0):
            continue
        if row["mode"] == "off":
            continue
        cap = int(row["daily_cap"] or 0)
        if cap <= 0:
            continue
        if counts.get(row["platform"], 0) >= cap:
            continue
        selected.append(row["platform"])
    return selected


def schedule_candidate_next(
    conn: sqlite3.Connection,
    candidate_id: str,
    profile_id: str = "nourbit",
    platforms: list[str] | None = None,
    now: datetime | None = None,
    scheduled_at: str | None = None,
    republish: bool = False,
) -> dict:
    candidate = conn.execute("SELECT id, profile_id, status FROM clip_candidates WHERE id = ?", (candidate_id,)).fetchone()
    if not candidate:
        raise ValueError("candidate not found")
    if candidate["status"] not in {"approved", "scheduled", "ready_to_publish", "pending_auto_schedule"}:
        if not (republish and candidate["status"] == "published"):
            raise ValueError("only approved clips can be scheduled")
    profile_id = candidate["profile_id"] or profile_id
    clock = (now or datetime.now(DEFAULT_TZ)).astimezone(DEFAULT_TZ)
    if scheduled_at:
        parsed = _parse_iso(scheduled_at)
        if parsed <= clock:
            raise ValueError("scheduled_at must be in the future")
        scheduled_at_dt = parsed
    else:
        scheduled_at_dt = next_available_slot(conn, profile_id=profile_id, now=clock)
    schedule_id = f"sched_{uuid.uuid4().hex[:12]}"
    platform_list = platforms or enabled_delivery_platforms(conn, profile_id, now=clock)
    if not platform_list:
        raise ValueError("no delivery platforms with remaining daily capacity")
    orientation = candidate_orientation_for_id(conn, candidate_id)
    platform_list = filter_platforms_for_orientation(platform_list, orientation)
    if not platform_list:
        raise ValueError("no delivery platforms compatible with this clip orientation")
    conn.execute(
        """
        INSERT OR REPLACE INTO scheduled_posts
          (id, candidate_id, profile_id, scheduled_at, status, publish_mode, platforms_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            schedule_id,
            candidate_id,
            profile_id,
            _iso(scheduled_at_dt),
            "scheduled",
            SCHEDULED_PUBLISH,
            json.dumps(platform_list, ensure_ascii=False),
        ),
    )
    conn.execute("UPDATE clip_candidates SET status = 'scheduled' WHERE id = ?", (candidate_id,))
    conn.commit()
    from .postiz_sync import sync_schedule_to_postiz

    sync_schedule_to_postiz(conn, schedule_id)
    return {"id": schedule_id, "candidate_id": candidate_id, "scheduled_at": _iso(scheduled_at_dt), "status": "scheduled"}


def process_due_auto_schedule(conn: sqlite3.Connection, profile_id: str = "nourbit", now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(DEFAULT_TZ)
    now = now.astimezone(DEFAULT_TZ)
    settings = conn.execute("SELECT * FROM autonomy_settings WHERE profile_id = ?", (profile_id,)).fetchone()
    if not settings or settings["autonomy_mode"] == "off" or not int(settings["auto_schedule_enabled"]):
        return []
    rows = conn.execute(
        """
        SELECT id, review_deadline_at, quality_gate_json
        FROM clip_candidates
        WHERE profile_id = ? AND status = 'pending_auto_schedule' AND review_deadline_at != ''
        ORDER BY review_deadline_at ASC, created_at ASC
        """,
        (profile_id,),
    ).fetchall()
    scheduled = []
    for row in rows:
        if _parse_iso(row["review_deadline_at"]) > now:
            continue
        try:
            gate = json.loads(row["quality_gate_json"] or "{}")
        except json.JSONDecodeError:
            gate = {}
        if not gate.get("passed"):
            conn.execute("UPDATE clip_candidates SET status = 'rendered' WHERE id = ?", (row["id"],))
            continue
        try:
            platforms = enabled_delivery_platforms(conn, profile_id, now=now)
            if not platforms:
                break
            scheduled.append(schedule_candidate_next(conn, row["id"], profile_id=profile_id, platforms=platforms, now=now))
        except ValueError:
            continue
    conn.commit()
    return scheduled


def process_due_auto_schedule_all(conn: sqlite3.Connection, now: datetime | None = None) -> list[dict]:
    profiles = [row["id"] for row in conn.execute("SELECT id FROM media_profiles ORDER BY id ASC").fetchall()]
    if not profiles:
        profiles = ["nourbit"]
    scheduled: list[dict] = []
    for profile_id in profiles:
        scheduled.extend(process_due_auto_schedule(conn, profile_id=profile_id, now=now))
    return scheduled


def update_schedule(conn: sqlite3.Connection, schedule_id: str, scheduled_at: str) -> dict:
    parsed = _parse_iso(scheduled_at)
    result = conn.execute(
        """
        UPDATE scheduled_posts
        SET scheduled_at = ?, status = 'scheduled', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (_iso(parsed), schedule_id),
    )
    conn.commit()
    if result.rowcount == 0:
        raise ValueError("schedule not found")
    from .postiz_sync import sync_schedule_to_postiz

    sync_schedule_to_postiz(conn, schedule_id)
    return {"id": schedule_id, "scheduled_at": _iso(parsed), "status": "scheduled"}


def update_schedule_platforms(conn: sqlite3.Connection, schedule_id: str, platforms: list[str]) -> dict:
    allowed = set(ALL_DELIVERY_PLATFORMS)
    normalized = [platform for platform in platforms if platform in allowed]
    if not normalized:
        raise ValueError("at least one publish platform is required")
    row = conn.execute(
        "SELECT candidate_id FROM scheduled_posts WHERE id = ?",
        (schedule_id,),
    ).fetchone()
    if not row:
        raise ValueError("schedule not found")
    orientation = candidate_orientation_for_id(conn, str(row["candidate_id"]))
    normalized = filter_platforms_for_orientation(normalized, orientation)
    if not normalized:
        raise ValueError("no publish platforms compatible with this clip orientation")
    result = conn.execute(
        """
        UPDATE scheduled_posts
        SET platforms_json = ?, last_error = '', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (json.dumps(normalized, ensure_ascii=False), schedule_id),
    )
    conn.commit()
    if result.rowcount == 0:
        raise ValueError("schedule not found")
    from .postiz_sync import sync_schedule_to_postiz

    sync_schedule_to_postiz(conn, schedule_id)
    return {"id": schedule_id, "platforms": normalized}


def unschedule_candidate(conn: sqlite3.Connection, candidate_id: str) -> dict:
    from .postiz_sync import cancel_postiz_for_candidate

    row = conn.execute("SELECT status, platform_results_json FROM scheduled_posts WHERE candidate_id = ?", (candidate_id,)).fetchone()
    if row:
        if str(row["status"] or "") in {"published", "live"}:
            raise ValueError("cannot unschedule a post that is already live")
        try:
            results = json.loads(row["platform_results_json"] or "{}")
        except json.JSONDecodeError:
            results = {}
        if isinstance(results, dict) and any(str((item or {}).get("status") or "").lower() in {"live", "published"} for item in results.values() if isinstance(item, dict)):
            raise ValueError("cannot unschedule: at least one destination is already live")
    cancel_postiz_for_candidate(conn, candidate_id)
    result = conn.execute("DELETE FROM scheduled_posts WHERE candidate_id = ?", (candidate_id,))
    conn.execute(
        "UPDATE clip_candidates SET status = 'approved' WHERE id = ? AND status IN ('scheduled', 'ready_to_publish')",
        (candidate_id,),
    )
    conn.commit()
    if result.rowcount == 0:
        raise ValueError("schedule not found")
    return {"candidate_id": candidate_id, "status": "approved"}
