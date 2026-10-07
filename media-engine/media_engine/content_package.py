"""Content package schema, validation, and generation (six delivery formats)."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

Format = Literal["text_only", "still", "carousel", "short", "long_form", "clip"]
Job = Literal["inform", "teach", "save_for_later"]
VideoEngine = Literal["av_explainer", "motion", "heygen", "clip_cut"]
PackageStatus = Literal["draft", "ready_for_review", "approved", "published"]

FORMATS: frozenset[str] = frozenset({"text_only", "still", "carousel", "short", "long_form", "clip"})
JOBS: frozenset[str] = frozenset({"inform", "teach", "save_for_later"})
VIDEO_ENGINES: frozenset[str] = frozenset({"av_explainer", "motion", "heygen", "clip_cut"})


@dataclass
class PackageArtifacts:
    image_paths: list[str] = field(default_factory=list)
    video_path: str = ""
    slide_paths: list[str] = field(default_factory=list)
    package_meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_paths": list(self.image_paths),
            "video_path": self.video_path,
            "slide_paths": list(self.slide_paths),
            "package_meta": dict(self.package_meta),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> PackageArtifacts:
        raw = raw or {}
        return cls(
            image_paths=[str(p) for p in raw.get("image_paths") or []],
            video_path=str(raw.get("video_path") or ""),
            slide_paths=[str(p) for p in raw.get("slide_paths") or []],
            package_meta=dict(raw.get("package_meta") or {}),
        )


@dataclass
class PackageQA:
    passed: bool = False
    errors: list[str] = field(default_factory=list)
    visual_approved: bool = False
    claims_checked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "errors": list(self.errors),
            "visual_approved": self.visual_approved,
            "claims_checked": self.claims_checked,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> PackageQA:
        raw = raw or {}
        return cls(
            passed=bool(raw.get("passed")),
            errors=[str(e) for e in raw.get("errors") or []],
            visual_approved=bool(raw.get("visual_approved")),
            claims_checked=bool(raw.get("claims_checked")),
        )


@dataclass
class ContentPackage:
    id: str
    profile_id: str
    format: Format
    job: Job
    source_kind: str
    source_ref: str
    caption: str
    title: str = ""
    description: str = ""
    video_engine: VideoEngine | None = None
    parent_package_id: str = ""
    brand_preset: str = "blank"
    artifacts: PackageArtifacts = field(default_factory=PackageArtifacts)
    qa: PackageQA = field(default_factory=PackageQA)
    status: PackageStatus = "draft"
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "format": self.format,
            "job": self.job,
            "source": {"kind": self.source_kind, "ref": self.source_ref},
            "caption": self.caption,
            "title": self.title,
            "description": self.description,
            "video_engine": self.video_engine,
            "parent_package_id": self.parent_package_id,
            "brand_preset": self.brand_preset,
            "artifacts": self.artifacts.to_dict(),
            "qa": self.qa.to_dict(),
            "status": self.status,
            "created_at": self.created_at,
            "meta": dict(self.artifacts.package_meta),
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ContentPackage:
        source = json.loads(row.get("source_json") or "{}")
        return cls(
            id=str(row["id"]),
            profile_id=str(row["profile_id"]),
            format=row["format"],
            job=row["job"],
            source_kind=str(source.get("kind") or ""),
            source_ref=str(source.get("ref") or ""),
            caption=str(row.get("caption") or ""),
            title=str(row.get("title") or ""),
            description=str(row.get("description") or ""),
            video_engine=row.get("video_engine") or None,
            parent_package_id=str(row.get("parent_package_id") or ""),
            brand_preset=str(row.get("brand_preset") or "blank"),
            artifacts=PackageArtifacts.from_dict(json.loads(row.get("artifacts_json") or "{}")),
            qa=PackageQA.from_dict(json.loads(row.get("qa_json") or "{}")),
            status=row.get("status") or "draft",
            created_at=str(row.get("created_at") or ""),
        )


def validate_package(pkg: ContentPackage) -> PackageQA:
    errors: list[str] = []
    if pkg.format not in FORMATS:
        errors.append(f"invalid format: {pkg.format}")
    if pkg.job not in JOBS:
        errors.append(f"invalid job: {pkg.job}")
    if not pkg.caption.strip() and pkg.format != "clip":
        errors.append("caption is required")

    if pkg.format == "still":
        if not pkg.artifacts.image_paths:
            errors.append("still requires one image_paths entry")
    elif pkg.format == "carousel":
        n = len(pkg.artifacts.slide_paths) or len(pkg.artifacts.image_paths)
        if n < 3 or n > 5:
            errors.append("carousel requires 3–5 slides")
    elif pkg.format in ("short", "long_form"):
        if pkg.video_engine not in ("av_explainer", "motion", "heygen"):
            errors.append("short/long_form require video_engine av_explainer, motion, or heygen")
        if not pkg.artifacts.video_path:
            errors.append("video_path is required")
        if pkg.format == "long_form" and not pkg.title.strip():
            errors.append("long_form requires title")
    elif pkg.format == "clip":
        if not pkg.parent_package_id:
            errors.append("clip requires parent_package_id")
        if pkg.video_engine != "clip_cut":
            errors.append("clip must use video_engine clip_cut")
        if not pkg.artifacts.video_path:
            errors.append("clip requires video_path")

    passed = not errors
    return PackageQA(passed=passed, errors=errors, claims_checked=bool(pkg.caption.strip()))


def apply_qa_status(pkg: ContentPackage) -> ContentPackage:
    pkg.qa = validate_package(pkg)
    if pkg.qa.passed and pkg.status == "draft":
        pkg.status = "ready_for_review"
    elif not pkg.qa.passed:
        pkg.status = "draft"
    return pkg


def _youtube_id(url: str) -> str:
    match = re.search(r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{6,})", url)
    return match.group(1) if match else ""


def stub_generate_package(
    *,
    profile_id: str,
    format: Format,
    job: Job = "inform",
    source_kind: str = "youtube",
    source_ref: str = "",
    brand_preset: str = "blank",
    llm_provider: str = "none",
    parent_package_id: str = "",
    video_engine: VideoEngine | None = None,
) -> ContentPackage:
    """Deterministic package for tests and llm_provider=none."""
    now = datetime.now(timezone.utc).isoformat()
    pkg_id = f"pkg_{uuid.uuid4().hex[:12]}"
    yt = _youtube_id(source_ref) if source_kind == "youtube" else ""
    hook = f"Stub package from {source_kind}"
    if yt:
        hook = f"Key takeaway from YouTube {yt}"

    caption = f"{hook}\n\n— Generated with provider={llm_provider} (stub). Edit in Review."

    artifacts = PackageArtifacts()
    engine = video_engine

    if format == "text_only":
        engine = None
    elif format == "still":
        engine = None
        artifacts.image_paths = ["artifacts/content_packages/placeholder_still.png"]
    elif format == "carousel":
        engine = None
        artifacts.slide_paths = [f"artifacts/content_packages/slide_{i}.png" for i in range(1, 4)]
    elif format == "short":
        engine = engine or "av_explainer"
        artifacts.video_path = "artifacts/content_packages/placeholder_short.mp4"
    elif format == "long_form":
        engine = engine or "av_explainer"
        artifacts.video_path = "artifacts/content_packages/placeholder_long.mp4"
    elif format == "clip":
        engine = "clip_cut"
        artifacts.video_path = "artifacts/content_packages/placeholder_clip.mp4"

    pkg = ContentPackage(
        id=pkg_id,
        profile_id=profile_id,
        format=format,
        job=job,
        source_kind=source_kind,
        source_ref=source_ref,
        caption=caption,
        title="Stub long-form title" if format == "long_form" else "",
        description="Stub description for long-form." if format == "long_form" else "",
        video_engine=engine,
        parent_package_id=parent_package_id,
        brand_preset=brand_preset,
        artifacts=artifacts,
        created_at=now,
    )
    return apply_qa_status(pkg)
