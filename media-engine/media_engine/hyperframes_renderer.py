"""HyperFrames renderer integration for production video renders."""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any

from .db import ARTIFACTS_DIR, ROOT
from .hyperframes_oss import build_oss_host_bundle, copy_oss_files_to_project, resolve_oss_selections
from .hyperframes_recipes import LayoutContext, get_recipe
from .hyperframes_templates import TEMPLATE_VERSION, dimensions_for_format, resolve_hyperframes_template
from .styles import apply_readable_template_only_caption

HYPERFRAMES_PACKAGE = "hyperframes@0.6.40"
HYPERFRAMES_DIR = ROOT / "render" / "hyperframes"
# HyperFrames defaults to 600_000 ms streaming inactivity; slow local renders (or the
# ffmpeg tail after the last frame is piped) can exceed that and get SIGTERM (code 255).
DEFAULT_FFMPEG_STREAMING_TIMEOUT_MS = "1800000"
DEFAULT_FFMPEG_ENCODE_TIMEOUT_MS = "1800000"
_HYPERFRAMES_RENDER_LOCK = threading.Lock()


def _flag_enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _hyperframes_subprocess_env() -> dict[str, str]:
    """Env overrides for HyperFrames child processes (respect existing operator settings)."""
    env = dict(os.environ)
    env.setdefault("FFMPEG_STREAMING_TIMEOUT_MS", DEFAULT_FFMPEG_STREAMING_TIMEOUT_MS)
    env.setdefault("FFMPEG_ENCODE_TIMEOUT_MS", DEFAULT_FFMPEG_ENCODE_TIMEOUT_MS)
    return env


def _sanitize_cli_output(text: str, *, tail_chars: int = 2400) -> str:
    cleaned = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", text or "")
    cleaned = re.sub(r"\r", "", cleaned)
    lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
    if not lines:
        return ""
    progress_markers = ("Streaming frame", "█", "░░")
    kept = [line for line in lines if not any(marker in line for marker in progress_markers)]
    summary = kept if kept else lines[-6:]
    body = "\n".join(summary)
    if len(body) > tail_chars:
        body = body[-tail_chars:]
    return body.strip()


def _node_major(version: str) -> int:
    match = re.search(r"v?(\d+)", version)
    return int(match.group(1)) if match else 0


def hyperframes_command(*args: str) -> list[str]:
    local_cli = HYPERFRAMES_DIR / "node_modules" / ".bin" / "hyperframes"
    if local_cli.exists():
        return [str(local_cli), *args]
    return ["npm", "exec", "--yes", "--package", HYPERFRAMES_PACKAGE, "--", "hyperframes", *args]


def check_hyperframes_runtime(run_doctor: bool = False) -> dict[str, Any]:
    enabled = _flag_enabled(os.environ.get("HYPERFRAMES_ENABLED"))
    checks: dict[str, Any] = {
        "enabled": enabled,
        "package": HYPERFRAMES_PACKAGE,
        "node": {"ok": False, "version": "", "minimum": "22"},
        "ffmpeg": {"ok": False, "path": ""},
        "hyperframes": {"ok": False, "version": "", "doctor_ok": None, "doctor_output": ""},
    }

    node = shutil.which("node")
    if node:
        result = subprocess.run([node, "--version"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        version = (result.stdout or result.stderr).strip()
        checks["node"] = {"ok": result.returncode == 0 and _node_major(version) >= 22, "version": version, "minimum": "22"}

    ffmpeg = shutil.which("ffmpeg")
    checks["ffmpeg"] = {"ok": bool(ffmpeg), "path": ffmpeg or ""}

    try:
        version_result = subprocess.run(
            hyperframes_command("--version"),
            cwd=HYPERFRAMES_DIR if HYPERFRAMES_DIR.exists() else ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        version_text = (version_result.stdout or version_result.stderr).strip()
        checks["hyperframes"]["ok"] = version_result.returncode == 0
        checks["hyperframes"]["version"] = version_text
    except (OSError, subprocess.TimeoutExpired) as exc:
        checks["hyperframes"]["doctor_output"] = str(exc)

    if run_doctor and checks["hyperframes"]["ok"]:
        try:
            doctor = subprocess.run(
                hyperframes_command("doctor"),
                cwd=HYPERFRAMES_DIR if HYPERFRAMES_DIR.exists() else ROOT,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=90,
            )
            checks["hyperframes"]["doctor_ok"] = doctor.returncode == 0
            checks["hyperframes"]["doctor_output"] = doctor.stdout[-4000:]
        except (OSError, subprocess.TimeoutExpired) as exc:
            checks["hyperframes"]["doctor_ok"] = False
            checks["hyperframes"]["doctor_output"] = str(exc)

    checks["ready"] = bool(
        enabled
        and checks["node"]["ok"]
        and checks["ffmpeg"]["ok"]
        and checks["hyperframes"]["ok"]
    )
    if not enabled:
        checks["reason"] = "HYPERFRAMES_ENABLED is not true"
    elif not checks["node"]["ok"]:
        checks["reason"] = "Node.js 22+ is required"
    elif not checks["ffmpeg"]["ok"]:
        checks["reason"] = "ffmpeg is required"
    elif not checks["hyperframes"]["ok"]:
        checks["reason"] = "HyperFrames CLI is unavailable"
    else:
        checks["reason"] = ""
    return checks


def require_hyperframes_runtime() -> dict[str, Any]:
    status = check_hyperframes_runtime(run_doctor=False)
    if not status["ready"]:
        raise RuntimeError(f"hyperframes renderer is not ready: {status['reason']}")
    return status


def _seconds(ms: int) -> str:
    return f"{max(0, ms) / 1000:.3f}"


def _attr(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _style_hex(value: Any, fallback: str) -> str:
    text = str(value or fallback).strip()
    return text if re.fullmatch(r"#[0-9a-fA-F]{6}", text) else fallback


def _shell_css(
    width: int,
    height: int,
    is_landscape: bool,
    text_color: str,
    accent: str,
    secondary_accent: str,
    caption_font_size: int,
    video_filter: str,
    font_family: str = "Arial, sans-serif",
    caption_background: str = "rgba(4, 7, 8, 0.72)",
    stroke_width: float = 0,
) -> str:
    stroke_css = (
        f"-webkit-text-stroke: {min(max(stroke_width / 3, 0), 3):.2f}px rgba(0,0,0,.72);"
        if stroke_width > 0
        else ""
    )
    return f"""
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #111111; font-family: {font_family}; }}
    #root {{
      position: relative;
      width: {width}px;
      height: {height}px;
      overflow: hidden;
      background: #050607;
      color: {text_color};
      font-family: {font_family};
      --template-accent: {accent};
      --template-secondary: {secondary_accent};
      --shell-cta-border: var(--template-accent);
      --shell-cta-color: var(--template-accent);
      --shell-cta-bg: rgba(0, 0, 0, 0.68);
      --shell-source-color: var(--template-secondary);
      --shell-hook-subtitle: rgba(255,255,255,0.84);
    }}
    video {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: cover;
      object-position: center;
      filter: {video_filter};
    }}
    .shade {{
      position: absolute;
      inset: 0;
      z-index: 1;
      background: linear-gradient(180deg, rgba(0,0,0,0.58) 0%, rgba(0,0,0,0.12) 28%, rgba(0,0,0,0.18) 55%, rgba(0,0,0,0.76) 100%);
      pointer-events: none;
    }}
    .brand-texture-layer {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      max-width: none;
      pointer-events: none;
      z-index: 4;
    }}
    #grain-overlay,
    #hf-vignette,
    #vignette {{
      z-index: 4 !important;
    }}
    .template-layer {{
      box-sizing: border-box;
      overflow-wrap: anywhere;
      word-break: break-word;
      max-width: calc(100% - 96px);
    }}
    .hook {{
      position: absolute;
      top: {110 if is_landscape else 170}px;
      left: {120 if is_landscape else 72}px;
      right: {120 if is_landscape else 72}px;
      text-align: center;
      text-shadow: 0 5px 24px rgba(0,0,0,0.72);
    }}
    .hook h1 {{ margin: 0; font-size: {62 if is_landscape else 74}px; line-height: 0.98; font-weight: 900; letter-spacing: 0; font-family: {font_family}; }}
    .hook p {{ margin: 22px 0 0; font-size: {26 if is_landscape else 30}px; line-height: 1.18; color: var(--shell-hook-subtitle); font-weight: 650; }}
    .caption-clip {{
      position: absolute;
      left: 0;
      right: 0;
      bottom: {176 if is_landscape else 365}px;
      z-index: 220;
      display: flex;
      justify-content: center;
      padding: 0 62px;
      pointer-events: none;
    }}
    .caption-card {{
      display: inline-flex;
      max-width: {1280 if is_landscape else 956}px;
      padding: 20px 30px 23px;
      border-radius: 16px;
      border: 1px solid rgba(255,255,255,0.16);
      background: {caption_background};
      box-shadow: 0 18px 48px rgba(0,0,0,0.42);
      text-align: center;
    }}
    .caption-text {{
      display: inline-flex;
      flex-wrap: wrap;
      justify-content: center;
      align-items: baseline;
      column-gap: 14px;
      row-gap: 2px;
      max-width: 100%;
      font-size: {caption_font_size}px !important;
      line-height: 1.08;
      font-weight: 900;
      font-family: {font_family};
      text-shadow: 0 3px 12px rgba(0,0,0,0.9);
      paint-order: stroke fill;
      {stroke_css}
    }}
    .caption-text span {{ display: inline-block; color: {text_color}; }}
    .brand-row {{
      position: absolute;
      left: {72 if is_landscape else 48}px;
      right: {72 if is_landscape else 48}px;
      bottom: {124 if is_landscape else 230}px;
      display: flex;
      justify-content: space-between;
      gap: 22px;
      font-size: 25px;
      color: rgba(255,255,255,0.82);
      font-weight: 700;
      text-shadow: 0 2px 10px rgba(0,0,0,0.8);
    }}
    .source {{ color: var(--shell-source-color); text-align: right; }}
    .cta {{
      position: absolute;
      left: {90 if is_landscape else 62}px;
      right: {90 if is_landscape else 62}px;
      bottom: {50 if is_landscape else 95}px;
      padding: 22px 26px;
      border-radius: 18px;
      background: var(--shell-cta-bg);
      border: 2px solid var(--shell-cta-border);
      color: var(--shell-cta-color);
      text-align: center;
      font-size: 34px;
      line-height: 1.12;
      font-weight: 900;
      box-shadow: 0 16px 44px rgba(0,0,0,0.38);
    }}
    .oss-caption-pill-karaoke .caption-text span {{
      padding: 4px 10px;
      border-radius: 999px;
    }}
    """


def _overlay_exit_seconds(duration_ms: int, captions: list[dict[str, Any]]) -> float:
    total_s = duration_ms / 1000
    if captions:
        first_end_s = int(captions[0].get("endMs") or duration_ms) / 1000
    else:
        first_end_s = total_s * 0.5
    overlay_exit_s = min(max(1.8, total_s * 0.42), first_end_s * 0.55 + 0.6)
    return min(overlay_exit_s, max(1.5, total_s - 0.35))


def _overlay_lifecycle_js(
    duration_ms: int,
    captions: list[dict[str, Any]],
    overlay_exit_s: float | None = None,
) -> str:
    if overlay_exit_s is None:
        overlay_exit_s = _overlay_exit_seconds(duration_ms, captions)
    return f"""
    const overlayExitS = {overlay_exit_s:.3f};
    const overlayLayers = Array.from(document.querySelectorAll(".template-layer"));
    if (overlayLayers.length) {{
      tl.from(overlayLayers, {{
        y: 26,
        opacity: 0,
        scale: 0.94,
        duration: 0.42,
        ease: "power3.out",
        stagger: 0.07,
        transformOrigin: "50% 50%",
      }}, 0.12);
      overlayLayers.forEach((el, index) => {{
        const ambientStart = 0.58 + index * 0.04;
        const halfCycle = 2.1 + index * 0.08;
        const cycleDuration = halfCycle * 2;
        const ambientWindow = Math.max(0, overlayExitS - ambientStart - 0.05);
        const repeat = Math.max(0, Math.floor(ambientWindow / cycleDuration) - 1);
        const tilt = el.classList.contains("sticky-note") ? -3 : el.classList.contains("pink-callout") ? 2 : 0;
        if (repeat > 0) {{
          tl.to(el, {{
            y: -5,
            rotation: tilt,
            duration: halfCycle,
            ease: "sine.inOut",
            yoyo: true,
            repeat,
          }}, ambientStart);
        }}
      }});
      tl.to(overlayLayers, {{
        y: -18,
        opacity: 0,
        scale: 0.96,
        duration: 0.32,
        ease: "power2.in",
        stagger: 0.04,
      }}, overlayExitS);
    }}
"""


_TEMPLATE_LAYOUT_FIT_JS = """
    function fitTemplateLayersToCanvas() {
      const root = document.getElementById("root");
      const tl = window.__timelines && window.__timelines["premium-hyperframes"];
      if (!root || !tl) return;
      const pad = 36;
      const samples = [0.12, 0.35, 0.65, 1];
      root.querySelectorAll(".template-layer").forEach((el) => {
        let size = parseFloat(window.getComputedStyle(el).fontSize) || 48;
        const minSize = 22;
        if (!el.style.transformOrigin || el.style.transformOrigin === "50% 50% 0px") {
          el.style.transformOrigin = "left top";
        }
        outer: for (let step = 0; step < 36 && size >= minSize; step += 1) {
          el.style.fontSize = size + "px";
          for (const sample of samples) {
            tl.progress(Math.min(1, Math.max(0, sample)));
            const rect = el.getBoundingClientRect();
            const bounds = root.getBoundingClientRect();
            const ok =
              rect.left >= bounds.left + pad - 2 &&
              rect.right <= bounds.right - pad + 2 &&
              rect.top >= bounds.top + pad - 2 &&
              rect.bottom <= bounds.bottom - pad + 2;
            if (!ok) {
              size -= 1.25;
              continue outer;
            }
          }
          break;
        }
      });
      tl.progress(0);
    }
"""


def _parse_inspect_json(output: str) -> dict[str, Any]:
    text = (output or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            return {}
        try:
            parsed = json.loads(text[start:])
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


def summarize_hyperframes_inspect_failure(output: str) -> str:
    data = _parse_inspect_json(output)
    if not data:
        cleaned = (output or "HyperFrames layout check failed.").strip()
        return cleaned[:500]
    if data.get("ok"):
        return ""
    issues = [issue for issue in (data.get("issues") or []) if issue.get("severity") == "error"]
    if not issues:
        return "HyperFrames layout check failed before render."
    parts: list[str] = []
    for issue in issues[:3]:
        code = str(issue.get("code") or "layout_error")
        message = str(issue.get("message") or "Layout issue detected.")
        sample = str(issue.get("text") or "").strip()
        if len(sample) > 72:
            sample = sample[:69] + "..."
        if sample:
            parts.append(f"{code}: {message} Text: \"{sample}\"")
        else:
            parts.append(f"{code}: {message}")
    return "HyperFrames layout check failed. " + " ".join(parts)


def _css_font_family(value: Any) -> str:
    text = str(value or "").strip() or "Arial"
    safe = re.sub(r"[^a-zA-Z0-9 \-_]", "", text) or "Arial"
    return f'"{safe}", Arial, sans-serif'


def _css_background(value: Any, fallback: str = "rgba(4, 7, 8, 0.72)") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    lowered = text.lower().replace(" ", "")
    if lowered in {"transparent", "none", "rgba(0,0,0,0)", "#00000000"}:
        return "transparent"
    if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return text
    if re.fullmatch(r"rgba?\([^)]+\)", text):
        return text
    return fallback


def _render_shell(contract: dict[str, Any], recipe, template: dict[str, Any], layout: LayoutContext, duration_s: str) -> str:
    return recipe.render_shell_html(contract, template, layout, duration_s, _seconds, _attr)


def _render_captions(
    contract: dict[str, Any],
    recipe,
    layout: LayoutContext,
    caption_class: str = "",
) -> str:
    captions = contract.get("captions") or []
    nodes = [
        recipe.render_caption_html(caption, index, layout, _seconds, _attr)
        for index, caption in enumerate(captions)
    ]
    if caption_class and "shimmer-sweep" in caption_class:
        return "\n".join(node.replace('class="caption-card"', 'class="caption-card shimmer-sweep-target"') for node in nodes)
    if caption_class and "pill-karaoke" in caption_class:
        return "\n".join(
            node.replace('class="caption-text"', 'class="caption-text shimmer-sweep-target"')
            for node in nodes
        )
    return "\n".join(nodes)


def _render_template_overlay(recipe, contract: dict[str, Any], template: dict[str, Any], layout: LayoutContext) -> str:
    return recipe.render_overlay(contract, template, layout)


def build_hyperframes_index_html(
    contract: dict[str, Any],
    hyperframes_template: str = "auto",
    hyperframes_format: str = "auto",
    genres: list[str] | None = None,
) -> str:
    duration_ms = int(contract["durationMs"])
    duration_s = _seconds(duration_ms)
    width, height, resolved_format = dimensions_for_format(hyperframes_format or contract.get("hyperframesFormat") or "auto")
    is_landscape = width > height
    style = contract.get("style") or {}
    caption_style = style.get("caption") or {}
    template = resolve_hyperframes_template(
        hyperframes_template,
        genres or contract.get("genres") or [],
        str(style.get("template") or ""),
        hyperframes_format=resolved_format,
    )
    contract = {
        **contract,
        "hyperframesTemplate": template["id"],
        "hyperframesFormat": resolved_format,
        "templateVersion": TEMPLATE_VERSION,
        "effectsUsed": template["effects"],
        "componentsUsed": template.get("components_used", []),
        "blocksUsed": template.get("blocks_used", []),
    }
    text_color = _style_hex(caption_style.get("text_color"), "#ffffff")
    highlight_color = _style_hex(caption_style.get("highlight_word_color"), template["accent"])
    if style.get("brand_system"):
        accent = _style_hex(caption_style.get("highlight_word_color"), template["accent"])
    else:
        accent = _style_hex(template.get("accent"), "#d8b45f")
    secondary_accent = _style_hex(template.get("secondary_accent"), "#8ee6c8")
    caption_font_size = int(caption_style.get("font_size") or 54)
    if style.get("template_only"):
        caption_style = apply_readable_template_only_caption(dict(caption_style))
        caption_font_size = int(caption_style.get("font_size") or 48)
        style = {**style, "caption": caption_style}
    font_family = _css_font_family(caption_style.get("font_family") or template.get("font_family") or "Arial")
    caption_background = _css_background(caption_style.get("background_color"))
    stroke_width = float(caption_style.get("stroke_width") or 0)
    recipe = get_recipe(str(template.get("recipe_module") or template["id"]))
    shell_components = recipe.resolved_shell_components(contract)
    brand_system = style.get("brand_system") if isinstance(style.get("brand_system"), dict) else {}
    oss_selections = resolve_oss_selections(
        brand_system,
        duration_ms=duration_ms,
        host_width=width,
        host_height=height,
    )
    placement_timeline = oss_selections.get("timeline")
    has_oss_cta = any(
        block.block_id == str(brand_system.get("cta_overlay") or "")
        for block in oss_selections.get("blocks", [])
    )
    if has_oss_cta:
        shell_components = {**shell_components, "cta": False}
    oss_bundle = build_oss_host_bundle(
        oss_selections,
        contract,
        text_color=text_color,
        highlight_color=highlight_color,
    )
    contract = {
        **contract,
        "shellComponents": shell_components,
        "ossBlocksUsed": list(oss_bundle.block_ids),
        "ossComponentsUsed": list(oss_bundle.component_ids),
    }
    layout = LayoutContext(
        width=width,
        height=height,
        is_landscape=is_landscape,
        caption_font_size=caption_font_size,
        text_color=text_color,
        highlight_color=highlight_color,
        accent=accent,
        secondary_accent=secondary_accent,
    )
    caption_nodes = _render_captions(contract, recipe, layout, oss_bundle.caption_class)
    show_recipe_overlay = True
    overlay_exit_override: float | None = None
    cta_start_s = max(0.0, (duration_ms / 1000) - 6.5)
    if placement_timeline is not None:
        show_recipe_overlay = bool(getattr(placement_timeline, "show_recipe_overlay", True))
        overlay_exit_override = float(getattr(placement_timeline, "overlay_exit_s", 0.0) or 0.0)
        if getattr(placement_timeline, "cta_block_id", ""):
            cta_start_s = float(getattr(placement_timeline, "cta_start_s", cta_start_s))
    template_overlay = (
        _render_template_overlay(recipe, contract, template, layout) if show_recipe_overlay else ""
    )
    shell_body = _render_shell(contract, recipe, template, layout, duration_s)
    recipe_css = recipe.css_block(layout)
    shell_recipe_css = recipe.shell_css(layout)
    cta_start_ms = max(0, int(cta_start_s * 1000))
    hook_exit_s = overlay_exit_override if overlay_exit_override else max(0.2, min(4.5, (duration_ms / 1000) - 0.5))
    overlay_lifecycle_js = _overlay_lifecycle_js(
        duration_ms,
        contract.get("captions") or [],
        overlay_exit_s=overlay_exit_override if show_recipe_overlay and overlay_exit_override else None,
    )
    motion_extra = recipe.motion_block(contract, layout, hook_exit_s, cta_start_s)
    cta_html = (
        recipe.render_cta_html(contract, cta_start_ms, duration_ms, _seconds, _attr)
        if shell_components.get("cta") and str(contract.get("ctaText") or "").strip()
        else ""
    )
    hook_motion = (
        f"""    tl.from("#hook", {{ y: 36, opacity: 0, scale: 0.96, duration: 0.5, ease: "power3.out" }}, 0);
    tl.to("#hook", {{ y: -18, opacity: 0, duration: 0.28, ease: "power2.in" }}, {hook_exit_s:.3f});
"""
        if shell_components.get("hook")
        else ""
    )
    cta_motion = (
        f'    tl.from("#cta", {{ y: 28, opacity: 0, scale: 0.97, duration: 0.35, ease: "power3.out" }}, {cta_start_s:.3f});\n'
        if shell_components.get("cta") and cta_html
        else ""
    )
    root_class = f"{_attr(template['overlay_class'])} {_attr(recipe.overlay_class())}"
    if oss_bundle.caption_class:
        root_class = f"{root_class} {_attr(oss_bundle.caption_class)}"
    caption_word_motion = oss_bundle.caption_timeline_js or f"""
      tl.to(wordEl, {{ color: "{highlight_color}", scale: 1.08, y: -2, duration: 0.06, ease: "power1.out" }}, wordStart);
      tl.to(wordEl, {{ color: "{text_color}", scale: 1, y: 0, duration: 0.06, ease: "power1.in" }}, Math.max(wordStart + 0.08, wordEnd));
"""
    contract_json = json.dumps(contract, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(str(contract.get("candidateId", "hyperframes-render")))}</title>
{recipe.shell_extras_head()}  <style>
{_shell_css(width, height, is_landscape, text_color, accent, secondary_accent, caption_font_size, recipe.video_filter(), font_family, caption_background, stroke_width)}
{shell_recipe_css}
{recipe_css}
{oss_bundle.effect_css}
{oss_bundle.caption_css}
  </style>
</head>
<body>
  <div id="root" class="{root_class}" data-composition-id="premium-hyperframes" data-start="0" data-duration="{duration_s}" data-width="{width}" data-height="{height}">
{shell_body}
    {template_overlay}
    {oss_bundle.effect_html}
    {caption_nodes}
    {cta_html}
{oss_bundle.block_html}
  </div>
  <script id="render-contract" type="application/json">{contract_json}</script>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <script>
    window.__timelines = window.__timelines || {{}};
    const contract = JSON.parse(document.getElementById("render-contract").textContent);
    const tl = gsap.timeline({{ paused: true }});
    const totalSeconds = contract.durationMs / 1000;
    tl.from("#source-video", {{ scale: 1.03, duration: totalSeconds, ease: "none" }}, 0);
{oss_bundle.effect_js}
{overlay_lifecycle_js}{hook_motion}{oss_bundle.effect_timeline_js}    for (let i = 0; i < contract.captions.length; i += 1) {{
      const caption = contract.captions[i];
      const start = caption.startMs / 1000;
      const end = caption.endMs / 1000;
      tl.from(`#cap-${{i}} .caption-card`, {{ y: 24, opacity: 0, duration: 0.16, ease: "power2.out" }}, start);
      tl.to(`#cap-${{i}} .caption-card`, {{ y: -12, opacity: 0, duration: 0.12, ease: "power2.in" }}, Math.max(start, end - 0.12));
      const words = caption.words || [];
      for (let j = 0; j < words.length; j += 1) {{
        const word = words[j];
        const wordStart = Math.max(start, (word.startMs || caption.startMs) / 1000);
        const wordEnd = Math.min(end, (word.endMs || caption.endMs) / 1000);
        const wordEl = `#cap-${{i}}-word-${{j}}`;
{caption_word_motion}
      }}
    }}
{cta_motion}    {motion_extra}
{_TEMPLATE_LAYOUT_FIT_JS}
    window.__timelines["premium-hyperframes"] = tl;
    fitTemplateLayersToCanvas();
  </script>
</body>
</html>
"""


def prepare_hyperframes_project(
    contract: dict[str, Any],
    source_video_path: str,
    project_dir: Path,
    hyperframes_template: str = "auto",
    hyperframes_format: str = "auto",
    genres: list[str] | None = None,
) -> Path:
    media_dir = project_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_video_path, media_dir / "source.mp4")
    html = build_hyperframes_index_html(contract, hyperframes_template, hyperframes_format, genres)
    index_path = project_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    style = contract.get("style") if isinstance(contract.get("style"), dict) else {}
    brand_system = style.get("brand_system") if isinstance(style.get("brand_system"), dict) else {}
    width, height, _ = dimensions_for_format(hyperframes_format or contract.get("hyperframesFormat") or "auto")
    selections = resolve_oss_selections(
        brand_system,
        duration_ms=int(contract.get("durationMs") or 0),
        host_width=width,
        host_height=height,
    )
    copy_oss_files_to_project(project_dir, selections, contract)
    return index_path


def _run_hyperframes(args: list[str], cwd: Path) -> dict[str, Any]:
    result = subprocess.run(
        hyperframes_command(*args),
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=_hyperframes_subprocess_env(),
    )
    output = _sanitize_cli_output(result.stdout or "")
    raw_output = (result.stdout or "").strip()
    return {
        "command": " ".join(hyperframes_command(*args)),
        "returncode": result.returncode,
        "output": output,
        "raw_output": raw_output,
    }


def render_hyperframes_project(project_dir: Path, output_path: Path, quality: str = "standard") -> dict[str, Any]:
    with _HYPERFRAMES_RENDER_LOCK:
        lint = _run_hyperframes(["lint"], project_dir)
        if lint["returncode"] != 0:
            raise RuntimeError(f"hyperframes lint failed: {lint['output']}")
        inspect = _run_hyperframes(["inspect", "--json", "--samples", "9"], project_dir)
        if inspect["returncode"] != 0:
            detail = summarize_hyperframes_inspect_failure(inspect.get("raw_output") or inspect.get("output") or "")
            raise RuntimeError(detail or "HyperFrames layout check failed before render.")
        render = _run_hyperframes(
            ["render", "--output", str(output_path), "--quality", quality, "--workers", "1"],
            project_dir,
        )
        if render["returncode"] != 0:
            raise RuntimeError(f"hyperframes render failed: {render['output']}")
        return {"lint": lint, "inspect": inspect, "render": render}


def render_premium_hyperframes(
    contract: dict[str, Any],
    source_video_path: str,
    profile_id: str,
    candidate_id: str,
    job_id: str,
    quality: str = "standard",
    hyperframes_template: str = "auto",
    hyperframes_format: str = "auto",
    brand_system_template_id: str = "",
    genres: list[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    runtime = require_hyperframes_runtime()
    out_dir = ARTIFACTS_DIR / profile_id / candidate_id
    project_dir = out_dir / f"{job_id}_hyperframes"
    project_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{job_id}_hyperframes.mp4"
    metadata_path = out_dir / f"{job_id}_hyperframes.json"
    width, height, resolved_format = dimensions_for_format(hyperframes_format)
    resolved_template = resolve_hyperframes_template(
        hyperframes_template,
        genres or contract.get("genres") or [],
        str((contract.get("style") or {}).get("template") or ""),
        hyperframes_format=resolved_format,
    )
    contract = {
        **contract,
        "width": width,
        "height": height,
        "hyperframesFormat": resolved_format,
        "brandSystemTemplateId": brand_system_template_id,
    }
    prepare_hyperframes_project(contract, source_video_path, project_dir, hyperframes_template, resolved_format, genres)
    checks = render_hyperframes_project(project_dir, output, quality=quality)
    contract = {
        **contract,
        "renderer": "hyperframes",
        "hyperframesTemplate": resolved_template["id"],
        "hyperframesFormat": resolved_format,
        "brandSystemTemplateId": brand_system_template_id,
        "templateVersion": TEMPLATE_VERSION,
        "effectsUsed": resolved_template["effects"],
        "componentsUsed": resolved_template.get("components_used", []),
        "blocksUsed": resolved_template.get("blocks_used", []),
        "engine": {
            "name": "hyperframes",
            "package": HYPERFRAMES_PACKAGE,
            "runtime": runtime,
            "projectDir": str(project_dir),
            "checks": checks,
        },
    }
    metadata_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(output), contract
