"""Base types for per-template HyperFrames recipe modules."""

from __future__ import annotations

import html
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


def escape_attr(value: Any) -> str:
    return html.escape(str(value), quote=True)


def escape_text(value: Any) -> str:
    return html.escape(str(value))


def style_hex(value: Any, fallback: str) -> str:
    text = str(value or fallback).strip()
    return text if re.fullmatch(r"#[0-9a-fA-F]{6}", text) else fallback


@dataclass(frozen=True)
class RecipeStyleMeta:
    font_family: str
    google_fonts_href: str
    caption_style: str
    motion_preset: str
    color_grade: str


@dataclass(frozen=True)
class LayoutContext:
    width: int
    height: int
    is_landscape: bool
    caption_font_size: int
    text_color: str
    highlight_color: str
    accent: str
    secondary_accent: str


class TemplateRecipe(ABC):
    """Per-template HTML/CSS/GSAP recipe."""

    template_id: str

    @abstractmethod
    def style_meta(self) -> RecipeStyleMeta:
        raise NotImplementedError

    def recipe_module(self) -> str:
        return self.template_id

    def overlay_class(self) -> str:
        return f"recipe-{self.template_id.replace('_', '-')}"

    def video_filter(self) -> str:
        return "contrast(1.06) saturate(0.96) brightness(0.92)"

    @abstractmethod
    def render_overlay(self, contract: dict[str, Any], template: dict[str, Any], layout: LayoutContext) -> str:
        raise NotImplementedError

    def render_caption_html(
        self,
        caption: dict[str, Any],
        index: int,
        layout: LayoutContext,
        seconds_fn,
        attr_fn,
    ) -> str:
        start_ms = int(caption.get("startMs", 0))
        end_ms = int(caption.get("endMs", start_ms + 1000))
        duration_ms = max(1, end_ms - start_ms - 2)
        words = caption.get("words") or [
            {"text": word, "startMs": start_ms, "endMs": end_ms}
            for word in str(caption.get("text", "")).split()
        ]
        spans = []
        for word_index, word in enumerate(words):
            spans.append(
                '<span '
                f'id="cap-{index}-word-{word_index}" '
                f'data-word-start="{attr_fn(seconds_fn(int(word.get("startMs", start_ms))))}" '
                f'data-word-end="{attr_fn(seconds_fn(int(word.get("endMs", end_ms))))}">'
                f'{escape_text(word.get("text", ""))}'
                "</span>"
            )
        return (
            f'<div id="cap-{index}" class="clip caption-clip recipe-caption" '
            f'data-start="{attr_fn(seconds_fn(start_ms))}" '
            f'data-duration="{attr_fn(seconds_fn(duration_ms))}" '
            'data-track-index="2">'
            '<div class="caption-card">'
            f'<div class="caption-text" style="--highlight-color:{attr_fn(layout.highlight_color)}">'
            + "\n".join(spans)
            + "</div></div></div>"
        )

    @abstractmethod
    def css_block(self, layout: LayoutContext) -> str:
        raise NotImplementedError

    @abstractmethod
    def motion_block(
        self,
        contract: dict[str, Any],
        layout: LayoutContext,
        hook_exit_s: float,
        cta_start_s: float,
    ) -> str:
        raise NotImplementedError

    def shell_extras_head(self) -> str:
        meta = self.style_meta()
        if not meta.google_fonts_href:
            return ""
        return f'  <link rel="stylesheet" href="{escape_attr(meta.google_fonts_href)}" />\n'
