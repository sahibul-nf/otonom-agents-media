"""Publish approved content packages via Postiz.

Platform defaults (Review UI, no picker yet):
- text_only / short / long_form / clip → ``telegram_channel`` unless ``platform`` is set
- still / carousel → ``instagram`` (feed post / multi-image carousel) — map that channel in Publish first
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .content_package import ContentPackage
from .content_package_explainer import refresh_package_explainer_artifacts
from .content_package_store import get_package, save_package
from .postiz_client import (
    PostizError,
    build_create_text_post_body,
    channel_id_for_platform,
    create_post,
    extract_remote_id,
    publish_images,
    publish_video,
    validate_channel,
)

_IMAGE_FORMAT_DEFAULT_PLATFORMS = ("instagram", "instagram_reels", "telegram_channel")


def resolve_publish_platform(pkg: ContentPackage, platform: str, profile_id: str) -> str:
    explicit = (platform or "").strip()
    if explicit and explicit not in ("telegram_channel", "default"):
        return explicit
    if pkg.format in ("still", "carousel"):
        for candidate in _IMAGE_FORMAT_DEFAULT_PLATFORMS:
            if channel_id_for_platform(candidate, profile_id):
                return candidate
        return "instagram"
    return "telegram_channel"


def publish_content_package(
    package_id: str,
    *,
    platform: str,
    profile_id: str,
    post_type: str = "now",
    date_iso: str | None = None,
    db_path,
) -> dict[str, Any]:
    pkg = get_package(package_id, db_path=db_path)
    if not pkg:
        raise ValueError(f"package not found: {package_id}")
    pkg = refresh_package_explainer_artifacts(pkg, db_path=db_path)
    if pkg.status != "approved":
        raise ValueError("package must be approved before publish")

    platform = resolve_publish_platform(pkg, platform, profile_id)
    if pkg.format == "text_only":
        result = _publish_text(pkg, platform=platform, profile_id=profile_id, post_type=post_type, date_iso=date_iso)
    elif pkg.format == "still":
        paths = [p for p in pkg.artifacts.image_paths if p]
        if not paths or not all(_artifact_ready(p) for p in paths):
            raise ValueError("still image artifact is not ready — re-create or re-render the package")
        result = publish_images(
            platform,
            {
                "image_paths": paths,
                "caption": pkg.caption,
                "title": pkg.title or pkg.caption[:80],
            },
            profile_id=profile_id,
            post_type=post_type,
            date_iso=date_iso,
        )
    elif pkg.format == "carousel":
        paths = [p for p in pkg.artifacts.slide_paths if p]
        if len(paths) < 3 or not all(_artifact_ready(p) for p in paths):
            raise ValueError("carousel slides are not ready — need 3–5 rendered PNGs")
        result = publish_images(
            platform,
            {
                "image_paths": paths,
                "caption": pkg.caption,
                "title": pkg.title or pkg.caption[:80],
            },
            profile_id=profile_id,
            post_type=post_type,
            date_iso=date_iso,
        )
    elif pkg.format in ("short", "long_form", "clip"):
        video_path = pkg.artifacts.video_path
        if not video_path or not Path(video_path).exists() or Path(video_path).stat().st_size == 0:
            raise ValueError("video artifact is not ready — finish explainer render first")
        result = publish_video(
            platform,
            {
                "video_path": video_path,
                "caption": pkg.caption,
                "title": pkg.title or pkg.caption[:80],
            },
            profile_id=profile_id,
            post_type=post_type,
            date_iso=date_iso,
        )
    else:
        raise ValueError(f"auto-publish not supported for format {pkg.format} yet — use Postiz manually")

    pkg.status = "published"
    pkg.artifacts.package_meta = {
        **pkg.artifacts.package_meta,
        "last_publish": {"platform": platform, **{k: result.get(k) for k in ("status", "remote_id", "remote_url")}},
    }
    save_package(pkg, db_path=db_path)
    return {"package_id": package_id, "format": pkg.format, **result}


def _publish_text(
    pkg: ContentPackage,
    *,
    platform: str,
    profile_id: str,
    post_type: str,
    date_iso: str | None,
) -> dict[str, Any]:
    validate_channel(platform, profile_id)
    integration_id = channel_id_for_platform(platform, profile_id)
    body = build_create_text_post_body(
        integration_id=integration_id,
        caption=pkg.caption,
        platform=platform,
        title=pkg.title or pkg.caption[:80],
        post_type=post_type,
        date_iso=date_iso,
    )
    try:
        result = create_post(body, profile_id=profile_id)
    except PostizError as exc:
        raise ValueError(str(exc)) from exc
    remote_id = extract_remote_id(result)
    return {
        "platform": platform,
        "status": "accepted",
        "backend": "postiz",
        "remote_id": remote_id,
        "remote_url": "",
        "raw": result,
    }


def _artifact_ready(path: str) -> bool:
    p = Path(path)
    return p.is_file() and p.stat().st_size > 0
