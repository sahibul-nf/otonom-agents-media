"""One-click shorts from approved long-form candidates (issue #85)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .db import ARTIFACTS_DIR, DEFAULT_DB, connect, fetch_one, initialize
from .generation_jobs import create_generation_job
from .genres import normalize_genres
from .ingest_longform import clip_batch_from_local_path
from .publish_delivery import candidate_delivery_orientation, latest_render_job
from .source_resolve import normalize_youtube_video_url
from .workspace_profiles import get_profile

YOUTUBE_HOST_MARKERS = ("youtube.com", "youtu.be", "m.youtube.com", "music.youtube.com")
YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


class LongformShortsError(ValueError):
    """Raised when a long-form candidate cannot enqueue shorts."""


def _loads(value: Any, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return fallback or {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback or {}
    return parsed if isinstance(parsed, dict) else (fallback or {})


def is_longform_candidate(candidate: dict[str, Any], render_job: dict[str, Any] | None = None) -> bool:
    return candidate_delivery_orientation(candidate, render_job) == "landscape"


def _is_youtube_url(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.netloc or "").lower().replace("www.", "")
    return any(marker in host for marker in YOUTUBE_HOST_MARKERS)


def _youtube_video_id(url: str) -> str:
    canonical = normalize_youtube_video_url(url)
    video_id = (parse_qs(urlparse(canonical).query).get("v") or [""])[0].strip()
    if not YOUTUBE_VIDEO_ID_RE.fullmatch(video_id):
        raise LongformShortsError("Published YouTube link is missing a valid video id.")
    return video_id


def _published_youtube_url(conn, candidate_id: str) -> str | None:
    row = conn.execute(
        """
        SELECT payload_json
        FROM publish_attempts
        WHERE candidate_id = ?
          AND platform IN ('youtube_video', 'youtube_shorts')
          AND status = 'published'
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (candidate_id,),
    ).fetchone()
    if not row:
        return None
    payload = _loads(row["payload_json"])
    live = payload.get("live_result") if isinstance(payload.get("live_result"), dict) else {}
    remote_url = str((live or {}).get("remote_url") or "").strip()
    if remote_url and _is_youtube_url(remote_url):
        return remote_url
    remote_id = str((live or {}).get("remote_id") or "").strip()
    if remote_id and YOUTUBE_VIDEO_ID_RE.fullmatch(remote_id):
        return f"https://www.youtube.com/watch?v={remote_id}"
    return None


def _local_source_path(candidate: dict[str, Any], render_job: dict[str, Any] | None) -> Path | None:
    candidates: list[str] = []
    if render_job:
        candidates.append(str(render_job.get("output_path") or ""))
    candidates.append(str(candidate.get("output_path") or ""))
    metadata = _loads(candidate.get("curation_metadata_json"))
    if not metadata and isinstance(candidate.get("curation_metadata"), dict):
        metadata = candidate["curation_metadata"]
    job_id = str(metadata.get("job_id") or "").strip()
    profile_id = str(candidate.get("profile_id") or "").strip()
    if job_id and profile_id:
        candidates.append(str(ARTIFACTS_DIR / profile_id / "ingest" / job_id / "source.mp4"))
    for value in candidates:
        path = Path(value).expanduser()
        if value and path.exists() and path.is_file():
            return path
    return None


def resolve_longform_shorts_source(conn, candidate_id: str) -> dict[str, Any]:
    candidate = fetch_one(conn, "SELECT * FROM clip_candidates WHERE id = ?", (candidate_id,))
    if not candidate:
        raise LongformShortsError("candidate not found")
    render_job = latest_render_job(conn, candidate_id)
    candidate = dict(candidate)
    if not is_longform_candidate(candidate, render_job):
        raise LongformShortsError("Make shorts is only available for landscape long-form clips")

    profile_id = str(candidate.get("profile_id") or "").strip()
    title = str(candidate.get("title_hook") or "Long-form video").strip() or "Long-form video"
    source_id = str(candidate.get("source_id") or "").strip()

    published_url = _published_youtube_url(conn, candidate_id)
    if published_url:
        return {
            "source_type": "youtube",
            "source_url": published_url,
            "profile_id": profile_id,
            "source_id": source_id,
            "title": title,
            "parent_candidate_id": candidate_id,
        }

    source_row = fetch_one(conn, "SELECT source_url FROM source_manifests WHERE id = ?", (source_id,)) if source_id else None
    manifest_url = str((source_row or {}).get("source_url") or "").strip()
    if manifest_url and _is_youtube_url(manifest_url):
        return {
            "source_type": "youtube",
            "source_url": manifest_url,
            "profile_id": profile_id,
            "source_id": source_id,
            "title": title,
            "parent_candidate_id": candidate_id,
        }

    local_path = _local_source_path(candidate, render_job)
    if local_path:
        metadata = _loads(candidate.get("curation_metadata_json"))
        return {
            "source_type": "local",
            "local_path": str(local_path),
            "profile_id": profile_id,
            "source_id": source_id,
            "title": title,
            "parent_candidate_id": candidate_id,
            "job_id": str(metadata.get("job_id") or "").strip() or None,
        }

    raise LongformShortsError(
        "No usable source for shorts yet. Publish to YouTube first, or re-ingest when the local file is still available."
    )


def _generation_defaults(profile_id: str, *, count: int) -> dict[str, Any]:
    conn = connect(DEFAULT_DB)
    initialize(conn)
    profile = get_profile(conn, profile_id) or {}
    niche = str(profile.get("niche") or "").strip()
    return {
        "count": count,
        "clip_length_preset": "auto",
        "hyperframes_format": "short_9_16",
        "brand_template": "auto",
        "hyperframes_template": "auto",
        "brand_system_template_id": "",
        "renderer": "hyperframes",
        "quality": "production",
        "caption_source": "hybrid",
        "asr_model": "medium",
        "speech_language": "auto",
        "transcript_languages": "auto",
        "llm_provider": "deepseek",
        "genres": normalize_genres(None, profile_id=profile_id, niche=niche or None),
        "niche": niche,
        "workspace_name": str(profile.get("name") or profile_id),
        "env_file": "../.env.local",
    }


def make_shorts_from_longform(
    candidate_id: str,
    *,
    count: int = 5,
    language: str = "id",
    db_path: str | Path = DEFAULT_DB,
) -> dict[str, Any]:
    """Enqueue shorts from an approved long-form candidate without manual URL copy."""
    conn = connect(db_path)
    initialize(conn)
    resolved = resolve_longform_shorts_source(conn, candidate_id)
    profile_id = str(resolved.get("profile_id") or "").strip()
    count = max(1, min(int(count), 10))

    if resolved["source_type"] == "youtube":
        source_url = str(resolved["source_url"])
        video_id = _youtube_video_id(source_url)
        canonical_url = f"https://www.youtube.com/watch?v={video_id}"
        defaults = _generation_defaults(profile_id, count=count)
        job = create_generation_job(
            {
                **defaults,
                "profile_id": profile_id,
                "source_url": canonical_url,
                "source_id": f"{profile_id}_{video_id}",
                "source_metadata": {
                    "provider": "youtube",
                    "video_id": video_id,
                    "title": resolved.get("title") or "",
                    "canonical_url": canonical_url,
                },
                "parent_candidate_id": candidate_id,
            },
            start=True,
        )
        return {
            "ok": True,
            "route": "generation_job",
            "parent_candidate_id": candidate_id,
            "generation_job_id": job["id"],
            "source_url": canonical_url,
            "message": "Shorts batch queued from published YouTube source. Open Create to watch progress.",
        }

    local_path = Path(str(resolved["local_path"]))
    source_id = str(resolved.get("source_id") or "").strip()
    if not source_id:
        raise LongformShortsError("long-form source id is missing")
    batch = clip_batch_from_local_path(
        local_path=local_path,
        profile_id=profile_id,
        source_id=source_id,
        title=str(resolved.get("title") or ""),
        count=count,
        language=language,
        db_path=db_path,
        parent_candidate_id=candidate_id,
        job_id=resolved.get("job_id"),
    )
    return {
        "ok": True,
        "route": "clip_batch",
        "parent_candidate_id": candidate_id,
        "candidate_ids": batch["candidate_ids"],
        "source_id": source_id,
        "message": "Short clips cut into Review. Re-render with HyperFrames from Review if needed.",
    }
