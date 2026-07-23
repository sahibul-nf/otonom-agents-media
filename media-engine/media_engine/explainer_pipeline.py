"""Orchestrate Explainer Mode Phase 0: plan → stitch → register review candidate."""

from __future__ import annotations

import json
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlretrieve

from .db import (
    ARTIFACTS_DIR,
    DEFAULT_DB,
    DEFAULT_WORKSPACE_PROFILE_ID,
    connect,
    ensure_media_profile,
    ensure_source_manifest,
    initialize,
)
from .explainer_planner import load_plan_file, plan_explainer
from .explainer_stitch import (
    build_scene_segments,
    explainer_artifact_dir,
    probe_duration_seconds,
    stitch_segments,
    write_stitch_manifest,
)
from .hyperframes_templates import normalize_hyperframes_template


def _job_id() -> str:
    return f"expl_{uuid.uuid4().hex[:12]}"


def _candidate_id(job_id: str) -> str:
    return f"cand_{job_id}"


def import_avatar_clip(
    *,
    job_id: str,
    dest_name: str,
    source: str,
    profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID,
) -> Path:
    """Copy a local path or download a URL into the job fixtures folder."""
    dest_name = Path(dest_name).name
    if not dest_name.lower().endswith((".mp4", ".mov", ".webm", ".mkv")):
        dest_name = f"{dest_name}.mp4"
    fixtures = explainer_artifact_dir(profile_id, job_id) / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    dest = fixtures / dest_name
    source = (source or "").strip()
    if not source:
        raise ValueError("source path or URL is required")

    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        urlretrieve(source, dest)  # noqa: S310 — operator-controlled HeyGen CDN URLs
    else:
        src_path = Path(source).expanduser().resolve()
        if not src_path.exists():
            raise FileNotFoundError(f"clip not found: {src_path}")
        shutil.copy2(src_path, dest)

    manifest_path = fixtures / "imports.json"
    imports: list[dict[str, Any]] = []
    if manifest_path.exists():
        try:
            imports = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(imports, list):
                imports = []
        except json.JSONDecodeError:
            imports = []
    imports.append({"dest": dest_name, "source": source})
    manifest_path.write_text(json.dumps(imports, indent=2, ensure_ascii=False), encoding="utf-8")
    return dest


def _apply_template_to_plan(plan: dict[str, Any], template: str) -> dict[str, Any]:
    template_id = normalize_hyperframes_template(template or "techtalk_explainer")
    if template_id == "auto":
        template_id = "techtalk_intel_brief"
    for scene in plan.get("scenes") or []:
        if not isinstance(scene, dict):
            continue
        if str(scene.get("type") or "") in {"text", "broll"}:
            scene["template"] = template_id
    plan["hyperframes_template"] = template_id
    return plan


def create_explainer_job(
    *,
    topic: str,
    sources: list[str] | None = None,
    profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID,
    llm_provider: str = "none",
    language: str = "id",
    scenes_path: str | None = None,
    hyperframes_template: str = "techtalk_explainer",
    db_path: str | Path = DEFAULT_DB,
) -> dict[str, Any]:
    """Create job folder + scene plan (does not stitch yet)."""
    job_id = _job_id()
    root = explainer_artifact_dir(profile_id, job_id)
    fixtures = root / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)

    if scenes_path:
        plan = load_plan_file(scenes_path)
    else:
        plan = plan_explainer(topic, sources=sources, llm_provider=llm_provider, language=language)
    plan = _apply_template_to_plan(plan, hyperframes_template)

    plan_path = root / "scenes.json"
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

    status = {
        "job_id": job_id,
        "profile_id": profile_id,
        "topic": topic,
        "status": "planned",
        "plan_path": str(plan_path),
        "fixtures_dir": str(fixtures),
        "hyperframes_template": plan.get("hyperframes_template") or "techtalk_intel_brief",
        "candidate_id": None,
        "output_path": None,
        "error": "",
        "scene_count": len(plan.get("scenes") or []),
        "avatar_scene_count": sum(1 for s in (plan.get("scenes") or []) if isinstance(s, dict) and s.get("type") == "avatar"),
    }
    (root / "status.json").write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")

    # Ensure DB profile exists early so dashboard/MCP can reference workspace.
    conn = connect(db_path)
    initialize(conn)
    ensure_media_profile(conn, profile_id)
    return status


def read_explainer_status(job_id: str, *, profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID) -> dict[str, Any]:
    root = ARTIFACTS_DIR / profile_id / "explainers" / job_id
    status_path = root / "status.json"
    if not status_path.exists():
        raise FileNotFoundError(f"explainer job not found: {job_id}")
    return json.loads(status_path.read_text(encoding="utf-8"))


def list_explainer_jobs(*, profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID, limit: int = 20) -> list[dict[str, Any]]:
    root = ARTIFACTS_DIR / profile_id / "explainers"
    if not root.exists():
        return []
    jobs: list[dict[str, Any]] = []
    for path in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        status_file = path / "status.json"
        if not status_file.exists():
            continue
        try:
            jobs.append(json.loads(status_file.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
        if len(jobs) >= limit:
            break
    return jobs


def _write_status(root: Path, status: dict[str, Any]) -> None:
    (root / "status.json").write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")


def register_explainer_in_review(
    conn,
    *,
    job_id: str,
    profile_id: str,
    plan: dict[str, Any],
    output_path: Path,
    duration_seconds: float,
) -> str:
    candidate_id = _candidate_id(job_id)
    source_id = f"explainer_{job_id}"
    ensure_media_profile(conn, profile_id)
    ensure_source_manifest(
        conn,
        profile_id=profile_id,
        source_id=source_id,
        source_url=f"explainer://local/{job_id}",
    )
    end_ms = max(1000, int(duration_seconds * 1000))
    title = str(plan.get("title") or "Explainer")
    transcript = " | ".join(
        str(s.get("script") or s.get("headline") or s.get("narration") or "") for s in plan.get("scenes", [])
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO clip_candidates
          (id, profile_id, source_id, start_ms, end_ms, title_hook, hook_subtitle, viral_reason,
           transcript_span, risk_flags_json, score_json, curation_metadata_json,
           caption_source, asr_metadata_json, render_quality_json, cost_json,
           quality_gate_json, caption_corrections_json, dedupe_key, review_deadline_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id,
            profile_id,
            source_id,
            0,
            end_ms,
            title,
            "Explainer Mode hybrid long-form",
            "operator explainer pipeline",
            transcript[:4000],
            "[]",
            json.dumps({"explainer": True}, ensure_ascii=False),
            json.dumps({"kind": "explainer", "job_id": job_id}, ensure_ascii=False),
            "explainer",
            "{}",
            json.dumps({"output_path": str(output_path), "renderer": "explainer_stitch"}, ensure_ascii=False),
            "{}",
            "{}",
            "{}",
            f"explainer:{job_id}",
            "",
            "rendered",
        ),
    )
    render_id = f"render_{job_id}"
    conn.execute(
        """
        INSERT OR REPLACE INTO render_jobs
          (id, candidate_id, preset, crop_strategy, caption_style, status, output_path, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            render_id,
            candidate_id,
            "explainer_long_16_9",
            "none",
            "explainer",
            "rendered",
            str(output_path),
            json.dumps({"kind": "explainer", "job_id": job_id, "title": title}, ensure_ascii=False),
        ),
    )
    conn.commit()
    return candidate_id


def run_explainer(
    *,
    topic: str = "",
    scenes_path: str | None = None,
    clips_dir: str | Path | None = None,
    job_id: str | None = None,
    profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID,
    llm_provider: str = "none",
    language: str = "id",
    sources: list[str] | None = None,
    prefer_hyperframes: bool = True,
    register_review: bool = True,
    db_path: str | Path = DEFAULT_DB,
) -> dict[str, Any]:
    """
    Run Phase 0 pipeline.

    Provide either:
    - existing job_id (uses its scenes.json + fixtures/), or
    - topic / scenes_path + clips_dir
    """
    conn = connect(db_path)
    initialize(conn)
    ensure_media_profile(conn, profile_id)

    if job_id:
        root = explainer_artifact_dir(profile_id, job_id)
        plan_path = root / "scenes.json"
        if not plan_path.exists():
            raise FileNotFoundError(f"scenes.json missing for job {job_id}")
        plan = load_plan_file(str(plan_path))
        fixtures = Path(clips_dir) if clips_dir else (root / "fixtures")
        status = read_explainer_status(job_id, profile_id=profile_id)
    else:
        created = create_explainer_job(
            topic=topic or "Explainer",
            sources=sources,
            profile_id=profile_id,
            llm_provider=llm_provider,
            language=language,
            scenes_path=scenes_path,
            db_path=db_path,
        )
        job_id = created["job_id"]
        root = explainer_artifact_dir(profile_id, job_id)
        plan = load_plan_file(str(root / "scenes.json"))
        fixtures = Path(clips_dir) if clips_dir else (root / "fixtures")
        if clips_dir and Path(clips_dir).resolve() != fixtures.resolve():
            fixtures.mkdir(parents=True, exist_ok=True)
            for media in Path(clips_dir).glob("*"):
                if media.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"}:
                    shutil.copy2(media, fixtures / media.name)
        status = created

    status["status"] = "rendering"
    _write_status(root, status)

    try:
        work_dir = root / "segments"
        candidate_id = _candidate_id(job_id)
        segments = build_scene_segments(
            plan,
            fixtures,
            work_dir,
            profile_id=profile_id,
            candidate_id=candidate_id,
            prefer_hyperframes=prefer_hyperframes,
        )
        output_path = root / "final.mp4"
        stitch_segments(segments, output_path)
        duration = probe_duration_seconds(output_path)
        write_stitch_manifest(
            root / "manifest.json",
            {
                "job_id": job_id,
                "title": plan.get("title"),
                "segments": [str(p) for p in segments],
                "output_path": str(output_path),
                "duration_seconds": duration,
            },
        )

        registered_id = None
        if register_review:
            registered_id = register_explainer_in_review(
                conn,
                job_id=job_id,
                profile_id=profile_id,
                plan=plan,
                output_path=output_path,
                duration_seconds=duration,
            )

        status.update(
            {
                "status": "rendered",
                "candidate_id": registered_id,
                "output_path": str(output_path),
                "duration_seconds": duration,
                "error": "",
            }
        )
        _write_status(root, status)
        return status
    except Exception as exc:
        status["status"] = "failed"
        status["error"] = str(exc)
        _write_status(root, status)
        raise


def list_review_queue(*, db_path: str | Path = DEFAULT_DB, limit: int = 50) -> list[dict[str, Any]]:
    conn = connect(db_path)
    initialize(conn)
    rows = conn.execute(
        """
        SELECT c.id, c.profile_id, c.title_hook, c.status, c.created_at,
               r.output_path, c.curation_metadata_json
        FROM clip_candidates c
        LEFT JOIN render_jobs r ON r.candidate_id = c.id
        WHERE c.status != 'archived'
        ORDER BY c.created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            meta = json.loads(item.get("curation_metadata_json") or "{}")
        except json.JSONDecodeError:
            meta = {}
        item["curation_metadata"] = meta
        items.append(item)
    return items


def start_explainer_run(
    *,
    job_id: str,
    profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID,
    prefer_hyperframes: bool = False,
    db_path: str | Path = DEFAULT_DB,
) -> dict[str, Any]:
    """Queue an async stitch for an existing Explainer job. Returns current status."""
    status = read_explainer_status(job_id, profile_id=profile_id)
    if status.get("status") == "rendering":
        return status

    root = explainer_artifact_dir(profile_id, job_id)
    status["status"] = "rendering"
    status["error"] = ""
    _write_status(root, status)

    def _worker() -> None:
        try:
            run_explainer(
                job_id=job_id,
                profile_id=profile_id,
                prefer_hyperframes=prefer_hyperframes,
                db_path=db_path,
            )
        except Exception:
            # run_explainer already persists failed status
            return

    threading.Thread(target=_worker, daemon=True, name=f"explainer-run-{job_id}").start()
    return status
