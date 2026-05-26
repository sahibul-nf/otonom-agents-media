"""HyperFrames renderer integration for production video renders."""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .db import ARTIFACTS_DIR, ROOT
from .hyperframes_templates import TEMPLATE_VERSION, dimensions_for_format, resolve_hyperframes_template

HYPERFRAMES_PACKAGE = "hyperframes@0.6.40"
HYPERFRAMES_DIR = ROOT / "render" / "hyperframes"


def _flag_enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _node_major(version: str) -> int:
    match = re.search(r"v?(\d+)", version)
    return int(match.group(1)) if match else 0


def hyperframes_command(*args: str) -> list[str]:
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


def _caption_html(caption: dict[str, Any], index: int, highlight_color: str) -> str:
    start_ms = int(caption.get("startMs", 0))
    end_ms = int(caption.get("endMs", start_ms + 1000))
    duration_ms = max(1, end_ms - start_ms - 2)
    words = caption.get("words") or [{"text": word, "startMs": start_ms, "endMs": end_ms} for word in str(caption.get("text", "")).split()]
    spans = []
    for word_index, word in enumerate(words):
        spans.append(
            '<span '
            f'id="cap-{index}-word-{word_index}" '
            f'data-word-start="{_attr(_seconds(int(word.get("startMs", start_ms))))}" '
            f'data-word-end="{_attr(_seconds(int(word.get("endMs", end_ms))))}">'
            f'{html.escape(str(word.get("text", "")))}'
            "</span>"
        )
    return (
        f'<div id="cap-{index}" class="clip caption-clip" '
        f'data-start="{_attr(_seconds(start_ms))}" '
        f'data-duration="{_attr(_seconds(duration_ms))}" '
        'data-track-index="2">'
        '<div class="caption-card">'
        f'<div class="caption-text" style="--highlight-color:{_attr(highlight_color)}">'
        + "\n".join(spans)
        + "</div></div></div>"
    )


def _template_overlay_html(template: dict[str, Any], contract: dict[str, Any]) -> str:
    template_id = template["id"]
    source = html.escape(str(contract.get("sourceAttribution", "")))
    watermark = html.escape(str(contract.get("watermarkText", "")))
    title = html.escape(str(contract.get("titleHook", "")))
    cta = html.escape(str(contract.get("ctaText", "")))
    if template_id == "podcast_talking_head":
        return f"""
    <div id="template-lower-third" class="template-layer lower-third">
      <span class="micro-label">Guest highlight</span>
      <strong>{title}</strong>
      <small>{watermark}</small>
    </div>
    <div id="template-social" class="template-layer social-pill">Follow for the next clip</div>"""
    if template_id == "data_market_explainer":
        return f"""
    <div id="template-metrics" class="template-layer metrics-panel">
      <div><span>Signal</span><strong>74</strong></div>
      <div><span>Window</span><strong>Short</strong></div>
      <div><span>Action</span><strong>Watch</strong></div>
    </div>
    <div id="template-bars" class="template-layer chart-bars"><span></span><span></span><span></span><span></span></div>"""
    if template_id == "news_geo_brief":
        return f"""
    <div id="template-map" class="template-layer map-card">
      <span class="micro-label">Regional brief</span>
      <strong>{source or "Verified source"}</strong>
      <div class="map-grid"><i></i><i></i><i></i><i></i></div>
    </div>
    <div id="template-ticker" class="template-layer ticker">Source checked · Context preserved · Review required</div>"""
    if template_id == "product_brand_promo":
        return f"""
    <div id="template-logo" class="template-layer logo-badge">{watermark or "Brand"}</div>
    <div id="template-offer" class="template-layer promo-card">
      <span class="micro-label">Creator promo</span>
      <strong>{cta}</strong>
      <small>Save, follow, and share</small>
    </div>"""
    return f"""
    <div id="template-grain" class="template-layer grain"></div>
    <div id="template-reflection" class="template-layer reflection-note">
      <span class="micro-label">Reflective clip</span>
      <strong>{watermark}</strong>
    </div>"""


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
    template = resolve_hyperframes_template(hyperframes_template, genres or contract.get("genres") or [], str(style.get("template") or ""))
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
    accent = _style_hex(template.get("accent"), "#d8b45f")
    secondary_accent = _style_hex(template.get("secondary_accent"), "#8ee6c8")
    caption_font_size = int(caption_style.get("font_size") or 54)
    captions = contract.get("captions") or []
    caption_nodes = "\n".join(_caption_html(caption, index, highlight_color) for index, caption in enumerate(captions))
    template_overlay = _template_overlay_html(template, contract)
    cta_start_ms = max(0, duration_ms - 6500)
    hook_exit_s = max(0.2, min(4.5, (duration_ms / 1000) - 0.5))
    cta_start_s = max(0, (duration_ms / 1000) - 6.5)
    contract_json = json.dumps(contract, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(str(contract.get("candidateId", "hyperframes-render")))}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #111111; font-family: Arial, sans-serif; }}
    #root {{
      position: relative;
      width: {width}px;
      height: {height}px;
      overflow: hidden;
      background: #050607;
      color: {text_color};
      --template-accent: {accent};
      --template-secondary: {secondary_accent};
    }}
    video {{ width: 100%; height: 100%; object-fit: cover; filter: contrast(1.06) saturate(0.96) brightness(0.92); }}
    .shade {{
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, rgba(0,0,0,0.58) 0%, rgba(0,0,0,0.12) 28%, rgba(0,0,0,0.18) 55%, rgba(0,0,0,0.76) 100%);
      pointer-events: none;
    }}
    .template-layer {{ position: absolute; z-index: 5; pointer-events: none; }}
    .grain {{
      inset: 0;
      opacity: 0.16;
      background-image: radial-gradient(rgba(255,255,255,0.20) 1px, transparent 1px);
      background-size: 7px 7px;
      mix-blend-mode: overlay;
    }}
    .reflection-note, .lower-third, .map-card, .promo-card, .metrics-panel {{
      border: 1px solid rgba(255,255,255,0.14);
      background: rgba(4,7,8,0.68);
      box-shadow: 0 18px 48px rgba(0,0,0,0.36);
      backdrop-filter: blur(12px);
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
    .reflection-note {{
      left: 56px;
      top: 58px;
      max-width: 390px;
      border-radius: 18px;
      padding: 16px 20px;
      color: rgba(255,255,255,0.86);
      font-size: 23px;
      line-height: 1.16;
    }}
    .lower-third {{
      left: {72 if is_landscape else 58}px;
      right: {72 if is_landscape else 58}px;
      top: {690 if is_landscape else 1180}px;
      border-radius: 22px;
      padding: 18px 22px;
    }}
    .lower-third strong, .map-card strong, .promo-card strong {{ display: block; color: #fff; font-size: 30px; line-height: 1.08; }}
    .lower-third small, .promo-card small {{ display: block; margin-top: 8px; color: rgba(255,255,255,0.66); font-size: 21px; }}
    .social-pill {{
      right: 58px;
      bottom: 210px;
      border-radius: 999px;
      padding: 16px 22px;
      background: var(--template-accent);
      color: #061114;
      font-size: 23px;
      font-weight: 900;
    }}
    .metrics-panel {{
      left: {72 if is_landscape else 50}px;
      right: {72 if is_landscape else 50}px;
      top: 86px;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
      border-radius: 20px;
      padding: 14px;
    }}
    .metrics-panel div {{ border-radius: 14px; background: rgba(255,255,255,0.07); padding: 13px; }}
    .metrics-panel span {{ display: block; color: rgba(255,255,255,0.62); font-size: 17px; font-weight: 800; }}
    .metrics-panel strong {{ display: block; margin-top: 3px; color: var(--template-accent); font-size: 30px; }}
    .chart-bars {{
      right: {86 if is_landscape else 60}px;
      top: {230 if is_landscape else 290}px;
      display: flex;
      align-items: end;
      gap: 8px;
      height: 92px;
    }}
    .chart-bars span {{ width: 24px; border-radius: 999px; background: linear-gradient(180deg, var(--template-accent), var(--template-secondary)); }}
    .chart-bars span:nth-child(1) {{ height: 44px; }}
    .chart-bars span:nth-child(2) {{ height: 72px; }}
    .chart-bars span:nth-child(3) {{ height: 56px; }}
    .chart-bars span:nth-child(4) {{ height: 90px; }}
    .map-card {{
      left: {72 if is_landscape else 58}px;
      right: {72 if is_landscape else 58}px;
      top: 68px;
      border-radius: 22px;
      padding: 18px;
    }}
    .map-grid {{ margin-top: 14px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }}
    .map-grid i {{ height: 34px; border-radius: 10px; background: rgba(125,211,252,0.18); border: 1px solid rgba(125,211,252,0.24); }}
    .ticker {{
      left: 0;
      right: 0;
      bottom: 0;
      padding: 16px 24px;
      background: rgba(0,0,0,0.76);
      border-top: 2px solid var(--template-accent);
      color: rgba(255,255,255,0.82);
      text-align: center;
      font-size: 21px;
      font-weight: 800;
    }}
    .logo-badge {{
      top: 62px;
      right: 54px;
      border-radius: 999px;
      padding: 15px 20px;
      background: rgba(0,0,0,0.62);
      border: 1px solid rgba(255,255,255,0.16);
      color: var(--template-accent);
      font-size: 24px;
      font-weight: 950;
    }}
    .promo-card {{
      left: {72 if is_landscape else 56}px;
      right: {72 if is_landscape else 56}px;
      bottom: {142 if is_landscape else 220}px;
      overflow: hidden;
      border-radius: 24px;
      padding: 20px 24px;
    }}
    .promo-card::after {{
      content: "";
      position: absolute;
      inset: 0;
      transform: translateX(-120%);
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.18), transparent);
    }}
    .template-podcast .caption-card {{ border-radius: 999px; border-color: color-mix(in srgb, var(--template-accent) 45%, transparent); }}
    .template-data .caption-card, .template-promo .caption-card {{ border-color: color-mix(in srgb, var(--template-accent) 42%, transparent); }}
    .template-news .hook {{ text-align: left; }}
    .template-news .hook h1 {{ font-size: 64px; }}
    .hook {{
      position: absolute;
      top: {110 if is_landscape else 170}px;
      left: {120 if is_landscape else 72}px;
      right: {120 if is_landscape else 72}px;
      text-align: center;
      text-shadow: 0 5px 24px rgba(0,0,0,0.72);
    }}
    .hook h1 {{ margin: 0; font-size: {62 if is_landscape else 74}px; line-height: 0.98; font-weight: 900; letter-spacing: 0; }}
    .hook p {{ margin: 22px 0 0; font-size: {26 if is_landscape else 30}px; line-height: 1.18; color: rgba(255,255,255,0.84); font-weight: 650; }}
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
      background: rgba(4, 7, 8, 0.72);
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
      font-size: {caption_font_size}px;
      line-height: 1.08;
      font-weight: 900;
      text-shadow: 0 3px 12px rgba(0,0,0,0.9);
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
    .source {{ color: #9be7b0; text-align: right; }}
    .cta {{
      position: absolute;
      left: {90 if is_landscape else 62}px;
      right: {90 if is_landscape else 62}px;
      bottom: {50 if is_landscape else 95}px;
      padding: 22px 26px;
      border-radius: 18px;
      background: rgba(0, 0, 0, 0.68);
      border: 2px solid #f4d35e;
      color: #f4d35e;
      text-align: center;
      font-size: 34px;
      line-height: 1.12;
      font-weight: 900;
      box-shadow: 0 16px 44px rgba(0,0,0,0.38);
    }}
  </style>
</head>
<body>
  <div id="root" class="{_attr(template["overlay_class"])}" data-composition-id="premium-hyperframes" data-start="0" data-duration="{duration_s}" data-width="{width}" data-height="{height}">
    <video id="source-video" class="clip" data-start="0" data-duration="{duration_s}" data-track-index="0" src="media/source.mp4" muted playsinline></video>
    <audio id="source-audio" class="clip" data-start="0" data-duration="{duration_s}" data-track-index="4" src="media/source.mp4" data-volume="1"></audio>
    <div class="shade"></div>
    {template_overlay}
    <div id="hook" class="clip hook" data-start="0" data-duration="{_attr(_seconds(min(4800, duration_ms)))}" data-track-index="1">
      <h1>{html.escape(str(contract.get("titleHook", "")))}</h1>
      <p>{html.escape(str(contract.get("subtitle", "")))}</p>
    </div>
    {caption_nodes}
    <div class="brand-row">
      <span>{html.escape(str(contract.get("watermarkText", "")))}</span>
      <span class="source">{html.escape(str(contract.get("sourceAttribution", "")))}</span>
    </div>
    <div id="cta" class="clip cta" data-start="{_attr(_seconds(cta_start_ms))}" data-duration="{_attr(_seconds(duration_ms - cta_start_ms))}" data-track-index="3">
      {html.escape(str(contract.get("ctaText", "")))}
    </div>
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
    tl.from("#hook", {{ y: 36, opacity: 0, scale: 0.96, duration: 0.5, ease: "power3.out" }}, 0);
    tl.to("#hook", {{ y: -18, opacity: 0, duration: 0.28, ease: "power2.in" }}, {hook_exit_s:.3f});
    for (let i = 0; i < contract.captions.length; i += 1) {{
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
    tl.from("#cta", {{ y: 28, opacity: 0, scale: 0.97, duration: 0.35, ease: "power3.out" }}, {cta_start_s:.3f});
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
    )
    return {"command": " ".join(hyperframes_command(*args)), "returncode": result.returncode, "output": result.stdout[-6000:]}


def render_hyperframes_project(project_dir: Path, output_path: Path, quality: str = "standard") -> dict[str, Any]:
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
    resolved_template = resolve_hyperframes_template(hyperframes_template, genres or contract.get("genres") or [], str((contract.get("style") or {}).get("template") or ""))
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
