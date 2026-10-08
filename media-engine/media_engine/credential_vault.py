"""Workspace-scoped publish credential vault (local JSON, gitignored under data/)."""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator

from .db import ROOT
from .env_loader import ALLOWED_ENV_KEYS, load_env_file

VAULT_DIR = ROOT / "data" / "credentials"
DEFAULT_MIGRATE_PROFILE = "nourbit"
_lock = threading.RLock()
_active_profile: ContextVar[str | None] = ContextVar("credential_profile", default=None)

# App-level OAuth client config stays in global .env; account tokens live in the vault.
LLM_ENV_KEYS = frozenset(
    {
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "GROQ_API_KEY",
        "OTONOM_LLM_AGENT_COMMAND",
        "OTONOM_LLM_AGENT_CONNECTOR",
        "OTONOM_LLM_AGENT_LAST_ERROR",
        "OTONOM_LLM_AGENT_TEST_OK",
    }
)

ACCOUNT_ENV_KEYS = {
    *LLM_ENV_KEYS,
    "META_PAGE_ID",
    "META_PAGE_ACCESS_TOKEN",
    "NOURBIT_FACEBOOK_PAGE_ID",
    "NOURBIT_FACEBOOK_PAGE_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHANNEL_ID",
    "TELEGRAM_CHAT_ID",
    "TIKTOK_ACCESS_TOKEN",
    "TIKTOK_REFRESH_TOKEN",
    "TIKTOK_OPEN_ID",
    "YOUTUBE_REFRESH_TOKEN",
    "NOURBIT_YOUTUBE_CHANNEL_ID",
    "POSTIZ_API_URL",
    "POSTIZ_API_KEY",
    "POSTIZ_CHANNEL_MAP",
}

PLATFORM_ACCOUNT_KEYS: dict[str, list[str]] = {
    "telegram_channel": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID", "TELEGRAM_CHAT_ID"],
    "youtube_shorts": ["YOUTUBE_REFRESH_TOKEN"],
    "youtube_video": ["YOUTUBE_REFRESH_TOKEN"],
    "facebook_reels": ["META_PAGE_ID", "META_PAGE_ACCESS_TOKEN", "NOURBIT_FACEBOOK_PAGE_ID", "NOURBIT_FACEBOOK_PAGE_TOKEN"],
    "tiktok": ["TIKTOK_ACCESS_TOKEN", "TIKTOK_REFRESH_TOKEN", "TIKTOK_OPEN_ID"],
    "instagram": [],
}

PLATFORM_REQUIRED_GROUPS: dict[str, list[list[str]]] = {
    "telegram_channel": [["TELEGRAM_BOT_TOKEN"], ["TELEGRAM_CHANNEL_ID", "TELEGRAM_CHAT_ID"]],
    "youtube_shorts": [["YOUTUBE_CLIENT_ID"], ["YOUTUBE_CLIENT_SECRET"], ["YOUTUBE_REFRESH_TOKEN"]],
    "youtube_video": [["YOUTUBE_CLIENT_ID"], ["YOUTUBE_CLIENT_SECRET"], ["YOUTUBE_REFRESH_TOKEN"]],
    "facebook_reels": [
        ["META_PAGE_ID", "NOURBIT_FACEBOOK_PAGE_ID"],
        ["META_PAGE_ACCESS_TOKEN", "NOURBIT_FACEBOOK_PAGE_TOKEN"],
    ],
    "tiktok": [["TIKTOK_CLIENT_KEY"], ["TIKTOK_CLIENT_SECRET"], ["TIKTOK_ACCESS_TOKEN"], ["TIKTOK_REFRESH_TOKEN"]],
    # Postiz-only — native keys intentionally absent; map channel in Publish.
    "instagram": [["OTONOM_POSTIZ_INSTAGRAM_CHANNEL"]],
}


def _vault_path(profile_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in profile_id.strip()) or "workspace"
    return VAULT_DIR / f"{safe}.json"


def active_profile_id() -> str | None:
    return _active_profile.get()


@contextmanager
def use_profile_credentials(profile_id: str | None) -> Iterator[str | None]:
    token = _active_profile.set((profile_id or "").strip() or None)
    try:
        yield _active_profile.get()
    finally:
        _active_profile.reset(token)


def get_profile_secrets(profile_id: str) -> dict[str, str]:
    path = _vault_path(profile_id)
    if not path.exists():
        return {}
    with _lock:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    if not isinstance(payload, dict):
        return {}
    secrets: dict[str, str] = {}
    for key, value in payload.items():
        if key not in ALLOWED_ENV_KEYS and key not in ACCOUNT_ENV_KEYS:
            continue
        text = str(value or "").strip()
        if text:
            secrets[str(key)] = text
    return secrets


def set_profile_secrets(profile_id: str, updates: dict[str, str]) -> dict[str, str]:
    profile_id = (profile_id or "").strip()
    if not profile_id:
        raise ValueError("profile_id is required")
    path = _vault_path(profile_id)
    with _lock:
        current = get_profile_secrets(profile_id)
        for key, value in updates.items():
            key = str(key).strip()
            if key not in ACCOUNT_ENV_KEYS and key not in ALLOWED_ENV_KEYS:
                continue
            text = str(value or "").replace("\n", " ").strip()
            if text:
                current[key] = text
            else:
                current.pop(key, None)
        VAULT_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return current


def ensure_profile_vault(profile_id: str) -> Path:
    """Create an empty per-workspace vault file if missing (no secrets yet)."""
    profile_id = (profile_id or "").strip()
    if not profile_id:
        raise ValueError("profile_id is required")
    path = _vault_path(profile_id)
    with _lock:
        VAULT_DIR.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("{}\n", encoding="utf-8")
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
    return path


def delete_profile_vault(profile_id: str) -> bool:
    """Remove the vault JSON for a workspace. Returns True if a file was deleted."""
    profile_id = (profile_id or "").strip()
    if not profile_id:
        return False
    path = _vault_path(profile_id)
    with _lock:
        if not path.exists():
            return False
        path.unlink()
        return True


def unset_profile_secrets(profile_id: str, keys: list[str]) -> dict[str, str]:
    current = get_profile_secrets(profile_id)
    for key in keys:
        current.pop(key, None)
        # Also drop aliases when disconnecting Meta page token
        if key == "META_PAGE_ACCESS_TOKEN":
            current.pop("NOURBIT_FACEBOOK_PAGE_TOKEN", None)
        if key == "META_PAGE_ID":
            current.pop("NOURBIT_FACEBOOK_PAGE_ID", None)
    path = _vault_path(profile_id)
    with _lock:
        VAULT_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return current


def resolve_env_value(*keys: str, profile_id: str | None = None) -> str:
    """Resolve a secret: workspace vault for account keys; global env for app client keys."""
    profile = (profile_id or active_profile_id() or "").strip() or None
    vault = get_profile_secrets(profile) if profile else {}
    for key in keys:
        if profile and key in ACCOUNT_ENV_KEYS:
            value = vault.get(key, "").strip()
            if value:
                return value
            continue
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def migrate_env_file_to_profile(
    env_file: str | Path | None,
    profile_id: str = DEFAULT_MIGRATE_PROFILE,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """One-shot import of account keys from .env.local into a workspace vault."""
    profile_id = (profile_id or DEFAULT_MIGRATE_PROFILE).strip() or DEFAULT_MIGRATE_PROFILE
    existing = get_profile_secrets(profile_id)
    account_present = any(existing.get(key) for key in ACCOUNT_ENV_KEYS)
    if account_present and not force:
        return {"migrated": False, "reason": "vault_already_has_account_keys", "profile_id": profile_id, "keys": []}

    if env_file:
        path = Path(env_file)
        if path.exists():
            try:
                load_env_file(path)
            except FileNotFoundError:
                pass

    updates: dict[str, str] = {}
    loaded_keys: list[str] = []
    for key in sorted(ACCOUNT_ENV_KEYS):
        value = os.environ.get(key, "").strip()
        if value:
            updates[key] = value
            loaded_keys.append(key)
    if not updates:
        return {"migrated": False, "reason": "no_account_keys_in_env", "profile_id": profile_id, "keys": []}
    set_profile_secrets(profile_id, updates)
    return {"migrated": True, "profile_id": profile_id, "keys": loaded_keys}


def ensure_default_migration(env_file: str | Path | None) -> dict[str, Any]:
    marker = VAULT_DIR / ".migrated_from_env"
    if marker.exists():
        return {"migrated": False, "reason": "already_migrated"}
    result = migrate_env_file_to_profile(env_file, DEFAULT_MIGRATE_PROFILE, force=False)
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps({"profile_id": DEFAULT_MIGRATE_PROFILE, "result": result}, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def credential_status_for_profile(profile_id: str) -> dict[str, Any]:
    from .postiz_client import connection_status, uses_postiz
    from .publish_platforms import disabled_publish_platform_reason, is_publish_platform_disabled

    profile_id = (profile_id or DEFAULT_MIGRATE_PROFILE).strip() or DEFAULT_MIGRATE_PROFILE
    channel_map = connection_status(profile_id).get("channels") or {}
    vault = get_profile_secrets(profile_id)
    platforms: dict[str, Any] = {}
    for platform, key_groups in PLATFORM_REQUIRED_GROUPS.items():
        missing: list[str] = []
        for group in key_groups:
            found = False
            for key in group:
                if key in ACCOUNT_ENV_KEYS:
                    if vault.get(key, "").strip() or os.environ.get(key, "").strip():
                        found = True
                        break
                elif os.environ.get(key, "").strip():
                    found = True
                    break
            if not found:
                missing.append("/".join(group))
        unavailable = is_publish_platform_disabled(platform)
        postiz_ready = uses_postiz(platform, profile_id)
        mapped = channel_map.get(platform) or {}
        platforms[platform] = {
            "ready": False if unavailable else ((not missing) or postiz_ready),
            "unavailable": unavailable,
            "unavailable_reason": disabled_publish_platform_reason(platform) if unavailable else "",
            "required_keys": ["/".join(group) for group in key_groups],
            "missing_keys": [] if postiz_ready or unavailable else missing,
            "profile_id": profile_id,
            "backend": "postiz" if postiz_ready else "native",
            "postiz_integration_id": mapped.get("id", ""),
            "postiz_integration_name": mapped.get("name", ""),
        }
    llm: dict[str, Any] = {}
    for name, env_key in (
        ("openai", "OPENAI_API_KEY"),
        ("deepseek", "DEEPSEEK_API_KEY"),
        ("groq", "GROQ_API_KEY"),
    ):
        llm[name] = {
            "ready": bool(vault.get(env_key, "").strip() or os.environ.get(env_key, "").strip()),
            "key_env": env_key,
        }
    from .llm import llm_provider_ready

    llm["agent"] = {**llm_provider_ready("agent", profile_id=profile_id), "key_env": "OTONOM_LLM_AGENT_COMMAND"}

    return {
        "profile_id": profile_id,
        "postiz": connection_status(profile_id),
        "llm": llm,
        "platforms": platforms,
        "settings": {
            "nourbit_daily_content_cap": os.environ.get("NOURBIT_DAILY_CONTENT_CAP", "2"),
            "nourbit_default_publish_mode": os.environ.get("NOURBIT_DEFAULT_PUBLISH_MODE", "review_required"),
            "comment_automation_enabled": os.environ.get("COMMENT_AUTOMATION_ENABLED", "false"),
            "comment_automation_mode": os.environ.get("COMMENT_AUTOMATION_MODE", "review_required"),
        },
        "vault": {
            "has_secrets": bool(vault),
            "secret_keys": sorted(vault.keys()),
        },
    }
