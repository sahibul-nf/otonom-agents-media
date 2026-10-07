"""LLM-backed copy for content packages."""

from __future__ import annotations

import json
from typing import Any

from .content_package import ContentPackage, Format, Job, apply_qa_status
from .llm import LLMError, call_llm_json, llm_provider_ready


def _system_prompt(brain_snippet: str) -> str:
    brain = brain_snippet.strip() or "(no brand brain loaded — use clear tech/finance edutainment tone)"
    return (
        "You are a content strategist for Otonom Media. "
        "Return strict JSON only. Ground claims in the source; no invented statistics. "
        f"Brand context:\n{brain[:4000]}"
    )


def _user_prompt(
    *,
    format: Format,
    job: Job,
    source_text: str,
    source_meta: dict[str, Any],
) -> str:
    schema = {
        "caption": "main post body (required)",
        "title": "YouTube-style title when long_form",
        "description": "long-form description when long_form",
        "slide_texts": ["3-5 short lines for carousel slides"],
        "still_headline": "short headline for still image overlay",
    }
    return (
        f"Delivery format: {format}\n"
        f"Job intent: {job}\n"
        f"Source metadata: {json.dumps(source_meta, ensure_ascii=False)}\n\n"
        f"Source text:\n{source_text[:20000]}\n\n"
        "Fill this JSON schema (omit unused keys):\n"
        f"{json.dumps(schema, indent=2)}\n"
        "caption must be complete and ready to publish. Indonesian unless source is English."
    )


def apply_llm_to_package(
    pkg: ContentPackage,
    *,
    source_text: str,
    source_meta: dict[str, Any],
    brain_snippet: str,
    llm_provider: str,
    profile_id: str,
) -> ContentPackage:
    provider = (llm_provider or "none").strip().lower()
    if provider == "none":
        return pkg

    ready = llm_provider_ready(provider, profile_id=profile_id)
    if not ready.get("ready"):
        pkg.qa.errors.append(f"LLM not configured: {ready.get('missing') or provider}")
        return apply_qa_status(pkg)

    try:
        raw = call_llm_json(
            provider,
            _system_prompt(brain_snippet),
            _user_prompt(format=pkg.format, job=pkg.job, source_text=source_text, source_meta=source_meta),
            timeout_seconds=90,
            profile_id=profile_id,
        )
    except (LLMError, ValueError, json.JSONDecodeError) as exc:
        pkg.qa.errors.append(f"LLM failed ({provider}): {exc}")
        return apply_qa_status(pkg)

    if not isinstance(raw, dict):
        pkg.qa.errors.append("LLM returned non-object JSON")
        return apply_qa_status(pkg)

    caption = str(raw.get("caption") or "").strip()
    if caption:
        pkg.caption = caption
    if pkg.format == "long_form":
        title = str(raw.get("title") or "").strip()
        desc = str(raw.get("description") or "").strip()
        if title:
            pkg.title = title
        if desc:
            pkg.description = desc
    slides = raw.get("slide_texts")
    if pkg.format == "carousel" and isinstance(slides, list):
        texts = [str(s).strip() for s in slides if str(s).strip()]
        if 3 <= len(texts) <= 5:
            pkg.artifacts.package_meta = {**pkg.artifacts.package_meta, "slide_texts": texts}
            pkg.artifacts.slide_paths = [f"pending_slide_{i}" for i in range(1, len(texts) + 1)]
    if pkg.format == "still":
        headline = str(raw.get("still_headline") or raw.get("title") or "").strip()
        if headline and not pkg.title:
            pkg.title = headline

    pkg.qa.claims_checked = True
    return apply_qa_status(pkg)
