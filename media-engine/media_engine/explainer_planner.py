"""Plan hybrid explainer scenes (avatar | text | broll) from a topic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from .llm import LLMError, call_llm_json

SceneType = Literal["avatar", "text", "broll"]

VALID_SCENE_TYPES = {"avatar", "text", "broll"}

PLANNER_SYSTEM = """You plan hybrid educational YouTube explainers in Indonesian.
Return JSON only with shape:
{"title": string, "scenes": [{"type":"avatar"|"text"|"broll","id":string,"script"?:string,"headline"?:string,"narration"?:string,"duration_target":number,"clip_file"?:string}]}
Rules:
- Alternate avatar (5-15s) with text/broll scenes.
- Avatar scenes need script (spoken).
- Text/broll need headline and optional narration.
- duration_target is seconds (number).
- Prefer 6-10 scenes for a short pilot (~2-5 minutes).
- clip_file for avatar scenes is optional (e.g. scene_01.mp4); leave empty if unknown.
"""


def default_plan(topic: str, *, language: str = "id") -> dict[str, Any]:
    """Deterministic fallback plan (no LLM)."""
    topic = (topic or "Topik").strip() or "Topik"
    if language.startswith("en"):
        return {
            "title": topic,
            "scenes": [
                {
                    "id": "s01",
                    "type": "avatar",
                    "script": f"Hey! Today we break down: {topic}.",
                    "duration_target": 10,
                    "clip_file": "scene_01.mp4",
                },
                {
                    "id": "s02",
                    "type": "text",
                    "headline": topic,
                    "narration": f"Here is the core idea behind {topic}.",
                    "duration_target": 12,
                },
                {
                    "id": "s03",
                    "type": "broll",
                    "headline": "How it works",
                    "narration": "Key mechanics in plain language.",
                    "duration_target": 12,
                },
                {
                    "id": "s04",
                    "type": "avatar",
                    "script": "So what should you watch out for?",
                    "duration_target": 8,
                    "clip_file": "scene_04.mp4",
                },
                {
                    "id": "s05",
                    "type": "text",
                    "headline": "Risks & tips",
                    "narration": "Not a scam by default — but always do your own research.",
                    "duration_target": 12,
                },
                {
                    "id": "s06",
                    "type": "avatar",
                    "script": "If this helped, subscribe for the next deep dive.",
                    "duration_target": 10,
                    "clip_file": "scene_06.mp4",
                },
            ],
        }
    return {
        "title": topic,
        "scenes": [
            {
                "id": "s01",
                "type": "avatar",
                "script": f"Halo! Hari ini kita bahas: {topic}.",
                "duration_target": 10,
                "clip_file": "scene_01.mp4",
            },
            {
                "id": "s02",
                "type": "text",
                "headline": topic,
                "narration": f"Inti dari {topic} bisa dipahami dengan sederhana.",
                "duration_target": 12,
            },
            {
                "id": "s03",
                "type": "broll",
                "headline": "Cara kerjanya",
                "narration": "Mekanisme utamanya dijelaskan singkat di bagian ini.",
                "duration_target": 12,
            },
            {
                "id": "s04",
                "type": "avatar",
                "script": "Lalu, apa yang perlu diwaspadai?",
                "duration_target": 8,
                "clip_file": "scene_04.mp4",
            },
            {
                "id": "s05",
                "type": "text",
                "headline": "Risiko & tips",
                "narration": "Bukan scam secara default — tapi tetap lakukan riset sendiri.",
                "duration_target": 12,
            },
            {
                "id": "s06",
                "type": "avatar",
                "script": "Kalau bermanfaat, subscribe untuk topik berikutnya!",
                "duration_target": 10,
                "clip_file": "scene_06.mp4",
            },
        ],
    }


def normalize_plan(raw: dict[str, Any]) -> dict[str, Any]:
    title = str(raw.get("title") or "Explainer").strip() or "Explainer"
    scenes_in = raw.get("scenes")
    if not isinstance(scenes_in, list) or not scenes_in:
        raise ValueError("plan.scenes must be a non-empty list")

    scenes: list[dict[str, Any]] = []
    for index, item in enumerate(scenes_in):
        if not isinstance(item, dict):
            raise ValueError(f"scene[{index}] must be an object")
        scene_type = str(item.get("type") or "").strip().lower()
        if scene_type not in VALID_SCENE_TYPES:
            raise ValueError(f"scene[{index}].type must be one of {sorted(VALID_SCENE_TYPES)}")
        duration = float(item.get("duration_target") or 10)
        duration = max(3.0, min(30.0, duration))
        scene_id = str(item.get("id") or f"s{index + 1:02d}").strip()
        scene: dict[str, Any] = {
            "id": scene_id,
            "type": scene_type,
            "duration_target": duration,
        }
        if scene_type == "avatar":
            script = str(item.get("script") or "").strip()
            if not script:
                raise ValueError(f"scene[{index}] avatar requires script")
            scene["script"] = script
            clip_file = str(item.get("clip_file") or "").strip()
            if clip_file:
                scene["clip_file"] = clip_file
        else:
            headline = str(item.get("headline") or item.get("title") or "").strip()
            if not headline:
                raise ValueError(f"scene[{index}] {scene_type} requires headline")
            scene["headline"] = headline
            narration = str(item.get("narration") or "").strip()
            if narration:
                scene["narration"] = narration
            template = str(item.get("template") or "").strip()
            if template:
                scene["template"] = template
        scenes.append(scene)

    return {"title": title, "scenes": scenes}


def plan_explainer(
    topic: str,
    *,
    sources: list[str] | None = None,
    llm_provider: str = "none",
    language: str = "id",
) -> dict[str, Any]:
    """Build a scene plan. Falls back to default_plan when LLM is unavailable."""
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("topic is required")

    if llm_provider and llm_provider != "none":
        source_block = "\n".join(f"- {s}" for s in (sources or []) if str(s).strip()) or "(none)"
        user_prompt = json.dumps(
            {
                "topic": topic,
                "language": language,
                "sources": source_block,
            },
            ensure_ascii=False,
        )
        try:
            raw = call_llm_json(llm_provider, PLANNER_SYSTEM, user_prompt)
            if isinstance(raw, dict):
                return normalize_plan(raw)
        except (LLMError, ValueError, TypeError, json.JSONDecodeError):
            pass

    return normalize_plan(default_plan(topic, language=language))


def load_plan_file(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("scenes file must be a JSON object")
    return normalize_plan(data)
