"""HyperFrames recipe: studio_kinetic_reel.

High-end kinetic talking-head reel engine with:
- Visual hierarchy: thin filler words vs. 2-3x bold punch words with neon glow
- Floating tilted 3D proof card overlay with glassmorphism
- Text-behind-subject cutout depth layer
- Multi-layer sound design cues
"""

from __future__ import annotations

import html
import re
from typing import Any

from ._base import LayoutContext, RecipeStyleMeta, TemplateRecipe, escape_attr, escape_text
from ..subject_cutout import resolve_depth_keyword

_EMPHASIS_KEYWORDS = frozenset(
    {
        "secret", "never", "always", "rahasia", "kunci", "fokus", "stop", "biggest",
        "critical", "massive", "viral", "scale", "growth", "money", "profit", "results",
        "proven", "mistake", "kesalahan", "solusi", "trik", "tips", "hacks", "hack",
    }
)


def _is_punch_word(word_text: str, all_words: list[str]) -> bool:
    clean = re.sub(r"[^\w%+$]", "", word_text).strip()
    if not clean:
        return False
    # Explicit punch indicators or numbers/metrics ($10k, +300%, 10x)
    if re.search(r"(\d+|%|\$|\+)", clean):
        return True
    # All caps word of 2+ chars
    if len(clean) >= 2 and clean.isupper():
        return True
    # Emphatic dictionary match
    if clean.lower() in _EMPHASIS_KEYWORDS:
        return True
    # If no word in phrase is uppercase/metric, pick the longest word (>=5 chars)
    has_any_metric = any(re.search(r"(\d+|%|\$|\+)", w) or (len(w) >= 2 and w.isupper()) for w in all_words)
    if not has_any_metric and len(clean) >= 5:
        longest = max((re.sub(r"[^\w]", "", w) for w in all_words), key=len, default="")
        if clean.lower() == longest.lower():
            return True
    return False


class StudioKineticReelRecipe(TemplateRecipe):
    """High-end kinetic talking-head reel recipe."""

    template_id = "studio_kinetic_reel"

    def style_meta(self) -> RecipeStyleMeta:
        return RecipeStyleMeta(
            font_family='"Outfit", "Inter", sans-serif',
            google_fonts_href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;900&display=swap",
            caption_style="Kinetic punch hierarchy",
            motion_preset="kinetic-reel",
            color_grade="studio kinetic",
        )

    def video_filter(self) -> str:
        return "contrast(1.14) saturate(1.08) brightness(0.92)"

    def render_overlay(self, contract: dict[str, Any], template: dict[str, Any], layout: LayoutContext) -> str:
        depth_word = resolve_depth_keyword(contract)
        style = contract.get("style") if isinstance(contract.get("style"), dict) else {}
        proof_metric = str(contract.get("proofMetric") or style.get("proof_metric") or "+312%").strip()
        proof_label = str(contract.get("proofLabel") or style.get("proof_label") or "VERIFIED METRIC").strip()
        proof_sub = str(contract.get("proofSub") or style.get("proof_sub") or "Otonom Media OS").strip()

        return f"""
    <!-- Subject Cutout Depth Layer (renders behind speaker) -->
    <div class="template-layer depth-behind-subject" data-layout-ignore="true" data-layout-allow-overflow="true" aria-hidden="true">
      <span class="depth-giant-word">{escape_text(depth_word)}</span>
    </div>

    <!-- Floating Tilted 3D Proof Card -->
    <div class="template-layer proof-card-3d">
      <div class="proof-card-inner">
        <div class="proof-badge">
          <span class="proof-dot"></span>
          <span class="proof-badge-text">{escape_text(proof_label)}</span>
        </div>
        <div class="proof-metric-stat">{escape_text(proof_metric)}</div>
        <div class="proof-sub-label">{escape_text(proof_sub)}</div>
      </div>
    </div>

    <!-- Kinetic Grid & Accent Beams -->
    <div class="template-layer kinetic-beam-top"></div>
    <div class="template-layer kinetic-beam-bottom"></div>
"""

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
        all_raw_words = [str(w.get("text", "")) for w in words]

        spans = []
        for word_index, word in enumerate(words):
            word_text = str(word.get("text", ""))
            is_punch = _is_punch_word(word_text, all_raw_words)
            span_cls = "word-span word-punch" if is_punch else "word-span word-filler"
            
            spans.append(
                f'<span '
                f'id="cap-{index}-word-{word_index}" '
                f'class="{span_cls}" '
                f'data-word-start="{attr_fn(seconds_fn(int(word.get("startMs", start_ms))))}" '
                f'data-word-end="{attr_fn(seconds_fn(int(word.get("endMs", end_ms))))}">'
                f'{escape_text(word_text)}'
                "</span>"
            )

        return (
            f'<div id="cap-{index}" class="clip caption-clip recipe-caption" '
            f'data-start="{attr_fn(seconds_fn(start_ms))}" '
            f'data-duration="{attr_fn(seconds_fn(duration_ms))}" '
            'data-track-index="2">'
            '<div class="caption-card">'
            f'<div class="caption-text" style="--highlight-color:{attr_fn(layout.highlight_color)};--accent-color:{attr_fn(layout.accent)}">'
            + "\n".join(spans)
            + "</div></div></div>"
        )

    def css_block(self, layout: LayoutContext) -> str:
        return f"""
/* Studio Kinetic Reel: Deep Typography & Visual Hierarchy */
#root.recipe-studio-kinetic-reel .caption-card {{
  border-radius: 20px;
  background: rgba(10, 15, 29, 0.78);
  border: 1px solid rgba(255, 255, 255, 0.16);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.65), 0 0 35px rgba(0, 245, 160, 0.15);
  padding: 22px 34px 26px;
}}

#root.recipe-studio-kinetic-reel .caption-text {{
  font-family: 'Outfit', sans-serif;
  text-transform: uppercase;
  letter-spacing: -0.01em;
  row-gap: 6px;
  column-gap: 16px;
}}

#root.recipe-studio-kinetic-reel .caption-text .word-span {{
  transition: transform 0.08s cubic-bezier(0.34, 1.56, 0.64, 1), color 0.08s ease;
  will-change: transform, color;
}}

/* Thin filler words */
#root.recipe-studio-kinetic-reel .caption-text .word-filler {{
  font-weight: 600;
  opacity: 0.78;
  font-size: 0.92em;
  color: #f1f5f9;
}}

/* 2-3x bold punch words with neon glow */
#root.recipe-studio-kinetic-reel .caption-text .word-punch {{
  font-weight: 900;
  opacity: 1;
  font-size: 1.28em;
  color: var(--template-accent, #00f5a0);
  text-shadow:
    0 0 16px rgba(0, 245, 160, 0.65),
    0 0 32px rgba(0, 245, 160, 0.35),
    0 3px 12px rgba(0, 0, 0, 0.9);
  display: inline-block;
  transform: translateY(-1px);
}}

/* Text Behind Subject Cutout Depth Layer */
.depth-behind-subject {{
  position: absolute;
  left: 36px;
  right: 36px;
  display: flex;
  justify-content: center;
  align-items: center;
  top: {'22%' if layout.is_landscape else '26%'};
  height: 240px;
  z-index: 1;
  pointer-events: none;
  overflow: hidden;
}}

.depth-giant-word {{
  font-family: 'Outfit', sans-serif;
  font-weight: 900;
  font-size: {'84px' if layout.is_landscape else '112px'};
  line-height: 1;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.14);
  text-shadow: 0 0 40px rgba(0, 245, 160, 0.15);
  mix-blend-mode: overlay;
  user-select: none;
  white-space: nowrap;
  max-width: 100%;
  overflow: hidden;
  text-overflow: clip;
}}

/* Floating Tilted 3D Proof Card */
.proof-card-3d {{
  position: absolute;
  right: {'72px' if layout.is_landscape else '48px'};
  top: {'110px' if layout.is_landscape else '150px'};
  perspective: 900px;
  z-index: 8;
  pointer-events: none;
}}

.proof-card-inner {{
  background: linear-gradient(135deg, rgba(15, 23, 42, 0.88), rgba(30, 41, 59, 0.72));
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 18px;
  padding: 16px 22px;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  box-shadow: 0 20px 45px rgba(0, 0, 0, 0.55), 0 0 24px rgba(0, 245, 160, 0.22);
  transform: rotateY(-10deg) rotateX(6deg);
  transform-style: preserve-3d;
}}

.proof-badge {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}}

.proof-dot {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--template-accent, #00f5a0);
  box-shadow: 0 0 10px var(--template-accent, #00f5a0);
}}

.proof-badge-text {{
  font-family: 'Outfit', sans-serif;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--template-accent, #00f5a0);
}}

.proof-metric-stat {{
  font-family: 'Outfit', sans-serif;
  font-size: 32px;
  font-weight: 900;
  line-height: 1.1;
  color: #ffffff;
  letter-spacing: -0.02em;
}}

.proof-sub-label {{
  font-family: 'Outfit', sans-serif;
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
  margin-top: 4px;
}}

/* Kinetic Beams */
.kinetic-beam-top {{
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, transparent, var(--template-accent, #00f5a0), var(--template-secondary, #00d2ff), transparent);
  box-shadow: 0 0 20px var(--template-accent, #00f5a0);
  z-index: 10;
}}

.kinetic-beam-bottom {{
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, transparent, var(--template-secondary, #00d2ff), var(--template-accent, #00f5a0), transparent);
  opacity: 0.8;
  z-index: 10;
}}
"""

    def motion_block(
        self,
        contract: dict[str, Any],
        layout: LayoutContext,
        hook_exit_s: float,
        cta_start_s: float,
    ) -> str:
        return f"""
    // Studio Kinetic Reel 3D Card & Depth Motion
    tl.from(".proof-card-3d", {{
      y: 45,
      rotationY: -26,
      rotationX: 14,
      opacity: 0,
      scale: 0.88,
      duration: 0.55,
      ease: "back.out(1.8)",
    }}, 0.35);

    // Subtle 3D ambient floating hover for the proof card
    tl.to(".proof-card-3d .proof-card-inner", {{
      y: -8,
      rotationY: -5,
      rotationX: 3,
      duration: 2.2,
      ease: "sine.inOut",
      yoyo: true,
      repeat: 3,
    }}, 0.9);

    tl.to(".proof-card-3d", {{
      y: -25,
      opacity: 0,
      scale: 0.92,
      duration: 0.38,
      ease: "power2.in",
    }}, Math.max(1.5, {cta_start_s:.2f} - 0.4));

    // Behind-subject giant keyword reveal & breath
    tl.from(".depth-giant-word", {{
      scale: 0.85,
      opacity: 0,
      duration: 0.65,
      ease: "power3.out",
    }}, 0.1);

    tl.to(".depth-giant-word", {{
      scale: 1.04,
      duration: {hook_exit_s:.2f},
      ease: "sine.inOut",
    }}, 0.75);
"""

    def render_shell_html(
        self,
        contract: dict[str, Any],
        template: dict[str, Any],
        layout: LayoutContext,
        duration_s: str,
        seconds_fn,
        attr_fn,
    ) -> str:
        components = self.resolved_shell_components(contract)
        has_cutout = bool(contract.get("hasSubjectCutout"))
        sound_design = bool((contract.get("soundDesign") or {}).get("enabled", True))

        layers = [
            f"""
    <video id="source-video" class="clip" data-start="0" data-duration="{duration_s}" data-track-index="0" src="media/source.mp4" muted playsinline></video>
    <audio id="source-audio" class="clip" data-start="0" data-duration="{duration_s}" data-track-index="4" src="media/source.mp4" data-volume="1"></audio>"""
        ]
        if sound_design and contract.get("hasSoundDesignAssets"):
            layers.append(
                f"""
    <audio id="bg-music" class="clip" data-start="0" data-duration="{duration_s}" data-track-index="5" src="media/ambient_bed.wav" data-volume="0.14"></audio>
    <audio id="hook-sfx" class="clip" data-start="0" data-duration="1.5" data-track-index="6" src="media/hook_boom.wav" data-volume="0.60"></audio>"""
            )
        if has_cutout:
            layers.append(
                f"""
    <img id="subject-cutout-matte" class="clip subject-matte" data-start="0" data-duration="{duration_s}" data-track-index="1" src="media/subject_cutout.png" alt="" />"""
            )
        layers.append('<div class="shade"></div>')
        if components.get("hook"):
            layers.append(self.render_hook_html(contract, layout, seconds_fn, attr_fn))
        brand_row = self.render_brand_row_html(contract, components)
        if brand_row:
            layers.append(brand_row)
        return "".join(layers)

    def shell_css(self, layout: LayoutContext) -> str:
        return f"""
#root.recipe-studio-kinetic-reel .hook h1 {{
  font-family: 'Outfit', sans-serif;
  font-weight: 900;
  letter-spacing: -0.02em;
  text-shadow: 0 4px 20px rgba(0, 0, 0, 0.85);
}}
#root.recipe-studio-kinetic-reel .cta {{
  background: linear-gradient(135deg, #00f5a0, #00d2ff);
  color: #0b1120;
  border: none;
  font-family: 'Outfit', sans-serif;
  font-weight: 900;
  box-shadow: 0 16px 40px rgba(0, 245, 160, 0.35);
}}
#root.recipe-studio-kinetic-reel .source {{
  color: #67e8f9;
}}
.subject-matte {{
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
  z-index: 3;
  pointer-events: none;
}}
"""


recipe = StudioKineticReelRecipe()
