"""Sync short/long content packages when explainer jobs finish rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .content_package import ContentPackage, apply_qa_status
from .content_package_store import ensure_content_packages_table, get_package, save_package
from .db import connect, fetch_all, initialize
from .explainer_pipeline import read_explainer_status
from .explainer_stitch import explainer_artifact_dir

_EXPLAINER_QA_PREFIX = "explainer:"


def _write_explainer_status(profile_id: str, job_id: str, status: dict[str, Any]) -> None:
    root = explainer_artifact_dir(profile_id, job_id)
    (root / "status.json").write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")


def link_explainer_job_to_content_package(
    job_id: str,
    *,
    profile_id: str,
    package_id: str,
) -> None:
    if not job_id or not package_id:
        return
    try:
        status = read_explainer_status(job_id, profile_id=profile_id)
    except FileNotFoundError:
        return
    status["content_package_id"] = package_id
    _write_explainer_status(profile_id, job_id, status)


def find_packages_by_explainer_job(
    job_id: str,
    *,
    db_path: str | Path,
    profile_id: str | None = None,
) -> list[ContentPackage]:
    conn = connect(db_path)
    initialize(conn)
    ensure_content_packages_table(conn)
    rows = fetch_all(conn, "SELECT * FROM content_packages ORDER BY created_at DESC", ())
    out: list[ContentPackage] = []
    for row in rows:
        pkg = ContentPackage.from_row(dict(row))
        if profile_id and pkg.profile_id != profile_id:
            continue
        if str(pkg.artifacts.package_meta.get("explainer_job_id") or "") == job_id:
            out.append(pkg)
    return out


def _package_ids_for_job(
    job_id: str,
    *,
    profile_id: str,
    db_path: str | Path,
) -> list[str]:
    ids: list[str] = []
    try:
        status = read_explainer_status(job_id, profile_id=profile_id)
        cpid = status.get("content_package_id")
        if cpid:
            ids.append(str(cpid))
    except FileNotFoundError:
        pass
    for pkg in find_packages_by_explainer_job(job_id, db_path=db_path, profile_id=profile_id):
        if pkg.id not in ids:
            ids.append(pkg.id)
    return ids


def _video_ready(path: str | Path | None) -> bool:
    if not path:
        return False
    p = Path(path)
    return p.is_file() and p.stat().st_size > 0


def _strip_explainer_qa_errors(pkg: ContentPackage) -> None:
    pkg.qa.errors = [e for e in pkg.qa.errors if not str(e).startswith(_EXPLAINER_QA_PREFIX)]


def apply_explainer_output_to_package(
    pkg: ContentPackage,
    *,
    output_path: str | Path,
    explainer_status: str,
    duration_seconds: float | None = None,
) -> ContentPackage:
    meta = dict(pkg.artifacts.package_meta)
    meta["explainer_status"] = explainer_status
    if duration_seconds is not None:
        meta["explainer_duration_seconds"] = duration_seconds
    meta.pop("explainer_error", None)
    pkg.artifacts.video_path = str(output_path)
    pkg.artifacts.package_meta = meta
    _strip_explainer_qa_errors(pkg)
    return apply_qa_status(pkg)


def notify_explainer_render_complete(
    *,
    job_id: str,
    profile_id: str,
    output_path: str | Path,
    duration_seconds: float | None = None,
    db_path: str | Path,
) -> list[str]:
    if not _video_ready(output_path):
        return []
    updated: list[str] = []
    for package_id in _package_ids_for_job(job_id, profile_id=profile_id, db_path=db_path):
        pkg = get_package(package_id, db_path=db_path)
        if not pkg or pkg.format not in ("short", "long_form"):
            continue
        pkg = apply_explainer_output_to_package(
            pkg,
            output_path=output_path,
            explainer_status="rendered",
            duration_seconds=duration_seconds,
        )
        save_package(pkg, db_path=db_path)
        updated.append(package_id)
    return updated


def notify_explainer_render_failed(
    *,
    job_id: str,
    profile_id: str,
    error: str,
    db_path: str | Path,
) -> list[str]:
    updated: list[str] = []
    message = (error or "render failed").strip()
    for package_id in _package_ids_for_job(job_id, profile_id=profile_id, db_path=db_path):
        pkg = get_package(package_id, db_path=db_path)
        if not pkg or pkg.format not in ("short", "long_form"):
            continue
        meta = dict(pkg.artifacts.package_meta)
        meta["explainer_status"] = "failed"
        if message:
            meta["explainer_error"] = message
        pkg.artifacts.package_meta = meta
        _strip_explainer_qa_errors(pkg)
        if message:
            pkg.qa.errors.append(f"{_EXPLAINER_QA_PREFIX} {message}")
        pkg = apply_qa_status(pkg)
        save_package(pkg, db_path=db_path)
        updated.append(package_id)
    return updated


def refresh_package_explainer_artifacts(pkg: ContentPackage, *, db_path: str | Path) -> ContentPackage:
    """Poll explainer status.json and persist video_path when render completes."""
    job_id = str(pkg.artifacts.package_meta.get("explainer_job_id") or "")
    if not job_id or pkg.format not in ("short", "long_form"):
        return pkg
    try:
        status = read_explainer_status(job_id, profile_id=pkg.profile_id)
    except FileNotFoundError:
        return pkg

    st = str(status.get("status") or "")
    meta = dict(pkg.artifacts.package_meta)
    prev_status = str(meta.get("explainer_status") or "")
    changed = False

    if st == "rendered":
        output = status.get("output_path")
        if _video_ready(output):
            if pkg.artifacts.video_path != str(output):
                pkg = apply_explainer_output_to_package(
                    pkg,
                    output_path=output,
                    explainer_status="rendered",
                    duration_seconds=status.get("duration_seconds"),
                )
                changed = True
        elif prev_status != "rendered":
            meta["explainer_status"] = "rendered"
            meta["explainer_duration_seconds"] = status.get("duration_seconds")
            pkg.artifacts.package_meta = meta
            changed = True
    elif st == "failed":
        err = str(status.get("error") or "render failed")
        meta["explainer_status"] = "failed"
        meta["explainer_error"] = err
        pkg.artifacts.package_meta = meta
        _strip_explainer_qa_errors(pkg)
        pkg.qa.errors.append(f"{_EXPLAINER_QA_PREFIX} {err}")
        pkg = apply_qa_status(pkg)
        changed = True
    elif st and st != prev_status:
        meta["explainer_status"] = st
        pkg.artifacts.package_meta = meta
        changed = True

    if changed:
        save_package(pkg, db_path=db_path)
    return pkg
