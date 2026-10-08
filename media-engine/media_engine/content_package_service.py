"""Create and fetch content packages (API + MCP entry)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

from .brand_pack import load_brain_text
from .content_package import FORMATS, Format, Job, VideoEngine, stub_generate_package
from .content_package_llm import apply_llm_to_package
from .content_package_render import attach_render_artifacts
from .content_package_explainer import refresh_package_explainer_artifacts
from .content_package_store import get_package, list_packages, save_package
from .db import DEFAULT_DB, DEFAULT_WORKSPACE_PROFILE_ID
from .llm import LLMError, llm_provider_ready
from .package_sources import resolve_source_text

FormatArg = Literal["text_only", "still", "carousel", "short", "long_form", "clip"]


@dataclass(frozen=True)
class _SourceContext:
    ref: str
    kind: str
    source_text: str
    source_meta: dict[str, Any]
    provider: str
    brain_snippet: str


def parse_create_formats(
    *,
    format: str | None = None,
    formats: Sequence[str] | None = None,
    parent_package_id: str = "",
) -> list[FormatArg]:
    items: list[str] = []
    if formats:
        items.extend(str(f).strip() for f in formats if str(f).strip())
    elif format and str(format).strip():
        items = [str(format).strip()]
    if not items:
        raise ValueError("format or formats is required (at least one)")
    ordered: list[FormatArg] = []
    seen: set[str] = set()
    for raw in items:
        if raw not in FORMATS:
            raise ValueError(f"unsupported format: {raw}")
        if raw in seen:
            continue
        seen.add(raw)
        ordered.append(raw)  # type: ignore[arg-type]
    parent = parent_package_id.strip()
    if "clip" in ordered and not parent:
        raise ValueError("clip requires parent_package_id")
    return ordered


def _resolve_source_context(
    *,
    source_kind: str,
    source_ref: str,
    topic: str,
    profile_id: str,
    brand_preset: str,
    llm_provider: str,
    formats: Sequence[FormatArg],
) -> _SourceContext:
    ref = source_ref.strip() or topic.strip()
    non_clip = [f for f in formats if f != "clip"]
    if non_clip and not ref:
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
    if ref:
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

    return _SourceContext(
        ref=ref,
        kind=kind,
        source_text=source_text,
        source_meta=source_meta,
        provider=provider,
        brain_snippet=brain_snippet,
    )


def _create_one_package(
    format: FormatArg,
    *,
    ctx: _SourceContext,
    job: Job,
    profile_id: str,
    brand_preset: str,
    parent_package_id: str,
    video_engine: VideoEngine | None,
    db_path: str | Path,
    batch_id: str,
    batch_formats: list[str],
) -> dict[str, Any]:
    pkg = stub_generate_package(
        profile_id=profile_id,
        format=format,
        job=job,
        source_kind=ctx.kind,
        source_ref=ctx.ref,
        brand_preset=brand_preset,
        llm_provider=ctx.provider,
        parent_package_id=parent_package_id,
        video_engine=video_engine,
    )
    pkg.artifacts.package_meta = {
        "llm_provider": ctx.provider,
        "source_meta": ctx.source_meta,
        "batch_id": batch_id,
        "batch_formats": list(batch_formats),
    }

    if ctx.provider != "none":
        try:
            pkg = apply_llm_to_package(
                pkg,
                source_text=ctx.source_text,
                source_meta=ctx.source_meta,
                brain_snippet=ctx.brain_snippet,
                llm_provider=ctx.provider,
                profile_id=profile_id,
            )
        except LLMError as exc:
            pkg.qa.errors.append(str(exc))
    elif ctx.brain_snippet and pkg.format == "text_only":
        pkg.caption = f"{pkg.caption}\n\n[Brand context loaded: {len(ctx.brain_snippet)} chars]"

    if format != "text_only":
        pkg = attach_render_artifacts(pkg, source_text=ctx.source_text, llm_provider=ctx.provider, db_path=db_path)

    save_package(pkg, db_path=db_path)
    return pkg.to_dict()


def create_content_packages_batch(
    *,
    formats: Sequence[FormatArg],
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
    format_list = list(formats)
    if not format_list:
        raise ValueError("formats must not be empty")
    batch_id = uuid.uuid4().hex[:12]
    ctx = _resolve_source_context(
        source_kind=source_kind,
        source_ref=source_ref,
        topic=topic,
        profile_id=profile_id,
        brand_preset=brand_preset,
        llm_provider=llm_provider,
        formats=format_list,
    )
    batch_formats = [str(f) for f in format_list]
    packages: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for fmt in format_list:
        try:
            packages.append(
                _create_one_package(
                    fmt,
                    ctx=ctx,
                    job=job,
                    profile_id=profile_id,
                    brand_preset=brand_preset,
                    parent_package_id=parent_package_id,
                    video_engine=video_engine,
                    db_path=db_path,
                    batch_id=batch_id,
                    batch_formats=batch_formats,
                )
            )
        except (ValueError, LLMError, OSError) as exc:
            errors.append({"format": fmt, "error": str(exc)})
    if not packages:
        detail = errors[0]["error"] if errors else "no packages created"
        raise ValueError(detail)
    return {"batch_id": batch_id, "packages": packages, "errors": errors}


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
    batch = create_content_packages_batch(
        formats=[format],
        source_kind=source_kind,
        source_ref=source_ref,
        job=job,
        profile_id=profile_id,
        brand_preset=brand_preset,
        llm_provider=llm_provider,
        parent_package_id=parent_package_id,
        video_engine=video_engine,
        topic=topic,
        db_path=db_path,
    )
    if batch.get("errors"):
        raise ValueError(batch["errors"][0]["error"])
    return batch["packages"][0]


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
