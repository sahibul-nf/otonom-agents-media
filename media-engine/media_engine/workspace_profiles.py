"""CRUD helpers for dashboard media workspaces (media_profiles)."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from .credential_vault import delete_profile_vault, ensure_profile_vault
from .db import DEFAULT_WORKSPACE_PROFILE_ID, ensure_media_profile, fetch_all, fetch_one
from .publish_platforms import is_publish_platform_disabled

PROTECTED_PROFILE_IDS = frozenset({"nourbit", DEFAULT_WORKSPACE_PROFILE_ID})
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,39}$")

# Live publish destinations shown on Channels (matches dashboard publishPlatforms).
_DEFAULT_PUBLISH_PLATFORM_LABELS: tuple[tuple[str, str], ...] = (
    ("telegram_channel", "{name} Telegram"),
    ("youtube_shorts", "{name} YouTube Shorts"),
    ("youtube_video", "{name} YouTube Video"),
    ("facebook_reels", "{name} Facebook Reels"),
    ("instagram", "{name} Instagram"),
    ("tiktok", "{name} TikTok"),
)

DEFAULT_PUBLISH_PLATFORMS: tuple[tuple[str, str], ...] = _DEFAULT_PUBLISH_PLATFORM_LABELS


class WorkspaceProfileError(ValueError):
    """Raised for invalid workspace profile operations."""


def slugify_profile_id(value: str) -> str:
    text = (value or "").strip().lower()
    parts: list[str] = []
    for ch in text:
        if ch.isalnum():
            parts.append(ch)
        elif ch in {"-", "_", " ", "."}:
            parts.append("_")
    slug = re.sub(r"_+", "_", "".join(parts)).strip("_")
    return slug[:40]


def validate_profile_id(profile_id: str) -> str:
    profile_id = (profile_id or "").strip().lower()
    if not _SLUG_RE.fullmatch(profile_id):
        raise WorkspaceProfileError(
            "Workspace id must be 2–40 chars: lowercase letters, numbers, underscore, or hyphen."
        )
    return profile_id


def _normalize_languages(raw: Any) -> list[str]:
    if isinstance(raw, str):
        items = [part.strip() for part in raw.replace(",", " ").split() if part.strip()]
    elif isinstance(raw, list):
        items = [str(part).strip() for part in raw if str(part).strip()]
    else:
        items = []
    return items or ["id", "en"]


def _row_to_profile(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    languages: list[str] = []
    try:
        parsed = json.loads(row.get("languages_json") or "[]")
        if isinstance(parsed, list):
            languages = [str(item) for item in parsed if str(item).strip()]
    except (TypeError, json.JSONDecodeError):
        languages = ["id", "en"]
    profile_id = str(row["id"])
    return {
        "id": profile_id,
        "name": row.get("name") or profile_id,
        "niche": row.get("niche") or "",
        "languages": languages or ["id", "en"],
        "default_render_preset": row.get("default_render_preset") or "short_clean",
        "cta_text": row.get("cta_text") or "",
        "watermark_text": row.get("watermark_text") or "",
        "created_at": row.get("created_at") or "",
        "protected": profile_id in PROTECTED_PROFILE_IDS,
    }


def _insert_publish_target(conn: sqlite3.Connection, profile_id: str, platform: str, label: str) -> None:
    unavailable = is_publish_platform_disabled(platform)
    conn.execute(
        """
        INSERT INTO publish_targets
          (profile_id, platform, account_label, mode, require_approval,
           ai_disclosure_required, daily_cap, enabled)
        VALUES (?, ?, ?, ?, 1, 0, 2, ?)
        """,
        (
            profile_id,
            platform,
            label,
            "off" if unavailable else "review_required",
            0 if unavailable else 1,
        ),
    )


def sync_missing_publish_targets(
    conn: sqlite3.Connection,
    profile_id: str,
    *,
    display_name: str | None = None,
) -> list[str]:
    """Insert any newly added platform rows for workspaces that already have targets."""
    profile_id = (profile_id or "").strip()
    if not profile_id:
        return []
    existing = {
        str(row[0])
        for row in conn.execute(
            "SELECT platform FROM publish_targets WHERE profile_id = ?",
            (profile_id,),
        ).fetchall()
    }
    if not existing:
        return []
    profile = get_profile(conn, profile_id)
    name = (display_name or (profile or {}).get("name") or profile_id).strip() or profile_id
    created: list[str] = []
    for platform, label_template in DEFAULT_PUBLISH_PLATFORMS:
        if platform in existing:
            continue
        _insert_publish_target(conn, profile_id, platform, label_template.format(name=name))
        created.append(platform)
    if created:
        conn.commit()
    return created


def ensure_default_publish_targets(
    conn: sqlite3.Connection,
    profile_id: str,
    *,
    display_name: str | None = None,
) -> list[str]:
    """If a workspace has zero publish destinations, seed all live platforms."""
    profile_id = (profile_id or "").strip()
    if not profile_id:
        return []
    count_row = conn.execute(
        "SELECT COUNT(*) FROM publish_targets WHERE profile_id = ?",
        (profile_id,),
    ).fetchone()
    if int(count_row[0] if count_row else 0) > 0:
        return sync_missing_publish_targets(conn, profile_id, display_name=display_name)

    profile = get_profile(conn, profile_id)
    name = (display_name or (profile or {}).get("name") or profile_id).strip() or profile_id
    created: list[str] = []
    for platform, label_template in DEFAULT_PUBLISH_PLATFORMS:
        _insert_publish_target(conn, profile_id, platform, label_template.format(name=name))
        created.append(platform)
    if created:
        conn.commit()
    return created


def list_profiles(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    ensure_media_profile(conn, "nourbit")
    ensure_media_profile(conn, DEFAULT_WORKSPACE_PROFILE_ID)
    rows = fetch_all(
        conn,
        """
        SELECT id, name, niche, languages_json, default_render_preset,
               cta_text, watermark_text, created_at
        FROM media_profiles
        ORDER BY name ASC
        """,
    )
    profiles = [_row_to_profile(row) for row in rows if row]
    for profile in profiles:
        ensure_default_publish_targets(conn, profile["id"], display_name=profile.get("name"))
    return profiles


def get_profile(conn: sqlite3.Connection, profile_id: str) -> dict[str, Any] | None:
    row = fetch_one(
        conn,
        """
        SELECT id, name, niche, languages_json, default_render_preset,
               cta_text, watermark_text, created_at
        FROM media_profiles WHERE id = ?
        """,
        (profile_id,),
    )
    return _row_to_profile(row)


def profile_usage(conn: sqlite3.Connection, profile_id: str) -> dict[str, int]:
    def _count(query: str) -> int:
        row = conn.execute(query, (profile_id,)).fetchone()
        return int(row[0] if row else 0)

    return {
        "clips": _count("SELECT COUNT(*) FROM clip_candidates WHERE profile_id = ?"),
        "scheduled_posts": _count("SELECT COUNT(*) FROM scheduled_posts WHERE profile_id = ?"),
        "watch_channels": _count("SELECT COUNT(*) FROM watch_channels WHERE profile_id = ?"),
        "generation_jobs": _count("SELECT COUNT(*) FROM generation_jobs WHERE profile_id = ?"),
        "sources": _count("SELECT COUNT(*) FROM source_manifests WHERE profile_id = ?"),
        "publish_targets": _count("SELECT COUNT(*) FROM publish_targets WHERE profile_id = ?"),
    }


def create_profile(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise WorkspaceProfileError("name is required")
    requested_id = str(payload.get("id") or "").strip() or slugify_profile_id(name)
    profile_id = validate_profile_id(requested_id)
    if get_profile(conn, profile_id):
        raise WorkspaceProfileError(f"Workspace '{profile_id}' already exists")

    niche = str(payload.get("niche") or "General short-form clips").strip() or "General short-form clips"
    languages = _normalize_languages(payload.get("languages"))
    preset = str(payload.get("default_render_preset") or "short_clean").strip() or "short_clean"
    cta_text = str(payload.get("cta_text") or "").strip()
    watermark_text = str(payload.get("watermark_text") or "").strip()

    conn.execute(
        """
        INSERT INTO media_profiles
          (id, name, niche, languages_json, default_render_preset, cta_text, watermark_text)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            profile_id,
            name,
            niche,
            json.dumps(languages, ensure_ascii=False),
            preset,
            cta_text,
            watermark_text,
        ),
    )
    conn.commit()
    ensure_profile_vault(profile_id)
    ensure_default_publish_targets(conn, profile_id, display_name=name)
    profile = get_profile(conn, profile_id)
    if not profile:
        raise WorkspaceProfileError("Failed to create workspace")
    return profile


def update_profile(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    profile_id = str(payload.get("id") or payload.get("profile_id") or "").strip()
    if not profile_id:
        raise WorkspaceProfileError("id is required")
    existing = get_profile(conn, profile_id)
    if not existing:
        raise WorkspaceProfileError(f"Workspace '{profile_id}' not found")

    name = str(payload.get("name") if "name" in payload else existing["name"]).strip()
    if not name:
        raise WorkspaceProfileError("name is required")
    niche = str(payload.get("niche") if "niche" in payload else existing["niche"]).strip()
    languages = (
        _normalize_languages(payload.get("languages"))
        if "languages" in payload
        else list(existing.get("languages") or ["id", "en"])
    )
    preset = str(
        payload.get("default_render_preset")
        if "default_render_preset" in payload
        else existing.get("default_render_preset") or "short_clean"
    ).strip() or "short_clean"
    cta_text = str(payload.get("cta_text") if "cta_text" in payload else existing.get("cta_text") or "").strip()
    watermark_text = str(
        payload.get("watermark_text") if "watermark_text" in payload else existing.get("watermark_text") or ""
    ).strip()

    conn.execute(
        """
        UPDATE media_profiles
        SET name = ?, niche = ?, languages_json = ?, default_render_preset = ?,
            cta_text = ?, watermark_text = ?
        WHERE id = ?
        """,
        (
            name,
            niche or existing["niche"],
            json.dumps(languages, ensure_ascii=False),
            preset,
            cta_text,
            watermark_text,
            profile_id,
        ),
    )
    conn.commit()
    profile = get_profile(conn, profile_id)
    if not profile:
        raise WorkspaceProfileError("Failed to update workspace")
    return profile


def delete_profile(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    profile_id = str(payload.get("id") or payload.get("profile_id") or "").strip()
    if not profile_id:
        raise WorkspaceProfileError("id is required")
    existing = get_profile(conn, profile_id)
    if not existing:
        raise WorkspaceProfileError(f"Workspace '{profile_id}' not found")
    if profile_id in PROTECTED_PROFILE_IDS:
        raise WorkspaceProfileError(
            f"Built-in workspace '{profile_id}' cannot be deleted. Rename it instead, or create a new workspace."
        )

    force = bool(payload.get("force", False))
    confirm = str(payload.get("confirm") or "").strip()
    if confirm != profile_id:
        raise WorkspaceProfileError(f"confirm must match workspace id '{profile_id}'")

    usage = profile_usage(conn, profile_id)
    has_data = any(usage[key] > 0 for key in ("clips", "scheduled_posts", "watch_channels", "generation_jobs", "sources"))
    if has_data and not force:
        raise WorkspaceProfileError(
            "Workspace still has clips, schedule, watch channels, or sources. "
            "Pass force=true to permanently delete related data."
        )

    candidate_ids = [
        str(row["id"])
        for row in fetch_all(conn, "SELECT id FROM clip_candidates WHERE profile_id = ?", (profile_id,))
    ]
    try:
        if candidate_ids:
            placeholders = ",".join("?" for _ in candidate_ids)
            conn.execute(f"DELETE FROM scheduled_posts WHERE candidate_id IN ({placeholders})", tuple(candidate_ids))
            conn.execute(f"DELETE FROM rerender_jobs WHERE candidate_id IN ({placeholders})", tuple(candidate_ids))
            conn.execute(f"DELETE FROM publish_attempts WHERE candidate_id IN ({placeholders})", tuple(candidate_ids))
            conn.execute(f"DELETE FROM render_jobs WHERE candidate_id IN ({placeholders})", tuple(candidate_ids))
            conn.execute(f"DELETE FROM clip_candidates WHERE id IN ({placeholders})", tuple(candidate_ids))
        conn.execute("DELETE FROM scheduled_posts WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM generation_jobs WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM watch_channels WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM autonomy_settings WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM publish_targets WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM source_manifests WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM media_profiles WHERE id = ?", (profile_id,))
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise WorkspaceProfileError(f"Failed to delete workspace: {exc}") from exc

    vault_removed = delete_profile_vault(profile_id)
    return {
        "id": profile_id,
        "deleted": True,
        "force": force,
        "usage": usage,
        "vault_removed": vault_removed,
    }
