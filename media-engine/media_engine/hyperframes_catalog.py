"""HyperFrames catalog capability manifest for production-safe template building."""

from __future__ import annotations

from typing import Any


CATALOG_VERSION = "2026-05-25"


def _item(id: str, label: str, kind: str, category: str, status: str, best_for: str) -> dict[str, str]:
    return {
        "id": id,
        "label": label,
        "kind": kind,
        "category": category,
        "status": status,
        "best_for": best_for,
    }


CATALOG_ITEMS: tuple[dict[str, str], ...] = (
    _item("warm-grain", "Warm Grain", "example", "Official examples", "production-ready", "Branding, lifestyle, editorial clips"),
    _item("play-mode", "Play Mode", "example", "Official examples", "production-ready", "Social media and product launches"),
    _item("swiss-grid", "Swiss Grid", "example", "Official examples", "production-ready", "Corporate, data, technical explainers"),
    _item("vignelli", "Vignelli", "example", "Official examples", "production-ready", "Portrait headlines and announcements"),
    _item("decision-tree", "Decision Tree", "example", "Official examples", "production-ready", "Explainers and tutorials"),
    _item("kinetic-type", "Kinetic Type", "example", "Official examples", "production-ready", "Promos, intros, title cards"),
    _item("product-promo", "Product Promo", "example", "Official examples", "production-ready", "Product showcases and demos"),
    _item("nyt-graph", "NYT Graph", "example", "Official examples", "production-ready", "Data stories and reports"),
    _item("caption-clip-wipe", "Clip Wipe", "component", "Captions", "production-ready", "Clean per-word reveal"),
    _item("caption-editorial-emphasis", "Editorial Emphasis", "component", "Captions", "production-ready", "Dramatic editorial word hierarchy"),
    _item("caption-pill-karaoke", "Pill Karaoke", "component", "Captions", "production-ready", "Social/podcast karaoke captions"),
    _item("caption-weight-shift", "Weight Shift", "component", "Captions", "production-ready", "Calm reflective caption emphasis"),
    _item("caption-highlight", "Highlight", "component", "Captions", "production-ready", "TikTok-style active word highlight"),
    _item("caption-gradient-fill", "Gradient Fill", "component", "Captions", "production-ready", "Premium promo captions"),
    _item("caption-kinetic-slam", "Kinetic Slam", "component", "Captions", "beta", "High-impact title and hook words"),
    _item("caption-neon-glow", "Neon Glow", "component", "Captions", "beta", "High-energy creator or tech captions"),
    _item("caption-glitch-rgb", "Glitch RGB", "component", "Captions", "experimental", "Glitch/cyber visual treatment"),
    _item("caption-matrix-decode", "Matrix Decode", "component", "Captions", "experimental", "Tech/cyber decode effects"),
    _item("grain-overlay", "Grain Overlay", "component", "Texture/effects", "production-ready", "Analog warmth and texture"),
    _item("vignette", "Vignette", "component", "Texture/effects", "production-ready", "Focus pull and edge control"),
    _item("shimmer-sweep", "Shimmer Sweep", "component", "Texture/effects", "production-ready", "Premium text and CTA reveal"),
    _item("parallax-zoom", "Parallax Zoom", "component", "Transitions", "beta", "Card-to-full-frame zoom reveal"),
    _item("grid-pixelate-wipe", "Grid Pixelate Wipe", "component", "Transitions", "beta", "Grid dissolve scene change"),
    _item("yt-lower-third", "YouTube Lower Third", "block", "Social overlays", "production-ready", "Subscribe CTA and channel identity"),
    _item("instagram-follow", "Instagram Follow", "block", "Social overlays", "production-ready", "Instagram creator follow CTA"),
    _item("tiktok-follow", "TikTok Follow", "block", "Social overlays", "production-ready", "TikTok creator follow CTA"),
    _item("x-post", "X Post Card", "block", "Social overlays", "production-ready", "Tweet/social proof overlay"),
    _item("reddit-post", "Reddit Post Card", "block", "Social overlays", "beta", "Community/social proof overlay"),
    _item("spotify-card", "Spotify Now Playing", "block", "Social overlays", "beta", "Music/podcast now-playing card"),
    _item("data-chart", "Data Chart", "block", "Data", "production-ready", "Bar and line chart explainer"),
    _item("flowchart", "Flowchart", "block", "Data", "production-ready", "Decision tree/tutorial flow"),
    _item("world-map", "World Map", "block", "Maps", "production-ready", "Global news and region explainers"),
    _item("us-map", "US Map", "block", "Maps", "production-ready", "US regional data stories"),
    _item("app-showcase", "App Showcase", "block", "Product", "production-ready", "SaaS/product screen showcase"),
    _item("logo-outro", "Logo Outro", "block", "Product", "production-ready", "Brand outro and final CTA"),
    _item("vfx-iphone-device", "iPhone & MacBook 3D Showcase", "block", "HTML-in-Canvas", "beta", "Product/device cinematic showcase"),
    _item("vfx-liquid-background", "Liquid Background", "block", "HTML-in-Canvas", "experimental", "Fluid shader background"),
    _item("chromatic-radial-split", "Chromatic Radial Split", "block", "Shader transitions", "experimental", "Stylized shader transition"),
    _item("cinematic-zoom", "Cinematic Zoom", "block", "Shader transitions", "beta", "Fast dramatic zoom transition"),
    _item("whip-pan", "Whip Pan", "block", "Shader transitions", "beta", "Fast camera whip transition"),
)


def list_hyperframes_catalog() -> dict[str, Any]:
    groups: dict[str, list[dict[str, str]]] = {}
    for item in CATALOG_ITEMS:
        groups.setdefault(item["category"], []).append(item)
    return {
        "version": CATALOG_VERSION,
        "items": list(CATALOG_ITEMS),
        "groups": groups,
        "status_policy": {
            "production-ready": "Allowed in normal production renders.",
            "beta": "Available for brand templates with a visible warning.",
            "experimental": "Preview/sandbox only until lint, inspect, and performance checks pass.",
        },
    }
