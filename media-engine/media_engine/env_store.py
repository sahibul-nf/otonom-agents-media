"""Helpers to mutate local .env files safely."""

from __future__ import annotations

import os
from pathlib import Path

from .env_loader import ALLOWED_ENV_KEYS


def _normalize_value(value: str) -> str:
    return value.replace("\n", " ").strip()


def set_env_values(path: str | Path, updates: dict[str, str]) -> dict[str, str]:
    env_path = Path(path)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    kv: dict[str, str] = {}
    order: list[str] = []
    for raw in existing_lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in ALLOWED_ENV_KEYS:
            continue
        if key not in order:
            order.append(key)
        kv[key] = value.strip().strip('"').strip("'")

    for key, value in updates.items():
        if key not in ALLOWED_ENV_KEYS:
            continue
        normalized = _normalize_value(str(value))
        if key not in order:
            order.append(key)
        kv[key] = normalized
        os.environ[key] = normalized

    output = [f"{key}={kv[key]}" for key in order if key in kv and kv[key] != ""]
    env_path.write_text("\n".join(output) + ("\n" if output else ""), encoding="utf-8")
    return kv


def unset_env_keys(path: str | Path, keys: list[str]) -> dict[str, str]:
    env_path = Path(path)
    if not env_path.exists():
        for key in keys:
            os.environ.pop(key, None)
        return {}
    existing_lines = env_path.read_text(encoding="utf-8").splitlines()
    keyset = set(keys)
    output: list[str] = []
    for raw in existing_lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            output.append(raw)
            continue
        key, _ = line.split("=", 1)
        if key.strip() in keyset:
            continue
        output.append(raw)
    env_path.write_text("\n".join(output).rstrip() + ("\n" if output else ""), encoding="utf-8")
    for key in keys:
        os.environ.pop(key, None)
    return {}
