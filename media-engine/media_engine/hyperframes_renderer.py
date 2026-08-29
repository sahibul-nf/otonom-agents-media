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
    video {{ width: 100%; height: 100%; object-fit: cover; filter: {video_filter}; }}
    .shade {{
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, rgba(0,0,0,0.58) 0%, rgba(0,0,0,0.12) 28%, rgba(0,0,0,0.18) 55%, rgba(0,0,0,0.76) 100%);
      pointer-events: none;
    }}
    .micro-label {{
      display: block;
      margin-bottom: 8px;
      color: var(--template-accent);
      font-size: 18px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0;
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
    .brand-grain {{
      position: absolute; inset: 0; pointer-events: none; opacity: 0.22; mix-blend-mode: overlay;
      background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.55'/%3E%3C/svg%3E");
      background-size: 180px 180px;
    }}
    .brand-vignette {{
      position: absolute; inset: 0; pointer-events: none;
      background: radial-gradient(ellipse 70% 65% at 50% 45%, transparent 42%, rgba(0,0,0,.55) 100%);
    }}
    .brand-shimmer {{
      position: absolute; inset: 0; pointer-events: none; overflow: hidden;
    }}
    .brand-shimmer::before {{
      content: "";
      position: absolute; inset: -20% -40%;
      background: linear-gradient(105deg, transparent 30%, {accent}44 48%, transparent 66%);
      transform: translateX(-30%) skewX(-12deg);
      animation: brand-shimmer-sweep 2.8s ease-in-out infinite;
    }}
    @keyframes brand-shimmer-sweep {{
      0% {{ transform: translateX(-40%) skewX(-12deg); }}
      100% {{ transform: translateX(80%) skewX(-12deg); }}
    }}
    .brand-social-pill {{
      position: absolute;
      left: 50%;
      bottom: {300 if is_landscape else 520}px;
      transform: translateX(-50%);
      display: inline-flex;
      align-items: center;
      gap: 12px;
      padding: 12px 18px;
      border-radius: 999px;
      background: rgba(0,0,0,.55);
      border: 1px solid rgba(255,255,255,.16);
      color: #fff;
      font-size: 22px;
      font-weight: 800;
      z-index: 4;
    }}
    .brand-social-pill span {{
      display: grid; place-items: center; width: 28px; height: 28px; border-radius: 999px;
      background: var(--template-accent); color: #041018; font-size: 14px;
    }}
    """


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


def _brand_system_layers(style: dict[str, Any]) -> str:
    brand_system = style.get("brand_system") if isinstance(style.get("brand_system"), dict) else {}
    if not brand_system:
        return ""
    texture = str(brand_system.get("texture_effect") or "").lower()
    cta = str(brand_system.get("cta_overlay") or "").lower()
    layers: list[str] = []
    if "grain" in texture:
        layers.append('<div class="template-layer brand-grain" aria-hidden="true"></div>')
    if "vignette" in texture or (texture and "grain" not in texture and "shimmer" not in texture):
        layers.append('<div class="template-layer brand-vignette" aria-hidden="true"></div>')
    if "shimmer" in texture:
        layers.append('<div class="template-layer brand-shimmer" aria-hidden="true"></div>')
    if cta:
        label = "Follow"
        mark = "●"
        if "yt" in cta or "youtube" in cta:
            label, mark = "Subscribe", "▶"
        elif "instagram" in cta or cta.endswith("ig"):
            label, mark = "Follow", "◎"
        elif "tiktok" in cta:
            label, mark = "Follow", "♪"
        elif "x-" in cta or "twitter" in cta:
            label, mark = "Post", "𝕏"
        layers.append(
            f'<div class="template-layer brand-social-pill" aria-hidden="true"><span>{html.escape(mark)}</span>{html.escape(label)}</div>'
        )
    return "\n    ".join(layers)


def _render_shell(contract: dict[str, Any], recipe, template: dict[str, Any], layout: LayoutContext, duration_s: str) -> str:
    return recipe.render_shell_html(contract, template, layout, duration_s, _seconds, _attr)


def _render_captions(contract: dict[str, Any], recipe, layout: LayoutContext) -> str:
    captions = contract.get("captions") or []
    return "\n".join(
        recipe.render_caption_html(caption, index, layout, _seconds, _attr)
        for index, caption in enumerate(captions)
    )


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
    contract = {**contract, "shellComponents": shell_components}
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
    caption_nodes = _render_captions(contract, recipe, layout)
    template_overlay = _render_template_overlay(recipe, contract, template, layout)
    brand_layers = _brand_system_layers(style)
    shell_body = _render_shell(contract, recipe, template, layout, duration_s)
    recipe_css = recipe.css_block(layout)
    shell_recipe_css = recipe.shell_css(layout)
    cta_start_ms = max(0, duration_ms - 6500)
    hook_exit_s = max(0.2, min(4.5, (duration_ms / 1000) - 0.5))
    cta_start_s = max(0, (duration_ms / 1000) - 6.5)
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
  </style>
</head>
<body>
  <div id="root" class="{root_class}" data-composition-id="premium-hyperframes" data-start="0" data-duration="{duration_s}" data-width="{width}" data-height="{height}">
{shell_body}
    {template_overlay}
    {brand_layers}
    {caption_nodes}
    {cta_html}
  </div>
  <script id="render-contract" type="application/json">{contract_json}</script>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <script>
    window.__timelines = window.__timelines || {{}};
    const contract = JSON.parse(document.getElementById("render-contract").textContent);
    const tl = gsap.timeline({{ paused: true }});
    const totalSeconds = contract.durationMs / 1000;
    tl.from("#source-video", {{ scale: 1.03, duration: totalSeconds, ease: "none" }}, 0);
    tl.from(".template-layer", {{ y: 18, opacity: 0, duration: 0.45, ease: "power2.out", stagger: 0.08 }}, 0.18);
{hook_motion}    for (let i = 0; i < contract.captions.length; i += 1) {{
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
        tl.to(`#cap-${{i}}-word-${{j}}`, {{ color: "{highlight_color}", scale: 1.08, y: -2, duration: 0.06, ease: "power1.out" }}, wordStart);
        tl.to(`#cap-${{i}}-word-${{j}}`, {{ color: "{text_color}", scale: 1, y: 0, duration: 0.06, ease: "power1.in" }}, Math.max(wordStart + 0.08, wordEnd));
      }}
    }}
{cta_motion}    {motion_extra}
    window.__timelines["premium-hyperframes"] = tl;
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
    index_path = project_dir / "index.html"
    index_path.write_text(build_hyperframes_index_html(contract, hyperframes_template, hyperframes_format, genres), encoding="utf-8")
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
    return {"command": " ".join(hyperframes_command(*args)), "returncode": result.returncode, "output": output}


def render_hyperframes_project(project_dir: Path, output_path: Path, quality: str = "standard") -> dict[str, Any]:
    with _HYPERFRAMES_RENDER_LOCK:
        lint = _run_hyperframes(["lint"], project_dir)
        if lint["returncode"] != 0:
            raise RuntimeError(f"hyperframes lint failed: {lint['output']}")
        inspect = _run_hyperframes(["inspect", "--json", "--samples", "9"], project_dir)
        if inspect["returncode"] != 0:
            raise RuntimeError(f"hyperframes inspect failed: {inspect['output']}")
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
