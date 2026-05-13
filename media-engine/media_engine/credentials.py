"""Credential presence checks for local publish connectors."""

from __future__ import annotations

import os
from typing import Any


PLATFORM_REQUIRED_ENV = {
    "telegram_channel": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID"],
    "youtube_shorts": ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"],
    "facebook_reels": ["META_PAGE_ID", "META_PAGE_ACCESS_TOKEN"],
    "tiktok": ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_ACCESS_TOKEN", "TIKTOK_REFRESH_TOKEN"],
}


def credential_status() -> dict[str, Any]:
    platforms: dict[str, Any] = {}
    for platform, keys in PLATFORM_REQUIRED_ENV.items():
        missing = [key for key in keys if not os.environ.get(key, "").strip()]
        platforms[platform] = {
            "ready": not missing,
            "required_keys": keys,
            "missing_keys": missing,
        }
    return {
        "platforms": platforms,
        "settings": {
            "nourbit_daily_content_cap": os.environ.get("NOURBIT_DAILY_CONTENT_CAP", "2"),
            "nourbit_default_publish_mode": os.environ.get("NOURBIT_DEFAULT_PUBLISH_MODE", "review_required"),
            "comment_automation_enabled": os.environ.get("COMMENT_AUTOMATION_ENABLED", "false"),
            "comment_automation_mode": os.environ.get("COMMENT_AUTOMATION_MODE", "review_required"),
        },
    }
