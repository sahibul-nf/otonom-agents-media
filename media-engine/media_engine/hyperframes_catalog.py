"""HyperFrames catalog capability manifest — derived from vendored OSS manifest."""

from __future__ import annotations

from typing import Any

from .hyperframes_oss import installed_catalog_items, load_oss_manifest

CATALOG_VERSION = str(load_oss_manifest().get("version") or "2026-09-17")

OSS_SECTIONS: tuple[str, ...] = (
    "Captions",
    "Effects",
    "Social Overlays",
    "Lower Thirds",
    "Blocks",
    "Data",
    "CSS Transitions",
    "Shader Transitions",
    "HTML-in-Canvas",
    "Code Animations",
    "Showcases",
)


def list_hyperframes_catalog() -> dict[str, Any]:
    items = installed_catalog_items()
    groups: dict[str, list[dict[str, Any]]] = {}
    oss_groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        public = {
            "id": item["id"],
            "label": item["label"],
            "kind": item.get("kind", "component"),
            "category": item.get("category", ""),
            "oss_section": item.get("oss_section", item.get("category", "")),
            "status": item.get("status", "production-ready"),
            "best_for": item.get("best_for", ""),
            "lifecycle": item.get("lifecycle", "enter-ambient-exit"),
            "slot": item.get("slot", ""),
            "installed": True,
        }
        groups.setdefault(public["category"], []).append(public)
        oss_groups.setdefault(public["oss_section"], []).append(public)
    return {
        "version": CATALOG_VERSION,
        "oss_sections": list(OSS_SECTIONS),
        "items": items,
        "installed_items": [item["id"] for item in items],
        "groups": groups,
        "oss_groups": oss_groups,
        "status_policy": {
            "production-ready": "Allowed in normal production renders.",
            "beta": "Available for brand templates with a visible warning.",
            "experimental": "Preview/sandbox only until lint, inspect, and performance checks pass.",
        },
        "lifecycle_policy": {
            "word-timed": "Synced to caption word timings via GSAP.",
            "enter-ambient-exit": "Intro hook enters, subtle idle motion, exits before caption peak.",
            "enter-ambient": "Enters with motion and holds ambient drift.",
            "ambient": "Full-frame texture with no text lifecycle.",
            "outro": "Appears in final seconds of the clip.",
        },
    }


# Back-compat for tests importing CATALOG_ITEMS
CATALOG_ITEMS: tuple[dict[str, str], ...] = tuple(
    {
        "id": item["id"],
        "label": item["label"],
        "kind": str(item.get("kind", "component")),
        "category": str(item.get("category", "")),
        "oss_section": str(item.get("oss_section", "")),
        "status": str(item.get("status", "production-ready")),
        "best_for": str(item.get("best_for", "")),
        "lifecycle": str(item.get("lifecycle", "enter-ambient-exit")),
    }
    for item in installed_catalog_items()
)
