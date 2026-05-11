"""Safe local env loading for optional provider keys."""

from __future__ import annotations

import os
from pathlib import Path


ALLOWED_ENV_KEYS = {
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_MODEL",
    "GROQ_API_KEY",
    "GROQ_MODEL",
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
        loaded[key] = "***REDACTED***" if key.endswith("API_KEY") else value
    return loaded
