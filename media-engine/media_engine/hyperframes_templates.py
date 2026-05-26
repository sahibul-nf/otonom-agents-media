"""Curated HyperFrames template pack metadata and selection rules."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

AUTO_TEMPLATE_ID = "auto"
DEFAULT_TEMPLATE_ID = "spiritual_reflective"
TEMPLATE_VERSION = "1.1.0"
ROOT = Path(__file__).resolve().parents[1]
PREVIEW_SECONDS = 15
VALID_HYPERFRAMES_FORMATS = {"auto", "short_9_16", "long_16_9"}
ALIASES = {
    "nourbit_reflective": "spiritual_reflective",
}
OFFICIAL_PREVIEW_VIDEOS: dict[str, dict[str, str]] = {
    "spiritual_reflective": {
        "short_9_16": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4",
        "long_16_9": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/warm-grain.mp4",
    },
    "podcast_talking_head": {
        "short_9_16": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4",
        "long_16_9": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/play-mode.mp4",
    },
    "data_market_explainer": {
        "short_9_16": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4",
        "long_16_9": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/nyt-graph.mp4",
    },
    "news_geo_brief": {
        "short_9_16": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4",
        "long_16_9": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/swiss-grid.mp4",
    },
    "product_brand_promo": {
        "short_9_16": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4",
        "long_16_9": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/product-promo.mp4",
    },
    "warm_grain_editorial": {
        "short_9_16": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4",
        "long_16_9": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/warm-grain.mp4",
    },
    "play_mode_social": {
        "short_9_16": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4",
        "long_16_9": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/play-mode.mp4",
    },
    "swiss_grid_explainer": {
        "short_9_16": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4",
        "long_16_9": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/swiss-grid.mp4",
    },
    "vignelli_portrait_headline": {
        "short_9_16": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4",
        "long_16_9": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/kinetic-type.mp4",
    },
    "decision_tree_tutorial": {
        "short_9_16": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4",
        "long_16_9": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/decision-tree.mp4",
    },
    "kinetic_type_promo": {
        "short_9_16": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4",
        "long_16_9": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/kinetic-type.mp4",
    },
    "product_promo_showcase": {
        "short_9_16": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4",
        "long_16_9": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/product-promo.mp4",
    },
    "nyt_graph_data_story": {
        "short_9_16": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4",
        "long_16_9": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/nyt-graph.mp4",
    },
}


@dataclass(frozen=True)
class HyperframesTemplate:
    id: str
    label: str
    category: str
    best_for: str
    effects: tuple[str, ...]
    caption_style: str
    default_genres: tuple[str, ...]
    status: str
    tone: str
    accent: str
    secondary_accent: str
    overlay_class: str
    source: str = "built_in"
    formats: tuple[str, ...] = ("short_9_16", "long_16_9")
    components_used: tuple[str, ...] = ()
    blocks_used: tuple[str, ...] = ()

    def public_dict(self) -> dict[str, Any]:
        formats = list(self.formats)
        return {
            "id": self.id,
            "label": self.label,
            "category": self.category,
            "best_for": self.best_for,
            "effects": list(self.effects),
            "caption_style": self.caption_style,
            "default_genres": list(self.default_genres),
            "status": self.status,
            "tone": self.tone,
            "source": self.source,
            "formats": formats,
            "components_used": list(self.components_used),
            "blocks_used": list(self.blocks_used),
            "preview_seconds": PREVIEW_SECONDS,
            "preview_status": "ready",
            "preview_urls": _preview_urls(self.id, formats),
            "preview_video_urls": _official_preview_urls(self.id, formats),
            "production_checks": {
                "lint": "required",
                "inspect": "required",
                "render_preview": "required",
            },
        }

    def renderer_dict(self) -> dict[str, Any]:
        return {
            **self.public_dict(),
            "version": TEMPLATE_VERSION,
            "accent": self.accent,
            "secondary_accent": self.secondary_accent,
            "overlay_class": self.overlay_class,
        }


TEMPLATES: tuple[HyperframesTemplate, ...] = (
    HyperframesTemplate(
        id="spiritual_reflective",
        label="Spiritual Reflective",
        category="Spiritual",
        best_for="Spiritual teaching, reflective advice, and heart-softening clips.",
        effects=("warm vignette", "subtle grain", "editorial hook", "word emphasis"),
        caption_style="Editorial weighted captions",
        default_genres=("kajian", "spiritual_reflection", "advice", "history", "dua_and_dzikir"),
        status="ready",
        tone="Calm, warm, devotional",
        accent="#d8b45f",
        secondary_accent="#8ee6c8",
        overlay_class="template-reflective",
        components_used=("grain-overlay", "vignette", "caption-editorial-emphasis", "caption-weight-shift"),
    ),
    HyperframesTemplate(
        id="podcast_talking_head",
        label="Podcast Talking Head",
        category="Podcast",
        best_for="Interviews, personal brand clips, founder talks, and guest highlights.",
        effects=("karaoke pill captions", "lower third", "follow CTA", "soft push-in"),
        caption_style="Karaoke pill captions",
        default_genres=("podcast", "interview", "story", "personal_brand", "social_commentary"),
        status="ready",
        tone="Human, conversational, confident",
        accent="#6ee7f5",
        secondary_accent="#f7a8d8",
        overlay_class="template-podcast",
        components_used=("caption-pill-karaoke", "vignette"),
        blocks_used=("yt-lower-third", "instagram-follow"),
    ),
    HyperframesTemplate(
        id="data_market_explainer",
        label="Data Market Explainer",
        category="Data",
        best_for="Crypto, finance, markets, statistics, dashboards, and explainers.",
        effects=("metric cards", "chart bars", "shimmer emphasis", "structured callouts"),
        caption_style="Crisp analyst captions",
        default_genres=("crypto", "finance", "market", "markets", "data", "statistics", "business"),
        status="ready",
        tone="Sharp, analytical, energetic",
        accent="#74f2ce",
        secondary_accent="#f8d35c",
        overlay_class="template-data",
        components_used=("shimmer-sweep", "caption-clip-wipe", "vignette"),
        blocks_used=("data-chart", "flowchart"),
    ),
    HyperframesTemplate(
        id="news_geo_brief",
        label="News Geo Brief",
        category="News",
        best_for="News, geopolitics, current affairs, public updates, and region analysis.",
        effects=("map cards", "source lower third", "ticker bar", "restrained transitions"),
        caption_style="Broadcast captions",
        default_genres=("news", "geopolitics", "geo", "current_affairs", "history", "politics"),
        status="ready",
        tone="Restrained, factual, urgent",
        accent="#7dd3fc",
        secondary_accent="#f97373",
        overlay_class="template-news",
        components_used=("caption-highlight", "vignette"),
        blocks_used=("world-map", "x-post"),
    ),
    HyperframesTemplate(
        id="product_brand_promo",
        label="Product Brand Promo",
        category="Promo",
        best_for="SaaS, product demos, launches, creator promos, and brand offers.",
        effects=("clean shimmer", "logo outro", "social overlays", "energetic CTA"),
        caption_style="Clean promo captions",
        default_genres=("product", "promo", "saas", "brand", "creator", "launch", "marketing"),
        status="ready",
        tone="Clean, optimistic, commercial",
        accent="#a7f36b",
        secondary_accent="#67e8f9",
        overlay_class="template-promo",
        components_used=("shimmer-sweep", "caption-gradient-fill", "parallax-zoom"),
        blocks_used=("logo-outro", "app-showcase", "tiktok-follow"),
    ),
    HyperframesTemplate(
        id="warm_grain_editorial",
        label="Warm Grain Editorial",
        category="Official",
        best_for="Lifestyle, editorial commentary, human stories, and warm brand clips.",
        effects=("cream grade", "film grain", "soft editorial transitions"),
        caption_style="Editorial weighted captions",
        default_genres=("lifestyle", "editorial", "story", "spiritual_reflection"),
        status="ready",
        tone="Organic, textured, warm",
        accent="#e8c77d",
        secondary_accent="#9fe7c4",
        overlay_class="template-reflective",
        source="hyperframes_example",
        components_used=("grain-overlay", "vignette", "caption-weight-shift"),
    ),
    HyperframesTemplate(
        id="play_mode_social",
        label="Play Mode Social",
        category="Official",
        best_for="Social clips, product launches, creator updates, and fast-paced announcements.",
        effects=("elastic motion", "bold labels", "CTA pulses"),
        caption_style="Karaoke pill captions",
        default_genres=("social", "creator", "launch", "promo"),
        status="ready",
        tone="Energetic, playful, punchy",
        accent="#ffdf57",
        secondary_accent="#67e8f9",
        overlay_class="template-promo",
        source="hyperframes_example",
        components_used=("caption-pill-karaoke", "caption-gradient-fill", "shimmer-sweep"),
    ),
    HyperframesTemplate(
        id="swiss_grid_explainer",
        label="Swiss Grid Explainer",
        category="Official",
        best_for="Corporate, technical, structured explainers, and B2B knowledge clips.",
        effects=("grid cards", "precise typography", "structured reveals"),
        caption_style="Crisp analyst captions",
        default_genres=("technical", "business", "data", "tutorial"),
        status="ready",
        tone="Clean, structured, credible",
        accent="#f4f4f5",
        secondary_accent="#22d3ee",
        overlay_class="template-data",
        source="hyperframes_example",
        components_used=("caption-clip-wipe", "vignette"),
        blocks_used=("flowchart",),
    ),
    HyperframesTemplate(
        id="vignelli_portrait_headline",
        label="Vignelli Portrait Headline",
        category="Official",
        best_for="Portrait headlines, announcements, editorial statements, and news hooks.",
        effects=("bold type", "red accent", "headline beats"),
        caption_style="Kinetic headline captions",
        default_genres=("headline", "announcement", "news", "current_affairs"),
        status="ready",
        tone="Bold, typographic, decisive",
        accent="#ef4444",
        secondary_accent="#f8fafc",
        overlay_class="template-news",
        source="hyperframes_example",
        formats=("short_9_16",),
        components_used=("caption-kinetic-slam", "caption-highlight"),
    ),
    HyperframesTemplate(
        id="decision_tree_tutorial",
        label="Decision Tree Tutorial",
        category="Official",
        best_for="Tutorials, explainers, step-by-step choices, and framework clips.",
        effects=("flowchart reveal", "node emphasis", "decision callouts"),
        caption_style="Structured explainer captions",
        default_genres=("tutorial", "explainer", "advice", "education"),
        status="ready",
        tone="Helpful, visual, logical",
        accent="#8bff9f",
        secondary_accent="#f8d35c",
        overlay_class="template-data",
        source="hyperframes_example",
        blocks_used=("flowchart",),
        components_used=("caption-clip-wipe", "shimmer-sweep"),
    ),
    HyperframesTemplate(
        id="kinetic_type_promo",
        label="Kinetic Type Promo",
        category="Official",
        best_for="Promo intros, title cards, campaign hooks, and high-impact statements.",
        effects=("kinetic type", "dramatic entrance", "bold CTA"),
        caption_style="Kinetic slam captions",
        default_genres=("promo", "launch", "marketing", "announcement"),
        status="ready",
        tone="Dramatic, bold, high-impact",
        accent="#facc15",
        secondary_accent="#f472b6",
        overlay_class="template-promo",
        source="hyperframes_example",
        components_used=("caption-kinetic-slam", "caption-gradient-fill", "shimmer-sweep"),
    ),
    HyperframesTemplate(
        id="product_promo_showcase",
        label="Product Promo Showcase",
        category="Official",
        best_for="Product showcases, SaaS demos, feature launches, and offer clips.",
        effects=("multi-scene product cards", "logo outro", "device showcase"),
        caption_style="Clean promo captions",
        default_genres=("product", "saas", "brand", "promo", "launch"),
        status="ready",
        tone="Clean, commercial, polished",
        accent="#a7f36b",
        secondary_accent="#67e8f9",
        overlay_class="template-promo",
        source="hyperframes_example",
        blocks_used=("app-showcase", "logo-outro", "vfx-iphone-device"),
        components_used=("shimmer-sweep", "caption-gradient-fill"),
    ),
    HyperframesTemplate(
        id="nyt_graph_data_story",
        label="NYT Graph Data Story",
        category="Official",
        best_for="Data stories, reports, market explainers, and statistic-led narratives.",
        effects=("editorial chart", "data labels", "print-inspired motion"),
        caption_style="Crisp analyst captions",
        default_genres=("data", "statistics", "market", "finance", "report"),
        status="ready",
        tone="Editorial, analytical, precise",
        accent="#74f2ce",
        secondary_accent="#f8d35c",
        overlay_class="template-data",
        source="hyperframes_example",
        blocks_used=("data-chart",),
        components_used=("caption-editorial-emphasis", "vignette"),
    ),
)

TEMPLATE_BY_ID = {template.id: template for template in TEMPLATES}


def list_hyperframes_templates() -> list[dict[str, Any]]:
    return [template.public_dict() for template in TEMPLATES] + _saved_brand_system_templates()


def hyperframes_template_ids() -> set[str]:
    return set(TEMPLATE_BY_ID)


def normalize_hyperframes_template(value: Any) -> str:
    template_id = ALIASES.get(str(value or AUTO_TEMPLATE_ID).strip(), str(value or AUTO_TEMPLATE_ID).strip())
    if template_id == AUTO_TEMPLATE_ID or template_id in TEMPLATE_BY_ID or _saved_brand_template_by_id(template_id):
        return template_id
    return AUTO_TEMPLATE_ID


def normalize_hyperframes_format(value: Any) -> str:
    text = str(value or "auto").strip()
    return text if text in VALID_HYPERFRAMES_FORMATS else "auto"


def dimensions_for_format(value: Any) -> tuple[int, int, str]:
    normalized = normalize_hyperframes_format(value)
    if normalized == "long_16_9":
        return 1920, 1080, normalized
    return 1080, 1920, "short_9_16" if normalized == "auto" else normalized


def resolve_hyperframes_template(
    value: Any = AUTO_TEMPLATE_ID,
    genres: list[str] | tuple[str, ...] | None = None,
    brand_template: str = "",
) -> dict[str, Any]:
    template_id = normalize_hyperframes_template(value)
    saved = _saved_brand_template_by_id(template_id)
    if saved:
        base = TEMPLATE_BY_ID[DEFAULT_TEMPLATE_ID].renderer_dict()
        return {
            **base,
            **saved,
            "version": TEMPLATE_VERSION,
            "accent": base["accent"],
            "secondary_accent": base["secondary_accent"],
            "overlay_class": base["overlay_class"],
        }
    if template_id != AUTO_TEMPLATE_ID:
        return TEMPLATE_BY_ID[template_id].renderer_dict()

    signals = {str(item).strip().lower() for item in (genres or []) if str(item).strip()}
    brand = brand_template.lower()
    if "spiritual" in brand or "reflective" in brand:
        signals.add("kajian")

    for template in TEMPLATES:
        if signals.intersection(template.default_genres):
            return template.renderer_dict()
    return TEMPLATE_BY_ID[DEFAULT_TEMPLATE_ID].renderer_dict()


def _saved_brand_system_templates() -> list[dict[str, Any]]:
    profiles = ROOT / "profiles"
    templates: list[dict[str, Any]] = []
    for path in sorted(profiles.glob("custom_*.json")):
        try:
            raw = path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            continue
        if _contains_private_legacy_branding(raw):
            continue
        brand_system = payload.get("brand_system") if isinstance(payload.get("brand_system"), dict) else {}
        template_id = str(payload.get("id") or path.stem)
        label = str(payload.get("label") or path.stem.replace("_", " ").title())
        formats = ["short_9_16", "long_16_9"]
        public_id = f"brand:{template_id}"
        templates.append(
            {
                "id": public_id,
                "label": label,
                "category": "Brand",
                "best_for": "Saved brand system template for reusable HyperFrames production.",
                "effects": [
                    str(brand_system.get("texture_effect") or "brand texture"),
                    str(brand_system.get("transition_family") or "brand transition"),
                    str(brand_system.get("cta_overlay") or "brand CTA"),
                ],
                "caption_style": str(brand_system.get("caption_style") or payload.get("caption", {}).get("style") or "Brand captions"),
                "default_genres": [],
                "status": "ready",
                "tone": str(brand_system.get("motion_intensity") or "Brand controlled"),
                "source": "brand_system",
                "formats": formats,
                "components_used": [
                    str(brand_system.get("caption_style") or "caption-pill-karaoke"),
                    str(brand_system.get("texture_effect") or "vignette"),
                ],
                "blocks_used": [str(brand_system.get("cta_overlay") or "yt-lower-third")],
                "preview_seconds": PREVIEW_SECONDS,
                "preview_status": "ready",
                "preview_urls": _preview_urls(public_id, formats),
                "preview_video_urls": _official_preview_urls(public_id, formats),
                "production_checks": {
                    "lint": "required",
                    "inspect": "required",
                    "render_preview": "required",
                },
            }
        )
    return templates


def _contains_private_legacy_branding(raw: str) -> bool:
    """Prevent local/private legacy profiles from leaking into public template APIs."""
    private_terms = ("nourbit",)
    lower = raw.lower()
    return any(term in lower for term in private_terms)


def _saved_brand_template_by_id(template_id: str) -> dict[str, Any] | None:
    if not template_id.startswith("brand:"):
        return None
    for template in _saved_brand_system_templates():
        if template["id"] == template_id:
            return template
    return None


def _preview_urls(template_id: str, formats: list[str]) -> dict[str, str]:
    safe_id = template_id.replace(":", "__")
    return {
        item: f"/api/media/hyperframes-template-preview?template={safe_id}&format={item}"
        for item in formats
    }


def _official_preview_urls(template_id: str, formats: list[str]) -> dict[str, str]:
    mapped = OFFICIAL_PREVIEW_VIDEOS.get(template_id, {})
    if not mapped and template_id.startswith("brand:"):
        return {}
    return {item: mapped[item] for item in formats if item in mapped}
