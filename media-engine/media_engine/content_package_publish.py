"""Publish approved content packages via Postiz."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .content_package import ContentPackage
from .content_package_explainer import refresh_package_explainer_artifacts
from .content_package_store import get_package, save_package
from .postiz_client import PostizError, build_create_text_post_body, channel_id_for_platform, create_post, extract_remote_id, publish_video, validate_channel


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

    platform = (platform or "telegram_channel").strip()
    if pkg.format == "text_only":
        result = _publish_text(pkg, platform=platform, profile_id=profile_id, post_type=post_type, date_iso=date_iso)
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
