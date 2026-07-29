"""Watch YouTube channels for new uploads and enqueue clip generation."""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .db import (
    DEFAULT_WORKSPACE_PROFILE_ID,
    connect,
    ensure_media_profile,
    ensure_source_manifest,
    fetch_all,
    fetch_one,
    initialize,
)
from .generation_jobs import create_generation_job
from .youtube_pipeline import find_ytdlp

DEFAULT_POLL_INTERVAL_MINUTES = 30
DEFAULT_PLAYLIST_END = 8


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _slug(value: str, fallback: str = "channel") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return (cleaned[:48] or fallback)


def normalize_channel_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        raise ValueError("channel_url is required")
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower().replace("www.", "")
    if host not in {"youtube.com", "m.youtube.com", "youtu.be"}:
        raise ValueError("only YouTube channel or playlist URLs are supported")
    path = parsed.path.rstrip("/")
    # Prefer uploads tab for channel URLs so flat-playlist lists newest videos.
    if "/playlist" in path or "list=" in (parsed.query or ""):
        return raw.split("#", 1)[0]
    if path.endswith("/videos"):
        return f"https://www.youtube.com{path}"
    if path.startswith("/@"):
        handle = path.split("/", 2)[1]
        return f"https://www.youtube.com/{handle}/videos"
    if path.startswith("/channel/") or path.startswith("/c/") or path.startswith("/user/"):
        return f"https://www.youtube.com{path}/videos"
    raise ValueError("provide a YouTube channel (@handle), /channel/…, or playlist URL")


def _row_to_watch(row: dict[str, Any] | sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["generation_defaults"] = json.loads(item.get("generation_defaults_json") or "{}")
    except json.JSONDecodeError:
        item["generation_defaults"] = {}
    item["enabled"] = bool(item.get("enabled"))
    return item


def list_watch_channels(conn: sqlite3.Connection, profile_id: str | None = None) -> list[dict[str, Any]]:
    if profile_id:
        rows = fetch_all(
            conn,
            """
            SELECT * FROM watch_channels
            WHERE profile_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (profile_id,),
        )
    else:
        rows = fetch_all(conn, "SELECT * FROM watch_channels ORDER BY created_at DESC, id DESC")
    return [_row_to_watch(row) for row in rows]


def get_watch_channel(conn: sqlite3.Connection, channel_id: str) -> dict[str, Any] | None:
    row = fetch_one(conn, "SELECT * FROM watch_channels WHERE id = ?", (channel_id,))
    return _row_to_watch(row) if row else None


def add_watch_channel(
    conn: sqlite3.Connection,
    *,
    channel_url: str,
    profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID,
    label: str = "",
    permission_status: str = "user_attested",
    poll_interval_minutes: int = DEFAULT_POLL_INTERVAL_MINUTES,
    generation_defaults: dict[str, Any] | None = None,
    bootstrap_seen: bool = True,
) -> dict[str, Any]:
    ensure_media_profile(conn, profile_id)
    normalized = normalize_channel_url(channel_url)
    existing = fetch_one(
        conn,
        "SELECT id FROM watch_channels WHERE profile_id = ? AND channel_url = ?",
        (profile_id, normalized),
    )
    if existing:
        raise ValueError("channel already watched in this workspace")

    channel_id = f"watch_{uuid.uuid4().hex[:12]}"
    display = (label or "").strip() or _slug(normalized.rsplit("/", 2)[-2] if "/@" in normalized else normalized)
    defaults = generation_defaults or {}
    conn.execute(
        """
        INSERT INTO watch_channels
          (id, profile_id, channel_url, label, permission_status, enabled,
           poll_interval_minutes, generation_defaults_json)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (
            channel_id,
            profile_id,
            normalized,
            display,
            permission_status or "user_attested",
            max(5, min(int(poll_interval_minutes or DEFAULT_POLL_INTERVAL_MINUTES), 24 * 60)),
            json.dumps(defaults, ensure_ascii=False),
        ),
    )
    source_id = f"{profile_id}_{_slug(display)}"
    ensure_source_manifest(conn, profile_id=profile_id, source_id=source_id, source_url=normalized)
    conn.commit()

    channel = get_watch_channel(conn, channel_id)
    assert channel is not None
    if bootstrap_seen:
        try:
            videos = list_channel_video_ids(normalized, limit=1)
            if videos:
                video = videos[0]
                conn.execute(
                    """
                    UPDATE watch_channels
                    SET last_seen_video_id = ?, last_polled_at = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (video["id"], _now_iso(), channel_id),
                )
                conn.commit()
                channel = get_watch_channel(conn, channel_id)
        except Exception as exc:  # noqa: BLE001 — surface as status, keep channel saved
            conn.execute(
                """
                UPDATE watch_channels
                SET last_error = ?, last_polled_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (str(exc)[:500], _now_iso(), channel_id),
            )
            conn.commit()
            channel = get_watch_channel(conn, channel_id)
    return channel or {}


def update_watch_channel(conn: sqlite3.Connection, channel_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    current = get_watch_channel(conn, channel_id)
    if not current:
        raise ValueError("watch channel not found")
    label = str(payload.get("label", current["label"])).strip() or current["label"]
    permission_status = str(payload.get("permission_status", current["permission_status"])).strip() or current["permission_status"]
    enabled = int(bool(payload["enabled"])) if "enabled" in payload else int(current["enabled"])
    poll_interval = max(
        5,
        min(int(payload.get("poll_interval_minutes", current["poll_interval_minutes"])), 24 * 60),
    )
    defaults = payload.get("generation_defaults", current.get("generation_defaults") or {})
    if not isinstance(defaults, dict):
        raise ValueError("generation_defaults must be an object")
    conn.execute(
        """
        UPDATE watch_channels
        SET label = ?, permission_status = ?, enabled = ?, poll_interval_minutes = ?,
            generation_defaults_json = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (label, permission_status, enabled, poll_interval, json.dumps(defaults, ensure_ascii=False), channel_id),
    )
    conn.commit()
    updated = get_watch_channel(conn, channel_id)
    if not updated:
        raise ValueError("watch channel not found")
    return updated


def delete_watch_channel(conn: sqlite3.Connection, channel_id: str) -> dict[str, Any]:
    result = conn.execute("DELETE FROM watch_channels WHERE id = ?", (channel_id,))
    conn.commit()
    if result.rowcount == 0:
        raise ValueError("watch channel not found")
    return {"id": channel_id, "deleted": True}


def list_channel_video_ids(channel_url: str, limit: int = DEFAULT_PLAYLIST_END) -> list[dict[str, str]]:
    ytdlp = find_ytdlp()
    cmd = [
        ytdlp,
        "--flat-playlist",
        "--playlist-end",
        str(max(1, min(limit, 50))),
        "--print",
        "%(id)s\t%(title)s\t%(webpage_url)s",
        "--no-warnings",
        channel_url,
    ]
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=120)
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "yt-dlp failed").strip()
        raise RuntimeError(err[:500])
    videos: list[dict[str, str]] = []
    for line in (completed.stdout or "").splitlines():
        parts = line.split("\t")
        if len(parts) < 1 or not parts[0].strip():
            continue
        video_id = parts[0].strip()
        title = parts[1].strip() if len(parts) > 1 else ""
        webpage = parts[2].strip() if len(parts) > 2 else f"https://www.youtube.com/watch?v={video_id}"
        if video_id in {"NA", "None"}:
            continue
        videos.append({"id": video_id, "title": title, "url": webpage})
    return videos


def _already_queued_or_clipped(conn: sqlite3.Connection, profile_id: str, video_url: str, video_id: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM generation_jobs
        WHERE profile_id = ? AND (source_url = ? OR source_url LIKE ?)
        LIMIT 1
        """,
        (profile_id, video_url, f"%{video_id}%"),
    ).fetchone()
    return bool(row)


def poll_watch_channel(
    conn: sqlite3.Connection,
    channel_id: str,
    *,
    enqueue: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    channel = get_watch_channel(conn, channel_id)
    if not channel:
        raise ValueError("watch channel not found")
    if not channel["enabled"] and not force:
        return {"channel": channel, "new_videos": [], "jobs": [], "skipped": "paused"}

    try:
        videos = list_channel_video_ids(channel["channel_url"], limit=DEFAULT_PLAYLIST_END)
    except Exception as exc:  # noqa: BLE001
        conn.execute(
            """
            UPDATE watch_channels
            SET last_error = ?, last_polled_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (str(exc)[:500], _now_iso(), channel_id),
        )
        conn.commit()
        raise

    last_seen = channel.get("last_seen_video_id") or ""
    new_videos: list[dict[str, str]] = []
    if not last_seen:
        # First successful poll without bootstrap: mark newest as seen, do not clip history.
        if videos:
            last_seen = videos[0]["id"]
    else:
        for video in videos:
            if video["id"] == last_seen:
                break
            new_videos.append(video)
        new_videos.reverse()  # oldest first for stable enqueue order

    jobs: list[dict[str, Any]] = []
    newest_id = videos[0]["id"] if videos else last_seen
    last_job_id = channel.get("last_clip_job_id") or ""
    last_new_id = channel.get("last_new_video_id") or ""
    last_new_at = channel.get("last_new_video_at") or ""

    if enqueue:
        defaults = dict(channel.get("generation_defaults") or {})
        profile_id = channel["profile_id"]
        for video in new_videos:
            if _already_queued_or_clipped(conn, profile_id, video["url"], video["id"]):
                continue
            source_id = f"{profile_id}_{video['id']}"
            ensure_source_manifest(conn, profile_id=profile_id, source_id=source_id, source_url=video["url"])
            payload = {
                **defaults,
                "source_url": video["url"],
                "profile_id": profile_id,
                "source_id": source_id,
            }
            job = create_generation_job(payload, start=True)
            jobs.append(job)
            last_job_id = str(job.get("id") or last_job_id)
            last_new_id = video["id"]
            last_new_at = _now_iso()

    conn.execute(
        """
        UPDATE watch_channels
        SET last_polled_at = ?,
            last_seen_video_id = ?,
            last_new_video_id = CASE WHEN ? != '' THEN ? ELSE last_new_video_id END,
            last_new_video_at = CASE WHEN ? != '' THEN ? ELSE last_new_video_at END,
            last_clip_job_id = CASE WHEN ? != '' THEN ? ELSE last_clip_job_id END,
            last_error = '',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            _now_iso(),
            newest_id or last_seen,
            last_new_id,
            last_new_id,
            last_new_at,
            last_new_at,
            last_job_id,
            last_job_id,
            channel_id,
        ),
    )
    conn.commit()
    return {
        "channel": get_watch_channel(conn, channel_id),
        "new_videos": new_videos,
        "jobs": jobs,
        "skipped": None,
    }


def poll_due_watch_channels(
    conn: sqlite3.Connection,
    *,
    profile_id: str | None = None,
    force: bool = False,
) -> list[dict[str, Any]]:
    channels = list_watch_channels(conn, profile_id=profile_id)
    results: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for channel in channels:
        if not channel["enabled"] and not force:
            continue
        if not force and channel.get("last_polled_at"):
            try:
                last = datetime.fromisoformat(channel["last_polled_at"])
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                age_minutes = (now - last.astimezone(timezone.utc)).total_seconds() / 60.0
                if age_minutes < float(channel.get("poll_interval_minutes") or DEFAULT_POLL_INTERVAL_MINUTES):
                    continue
            except ValueError:
                pass
        try:
            results.append(poll_watch_channel(conn, channel["id"], enqueue=True, force=force))
        except Exception as exc:  # noqa: BLE001
            results.append({"channel": get_watch_channel(conn, channel["id"]), "error": str(exc), "new_videos": [], "jobs": []})
    return results


def list_media_profiles(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    from .workspace_profiles import list_profiles

    return list_profiles(conn)


def list_publish_targets(conn: sqlite3.Connection, profile_id: str | None = None) -> list[dict[str, Any]]:
    if profile_id:
        rows = fetch_all(
            conn,
            "SELECT * FROM publish_targets WHERE profile_id = ? ORDER BY platform ASC, id ASC",
            (profile_id,),
        )
    else:
        rows = fetch_all(conn, "SELECT * FROM publish_targets ORDER BY profile_id ASC, platform ASC, id ASC")
    for row in rows:
        row["enabled"] = bool(row.get("enabled", 1))
        row["require_approval"] = bool(row.get("require_approval", 1))
        row["ai_disclosure_required"] = bool(row.get("ai_disclosure_required", 0))
    return rows


def update_publish_target(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    target_id = payload.get("id")
    profile_id = str(payload.get("profile_id") or "").strip()
    platform = str(payload.get("platform") or "").strip()
    if target_id is not None:
        row = fetch_one(conn, "SELECT * FROM publish_targets WHERE id = ?", (int(target_id),))
    elif profile_id and platform:
        row = fetch_one(
            conn,
            "SELECT * FROM publish_targets WHERE profile_id = ? AND platform = ?",
            (profile_id, platform),
        )
    else:
        raise ValueError("id or profile_id+platform is required")
    if not row:
        raise ValueError("publish target not found")

    account_label = str(payload.get("account_label", row["account_label"])).strip() or row["account_label"]
    mode = str(payload.get("mode", row["mode"])).strip() or row["mode"]
    require_approval = int(bool(payload["require_approval"])) if "require_approval" in payload else int(row["require_approval"])
    ai_disclosure = int(bool(payload["ai_disclosure_required"])) if "ai_disclosure_required" in payload else int(row["ai_disclosure_required"])
    daily_cap = max(0, min(int(payload.get("daily_cap", row["daily_cap"])), 50))
    enabled = int(bool(payload["enabled"])) if "enabled" in payload else int(row.get("enabled", 1))

    conn.execute(
        """
        UPDATE publish_targets
        SET account_label = ?, mode = ?, require_approval = ?, ai_disclosure_required = ?,
            daily_cap = ?, enabled = ?
        WHERE id = ?
        """,
        (account_label, mode, require_approval, ai_disclosure, daily_cap, enabled, row["id"]),
    )
    conn.commit()
    updated = fetch_one(conn, "SELECT * FROM publish_targets WHERE id = ?", (row["id"],))
    assert updated is not None
    updated["enabled"] = bool(updated.get("enabled", 1))
    return updated


def upsert_publish_target(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    profile_id = str(payload.get("profile_id") or "").strip()
    platform = str(payload.get("platform") or "").strip()
    if not profile_id or not platform:
        raise ValueError("profile_id and platform are required")
    ensure_media_profile(conn, profile_id)
    existing = fetch_one(
        conn,
        "SELECT id FROM publish_targets WHERE profile_id = ? AND platform = ?",
        (profile_id, platform),
    )
    if existing:
        return update_publish_target(conn, {**payload, "id": existing["id"]})
    conn.execute(
        """
        INSERT INTO publish_targets
          (profile_id, platform, account_label, mode, require_approval,
           ai_disclosure_required, daily_cap, enabled)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            profile_id,
            platform,
            str(payload.get("account_label") or platform).strip() or platform,
            str(payload.get("mode") or "review_required"),
            int(bool(payload.get("require_approval", True))),
            int(bool(payload.get("ai_disclosure_required", False))),
            max(0, min(int(payload.get("daily_cap", 2)), 50)),
            int(bool(payload.get("enabled", True))),
        ),
    )
    conn.commit()
    row = fetch_one(
        conn,
        "SELECT * FROM publish_targets WHERE profile_id = ? AND platform = ?",
        (profile_id, platform),
    )
    assert row is not None
    row["enabled"] = bool(row.get("enabled", 1))
    return row
