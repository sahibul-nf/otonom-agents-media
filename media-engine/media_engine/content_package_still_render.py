"""PNG still / carousel slides for content packages (TechTalk card renderer)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from .brand_pack import resolve_wordmark_path
from .content_package import ContentPackage
from .explainer_stitch import _render_title_png

_BRAND_LABELS = {
    "techtalk": "TECHTALK",
    "personal": "PERSONAL",
    "blank": "OTONOM",
}


def brand_label(preset: str) -> str:
    return _BRAND_LABELS.get((preset or "blank").strip().lower(), "OTONOM")


def output_dimensions(brand_preset: str) -> tuple[int, int]:
    if (brand_preset or "").strip().lower() == "personal":
        return (1080, 1920)
    return (1080, 1080)


def carousel_slide_texts(pkg: ContentPackage) -> list[str]:
    meta = pkg.artifacts.package_meta or {}
    raw = meta.get("slide_texts")
    if isinstance(raw, list):
        texts = [str(item).strip() for item in raw if str(item).strip()]
        if 3 <= len(texts) <= 5:
            return texts
    caption = (pkg.caption or "").strip()
    if not caption:
        return [f"Slide {i}" for i in range(1, 4)]
    paragraphs = [p.strip() for p in caption.split("\n\n") if p.strip()]
    if 3 <= len(paragraphs) <= 5:
        return paragraphs
    lines = [ln.strip() for ln in caption.splitlines() if ln.strip()]
    if 3 <= len(lines) <= 5:
        return lines
    words = caption.split()
    count = 3 if len(words) < 24 else min(5, max(3, len(words) // 12))
    chunk = max(1, len(words) // count)
    slides: list[str] = []
    for i in range(count):
        part = words[i * chunk : (i + 1) * chunk]
        if not part and i == count - 1:
            part = words[i * chunk :]
        slides.append(" ".join(part) if part else f"Slide {i + 1}")
    while len(slides) < 3:
        slides.append(f"Slide {len(slides) + 1}")
    return slides[:5]


def _overlay_wordmark(path: Path, wordmark: Path) -> None:
    from PIL import Image

    base = Image.open(path).convert("RGBA")
    mark = Image.open(wordmark).convert("RGBA")
    max_w = max(120, int(base.width * 0.22))
    if mark.width > max_w:
        ratio = max_w / mark.width
        mark = mark.resize((int(mark.width * ratio), int(mark.height * ratio)), Image.Resampling.LANCZOS)
    padding = max(24, int(base.width * 0.04))
    x = base.width - mark.width - padding
    y = padding
    base.alpha_composite(mark, (x, y))
    base.convert("RGB").save(path, format="PNG")


def _fit_cover(path: Path, width: int, height: int) -> None:
    from PIL import Image

    img = Image.open(path).convert("RGB")
    src_w, src_h = img.size
    scale = max(width / src_w, height / src_h)
    resized = img.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    cropped = resized.crop((left, top, left + width, top + height))
    cropped.save(path, format="PNG")


def _finish_frame(path: Path, brand_preset: str) -> None:
    w, h = output_dimensions(brand_preset)
    _fit_cover(path, w, h)
    wordmark = resolve_wordmark_path(preset=brand_preset)
    if wordmark:
        _overlay_wordmark(path, wordmark)


def render_still_png(
    path: Path,
    *,
    headline: str,
    body: str,
    brand_preset: str,
) -> Path:
    headline = textwrap.shorten((headline or "Untitled").strip(), width=120, placeholder="…")
    body = textwrap.shorten((body or "").strip(), width=280, placeholder="…")
    label = brand_label(brand_preset)
    _render_title_png(
        path,
        headline=headline,
        narration=body,
        label=label,
        scene_type="text",
    )
    _finish_frame(path, brand_preset)
    return path


def render_carousel_slide_png(
    path: Path,
    *,
    headline: str,
    slide_text: str,
    slide_index: int,
    slide_total: int,
    brand_preset: str,
) -> Path:
    micro = f"SLIDE {slide_index}/{slide_total}"
    _render_title_png(
        path,
        headline=textwrap.shorten(headline, width=80, placeholder="…"),
        narration=textwrap.shorten(slide_text, width=320, placeholder="…"),
        label=micro,
        scene_type="text",
    )
    _finish_frame(path, brand_preset)
    return path
