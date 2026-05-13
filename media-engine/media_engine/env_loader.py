"""Safe local env loading for optional provider keys."""

from __future__ import annotations

import os
from pathlib import Path


ALLOWED_ENV_KEYS = {
    "COMMENT_AUTOMATION_ENABLED",
    "COMMENT_AUTOMATION_MODE",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_MODEL",
    "GROQ_API_KEY",
    "GROQ_MODEL",
    "META_API_VERSION",
    "META_APP_ID",
    "META_APP_SECRET",
    "META_PAGE_ACCESS_TOKEN",
    "META_PAGE_ID",
    "NOURBIT_DAILY_CONTENT_CAP",
    "NOURBIT_DEFAULT_PUBLISH_MODE",
    "NOURBIT_YOUTUBE_CHANNEL_ID",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHANNEL_ID",
    "TIKTOK_ACCESS_TOKEN",
    "TIKTOK_CLIENT_KEY",
    "TIKTOK_CLIENT_SECRET",
    "TIKTOK_DEFAULT_VISIBILITY",
    "TIKTOK_OPEN_ID",
    "TIKTOK_REFRESH_TOKEN",
    "YOUTUBE_CLIENT_ID",
    "YOUTUBE_CLIENT_SECRET",
    "YOUTUBE_PRIVACY_STATUS",
    "YOUTUBE_REFRESH_TOKEN",
}

SECRET_ENV_KEYS = {
    "DEEPSEEK_API_KEY",
    "GROQ_API_KEY",
    "META_APP_SECRET",
    "META_PAGE_ACCESS_TOKEN",
    "OPENAI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TIKTOK_ACCESS_TOKEN",
    "TIKTOK_CLIENT_SECRET",
    "TIKTOK_REFRESH_TOKEN",
    "YOUTUBE_CLIENT_SECRET",
    "YOUTUBE_REFRESH_TOKEN",
}


def load_env_file(path: str | Path | None) -> dict[str, str]:
    if not path:
        return {}
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(f"env file not found: {env_path}")
    loaded: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in ALLOWED_ENV_KEYS:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value
        loaded[key] = "***REDACTED***" if key in SECRET_ENV_KEYS else value
    return loaded
