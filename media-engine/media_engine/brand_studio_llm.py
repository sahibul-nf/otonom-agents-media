"""LLM Brand Studio (#80): natural-language prompt → validated brand_system.

Maps onto an existing HyperFrames starter recipe (no new builtins). Operator
previews in Brand Builder, then saves as ``profiles/custom_*.json``.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .hyperframes_templates import TEMPLATE_BY_ID, resolve_starter_template_id
from .llm import LLMError, call_llm_json, llm_provider_ready
from .styles import DEFAULT_STYLE_PATH, PROFILES_DIR, load_style, resolve_style_path

CAPTION_STYLE_IDS = frozenset(
    {
        "caption-editorial-emphasis",
        "caption-pill-karaoke",
        "caption-highlight",
        "caption-clip-wipe",
        "caption-weight-shift",
        "caption-gradient-fill",
        "caption-kinetic-slam",
        "caption-neon-glow",
    }
)
CTA_IDS = frozenset({"none", "yt-lower-third", "instagram-follow", "tiktok-follow"})
TEXTURE_IDS = frozenset({"none", "grain-overlay", "vignette", "shimmer-sweep"})
INTRO_IDS = frozenset({"none", "template-hook", "lower-third-hook"})
MOTION_IDS = frozenset({"calm", "balanced", "energetic"})
FONT_IDS = frozenset({"Sora", "Inter", "Montserrat", "Poppins", "Roboto", "Arial", "system-ui", "Lora", "Space Grotesk"})

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class BrandStudioLlmError(RuntimeError):
    pass


def available_starter_ids() -> list[str]:
    return sorted(TEMPLATE_BY_ID.keys())


def _normalize_hex(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not _HEX_RE.match(text):
        return fallback
    if len(text) == 4:
        return f"#{text[1]*2}{text[2]*2}{text[3]*2}".lower()
    return text.lower()


def _pick_starter(raw: Any) -> str:
    return resolve_starter_template_id(raw)


def validate_brand_studio_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate LLM (or heuristic) JSON into style + brand_system for Brand Builder."""
    if not isinstance(raw, dict):
        raise BrandStudioLlmError("expected JSON object")

    starter = _pick_starter(raw.get("starter_template") or raw.get("starter"))
    caption_style = str(raw.get("caption_style") or "caption-editorial-emphasis").strip()
    if caption_style not in CAPTION_STYLE_IDS:
        caption_style = "caption-editorial-emphasis"

    cta = str(raw.get("cta_overlay") or "none").strip()
    if cta not in CTA_IDS:
        cta = "none"

    textures_raw = raw.get("texture_effects")
    textures: list[str] = []
    if isinstance(textures_raw, list):
        for item in textures_raw:
            tid = str(item).strip()
            if tid in TEXTURE_IDS and tid != "none" and tid not in textures:
                textures.append(tid)
    else:
        legacy = str(raw.get("texture_effect") or "none").strip()
        if legacy in TEXTURE_IDS and legacy != "none":
            textures = [legacy]

    intro = str(raw.get("intro_layout") or "template-hook").strip().lower()
    if intro not in INTRO_IDS:
        intro = "template-hook"

    motion = str(raw.get("motion_intensity") or "balanced").strip().lower()
    if motion not in MOTION_IDS:
        motion = "balanced"

    font = str(raw.get("font_family") or "Sora").strip()
    if font not in FONT_IDS:
        font = "Sora"

    label = str(raw.get("label") or raw.get("name") or "AI Brand Look").strip() or "AI Brand Look"
    watermark = str(raw.get("watermark_text") or label).strip()[:48] or "Brand"

    style = {
        "caption": {
            "font_family": font,
            "font_size": max(36, min(72, int(raw.get("font_size") or 52))),
            "text_color": _normalize_hex(raw.get("text_color"), "#ffffff"),
            "highlight_word_color": _normalize_hex(raw.get("highlight_color") or raw.get("highlight_word_color"), "#67e8f9"),
            "background_color": _normalize_hex(raw.get("background_color") or raw.get("plate_color"), "#0a0a0c"),
            "stroke_width": max(0, min(14, int(raw.get("stroke_width") or 8))),
            "position": "bottom" if str(raw.get("position") or "bottom") != "top" else "top",
            "uppercase": bool(raw.get("uppercase")),
        },
        "brand": {
            "watermark_text": watermark,
        },
    }
    brand_system = {
        "starter_template": starter,
        "caption_style": caption_style,
        "intro_layout": intro,
        "cta_overlay": cta,
        "texture_effect": textures[0] if textures else "none",
        "texture_effects": textures,
        "extra_blocks": [],
        "motion_intensity": motion,
    }
    return {
        "ok": True,
        "label": label,
        "rationale": str(raw.get("rationale") or "").strip()[:400],
        "starter_template": starter,
        "style": style,
        "brand_system": brand_system,
    }


def heuristic_brand_from_prompt(prompt: str) -> dict[str, Any]:
    """Deterministic fallback when LLM is unavailable (tests / offline)."""
    text = (prompt or "").lower()
    starter = "spiritual_reflective"
    if any(k in text for k in ("neon", "cyber", "glow", "futur")):
        starter = "eva_neon_cyber"
    elif any(k in text for k in ("kinetic", "bounce", "lime", "punch")):
        starter = "volt_lime_kinetic"
    elif any(k in text for k in ("sunset", "warm", "ember", "golden")):
        starter = "ember_sunset_gradient"
    elif any(k in text for k in ("data", "market", "analyst", "chart", "finance")):
        starter = "techtalk_intel_brief"
    elif any(k in text for k in ("minimal", "clean", "mono")):
        starter = "swiss_grid_explainer"
    elif any(k in text for k in ("social", "podcast", "clip", "punch")):
        starter = "velocity_business_promo"

    highlight = "#67e8f9"
    bg = "#05070a"
    caption = "caption-editorial-emphasis"
    motion = "balanced"
    cta = "yt-lower-third"
    textures = ["grain-overlay"]
    if "neon" in text or "cyber" in text:
        highlight, caption, motion, cta = "#ff2a85", "caption-neon-glow", "energetic", "instagram-follow"
        textures = ["vignette"]
    elif "lime" in text or "kinetic" in text:
        highlight, caption, motion, cta = "#a7f36b", "caption-kinetic-slam", "energetic", "tiktok-follow"
        textures = []
    elif "calm" in text or "devotional" in text or "soft" in text:
        highlight, caption, motion = "#d8b45f", "caption-editorial-emphasis", "calm"
        textures = ["grain-overlay"]
    elif "finance" in text or "market" in text:
        highlight, caption = "#74f2ce", "caption-clip-wipe"
        textures = ["vignette"]

    return validate_brand_studio_payload(
        {
            "label": "Prompt Look",
            "rationale": "Heuristic mapping from keywords in the prompt (LLM offline).",
            "starter_template": starter,
            "caption_style": caption,
            "cta_overlay": cta,
            "texture_effects": textures,
            "intro_layout": "template-hook",
            "motion_intensity": motion,
            "font_family": "Sora",
            "font_size": 54,
            "highlight_color": highlight,
            "text_color": "#ffffff",
            "background_color": bg,
            "stroke_width": 8,
            "watermark_text": "Brand",
        }
    )


def _system_prompt(starter_ids: list[str]) -> str:
    return (
        "You design short-form video brand looks for Otonom Brand Studio. "
        "Return strict JSON only. Pick ONE starter_template from the allowlist — "
        "never invent a new recipe id. Keep captions/edutainment friendly.\n"
        f"Allowed starter_template ids:\n{json.dumps(starter_ids)}\n"
        f"Allowed caption_style: {sorted(CAPTION_STYLE_IDS)}\n"
        f"Allowed cta_overlay: {sorted(CTA_IDS)}\n"
        f"Allowed texture_effects items: grain-overlay, vignette, shimmer-sweep (or [])\n"
        f"Allowed intro_layout: {sorted(INTRO_IDS)}\n"
        f"Allowed motion_intensity: {sorted(MOTION_IDS)}\n"
        f"Allowed font_family: {sorted(FONT_IDS)}\n"
        "JSON keys: label, rationale, starter_template, caption_style, cta_overlay, "
        "texture_effects, intro_layout, motion_intensity, font_family, font_size, "
        "highlight_color, text_color, background_color, stroke_width, watermark_text, "
        "uppercase (bool), position (bottom|top)."
    )


def generate_brand_from_prompt(
    prompt: str,
    *,
    profile_id: str = "nourbit",
    llm_provider: str = "auto",
    allow_heuristic_fallback: bool = True,
) -> dict[str, Any]:
    text = (prompt or "").strip()
    if len(text) < 8:
        raise BrandStudioLlmError("prompt is too short — describe tone, colors, and use-case")

    starters = available_starter_ids()
    provider = (llm_provider or "auto").strip().lower() or "auto"

    if provider != "none":
        ready = llm_provider_ready(provider, profile_id=profile_id)
        if ready.get("ready"):
            try:
                raw = call_llm_json(
                    provider,
                    _system_prompt(starters),
                    f"Operator prompt:\n{text[:2000]}\n\nReturn the JSON brand look now.",
                    timeout_seconds=60,
                    profile_id=profile_id,
                )
                if isinstance(raw, dict):
                    result = validate_brand_studio_payload(raw)
                    result["source"] = "llm"
                    result["provider"] = provider
                    return result
            except (LLMError, ValueError, TypeError, json.JSONDecodeError) as exc:
                if not allow_heuristic_fallback:
                    raise BrandStudioLlmError(f"LLM brand generate failed: {exc}") from exc
        elif not allow_heuristic_fallback:
            raise BrandStudioLlmError(f"LLM not configured: {ready.get('missing') or provider}")

    if not allow_heuristic_fallback:
        raise BrandStudioLlmError("LLM unavailable and heuristic fallback disabled")

    result = heuristic_brand_from_prompt(text)
    result["source"] = "heuristic"
    result["provider"] = provider
    return result


def set_workspace_default_template(template_ref: str, *, style_path: str | None = None) -> dict[str, Any]:
    """Point workspace style ``hyperframes.default_template`` at a builtin or brand:custom_* id."""
    ref = str(template_ref or "").strip()
    if not ref:
        raise BrandStudioLlmError("template_ref is required")
    if ref.startswith("brand:"):
        custom_id = ref.split(":", 1)[1]
        path = resolve_style_path(f"profiles/{custom_id}.json" if not custom_id.endswith(".json") else custom_id)
        if not path.exists() or not path.name.startswith("custom_"):
            raise BrandStudioLlmError(f"custom brand template not found: {ref}")
        stored = f"brand:{path.stem}"
    elif ref in TEMPLATE_BY_ID or ref.startswith("custom_"):
        stored = ref if not ref.startswith("custom_") else f"brand:{ref.replace('.json', '')}"
        if stored.startswith("brand:"):
            path = resolve_style_path(f"profiles/{stored.split(':', 1)[1]}.json")
            if not path.exists():
                raise BrandStudioLlmError(f"custom brand template not found: {ref}")
    else:
        # allow profiles/custom_foo.json paths
        try:
            path = resolve_style_path(ref)
        except (OSError, ValueError) as exc:
            raise BrandStudioLlmError(str(exc)) from exc
        if path.name.startswith("custom_"):
            stored = f"brand:{path.stem}"
        elif path.stem in TEMPLATE_BY_ID:
            stored = path.stem
        else:
            raise BrandStudioLlmError(f"unsupported template_ref: {ref}")

    target = resolve_style_path(style_path) if style_path else DEFAULT_STYLE_PATH
    payload = load_style(target)
    hyper = payload.get("hyperframes") if isinstance(payload.get("hyperframes"), dict) else {}
    hyper = {**hyper, "default_template": stored}
    payload["hyperframes"] = hyper
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        rel = f"profiles/{target.name}" if target.parent.resolve() == PROFILES_DIR.resolve() else str(target)
    except OSError:
        rel = str(target)
    return {
        "ok": True,
        "default_template": stored,
        "path": rel,
    }
