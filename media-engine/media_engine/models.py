"""Shared constants and validation helpers for the media engine."""

from __future__ import annotations

from dataclasses import dataclass


RIGHTS_OWN_CHANNEL = "own_channel"
RIGHTS_AUTHORIZED_COMMUNITY = "authorized_community"
RIGHTS_PUBLIC_THIRD_PARTY = "public_third_party"
RIGHTS_USER_UPLOAD = "user_upload"

RIGHTS_MODES = {
    RIGHTS_OWN_CHANNEL,
    RIGHTS_AUTHORIZED_COMMUNITY,
    RIGHTS_PUBLIC_THIRD_PARTY,
    RIGHTS_USER_UPLOAD,
}

PUBLISH_OFF = "off"
PUBLISH_EXPORT_ONLY = "export_only"
PUBLISH_REVIEW_REQUIRED = "review_required"
PUBLISH_AUTO = "auto_publish"

PUBLISH_MODES = {
    PUBLISH_OFF,
    PUBLISH_EXPORT_ONLY,
    PUBLISH_REVIEW_REQUIRED,
    PUBLISH_AUTO,
}

STATUS_DRAFT = "draft"
STATUS_RENDERED = "rendered"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_SCHEDULED = "scheduled"
STATUS_PUBLISHED = "published"
STATUS_FAILED = "failed"

APPROVAL_STATUSES = {
    STATUS_DRAFT,
    STATUS_RENDERED,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_SCHEDULED,
    STATUS_PUBLISHED,
    STATUS_FAILED,
}

PLATFORM_FACEBOOK = "facebook_reels"
PLATFORM_YOUTUBE = "youtube_shorts"
PLATFORM_TIKTOK = "tiktok"
PLATFORM_INSTAGRAM = "instagram_reels"
PLATFORM_TELEGRAM = "telegram_channel"

PLATFORMS = {
    PLATFORM_FACEBOOK,
    PLATFORM_YOUTUBE,
    PLATFORM_TIKTOK,
    PLATFORM_INSTAGRAM,
    PLATFORM_TELEGRAM,
}


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    reason: str


def require_choice(value: str, allowed: set[str], field_name: str) -> str:
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name} must be one of: {choices}")
    return value
