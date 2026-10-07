"""Resolve brand brain text and optional assets from preset packs or CONTENT_OS_PATH."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BRAND_PACK_DIR = REPO_ROOT / "brand-pack"
VALID_PRESETS = frozenset({"blank", "techtalk", "personal"})

# Relative to CONTENT_OS_PATH root (private content-os checkout — not vendored in git).
CONTENT_OS_WORDMARK_CANDIDATES: dict[str, tuple[str, ...]] = {
    "techtalk": (
        "techtalk-production/brand/techtalk-intel-wordmark-cropped.png",
        "techtalk-production/brand/techtalk-intel-logo.png",
    ),
    "personal": (
        "personal-brand/brand/wordmark.png",
        "personal-brand/brand/logo.png",
    ),
}
CONTENT_OS_LOGO_CANDIDATES: dict[str, tuple[str, ...]] = {
    "techtalk": ("techtalk-production/brand/techtalk-intel-logo.png",),
}


@dataclass(frozen=True)
class BrandAssets:
    """Optional PNG paths resolved from content-os (None when unset or missing)."""

    wordmark_path: Path | None = None
    logo_path: Path | None = None


def content_os_root(content_os_path: str | None = None) -> Path | None:
    custom = (content_os_path or os.environ.get("CONTENT_OS_PATH") or "").strip()
    if not custom:
        return None
    root = Path(custom).expanduser()
    return root if root.is_dir() else None


def _first_existing(root: Path, relative_paths: tuple[str, ...]) -> Path | None:
    for rel in relative_paths:
        candidate = root / rel
        if candidate.is_file():
            return candidate
    return None


def resolve_wordmark_path(
    *,
    preset: str | None = None,
    content_os_path: str | None = None,
) -> Path | None:
    """TechTalk/personal wordmark PNG when CONTENT_OS_PATH points at content-os."""
    root = content_os_root(content_os_path)
    if not root:
        return None
    chosen = (preset or os.environ.get("OTONOM_BRAND_PRESET") or "techtalk").strip().lower()
    rels = CONTENT_OS_WORDMARK_CANDIDATES.get(chosen, ())
    return _first_existing(root, rels)


def resolve_logo_path(
    *,
    preset: str | None = None,
    content_os_path: str | None = None,
) -> Path | None:
    root = content_os_root(content_os_path)
    if not root:
        return None
    chosen = (preset or os.environ.get("OTONOM_BRAND_PRESET") or "techtalk").strip().lower()
    rels = CONTENT_OS_LOGO_CANDIDATES.get(chosen, ())
    return _first_existing(root, rels)


def resolve_brand_assets(
    *,
    preset: str | None = None,
    content_os_path: str | None = None,
) -> BrandAssets:
    chosen = (preset or os.environ.get("OTONOM_BRAND_PRESET") or "blank").strip().lower()
    return BrandAssets(
        wordmark_path=resolve_wordmark_path(preset=chosen, content_os_path=content_os_path),
        logo_path=resolve_logo_path(preset=chosen, content_os_path=content_os_path),
    )


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
