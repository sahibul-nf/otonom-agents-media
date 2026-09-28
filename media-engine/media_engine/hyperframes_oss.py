"""Vendored HyperFrames OSS catalog: manifest, copy, and host wiring."""

from __future__ import annotations

import base64
import html
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .db import ROOT

HYPERFRAMES_DIR = ROOT / "render" / "hyperframes"
OSS_MANIFEST_PATH = HYPERFRAMES_DIR / "oss-manifest.json"
OSS_ASSETS_DIR = HYPERFRAMES_DIR / "assets"
MAX_EXTRA_BLOCKS = 3
# Hidden from Brand Builder / production CTA picker until re-enabled.
DISABLED_CTA_OVERLAYS = frozenset({"x-post"})

INTRO_BLOCK_MAP: dict[str, str] = {
    "lower-third-hook": "yt-lower-third",
}
INTRO_LAYOUT_NONE = frozenset({"", "none"})
INTRO_LAYOUT_TEMPLATE_HOOK = frozenset(
    {"template-hook", "editorial-hook", "headline-slam", "data-callout"}
)
INTRO_LAYOUT_LOWER_THIRD = frozenset({"lower-third-hook"})
CTA_HOLD_MIN_S = 1.6
CTA_HOLD_MAX_S = 2.2
INTRO_BLOCK_MAX_S = 2.2
INTRO_BLOCK_MIN_S = 1.6
OVERLAY_CTA_GAP_S = 0.25

_GOOGLE_FONT_LINK_RE = re.compile(
    r"<link[^>]*fonts\.googleapis\.com[^>]*>\s*",
    re.IGNORECASE,
)
_GOOGLE_FONT_PRECONNECT_RE = re.compile(
    r'<link rel="preconnect" href="https://fonts\.gstatic\.com"[^>]*>\s*',
    re.IGNORECASE,
)
_STYLE_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.DOTALL | re.IGNORECASE)
_SCRIPT_RE = re.compile(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class PlacementTimeline:
    show_recipe_overlay: bool
    overlay_exit_s: float
    intro_block_id: str
    intro_block_start_s: float
    intro_block_duration_s: float
    cta_block_id: str
    cta_start_s: float
    cta_duration_s: float


@dataclass(frozen=True)
class OssBlockPlacement:
    block_id: str
    composition_id: str
    src: str
    start_s: float
    duration_s: float
    render_width: int
    render_height: int
    track_index: int
    wrapper_style: str
    inner_style: str


@dataclass(frozen=True)
class OssHostBundle:
    effect_html: str
    effect_css: str
    effect_js: str
    effect_timeline_js: str
    block_html: str
    caption_css: str
    caption_class: str
    caption_timeline_js: str
    block_ids: tuple[str, ...]
    component_ids: tuple[str, ...]
    copied_paths: tuple[str, ...]


def load_oss_manifest() -> dict[str, Any]:
    if not OSS_MANIFEST_PATH.exists():
        return {"version": "", "items": []}
    return json.loads(OSS_MANIFEST_PATH.read_text(encoding="utf-8"))


def installed_catalog_items() -> list[dict[str, Any]]:
    manifest = load_oss_manifest()
    items = manifest.get("items") if isinstance(manifest.get("items"), list) else []
    return [item for item in items if isinstance(item, dict) and item.get("id")]


def installed_item_ids() -> set[str]:
    return {str(item["id"]) for item in installed_catalog_items()}


def _item_by_id(item_id: str) -> dict[str, Any] | None:
    for item in installed_catalog_items():
        if item.get("id") == item_id:
            return item
    return None


def _normalize_texture_effects(brand_system: dict[str, Any]) -> list[str]:
    installed = installed_item_ids()
    raw_list = brand_system.get("texture_effects")
    if isinstance(raw_list, list):
        return [str(value).strip() for value in raw_list if str(value).strip() in installed]
    legacy = str(brand_system.get("texture_effect") or "none").strip().lower()
    if legacy in {"", "none"}:
        return []
    if legacy in installed:
        return [legacy]
    aliases = {
        "grain": "grain-overlay",
        "grain-overlay": "grain-overlay",
        "vignette": "vignette",
        "shimmer": "shimmer-sweep",
        "shimmer-sweep": "shimmer-sweep",
    }
    mapped = aliases.get(legacy)
    return [mapped] if mapped and mapped in installed else []


def _normalize_extra_blocks(brand_system: dict[str, Any]) -> list[str]:
    installed = installed_item_ids()
    raw = brand_system.get("extra_blocks")
    if not isinstance(raw, list):
        return []
    blocks: list[str] = []
    for value in raw:
        block_id = str(value).strip()
        if block_id in installed and block_id not in blocks:
            blocks.append(block_id)
        if len(blocks) >= MAX_EXTRA_BLOCKS:
            break
    return blocks


def _cta_hold_seconds(total_s: float) -> float:
    ratio_hold = total_s * (0.35 if total_s <= 10 else 0.22)
    return min(CTA_HOLD_MAX_S, max(CTA_HOLD_MIN_S, ratio_hold))


def resolve_intro_config(brand_system: dict[str, Any], installed: set[str]) -> tuple[str, bool]:
    """Return (intro OSS block id, show recipe template-layer overlay)."""
    intro_layout = str(brand_system.get("intro_layout") or "template-hook").strip().lower()
    intro_block = str(brand_system.get("intro_block") or "").strip()

    if intro_layout in INTRO_LAYOUT_NONE:
        return "", False

    block_id = ""
    if intro_block in installed:
        block_id = intro_block
    elif intro_layout in INTRO_LAYOUT_LOWER_THIRD and "yt-lower-third" in installed:
        block_id = "yt-lower-third"

    show_recipe_overlay = intro_layout in INTRO_LAYOUT_TEMPLATE_HOOK and not block_id
    if intro_layout in INTRO_LAYOUT_LOWER_THIRD:
        show_recipe_overlay = False
    return block_id, show_recipe_overlay


def placement_timeline(
    total_s: float,
    *,
    cta_id: str = "",
    intro_block_id: str = "",
    show_recipe_overlay: bool = False,
) -> PlacementTimeline:
    """Sequence recipe intro overlay and OSS blocks so outro never overlaps intro."""
    total_s = max(0.1, total_s)
    cta_hold = _cta_hold_seconds(total_s) if cta_id else 0.0
    cta_start = max(0.0, total_s - cta_hold) if cta_id else total_s
    cta_duration = max(0.5, min(cta_hold, total_s - cta_start)) if cta_id else 0.0

    intro_id = intro_block_id
    if intro_id and intro_id == cta_id:
        intro_id = ""

    intro_start = 0.0
    intro_duration = 0.0
    if intro_id:
        max_intro = cta_start - OVERLAY_CTA_GAP_S if cta_id else min(INTRO_BLOCK_MAX_S, total_s * 0.4)
        intro_duration = min(INTRO_BLOCK_MAX_S, max(INTRO_BLOCK_MIN_S, max_intro))
        intro_duration = max(0.5, min(intro_duration, total_s - 0.1))

    overlay_exit = 0.0
    if show_recipe_overlay:
        intro_cap = min(INTRO_BLOCK_MAX_S, total_s * 0.35)
        if cta_id:
            overlay_exit = min(intro_cap, cta_start - OVERLAY_CTA_GAP_S)
        else:
            overlay_exit = intro_cap
        overlay_exit = max(0.9, min(overlay_exit, total_s - 0.35))

    return PlacementTimeline(
        show_recipe_overlay=show_recipe_overlay,
        overlay_exit_s=overlay_exit,
        intro_block_id=intro_id,
        intro_block_start_s=intro_start,
        intro_block_duration_s=intro_duration,
        cta_block_id=cta_id,
        cta_start_s=cta_start,
        cta_duration_s=cta_duration,
    )


def resolve_oss_selections(
    brand_system: dict[str, Any],
    *,
    duration_ms: int,
    host_width: int,
    host_height: int,
) -> dict[str, Any]:
    installed = installed_item_ids()
    total_s = max(0.1, duration_ms / 1000)

    cta_id = str(brand_system.get("cta_overlay") or "none").strip()
    if cta_id in DISABLED_CTA_OVERLAYS or cta_id not in installed or cta_id == "none":
        cta_id = ""

    intro_block_id, show_recipe_overlay = resolve_intro_config(brand_system, installed)
    timeline = placement_timeline(
        total_s,
        cta_id=cta_id,
        intro_block_id=intro_block_id,
        show_recipe_overlay=show_recipe_overlay,
    )

    caption_style = str(brand_system.get("caption_style") or "").strip()
    if caption_style not in installed:
        caption_style = ""

    textures = _normalize_texture_effects(brand_system)
    extras = _normalize_extra_blocks(brand_system)

    blocks: list[OssBlockPlacement] = []
    track = 6

    def add_block(block_id: str, start_s: float, block_duration_s: float, placement_track: int) -> None:
        item = _item_by_id(block_id)
        if not item or item.get("kind") != "block":
            return
        block_duration = max(0.5, min(block_duration_s, total_s))
        start = max(0.0, min(start_s, total_s - 0.1))
        if start + block_duration > total_s:
            block_duration = max(0.5, total_s - start)
        bw = int(item.get("width") or host_width)
        bh = int(item.get("height") or host_height)
        render_w, render_h, wrapper_style, inner_style = _block_render_geometry(
            bw, bh, host_width, host_height
        )
        blocks.append(
            OssBlockPlacement(
                block_id=block_id,
                composition_id=str(item.get("composition_id") or block_id),
                src=str(item.get("path") or f"compositions/{block_id}.html"),
                start_s=start,
                duration_s=block_duration,
                render_width=render_w,
                render_height=render_h,
                track_index=placement_track,
                wrapper_style=wrapper_style,
                inner_style=inner_style,
            )
        )

    if timeline.intro_block_id:
        add_block(
            timeline.intro_block_id,
            timeline.intro_block_start_s,
            timeline.intro_block_duration_s,
            track,
        )
        track += 1
    if timeline.cta_block_id and timeline.cta_block_id not in {block.block_id for block in blocks}:
        add_block(timeline.cta_block_id, timeline.cta_start_s, timeline.cta_duration_s, track)
        track += 1
    for extra_id in extras:
        if extra_id in {block.block_id for block in blocks}:
            continue
        mid_start = max(timeline.overlay_exit_s + 0.2, total_s * 0.35)
        if timeline.cta_block_id:
            mid_start = min(mid_start, timeline.cta_start_s - 1.0)
        add_block(extra_id, max(0.0, mid_start), min(2.0, total_s * 0.25), track)
        track += 1

    return {
        "blocks": blocks,
        "textures": textures,
        "caption_style": caption_style,
        "timeline": timeline,
        "block_ids": tuple(block.block_id for block in blocks),
        "component_ids": tuple(
            [value for value in [caption_style, *textures] if value]
        ),
    }


def _block_render_geometry(
    block_w: int,
    block_h: int,
    host_w: int,
    host_h: int,
) -> tuple[int, int, str, str]:
    """Map block canvas to host coordinates for HyperFrames sub-composition compositing."""
    is_landscape_block = block_w > block_h
    is_portrait_host = host_h > host_w
    block_aspect = block_w / block_h
    host_aspect = host_w / host_h

    if is_landscape_block and is_portrait_host:
        # Landscape CTA (e.g. yt-lower-third): fit width, bottom strip only — avoids half-frame letterbox.
        render_w = host_w
        render_h = max(1, int(block_h * (host_w / block_w)))
        wrapper = f"position:absolute;left:0;right:0;bottom:0;height:{render_h}px;overflow:hidden;"
        inner = f"position:absolute;left:0;bottom:0;width:{render_w}px;height:{render_h}px;"
        return render_w, render_h, wrapper, inner

    if is_portrait_host and block_h >= block_w:
        # Portrait social blocks (tiktok/instagram): full-frame transparent overlay, card in lower third.
        scale = min(host_w / block_w, host_h / block_h)
        render_w = max(1, int(block_w * scale))
        render_h = max(1, int(block_h * scale))
        wrapper = "position:absolute;inset:0;overflow:hidden;"
        inner = f"position:absolute;left:0;top:0;width:{render_w}px;height:{render_h}px;"
        return render_w, render_h, wrapper, inner

    if not is_portrait_host and not is_landscape_block and abs(block_aspect - host_aspect) < 0.05:
        render_w = host_w
        render_h = host_h
        wrapper = "position:absolute;inset:0;overflow:hidden;"
        inner = f"position:absolute;left:0;top:0;width:{render_w}px;height:{render_h}px;"
        return render_w, render_h, wrapper, inner

    scale = min(host_w / block_w, host_h / block_h, 1.0)
    render_w = max(1, int(block_w * scale))
    render_h = max(1, int(block_h * scale))
    wrapper = "position:absolute;inset:0;overflow:hidden;"
    inner = (
        f"position:absolute;left:50%;bottom:8%;width:{render_w}px;height:{render_h}px;"
        f"transform:translateX(-50%);"
    )
    return render_w, render_h, wrapper, inner


def _truncate_label(text: str, max_len: int) -> str:
    compact = str(text or "").strip()
    if len(compact) <= max_len:
        return compact
    return f"{compact[: max_len - 1].rstrip()}…"


def _normalize_social_handle(raw: str, fallback: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return fallback
    return text if text.startswith("@") else f"@{text.lstrip('@')}"


def _brand_initials(channel_name: str) -> str:
    words = [word for word in channel_name.split() if word]
    if len(words) >= 2:
        return f"{words[0][0]}{words[1][0]}".upper()
    compact = re.sub(r"[^a-zA-Z0-9]", "", channel_name)
    return (compact[:2] or "BC").upper()


def _has_custom_avatar(brand: dict[str, Any]) -> bool:
    data_url = str(brand.get("social_avatar_data_url") or "").strip()
    if data_url.startswith("data:image/"):
        return True
    return bool(str(brand.get("social_avatar_asset") or "").strip())


def _brand_vars(contract: dict[str, Any]) -> dict[str, str]:
    style = contract.get("style") if isinstance(contract.get("style"), dict) else {}
    brand = style.get("brand") if isinstance(style.get("brand"), dict) else {}
    channel = str(brand.get("watermark_text") or contract.get("watermarkText") or "Brand Clips").strip()
    slug = re.sub(r"[^a-zA-Z0-9_]", "", channel.replace(" ", "")) or "brandclips"
    default_handle = f"@{slug.lower()}"
    handle = _normalize_social_handle(str(brand.get("social_handle") or ""), default_handle)
    follower_count = str(brand.get("social_follower_count") or "").strip()
    subscriber_count = str(brand.get("social_subscriber_count") or follower_count).strip()
    avatar_src = "assets/avatar.jpg" if _has_custom_avatar(brand) else "assets/avatar.svg"
    return {
        "channel_name": channel,
        "display_name": channel,
        "handle": handle,
        "x_post_display_name": _truncate_label(channel, 16),
        "x_post_handle": _truncate_label(handle, 16),
        "subscriber_count": subscriber_count or "Subscribe for more",
        "follower_count": follower_count,
        "hide_follower_count": "1" if not follower_count else "0",
        "avatar_src": avatar_src,
        "tweet_body": _truncate_label("New episode out now.", 36),
    }


def _social_hide_count_css() -> str:
    return """
      <style data-brand-social-hide="counts">
        .follower-count,
        .subscriber-count {
          display: none !important;
          height: 0 !important;
          margin: 0 !important;
          overflow: hidden !important;
        }
      </style>
"""


def _sanitize_vendored_html(content: str, brand: dict[str, str]) -> str:
    text = _GOOGLE_FONT_LINK_RE.sub("", content)
    text = _GOOGLE_FONT_PRECONNECT_RE.sub("", text)
    # Keep social CTA slide offsets inside canvas bounds for HyperFrames inspect.
    text = text.replace("gsap.set(card, { y: 300, opacity: 0 });", "gsap.set(card, { y: 64, opacity: 0 });")
    text = text.replace("gsap.set(card, { y: 400, opacity: 0 });", "gsap.set(card, { y: 64, opacity: 0 });")
    text = re.sub(r"y: 300,\s*\n\s*opacity: 0,", "y: 64,\n          opacity: 0,", text)
    text = re.sub(r"y: 400,\s*\n\s*opacity: 0,", "y: 64,\n          opacity: 0,", text)
    follower_count = brand.get("follower_count") or ""
    subscriber_count = brand.get("subscriber_count") or "Subscribe for more"
    x_display = brand.get("x_post_display_name") or brand["display_name"]
    x_handle = brand.get("x_post_handle") or brand["handle"]
    replacements = {
        "HeyGen": brand["display_name"],
        "Hyperframes": brand["display_name"],
        "@heygen.com": brand["handle"],
        "@heygen_official": brand["handle"],
        "@hyperframes": brand["handle"],
        "82.2K subscribers": subscriber_count,
        "1,999 followers": follower_count or "1,999 followers",
        "47.5K followers": follower_count or "47.5K followers",
        'alt="HeyGen"': f'alt="{html.escape(brand["channel_name"])}"',
        'src="assets/avatar.jpg"': f'src="{html.escape(brand["avatar_src"])}"',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(
        r'(<div class="tweet-body">\s*)(.*?)(\s*</div>)',
        lambda match: f"{match.group(1)}{brand['tweet_body']}{match.group(3)}",
        text,
        count=1,
        flags=re.DOTALL,
    )
    if 'data-composition-id="x-post"' in text:
        text = text.replace("HeyGen", x_display)
        text = text.replace("@heygen_official", x_handle)
        text = text.replace("gsap.set(card, { y: 64, opacity: 0 });", "gsap.set(card, { opacity: 0 });")
        text = re.sub(
            r"gsap\.set\(card, \{ y: 64, opacity: 0 \}\);",
            "gsap.set(card, { opacity: 0 });",
            text,
        )
        text = re.sub(
            r"tl\.to\(\s*card,\s*\{\s*y: 64,\s*opacity: 0,",
            "tl.to(card, { opacity: 0,",
            text,
        )
        text = re.sub(
            r"tl\.to\(\s*card,\s*\{\s*y: 0,\s*opacity: 1,",
            "tl.to(card, { opacity: 1,",
            text,
        )
    if brand.get("hide_follower_count") == "1":
        text = text.replace("</head>", f"{_social_hide_count_css()}\n  </head>", 1)
    return text


def _write_image_data_url(data_url: str, dest: Path) -> None:
    match = re.match(r"data:image/(?:png|jpe?g|webp);base64,(.+)", str(data_url or "").strip(), re.IGNORECASE)
    if not match:
        raise ValueError("social avatar must be a base64 image data URL")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(base64.b64decode(match.group(1)))


def _resolve_social_avatar_source(contract: dict[str, Any]) -> Path | None:
    style = contract.get("style") if isinstance(contract.get("style"), dict) else {}
    brand = style.get("brand") if isinstance(style.get("brand"), dict) else {}
    data_url = str(brand.get("social_avatar_data_url") or "").strip()
    if data_url.startswith("data:image/"):
        return None  # handled via data URL write in copy step
    asset_rel = str(brand.get("social_avatar_asset") or "").strip()
    if not asset_rel:
        return None
    path = (ROOT / asset_rel).resolve()
    if ROOT.resolve() not in path.parents or not path.is_file():
        return None
    return path


def _write_initials_avatar_svg(dest: Path, channel_name: str) -> None:
    initials = _brand_initials(channel_name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240" viewBox="0 0 240 240">'
            f'<circle cx="120" cy="120" r="120" fill="#2a2a2a"/>'
            f'<text x="120" y="132" text-anchor="middle" font-family="Arial,sans-serif" '
            f'font-size="88" font-weight="700" fill="#ffffff">{html.escape(initials)}</text>'
            f"</svg>"
        ),
        encoding="utf-8",
    )


def _write_social_avatar_to_project(contract: dict[str, Any], assets_dst: Path) -> str:
    style = contract.get("style") if isinstance(contract.get("style"), dict) else {}
    brand = style.get("brand") if isinstance(style.get("brand"), dict) else {}
    data_url = str(brand.get("social_avatar_data_url") or "").strip()
    if data_url.startswith("data:image/"):
        dest = assets_dst / "avatar.jpg"
        _write_image_data_url(data_url, dest)
        return "assets/avatar.jpg"
    source = _resolve_social_avatar_source(contract)
    if source:
        dest = assets_dst / "avatar.jpg"
        shutil.copy2(source, dest)
        return "assets/avatar.jpg"
    channel = str(brand.get("watermark_text") or contract.get("watermarkText") or "Brand Clips").strip()
    svg_dest = assets_dst / "avatar.svg"
    _write_initials_avatar_svg(svg_dest, channel)
    return "assets/avatar.svg"


def _parse_component_snippet(path: Path) -> dict[str, str]:
    raw = path.read_text(encoding="utf-8")
    styles = _STYLE_RE.findall(raw)
    scripts = _SCRIPT_RE.findall(raw)
    body = _STYLE_RE.sub("", raw)
    body = _SCRIPT_RE.sub("", body)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()
    return {
        "html": body,
        "css": "\n".join(styles).strip(),
        "js": "\n".join(scripts).strip(),
    }


def _extract_caption_css(component_path: Path) -> str:
    raw = component_path.read_text(encoding="utf-8")
    styles = _STYLE_RE.findall(raw)
    if not styles:
        return ""
    css = "\n".join(styles)
    css = _GOOGLE_FONT_LINK_RE.sub("", css)
    skip_prefixes = ("html,", "body {", "body,", "#editorial-emphasis", "#caption-")
    kept: list[str] = []
    for line in css.splitlines():
        stripped = line.strip()
        if any(stripped.startswith(prefix) for prefix in skip_prefixes):
            continue
        if stripped in {"html,", "body {"}:
            continue
        kept.append(line)
    return "\n".join(kept)


def _caption_timeline_js(caption_style: str, text_color: str, highlight_color: str) -> str:
    if caption_style == "caption-pill-karaoke":
        return f"""
      tl.to(wordEl, {{ backgroundColor: "{highlight_color}", color: "#041018", scale: 1.05, duration: 0.08, ease: "power2.out" }}, wordStart);
      tl.to(wordEl, {{ backgroundColor: "transparent", color: "{text_color}", scale: 1, duration: 0.08, ease: "power2.in" }}, Math.max(wordStart + 0.08, wordEnd));
"""
    if caption_style == "caption-neon-glow":
        return f"""
      tl.to(wordEl, {{ color: "{highlight_color}", textShadow: "0 0 18px {highlight_color}", scale: 1.06, duration: 0.07, ease: "power2.out" }}, wordStart);
      tl.to(wordEl, {{ color: "{text_color}", textShadow: "0 0 0px transparent", scale: 1, duration: 0.07, ease: "power2.in" }}, Math.max(wordStart + 0.08, wordEnd));
"""
    if caption_style == "caption-gradient-fill":
        return f"""
      tl.to(wordEl, {{ color: "{highlight_color}", scale: 1.08, duration: 0.07, ease: "power2.out" }}, wordStart);
      tl.to(wordEl, {{ color: "{text_color}", scale: 1, duration: 0.07, ease: "power2.in" }}, Math.max(wordStart + 0.08, wordEnd));
"""
    return f"""
      tl.to(wordEl, {{ color: "{highlight_color}", scale: 1.08, y: -2, duration: 0.06, ease: "power1.out" }}, wordStart);
      tl.to(wordEl, {{ color: "{text_color}", scale: 1, y: 0, duration: 0.06, ease: "power1.in" }}, Math.max(wordStart + 0.08, wordEnd));
"""


def _effect_timeline_js(texture_ids: list[str], total_s: float) -> str:
    lines: list[str] = []
    if "vignette" in texture_ids:
        lines.append(
            '    tl.fromTo("#hf-vignette", { "--vignette-color": "rgba(0, 0, 0, 0)" }, '
            '{ "--vignette-color": "rgba(0, 0, 0, 0.7)", duration: 1, ease: "power2.out" }, 0);'
        )
    if "shimmer-sweep" in texture_ids:
        half = max(0.4, total_s / 4)
        repeat = max(0, int(total_s / (half * 2)) - 1)
        lines.append(
            f'    tl.fromTo(".shimmer-sweep-target", {{ "--shimmer-pos": "-20%" }}, '
            f'{{ "--shimmer-pos": "120%", duration: {half:.2f}, ease: "power2.inOut" }}, 0.5);'
        )
        if repeat > 0:
            lines.append(
                f"    tl.fromTo('.shimmer-sweep-target', {{ '--shimmer-pos': '-20%' }}, "
                f"{{ '--shimmer-pos': '120%', duration: {half:.2f}, ease: 'power2.inOut', repeat: {repeat} }}, 1.5);"
            )
    return "\n".join(lines)


def copy_oss_files_to_project(
    project_dir: Path,
    selections: dict[str, Any],
    contract: dict[str, Any],
) -> tuple[str, ...]:
    brand = _brand_vars(contract)
    copied: list[str] = []
    assets_dst = project_dir / "assets"
    assets_dst.mkdir(parents=True, exist_ok=True)
    if OSS_ASSETS_DIR.exists():
        for asset in OSS_ASSETS_DIR.iterdir():
            if asset.is_file():
                shutil.copy2(asset, assets_dst / asset.name)
                copied.append(f"assets/{asset.name}")
    avatar_rel = _write_social_avatar_to_project(contract, assets_dst)
    copied.append(avatar_rel)

    compositions_dst = project_dir / "compositions"
    components_dst = compositions_dst / "components"
    compositions_dst.mkdir(parents=True, exist_ok=True)
    components_dst.mkdir(parents=True, exist_ok=True)

    needed_blocks = {block.block_id for block in selections.get("blocks", [])}
    for block_id in needed_blocks:
        item = _item_by_id(block_id)
        if not item:
            continue
        src = HYPERFRAMES_DIR / str(item["path"])
        if not src.exists():
            continue
        rel = Path(str(item["path"]))
        dst = project_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(_sanitize_vendored_html(src.read_text(encoding="utf-8"), brand), encoding="utf-8")
        copied.append(str(rel).replace("\\", "/"))

    texture_ids = selections.get("textures") or []
    caption_style = str(selections.get("caption_style") or "")
    component_ids = set(texture_ids)
    if caption_style:
        component_ids.add(caption_style)

    for component_id in component_ids:
        item = _item_by_id(component_id)
        if not item:
            continue
        src = HYPERFRAMES_DIR / str(item["path"])
        if src.exists():
            rel = Path(str(item["path"]))
            dst = project_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(str(rel).replace("\\", "/"))

    return tuple(sorted(set(copied)))


def build_oss_host_bundle(
    selections: dict[str, Any],
    contract: dict[str, Any],
    *,
    text_color: str,
    highlight_color: str,
) -> OssHostBundle:
    texture_ids: list[str] = list(selections.get("textures") or [])
    caption_style = str(selections.get("caption_style") or "")
    duration_ms = int(contract.get("durationMs") or 0)
    total_s = max(0.1, duration_ms / 1000)

    effect_html_parts: list[str] = []
    effect_css_parts: list[str] = []
    effect_js_parts: list[str] = []

    for texture_id in texture_ids:
        item = _item_by_id(texture_id)
        if not item:
            continue
        path = HYPERFRAMES_DIR / str(item["path"])
        if not path.exists():
            continue
        snippet = _parse_component_snippet(path)
        if snippet["html"]:
            effect_html_parts.append(snippet["html"])
        if snippet["css"]:
            effect_css_parts.append(snippet["css"])
        if snippet["js"]:
            effect_js_parts.append(snippet["js"])

    block_html_parts: list[str] = []
    for placement in selections.get("blocks", []):
        block_html_parts.append(
            f"""    <div class="oss-block-host" style="{placement.wrapper_style}z-index:{placement.track_index + 40};pointer-events:none;">
      <div
        data-composition-id="{html.escape(placement.composition_id)}"
        data-composition-src="{html.escape(placement.src)}"
        data-start="{placement.start_s:.3f}"
        data-duration="{placement.duration_s:.3f}"
        data-track-index="{placement.track_index}"
        data-width="{placement.render_width}"
        data-height="{placement.render_height}"
        style="{placement.inner_style}"
      ></div>
    </div>"""
        )

    caption_css = ""
    caption_class = ""
    if caption_style:
        item = _item_by_id(caption_style)
        if item:
            path = HYPERFRAMES_DIR / str(item["path"])
            if path.exists():
                caption_css = _extract_caption_css(path)
                caption_class = f"oss-caption-{caption_style}"

    return OssHostBundle(
        effect_html="\n".join(effect_html_parts),
        effect_css="\n".join(effect_css_parts),
        effect_js="\n".join(effect_js_parts),
        effect_timeline_js=_effect_timeline_js(texture_ids, total_s),
        block_html="\n".join(block_html_parts),
        caption_css=caption_css,
        caption_class=caption_class,
        caption_timeline_js=_caption_timeline_js(caption_style, text_color, highlight_color) if caption_style else "",
        block_ids=tuple(selections.get("block_ids") or ()),
        component_ids=tuple(selections.get("component_ids") or ()),
        copied_paths=(),
    )
