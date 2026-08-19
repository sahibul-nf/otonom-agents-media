"""Build TemplateRecipe instances from declarative specs."""

from __future__ import annotations

from typing import Any

from ..shell_components import normalize_shell_components
from ._base import LayoutContext, RecipeStyleMeta, TemplateRecipe


class SpecTemplateRecipe(TemplateRecipe):
    def __init__(self, spec: dict[str, Any]) -> None:
        self.template_id = str(spec["id"])
        self._spec = spec

    def style_meta(self) -> RecipeStyleMeta:
        style = self._spec.get("style") or {}
        return RecipeStyleMeta(
            font_family=str(style.get("font_family", "Arial, sans-serif")),
            google_fonts_href=str(style.get("google_fonts_href", "")),
            caption_style=str(style.get("caption_style", "Weighted captions")),
            motion_preset=str(style.get("motion_preset", "fade-pop")),
            color_grade=str(style.get("color_grade", "neutral grade")),
        )

    def video_filter(self) -> str:
        return str(self._spec.get("video_filter") or super().video_filter())

    def default_shell_components(self) -> dict[str, bool]:
        return normalize_shell_components(self._spec.get("shell_components"))

    def render_overlay(self, contract: dict[str, Any], template: dict[str, Any], layout: LayoutContext) -> str:
        builder = self._spec.get("overlay_builder")
        if callable(builder):
            return builder(contract, template, layout)
        return str(self._spec.get("overlay_html") or "")

    def css_block(self, layout: LayoutContext) -> str:
        builder = self._spec.get("css_builder")
        if callable(builder):
            base = builder(layout)
        else:
            base = str(self._spec.get("css") or "")
        motion_css = str(self._spec.get("motion_extra") or "")
        return base + motion_css

    def motion_block(
        self,
        contract: dict[str, Any],
        layout: LayoutContext,
        hook_exit_s: float,
        cta_start_s: float,
    ) -> str:
        builder = self._spec.get("motion_builder")
        if callable(builder):
            return builder(contract, layout, hook_exit_s, cta_start_s)
        return ""

    def shell_css(self, layout: LayoutContext) -> str:
        builder = self._spec.get("shell_css_builder")
        if callable(builder):
            return builder(layout)
        return str(self._spec.get("shell_css") or "")


def recipe_from_spec(spec: dict[str, Any]) -> TemplateRecipe:
    return SpecTemplateRecipe(spec)
