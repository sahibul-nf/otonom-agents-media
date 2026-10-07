"""Resolve brand brain text from preset packs or CONTENT_OS_PATH."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BRAND_PACK_DIR = REPO_ROOT / "brand-pack"
VALID_PRESETS = frozenset({"blank", "techtalk", "personal"})


def resolve_brain_path(
    *,
    preset: str | None = None,
    content_os_path: str | None = None,
) -> Path:
    custom = (content_os_path or os.environ.get("CONTENT_OS_PATH") or "").strip()
    if custom:
        root = Path(custom).expanduser()
        for candidate in (
            root / "techtalk-production" / "TECHTALK_BRAND_BIBLE.md",
            root / "content-ai-system" / "TECHTALK_MASTER_SYSTEM_DIRECTIVE.md",
            root / "personal-brand" / "MOTION.md",
        ):
            if candidate.is_file():
                return candidate
        if (root / "content-ai-system").is_dir():
            return root / "content-ai-system" / "README.md"
        raise FileNotFoundError(f"CONTENT_OS_PATH has no known brand files: {root}")

    chosen = (preset or os.environ.get("OTONOM_BRAND_PRESET") or "blank").strip().lower()
    if chosen not in VALID_PRESETS:
        raise ValueError(f"Unknown brand preset '{chosen}'. Use: {', '.join(sorted(VALID_PRESETS))}")
    path = BRAND_PACK_DIR / chosen / "BRAND_BRAIN.md"
    if not path.is_file():
        raise FileNotFoundError(f"Missing brand pack file: {path}")
    return path


def load_brain_text(
    *,
    preset: str | None = None,
    content_os_path: str | None = None,
    max_chars: int = 12000,
) -> str:
    path = resolve_brain_path(preset=preset, content_os_path=content_os_path)
    text = path.read_text(encoding="utf-8")
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n… [truncated for generation context]"
    return text
