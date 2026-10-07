"""Attach render artifacts to content packages (explainer jobs, placeholders)."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from .content_package import ContentPackage, apply_qa_status
from .db import ARTIFACTS_DIR
from .explainer_pipeline import create_explainer_job

_MIN_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


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
        img = root / "still.png"
        img.write_bytes(_MIN_PNG)
        pkg.artifacts.image_paths = [str(img)]
    elif pkg.format == "carousel":
        n = len(pkg.artifacts.slide_paths) or 3
        n = max(3, min(n, 5))
        paths = []
        for i in range(1, n + 1):
            slide = root / f"slide_{i}.png"
            slide.write_bytes(_MIN_PNG)
            paths.append(str(slide))
        pkg.artifacts.slide_paths = paths
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
