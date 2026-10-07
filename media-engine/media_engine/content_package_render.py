"""Attach render artifacts to content packages (explainer jobs, still/carousel PNG)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .content_package import ContentPackage, apply_qa_status
from .content_package_still_render import carousel_slide_texts, render_carousel_slide_png, render_still_png
from .db import ARTIFACTS_DIR
from .explainer_pipeline import create_explainer_job


def _package_dir(pkg_id: str) -> Path:
    root = ARTIFACTS_DIR / "content_packages" / pkg_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def attach_render_artifacts(
    pkg: ContentPackage,
    *,
    source_text: str,
    llm_provider: str = "none",
    db_path: Any,
) -> ContentPackage:
    root = _package_dir(pkg.id)
    meta = dict(pkg.artifacts.package_meta)

    if pkg.format == "still":
        headline = (pkg.title or pkg.caption or "Untitled").split("\n", 1)[0].strip()
        body = pkg.caption if pkg.title else ""
        img = root / "still.png"
        render_still_png(img, headline=headline, body=body, brand_preset=pkg.brand_preset)
        pkg.artifacts.image_paths = [str(img)]
        meta["render"] = {"kind": "still_png", "path": str(img)}
    elif pkg.format == "carousel":
        slides = carousel_slide_texts(pkg)
        headline = (pkg.title or pkg.caption or "Carousel").split("\n", 1)[0].strip()
        paths: list[str] = []
        total = len(slides)
        for i, slide_text in enumerate(slides, start=1):
            slide = root / f"slide_{i}.png"
            render_carousel_slide_png(
                slide,
                headline=headline,
                slide_text=slide_text,
                slide_index=i,
                slide_total=total,
                brand_preset=pkg.brand_preset,
            )
            paths.append(str(slide))
        pkg.artifacts.slide_paths = paths
        meta["render"] = {"kind": "carousel_png", "slides": len(paths)}
        meta["slide_texts"] = slides
    elif pkg.format in ("short", "long_form"):
        topic = (pkg.title or pkg.caption or source_text)[:500].strip() or "Untitled"
        job = create_explainer_job(
            topic=topic,
            sources=[source_text[:8000]] if source_text else None,
            profile_id=pkg.profile_id,
            llm_provider=llm_provider,
            db_path=db_path,
        )
        job_id = str(job.get("job_id") or "")
        pending = root / "pending_explainer.mp4"
        pending.write_bytes(b"")
        pkg.artifacts.video_path = str(pending)
        if job_id:
            meta["explainer_job_id"] = job_id
            meta["explainer_status"] = "planned"
    elif pkg.format == "clip":
        clip = root / "clip.mp4"
        clip.write_bytes(b"")
        pkg.artifacts.video_path = str(clip)

    pkg.artifacts.package_meta = meta
    return apply_qa_status(pkg)
