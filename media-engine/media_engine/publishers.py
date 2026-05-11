"""Dry-run publishing adapters and payload builders."""

from __future__ import annotations

import json
import uuid
from typing import Any

from .post_copy import build_post_caption
from .rights import can_publish_candidate


def build_payload(platform: str, candidate: dict[str, Any], render_job: dict[str, Any] | None) -> dict[str, Any]:
    output_path = render_job["output_path"] if render_job else ""
    caption = build_post_caption(candidate, render_job, platform)
    base = {
        "platform": platform,
        "candidate_id": candidate["id"],
        "video_path": output_path,
        "caption": caption,
        "dry_run": True,
    }

    if platform == "facebook_reels":
        return {**base, "endpoint": "meta-video-api/reels", "page_type": "facebook_page"}
    if platform == "youtube_shorts":
        return {**base, "endpoint": "youtube-data-api/videos.insert", "privacy_status": "private"}
    if platform == "tiktok":
        return {**base, "endpoint": "tiktok-content-posting/direct-post", "visibility": "private"}
    if platform == "telegram_channel":
        return {**base, "endpoint": "telegram-bot-api/sendVideo", "parse_mode": "HTML", "supports_streaming": True}
    if platform == "instagram_reels":
        return {**base, "endpoint": "instagram-graph-api/content-publishing", "media_type": "REELS"}
    raise ValueError(f"unsupported platform: {platform}")


def create_dry_run_attempt(
    conn,
    source: dict[str, Any],
    target: dict[str, Any],
    candidate: dict[str, Any],
    render_job: dict[str, Any] | None,
) -> dict[str, Any]:
    guard = can_publish_candidate(source, target, candidate)
    payload = build_payload(target["platform"], candidate, render_job)
    attempt = {
        "id": f"pub_{uuid.uuid4().hex[:12]}",
        "candidate_id": candidate["id"],
        "platform": target["platform"],
        "mode": target["mode"],
        "status": "ready" if guard.allowed else "blocked",
        "payload_json": json.dumps(payload, indent=2, ensure_ascii=False),
        "error": "" if guard.allowed else guard.reason,
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
