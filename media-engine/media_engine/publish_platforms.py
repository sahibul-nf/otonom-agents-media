"""Operator-facing publish destinations (Channels / Schedule / Publish)."""

from __future__ import annotations

# Native TikTok OAuth / Content Posting API is not supported in this repo (dev app removed).
# If TikTok returns via Postiz, map a Postiz channel — do not register a local TikTok developer app here.
DISABLED_PUBLISH_PLATFORMS: frozenset[str] = frozenset({"tiktok"})

DISABLED_PUBLISH_PLATFORM_REASONS: dict[str, str] = {
    "tiktok": (
        "Native TikTok OAuth is not supported (developer app removed). "
        "Post manually in the TikTok app, or map TikTok in Postiz when that connector is available."
    ),
}

_ALL_OPERATOR_PLATFORMS: tuple[str, ...] = (
    "telegram_channel",
    "youtube_shorts",
    "youtube_video",
    "facebook_reels",
    "tiktok",
)

OPERATOR_PUBLISH_PLATFORMS: tuple[str, ...] = tuple(
    platform for platform in _ALL_OPERATOR_PLATFORMS if platform not in DISABLED_PUBLISH_PLATFORMS
)

ALL_PUBLISH_DESTINATION_PLATFORMS: tuple[str, ...] = _ALL_OPERATOR_PLATFORMS


def is_publish_platform_disabled(platform: str) -> bool:
    return platform in DISABLED_PUBLISH_PLATFORMS


def disabled_publish_platform_reason(platform: str) -> str:
    return DISABLED_PUBLISH_PLATFORM_REASONS.get(platform, "This destination is temporarily unavailable.")


def is_operator_publish_platform(platform: str) -> bool:
    return platform in OPERATOR_PUBLISH_PLATFORMS


def filter_operator_platforms(platforms: list[str]) -> list[str]:
    return [platform for platform in platforms if is_operator_publish_platform(platform)]
