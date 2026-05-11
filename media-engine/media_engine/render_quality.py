"""Lightweight render and caption quality reports."""

from __future__ import annotations

from typing import Any


def build_render_quality_report(contract: dict[str, Any], output_path: str = "") -> dict[str, Any]:
    events = contract.get("captionEvents", [])
    duration_ms = int(contract.get("durationMs", 0))
    overlap_count = 0
    for previous, current in zip(events, events[1:]):
        if int(previous["endMs"]) > int(current["startMs"]):
            overlap_count += 1
    covered_ms = sum(max(0, int(event["endMs"]) - int(event["startMs"])) for event in events)
    caption_coverage = round(covered_ms / duration_ms, 3) if duration_ms else 0
    score = 100
    if overlap_count:
        score -= 35
    if caption_coverage < 0.45:
        score -= 20
    if not output_path:
        score -= 5
    return {
        "engine": "render_quality_v1",
        "output_path": output_path,
        "duration_ms": duration_ms,
        "caption_event_count": len(events),
        "caption_overlap_count": overlap_count,
        "caption_coverage": caption_coverage,
        "audio_expected": True,
        "quality_score": max(0, min(100, score)),
    }
