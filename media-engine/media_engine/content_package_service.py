"""Create and fetch content packages (API + MCP entry)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from .brand_pack import load_brain_text
from .content_package import Format, Job, VideoEngine, stub_generate_package
from .content_package_llm import apply_llm_to_package
from .content_package_render import attach_render_artifacts
from .content_package_explainer import refresh_package_explainer_artifacts
from .content_package_store import get_package, list_packages, save_package
from .db import DEFAULT_DB, DEFAULT_WORKSPACE_PROFILE_ID
from .llm import LLMError, llm_provider_ready
from .package_sources import resolve_source_text

FormatArg = Literal["text_only", "still", "carousel", "short", "long_form", "clip"]


def create_content_package(
    *,
    format: FormatArg,
    source_kind: str = "youtube",
    source_ref: str = "",
    job: Job = "inform",
    profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID,
    brand_preset: str = "blank",
    llm_provider: str = "none",
    parent_package_id: str = "",
    video_engine: VideoEngine | None = None,
    topic: str = "",
    db_path: str | Path = DEFAULT_DB,
) -> dict[str, Any]:
    ref = source_ref.strip() or topic.strip()
    if not ref and format != "clip":
        raise ValueError("source_ref or topic is required")

    provider = (llm_provider or "none").strip().lower()
    if provider != "none" and not llm_provider_ready(provider, profile_id=profile_id).get("ready"):
        provider = "none"

    brain_snippet = ""
    try:
        brain_snippet = load_brain_text(preset=brand_preset)[:5000]
    except (FileNotFoundError, ValueError):
        brain_snippet = ""

    kind = (source_kind or "youtube").strip().lower()
    if kind == "topic" and topic.strip():
        ref = topic.strip()

    source_text = ref
    source_meta: dict[str, Any] = {"kind": kind}
    try:
        if kind == "chat":
            source_text, source_meta = resolve_source_text("chat", ref)
        elif kind == "youtube" or ("youtu" in ref.lower() and kind != "chat"):
            source_text, source_meta = resolve_source_text("youtube", ref)
        else:
            source_text, source_meta = resolve_source_text("topic", ref)
    except ValueError:
        source_text = ref
        source_meta = {"kind": kind, "fallback": True}

    pkg = stub_generate_package(
        profile_id=profile_id,
        format=format,
        job=job,
        source_kind=kind if kind else source_kind,
        source_ref=ref,
        brand_preset=brand_preset,
        llm_provider=provider,
        parent_package_id=parent_package_id,
        video_engine=video_engine,
    )
    pkg.artifacts.package_meta = {
        "llm_provider": provider,
        "source_meta": source_meta,
    }

    if provider != "none":
        try:
            pkg = apply_llm_to_package(
                pkg,
                source_text=source_text,
                source_meta=source_meta,
                brain_snippet=brain_snippet,
                llm_provider=provider,
                profile_id=profile_id,
            )
        except LLMError as exc:
            pkg.qa.errors.append(str(exc))
    elif brain_snippet and pkg.format == "text_only":
        pkg.caption = f"{pkg.caption}\n\n[Brand context loaded: {len(brain_snippet)} chars]"

    if format != "text_only":
        pkg = attach_render_artifacts(pkg, source_text=source_text, llm_provider=provider, db_path=db_path)

    save_package(pkg, db_path=db_path)
    return pkg.to_dict()


def get_content_package(package_id: str, *, db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    pkg = get_package(package_id, db_path=db_path)
    if not pkg:
        raise ValueError(f"package not found: {package_id}")
    pkg = refresh_package_explainer_artifacts(pkg, db_path=db_path)
    return pkg.to_dict()


def list_content_packages(
    *,
    db_path: str | Path = DEFAULT_DB,
    profile_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    rows = list_packages(db_path=db_path, profile_id=profile_id, status=status, limit=limit)
    out: list[dict[str, Any]] = []
    for row in rows:
        pkg = get_package(str(row["id"]), db_path=db_path)
        if not pkg:
            continue
        pkg = refresh_package_explainer_artifacts(pkg, db_path=db_path)
        out.append(pkg.to_dict())
    return out
