"""Curated HyperFrames template pack metadata and selection rules."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from .genres import UNIVERSAL_CATALOG

AUTO_TEMPLATE_ID = "auto"
DEFAULT_TEMPLATE_ID = "spiritual_reflective"
TEMPLATE_VERSION = "1.4.0"
ROOT = Path(__file__).resolve().parents[1]
STOCK_DIR = ROOT / "render" / "hyperframes" / "stock"
PREVIEW_SECONDS = 15
VALID_HYPERFRAMES_FORMATS = {"auto", "short_9_16", "long_16_9"}
ALIASES = {
    "nourbit_reflective": "spiritual_reflective",
    "podcast_talking_head": "grit_training_stamp",
    "data_market_explainer": "velocity_business_promo",
    "techtalk_explainer": "techtalk_intel_brief",
    "techtalk": "techtalk_intel_brief",
    "news_geo_brief": "byline_trust_quote",
    "product_brand_promo": "prism_pro_pricing",
    "warm_grain_editorial": "archive_magazine",
    "play_mode_social": "cove_callout_pill",
    "swiss_grid_explainer": "blueprint_grid_paper",
    "vignelli_portrait_headline": "kai_mustard_uppercase",
    "decision_tree_tutorial": "blueprint_grid_paper",
    "kinetic_type_promo": "rocket_glitch",
    "product_promo_showcase": "prism_pro_pricing",
    "nyt_graph_data_story": "velocity_business_promo",
    "eva_neon_cyber": "neon_seize_future",
    "volt_lime_kinetic": "velocity_business_promo",
    "ember_sunset_gradient": "story_handwritten",
    "align_minimal_box": "byline_trust_quote",
}
OFFICIAL_PREVIEW_VIDEOS: dict[str, dict[str, str]] = {
    "spiritual_reflective": {
        "short_9_16": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4",
        "long_16_9": "https://static.heygen.ai/hyperframes-oss/docs/images/templates/warm-grain.mp4",
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
    recipe_module: str = ""
    preview_source_video: str = "spiritual_reflective.mp4"
    font_family: str = ""
    motion_preset: str = ""
    color_grade: str = ""

    def public_dict(self) -> dict[str, Any]:
        from .hyperframes_recipes import recipe_style_meta

        formats = list(self.formats)
        recipe_meta = recipe_style_meta(self.id)
        from .hyperframes_recipes import get_recipe

        shell_components = get_recipe(self.id).default_shell_components()
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
            "recipe_module": self.recipe_module or self.id,
            "preview_source_video": self.preview_source_video,
            "font_family": self.font_family or recipe_meta.font_family,
            "motion_preset": self.motion_preset or recipe_meta.motion_preset,
            "color_grade": self.color_grade or recipe_meta.color_grade,
            "shell_components": shell_components,
            "preview_seconds": PREVIEW_SECONDS,
            "preview_status": _aggregate_preview_status(self.id, formats),
            "preview_cache_ready": _preview_cache_ready(self.id, formats),
            "preview_urls": _preview_urls(self.id, formats),
            "preview_source_url": _preview_source_url(self.id),
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
        default_genres=("kajian", "spiritual_reflection", "dua_and_dzikir"),
        status="ready",
        tone="Calm, warm, devotional",
        accent="#d8b45f",
        secondary_accent="#8ee6c8",
        overlay_class="template-reflective",
        components_used=("grain-overlay", "vignette", "caption-editorial-emphasis", "caption-weight-shift"),
        preview_source_video="spiritual_reflective.mp4",
    ),
    HyperframesTemplate(
        id="energy_warm_question",
        label="Energy Warm Question",
        category="Promo",
        best_for="Creator growth hooks with sticky-note curiosity CTAs.",
        effects=("yellow sticky note", "warm question hook", "pop emphasis"),
        caption_style="Sticky note question captions",
        default_genres=("creator", "social", "marketing", "promo"),
        status="ready",
        tone="Warm, curious, inviting",
        accent="#ffe566",
        secondary_accent="#ff7ad1",
        overlay_class="template-promo",
        preview_source_video="energy_warm_question.mp4",
    ),
    HyperframesTemplate(
        id="arion_pink_callout",
        label="Arion Pink Callout",
        category="Promo",
        best_for="Bold mid-frame callouts for short social clips.",
        effects=("pink rounded callout", "center emphasis", "bounce entry"),
        caption_style="Pink callout captions",
        default_genres=("creator", "social", "promo"),
        status="ready",
        tone="Playful, loud, social",
        accent="#ff7ad1",
        secondary_accent="#f8fafc",
        overlay_class="template-promo",
        preview_source_video="arion_pink_callout.mp4",
    ),
    HyperframesTemplate(
        id="quintessence_serif",
        label="Quintessence Serif",
        category="Official",
        best_for="Display serif hooks with italic emphasis words.",
        effects=("display serif", "italic emphasis", "editorial fade"),
        caption_style="Display serif captions",
        default_genres=("editorial", "story", "brand"),
        status="ready",
        tone="Elegant, editorial, refined",
        accent="#e8c77d",
        secondary_accent="#f8fafc",
        overlay_class="template-reflective",
        preview_source_video="quintessence_serif.mp4",
    ),
    HyperframesTemplate(
        id="archive_magazine",
        label="Archive Magazine",
        category="Official",
        best_for="Magazine-cover editorial guidelines and archive storytelling.",
        effects=("cover frame", "masthead type", "print motion"),
        caption_style="Magazine cover captions",
        default_genres=("editorial", "history", "education"),
        status="ready",
        tone="Archival, authoritative, print",
        accent="#d8b45f",
        secondary_accent="#8ee6c8",
        overlay_class="template-reflective",
        preview_source_video="archive_magazine.mp4",
    ),
    HyperframesTemplate(
        id="story_handwritten",
        label="Story Handwritten",
        category="Official",
        best_for="Human stories with cursive accent overlays.",
        effects=("handwritten accent", "warm story grade", "soft drift"),
        caption_style="Handwritten story captions",
        default_genres=("story", "lifestyle", "creator"),
        status="ready",
        tone="Personal, handwritten, warm",
        accent="#ff9f68",
        secondary_accent="#fef08a",
        overlay_class="template-reflective",
        preview_source_video="story_handwritten.mp4",
    ),
    HyperframesTemplate(
        id="kai_mustard_uppercase",
        label="Kai Mustard Uppercase",
        category="Promo",
        best_for="Mustard card all-caps impact statements.",
        effects=("mustard card", "all-caps slam", "bold contrast"),
        caption_style="Mustard uppercase captions",
        default_genres=("promo", "announcement", "creator"),
        status="ready",
        tone="Bold, mustard, punchy",
        accent="#d4a017",
        secondary_accent="#111111",
        overlay_class="template-promo",
        preview_source_video="kai_mustard_uppercase.mp4",
    ),
    HyperframesTemplate(
        id="byline_trust_quote",
        label="Byline Trust Quote",
        category="News",
        best_for="Centered serif trust quotes and expert commentary.",
        effects=("centered quote", "serif trust type", "soft fade"),
        caption_style="Trust quote captions",
        default_genres=("news", "analysis", "geopolitics", "geo", "current_affairs", "politics"),
        status="ready",
        tone="Credible, calm, trustworthy",
        accent="#f8fafc",
        secondary_accent="#7dd3fc",
        overlay_class="template-news",
        preview_source_video="byline_trust_quote.mp4",
    ),
    HyperframesTemplate(
        id="sonnet_botanical",
        label="Sonnet Botanical",
        category="Spiritual",
        best_for="Soft lessons with botanical accents and script type.",
        effects=("botanical glow", "script accent", "gentle drift"),
        caption_style="Botanical script captions",
        default_genres=("spiritual_reflection", "lifestyle", "education"),
        status="ready",
        tone="Soft, botanical, poetic",
        accent="#9fe7c4",
        secondary_accent="#f8d35c",
        overlay_class="template-reflective",
        preview_source_video="sonnet_botanical.mp4",
    ),
    HyperframesTemplate(
        id="rocket_glitch",
        label="Rocket Glitch",
        category="Promo",
        best_for="Level-up hooks with VHS glitch styling.",
        effects=("VHS glitch", "RGB split", "retro slam"),
        caption_style="Glitch kinetic captions",
        default_genres=("gaming", "creator", "promo", "tech"),
        status="ready",
        tone="Retro, glitchy, hype",
        accent="#f0abfc",
        secondary_accent="#22d3ee",
        overlay_class="template-promo",
        preview_source_video="rocket_glitch.mp4",
    ),
    HyperframesTemplate(
        id="grit_training_stamp",
        label="Grit Training Stamp",
        category="Podcast",
        best_for="Dark mood training clips with stamp badges.",
        effects=("training stamp", "dark grade", "stamp slam"),
        caption_style="Stamp badge captions",
        default_genres=("fitness", "motivation", "podcast", "interview"),
        status="ready",
        tone="Gritty, disciplined, dark",
        accent="#22c55e",
        secondary_accent="#111111",
        overlay_class="template-podcast",
        preview_source_video="grit_training_stamp.mp4",
    ),
    HyperframesTemplate(
        id="cove_callout_pill",
        label="Cove Callout Pill",
        category="Promo",
        best_for="Pink and cyan pill stacks for caption CTAs.",
        effects=("pill stack", "dual-tone CTA", "rise motion"),
        caption_style="Pill stack captions",
        default_genres=("creator", "social", "product"),
        status="ready",
        tone="Bright, helpful, modern",
        accent="#ff7ad1",
        secondary_accent="#67e8f9",
        overlay_class="template-promo",
        preview_source_video="cove_callout_pill.mp4",
    ),
    HyperframesTemplate(
        id="pulse_remember_overlay",
        label="Pulse Remember Overlay",
        category="News",
        best_for="Consistency reminders with urgent red banners.",
        effects=("remember banner", "urgent red bar", "banner punch"),
        caption_style="Banner overlay captions",
        default_genres=("motivation", "news", "education"),
        status="ready",
        tone="Urgent, motivational, direct",
        accent="#dc2626",
        secondary_accent="#f8fafc",
        overlay_class="template-news",
        preview_source_video="pulse_remember_overlay.mp4",
    ),
    HyperframesTemplate(
        id="neon_seize_future",
        label="Neon Seize Future",
        category="Promo",
        best_for="Multicolor neon star bursts and future-facing hooks.",
        effects=("star burst", "neon multicolor", "burst spin"),
        caption_style="Neon burst captions",
        default_genres=("tech", "creator", "promo", "music_commentary"),
        status="ready",
        tone="Futuristic, neon, explosive",
        accent="#ff2a85",
        secondary_accent="#00f3ff",
        overlay_class="template-promo",
        preview_source_video="neon_seize_future.mp4",
    ),
    HyperframesTemplate(
        id="velocity_business_promo",
        label="Velocity Business Promo",
        category="Data",
        best_for="Stacked yellow business promo headlines.",
        effects=("stacked headline", "yellow velocity", "rise stack"),
        caption_style="Stacked business captions",
        default_genres=("business", "marketing", "finance", "crypto", "market", "markets", "data", "business_impact"),
        status="ready",
        tone="Corporate, fast, confident",
        accent="#facc15",
        secondary_accent="#f8fafc",
        overlay_class="template-data",
        preview_source_video="velocity_business_promo.mp4",
    ),
    HyperframesTemplate(
        id="blueprint_grid_paper",
        label="Blueprint Grid Paper",
        category="Official",
        best_for="Graph-paper explainers and blueprint tutorials.",
        effects=("graph paper", "blueprint grid", "mono labels"),
        caption_style="Blueprint mono captions",
        default_genres=("tutorial", "technical", "education"),
        status="ready",
        tone="Technical, blueprint, clear",
        accent="#7dd3fc",
        secondary_accent="#bae6fd",
        overlay_class="template-data",
        preview_source_video="blueprint_grid_paper.mp4",
    ),
    HyperframesTemplate(
        id="sketch_post_it",
        label="Sketch Post-it",
        category="Official",
        best_for="Sticky-note ideation overlays for sketch-style clips.",
        effects=("post-it notes", "sketch mood", "note pop"),
        caption_style="Post-it sketch captions",
        default_genres=("education", "creator", "tutorial"),
        status="ready",
        tone="Sketchy, playful, ideation",
        accent="#fef08a",
        secondary_accent="#fbcfe8",
        overlay_class="template-reflective",
        preview_source_video="sketch_post_it.mp4",
    ),
    HyperframesTemplate(
        id="prism_pro_pricing",
        label="Prism Pro Pricing",
        category="Promo",
        best_for="SaaS pricing highlights with pro labels.",
        effects=("price tag", "highlighted plan", "price pop"),
        caption_style="Pricing highlight captions",
        default_genres=("saas", "product", "promo"),
        status="ready",
        tone="Commercial, crisp, offer-led",
        accent="#a7f36b",
        secondary_accent="#67e8f9",
        overlay_class="template-promo",
        preview_source_video="prism_pro_pricing.mp4",
    ),
    HyperframesTemplate(
        id="chalk_word_emphasis",
        label="Chalk Word Emphasis",
        category="News",
        best_for="Chalk handwriting emphasis on dark boards.",
        effects=("chalk board", "handwriting emphasis", "scribble motion"),
        caption_style="Chalk handwriting captions",
        default_genres=("education", "analysis", "advice"),
        status="ready",
        tone="Classroom, chalky, focused",
        accent="#e2e8f0",
        secondary_accent="#94a3b8",
        overlay_class="template-news",
        preview_source_video="chalk_word_emphasis.mp4",
    ),
    HyperframesTemplate(
        id="techtalk_intel_brief",
        label="Intel Brief",
        category="Data",
        best_for="Edu-finance explainers: clean key takeaways, bilingual tech/finance talking-head hybrids.",
        effects=("intel lower-third", "teal keyline", "takeaway card", "brand chip"),
        caption_style="Weighted edu-finance captions",
        default_genres=("explainer", "techtalk", "tech_edu", "tech_ai", "markets", "opinion", "business_impact"),
        status="ready",
        tone="Clean, confident, edu-finance",
        accent="#2dd4bf",
        secondary_accent="#e2e8f0",
        overlay_class="template-data",
        preview_source_video="velocity_business_promo.mp4",
        formats=("long_16_9",),
    ),
)


TEMPLATE_BY_ID = {template.id: template for template in TEMPLATES}


def _preview_cache_ready(template_id: str, formats: list[str]) -> dict[str, bool]:
    from .hyperframes_previews import PREVIEW_CONTRACT_VERSION, PREVIEW_ROOT

    safe_template = template_id.replace(":", "__")
    ready: dict[str, bool] = {}
    for item in formats:
        path = PREVIEW_ROOT / safe_template / item / "preview.mp4"
        metadata_path = path.parent / "preview-metadata.json"
        if not path.exists() or path.stat().st_size <= 0 or not metadata_path.exists():
            ready[item] = False
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            ready[item] = False
            continue
        ready[item] = metadata.get("contract_version") == PREVIEW_CONTRACT_VERSION
    return ready


def _aggregate_preview_status(template_id: str, formats: list[str]) -> str:
    ready = _preview_cache_ready(template_id, formats)
    if all(ready.values()):
        return "ready"
    if any(ready.values()):
        return "partial"
    return "generating"


def preview_stock_path(template_id: str) -> Path | None:
    template = TEMPLATE_BY_ID.get(template_id)
    if not template:
        return None
    candidate = STOCK_DIR / template.preview_source_video
    return candidate if candidate.exists() else None


def template_supports_format(template: HyperframesTemplate | dict[str, Any], hyperframes_format: str) -> bool:
    _, _, resolved = dimensions_for_format(hyperframes_format)
    if isinstance(template, HyperframesTemplate):
        supported = template.formats
    else:
        supported = tuple(template.get("formats") or ("short_9_16", "long_16_9"))
    return resolved in supported


def list_hyperframes_templates(hyperframes_format: str | None = None) -> list[dict[str, Any]]:
    items = [template.public_dict() for template in TEMPLATES] + _saved_brand_system_templates()
    if not hyperframes_format:
        return items
    return [item for item in items if template_supports_format(item, hyperframes_format)]


def hyperframes_template_ids() -> set[str]:
    return set(TEMPLATE_BY_ID)


def normalize_hyperframes_template(value: Any) -> str:
    template_id = ALIASES.get(str(value or AUTO_TEMPLATE_ID).strip(), str(value or AUTO_TEMPLATE_ID).strip())
    if template_id.startswith("brand:") and _saved_brand_template_by_id(template_id):
        return template_id
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


def _auto_template_score(template: HyperframesTemplate, signals: set[str]) -> int:
    overlap = signals.intersection(template.default_genres)
    if not overlap:
        return 0
    specific = overlap - set(UNIVERSAL_CATALOG)
    return len(specific) * 100 + len(overlap)


def resolve_starter_template_id(value: Any) -> str:
    """Map a Brand Studio starter id (including aliases) to a builtin template id."""
    raw = str(value or "").strip() or DEFAULT_TEMPLATE_ID
    mapped = ALIASES.get(raw, raw)
    if mapped in TEMPLATE_BY_ID:
        return mapped
    return DEFAULT_TEMPLATE_ID


def resolve_hyperframes_template(
    value: Any = AUTO_TEMPLATE_ID,
    genres: list[str] | tuple[str, ...] | None = None,
    brand_template: str = "",
    hyperframes_format: str = "auto",
) -> dict[str, Any]:
    template_id = normalize_hyperframes_template(value)
    saved = _saved_brand_template_by_id(template_id)
    if saved:
        starter_id = resolve_starter_template_id(saved.get("starter_template"))
        base = TEMPLATE_BY_ID[starter_id].renderer_dict()
        return {
            **base,
            **saved,
            "version": TEMPLATE_VERSION,
            "starter_template": starter_id,
            "recipe_module": base.get("recipe_module") or starter_id,
            "accent": base["accent"],
            "secondary_accent": base["secondary_accent"],
            "overlay_class": base["overlay_class"],
            "font_family": base.get("font_family") or "",
            "motion_preset": base.get("motion_preset") or "",
            "color_grade": base.get("color_grade") or "",
            "preview_source_video": base.get("preview_source_video") or saved.get("preview_source_video"),
        }
    if template_id != AUTO_TEMPLATE_ID:
        return TEMPLATE_BY_ID[template_id].renderer_dict()

    signals = {str(item).strip().lower() for item in (genres or []) if str(item).strip()}
    brand = brand_template.lower()
    if "spiritual" in brand or "reflective" in brand:
        signals.add("kajian")

    best: HyperframesTemplate | None = None
    best_score = 0
    for template in TEMPLATES:
        if not template_supports_format(template, hyperframes_format):
            continue
        score = _auto_template_score(template, signals)
        if score > best_score:
            best = template
            best_score = score
    if best is not None:
        return best.renderer_dict()
    return TEMPLATE_BY_ID[DEFAULT_TEMPLATE_ID].renderer_dict()


def _build_brand_system_template_record(
    path: Path,
    payload: dict[str, Any],
    brand_system: dict[str, Any],
) -> dict[str, Any]:
    template_id = str(payload.get("id") or path.stem)
    label = str(payload.get("label") or path.stem.replace("_", " ").title())
    formats = ["short_9_16", "long_16_9"]
    public_id = f"brand:{template_id}"
    relative_path = str(path.relative_to(ROOT))
    starter_id = resolve_starter_template_id(brand_system.get("starter_template"))
    starter = TEMPLATE_BY_ID[starter_id]
    return {
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
        "brand_template_path": relative_path,
        "starter_template": starter_id,
        "recipe_module": starter.recipe_module or starter_id,
        "preview_source_video": starter.preview_source_video,
        "preview_seconds": PREVIEW_SECONDS,
        "preview_status": _aggregate_preview_status(public_id, formats),
        "preview_cache_ready": _preview_cache_ready(public_id, formats),
        "preview_urls": _preview_urls(public_id, formats),
        "preview_source_url": _preview_source_url(starter_id),
        "preview_video_urls": _official_preview_urls(starter_id, formats) or _official_preview_urls(public_id, formats),
        "production_checks": {
            "lint": "required",
            "inspect": "required",
            "render_preview": "required",
        },
    }


def _load_brand_system_template_by_public_id(template_id: str) -> dict[str, Any] | None:
    """Resolve saved brands for render even when hidden from public catalog APIs."""
    if not template_id.startswith("brand:"):
        return None
    stem = template_id.removeprefix("brand:")
    profiles = ROOT / "profiles"
    paths: list[Path] = []
    direct = profiles / f"{stem}.json"
    if direct.exists():
        paths.append(direct)
    for path in sorted(profiles.glob("custom_*.json")):
        if path not in paths:
            paths.append(path)
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        file_id = str(payload.get("id") or path.stem)
        if template_id != f"brand:{file_id}" and path.stem != stem:
            continue
        brand_system = payload.get("brand_system") if isinstance(payload.get("brand_system"), dict) else {}
        if not brand_system:
            continue
        return _build_brand_system_template_record(path, payload, brand_system)
    return None


def list_saved_brand_system_templates() -> list[dict[str, Any]]:
    """Public catalog entries for profiles/custom_*.json with a brand_system block."""
    return _saved_brand_system_templates()


def _saved_brand_system_templates() -> list[dict[str, Any]]:
    profiles = ROOT / "profiles"
    templates: list[dict[str, Any]] = []
    for path in sorted(profiles.glob("custom_*.json")):
        try:
            raw = path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            continue
        brand_system = payload.get("brand_system") if isinstance(payload.get("brand_system"), dict) else {}
        if not brand_system:
            continue
        templates.append(_build_brand_system_template_record(path, payload, brand_system))
    return templates


def _saved_brand_template_by_id(template_id: str) -> dict[str, Any] | None:
    if not template_id.startswith("brand:"):
        return None
    for template in _saved_brand_system_templates():
        if template["id"] == template_id:
            return template
    return _load_brand_system_template_by_public_id(template_id)


def _preview_urls(template_id: str, formats: list[str]) -> dict[str, str]:
    safe_id = template_id.replace(":", "__")
    return {
        item: f"/api/media/hyperframes-template-preview?template={safe_id}&format={item}"
        for item in formats
    }


def _preview_source_url(template_id: str) -> str:
    safe_id = template_id.replace(":", "__")
    return f"/api/media/hyperframes-template-stock?template={safe_id}"


def _official_preview_urls(template_id: str, formats: list[str]) -> dict[str, str]:
    mapped = OFFICIAL_PREVIEW_VIDEOS.get(template_id, {})
    if not mapped and template_id.startswith("brand:"):
        return {}
    return {item: mapped[item] for item in formats if item in mapped}
