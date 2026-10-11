"""Orchestrate Explainer Mode Phase 0: plan → stitch → register review candidate."""

from __future__ import annotations

import json
import os
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
from .explainer_planner import load_plan_file, normalize_plan, plan_explainer
from .explainer_stitch import (
    build_scene_segments,
    explainer_artifact_dir,
    extract_audio_track,
    probe_duration_seconds,
    stitch_segments,
    write_stitch_manifest,
)
from .autonomy import reconcile_caption_holds
from .heygen_client import HeyGenApiError, HeyGenConfig, generate_avatar_clips_for_scenes
from .hyperframes_templates import normalize_hyperframes_template


def _job_id() -> str:
    return f"expl_{uuid.uuid4().hex[:12]}"


def _candidate_id(job_id: str) -> str:
    return f"cand_{job_id}"


def _safe_path_component(value: Any, label: str) -> str:
    component = str(value or "").strip()
    if not component or component in {".", ".."} or Path(component).name != component:
        raise ValueError(f"invalid {label}")
    return component


def _safe_fixture_reference(value: Any, label: str) -> str:
    reference = str(value or "").strip()
    path = Path(reference)
    if not reference or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"invalid {label}")
    return reference


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _normalized_plan_with_render_fields(raw: dict[str, Any]) -> dict[str, Any]:
    plan = normalize_plan(raw)
    raw_scenes = raw.get("scenes")
    if not isinstance(raw_scenes, list):
        return plan
    for scene, source in zip(plan["scenes"], raw_scenes):
        if not isinstance(source, dict):
            continue
        for field in ("clip_file", "audio_file"):
            if source.get(field):
                scene[field] = _safe_fixture_reference(source[field], f"scene.{field}")
        if source.get("template") and scene["type"] in {"text", "broll"}:
            scene["template"] = normalize_hyperframes_template(source["template"])
    return plan


def resolve_explainer_review_candidate(
    candidate_id: str,
    *,
    db_path: str | Path = DEFAULT_DB,
) -> dict[str, Any]:
    """Resolve an Explainer job using only trusted candidate metadata."""
    candidate_id = str(candidate_id or "").strip()
    if not candidate_id:
        raise ValueError("candidate_id is required")
    conn = connect(db_path)
    initialize(conn)
    row = conn.execute(
        """
        SELECT id, profile_id, status, curation_metadata_json
        FROM clip_candidates
        WHERE id = ?
        """,
        (candidate_id,),
    ).fetchone()
    if not row:
        raise FileNotFoundError("candidate not found")
    candidate = dict(row)
    try:
        metadata = json.loads(candidate.get("curation_metadata_json") or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("candidate curation metadata is invalid") from exc
    if not isinstance(metadata, dict) or metadata.get("kind") != "explainer":
        raise ValueError("candidate is not an explainer")

    profile_id = _safe_path_component(candidate["profile_id"], "profile_id")
    job_id = _safe_path_component(metadata.get("job_id"), "explainer job_id")
    artifacts_root = ARTIFACTS_DIR.resolve()
    job_root = (artifacts_root / profile_id / "explainers" / job_id).resolve()
    if artifacts_root not in job_root.parents:
        raise ValueError("invalid explainer artifact path")
    scenes_path = job_root / "scenes.json"
    status_path = job_root / "status.json"
    if not scenes_path.is_file() or not status_path.is_file():
        raise FileNotFoundError(f"explainer job not found: {job_id}")
    scenes_path = scenes_path.resolve()
    status_path = status_path.resolve()
    if scenes_path.parent != job_root or status_path.parent != job_root:
        raise ValueError("invalid explainer artifact path")

    raw_plan = _read_json_object(scenes_path, "scenes.json")
    plan = _normalized_plan_with_render_fields(raw_plan)
    template = normalize_hyperframes_template(
        raw_plan.get("hyperframes_template") or _read_json_object(status_path, "status.json").get("hyperframes_template")
    )
    plan["hyperframes_template"] = template
    return {
        "candidate_id": candidate_id,
        "profile_id": profile_id,
        "job_id": job_id,
        "candidate_status": candidate["status"],
        "root": job_root,
        "plan_path": scenes_path,
        "status_path": status_path,
        "plan": plan,
    }


def save_explainer_scene_plan(
    candidate_id: str,
    *,
    title: Any,
    scenes: Any,
    rerender_after: bool = False,
    prefer_hyperframes: bool = False,
    db_path: str | Path = DEFAULT_DB,
) -> dict[str, Any]:
    """Validate and atomically persist an editor plan for a review candidate."""
    resolved = resolve_explainer_review_candidate(candidate_id, db_path=db_path)
    if resolved["candidate_status"] == "published":
        raise ValueError("published explainer plan is locked")
    if not isinstance(scenes, list):
        raise ValueError("scenes must be a list")

    existing = resolved["plan"]
    incoming = {"title": title, "scenes": scenes}
    plan = _normalized_plan_with_render_fields(incoming)
    ids = [scene["id"] for scene in plan["scenes"]]
    if len(ids) != len(set(ids)):
        raise ValueError("scene ids must be unique")

    existing_by_id = {scene["id"]: scene for scene in existing["scenes"]}
    for scene, source in zip(plan["scenes"], scenes):
        previous = existing_by_id.get(scene["id"])
        if not previous or not isinstance(source, dict):
            continue
        for field in ("clip_file", "audio_file", "template"):
            if field not in source and previous.get(field):
                scene[field] = previous[field]

    template = normalize_hyperframes_template(existing.get("hyperframes_template"))
    if template == "auto":
        template = "techtalk_intel_brief"
    for scene in plan["scenes"]:
        if scene["type"] in {"text", "broll"} and not scene.get("template"):
            scene["template"] = template
    plan["hyperframes_template"] = template

    plan_path = resolved["plan_path"]
    temp_path = plan_path.with_name(f".{plan_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temp_path, plan_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    status = _read_json_object(resolved["status_path"], "status.json")
    status.update(
        {
            "status": "planned",
            "error": "",
            "scene_count": len(plan["scenes"]),
            "avatar_scene_count": sum(scene["type"] == "avatar" for scene in plan["scenes"]),
            "hyperframes_template": template,
        }
    )
    _write_status(resolved["root"], status)
    if rerender_after:
        status = start_explainer_run(
            job_id=resolved["job_id"],
            profile_id=resolved["profile_id"],
            prefer_hyperframes=prefer_hyperframes,
            db_path=db_path,
        )
    return {
        "candidate_id": candidate_id,
        "profile_id": resolved["profile_id"],
        "job_id": resolved["job_id"],
        "plan": plan,
        "status": status,
        "rerender_started": rerender_after,
    }


def _avatar_fixture_missing(scene: dict[str, Any], fixtures: Path) -> bool:
    from .explainer_stitch import resolve_avatar_source

    try:
        resolve_avatar_source(scene, fixtures)
        return False
    except FileNotFoundError:
        return True


def ensure_avatar_clips_via_heygen(
    plan: dict[str, Any],
    fixtures: Path,
    *,
    generate: bool = False,
    config: HeyGenConfig | None = None,
) -> dict[str, Any] | None:
    """
    Fill missing avatar fixtures via HeyGen Direct API (issue #7).

    When ``generate`` is False, returns None (fixture-only / Path A import path).
    When True, batch-creates short clips for avatar scenes that lack files.
    """
    if not generate:
        return None
    scenes = [s for s in (plan.get("scenes") or []) if isinstance(s, dict)]
    missing = [s for s in scenes if str(s.get("type") or "").lower() == "avatar" and _avatar_fixture_missing(s, fixtures)]
    if not missing:
        return {"ok": True, "skipped": True, "reason": "all avatar fixtures present", "clips": []}
    try:
        return generate_avatar_clips_for_scenes(missing, fixtures, config=config, skip_existing=True)
    except HeyGenApiError:
        raise


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


def import_narration_audio(
    *,
    job_id: str,
    dest_name: str,
    source: str,
    profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID,
) -> Path:
    """
    Import VO for text/broll scenes into fixtures/.

    Accepts a local/HTTPS audio file, or a HeyGen avatar MP4 (Creator-plan path):
    video sources are extracted to AAC (.m4a). Prefer dest like `scene_02.m4a`.
    """
    dest_name = Path(dest_name).name
    suffix = Path(dest_name).suffix.lower()
    if suffix not in {".m4a", ".mp3", ".wav", ".aac"}:
        dest_name = f"{Path(dest_name).stem}.m4a"

    fixtures = explainer_artifact_dir(profile_id, job_id) / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    dest = fixtures / dest_name
    source = (source or "").strip()
    if not source:
        raise ValueError("source path or URL is required")

    parsed = urlparse(source)
    tmp_dir = fixtures / "_vo_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    if parsed.scheme in {"http", "https"}:
        download_name = Path(parsed.path).name or "vo_source.bin"
        downloaded = tmp_dir / download_name
        urlretrieve(source, downloaded)  # noqa: S310 — operator-controlled CDN URLs
        src_path = downloaded
    else:
        src_path = Path(source).expanduser().resolve()
        if not src_path.exists():
            raise FileNotFoundError(f"narration source not found: {src_path}")

    if src_path.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"}:
        extract_audio_track(src_path, dest)
    else:
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
    imports.append({"dest": dest_name, "source": source, "kind": "narration_audio"})
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
    prefer_hyperframes: bool = False,
    register_review: bool = True,
    generate_heygen_avatars: bool = False,
    db_path: str | Path = DEFAULT_DB,
) -> dict[str, Any]:
    """
    Run Phase 0 pipeline.

    Provide either:
    - existing job_id (uses its scenes.json + fixtures/), or
    - topic / scenes_path + clips_dir

    Default stitch uses FFmpeg TechTalk v2 cards (non-avatar happy path).
    Set prefer_hyperframes=True only when HyperFrames runtime is known-good.
    Set generate_heygen_avatars=True to fill missing avatar fixtures via Direct API (#7).
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
        heygen_batch = ensure_avatar_clips_via_heygen(
            plan,
            fixtures,
            generate=generate_heygen_avatars,
        )
        if heygen_batch is not None:
            status["heygen_avatars"] = {
                "dry_run": heygen_batch.get("dry_run"),
                "estimated_seconds": heygen_batch.get("estimated_seconds"),
                "estimated_usd": heygen_batch.get("estimated_usd"),
                "clip_count": len(heygen_batch.get("clips") or []),
            }
            _write_status(root, status)
            if heygen_batch.get("dry_run") and not heygen_batch.get("skipped"):
                raise HeyGenApiError(
                    "HEYGEN_API_DRY_RUN=1 — avatar clips were not downloaded. "
                    "Unset dry-run and ensure HEYGEN_API_KEY + API wallet top-up for a real run."
                )
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
        from .content_package_explainer import notify_explainer_render_complete

        notify_explainer_render_complete(
            job_id=job_id,
            profile_id=profile_id,
            output_path=output_path,
            duration_seconds=duration,
            db_path=db_path,
        )
        return status
    except Exception as exc:
        status["status"] = "failed"
        status["error"] = str(exc)
        _write_status(root, status)
        from .content_package_explainer import notify_explainer_render_failed

        notify_explainer_render_failed(
            job_id=job_id,
            profile_id=profile_id,
            error=str(exc),
            db_path=db_path,
        )
        raise


def list_review_queue(*, db_path: str | Path = DEFAULT_DB, limit: int = 50) -> list[dict[str, Any]]:
    conn = connect(db_path)
    initialize(conn)
    reconcile_caption_holds(conn)
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
