"""Single-clip rerender workflow for reviewed caption edits."""

from __future__ import annotations

import json
import threading
import uuid
from argparse import Namespace
from pathlib import Path
from typing import Any, Callable

from .autonomy import complete_autonomy_after_persist, finalize_candidate_autonomy
from .caption_pipeline import build_production_captions
from .captions import captions_out_of_sync, normalize_caption_timeline_for_render
from .costs import estimate_clip_cost
from .db import ARTIFACTS_DIR, DEFAULT_DB, ROOT, connect, fetch_one, initialize, load_json, seed_profile
from .render_quality import build_render_quality_report
from .rendering import PREMIUM_PRESET, render_premium_ffmpeg, render_premium_hyperframes, render_premium_remotion
from .silence_trim import apply_silence_trim_for_render, probe_duration_ms, source_already_silence_trimmed
from .styles import is_template_only_style, load_style_for_render
from .youtube_pipeline import download_youtube_section


def _loads(value: str | None) -> dict[str, Any]:
    try:
        data = json.loads(value or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _latest_render(conn, candidate_id: str) -> dict[str, Any]:
    render_job = fetch_one(
        conn,
        "SELECT * FROM render_jobs WHERE candidate_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
        (candidate_id,),
    )
    if not render_job:
        raise ValueError("clip has no render job to reuse")
    return dict(render_job)


def _find_source_clip(profile_id: str, candidate_id: str, render_metadata: dict[str, Any]) -> str:
    metadata_path = str(render_metadata.get("sourceVideoPath") or "")
    if metadata_path and Path(metadata_path).is_absolute() and Path(metadata_path).exists():
        return metadata_path

    source_dir = ARTIFACTS_DIR / profile_id / candidate_id / "source"
    matches = sorted(source_dir.glob("*.mp4"))
    if matches:
        return str(matches[-1])
    raise ValueError("source clip is missing; regenerate the batch before rerendering")


def _source_url_for_candidate(conn, candidate: dict[str, Any], render_metadata: dict[str, Any]) -> str:
    url = str(render_metadata.get("sourceUrl") or "").strip()
    if url:
        return url
    source = fetch_one(conn, "SELECT source_url FROM source_manifests WHERE id = ?", (candidate["source_id"],))
    url = str((source or {}).get("source_url") or "").strip()
    if not url:
        raise ValueError("source URL is missing; cannot download the edited boundary")
    return url


def _profile_for_candidate(conn, profile_id: str) -> dict[str, Any]:
    profile = fetch_one(conn, "SELECT * FROM media_profiles WHERE id = ?", (profile_id,))
    if not profile:
        seed_profile(conn, load_json(ROOT / "profiles" / "nourbit.json"))
        profile = fetch_one(conn, "SELECT * FROM media_profiles WHERE id = ?", (profile_id,))
    if not profile:
        raise ValueError(f"profile not found: {profile_id}")
    return dict(profile)


def _hydrate_candidate(row: dict[str, Any]) -> dict[str, Any]:
    candidate = dict(row)
    candidate["score"] = _loads(candidate.get("score_json"))
    candidate["curation_metadata"] = _loads(candidate.get("curation_metadata_json"))
    candidate["asr_metadata"] = _loads(candidate.get("asr_metadata_json"))
    candidate["render_quality"] = _loads(candidate.get("render_quality_json"))
    candidate["cost"] = _loads(candidate.get("cost_json"))
    candidate["quality_gate"] = _loads(candidate.get("quality_gate_json"))
    candidate["caption_corrections"] = _loads(candidate.get("caption_corrections_json"))
    return candidate


def _update_candidate_after_rerender(conn, candidate: dict[str, Any]) -> None:
    conn.execute(
        """
        UPDATE clip_candidates
        SET score_json = ?, caption_source = ?, render_quality_json = ?, cost_json = ?,
            quality_gate_json = ?, caption_corrections_json = ?, curation_metadata_json = ?,
            review_deadline_at = ?, status = ?
        WHERE id = ?
        """,
        (
            json.dumps(candidate.get("score", {}), ensure_ascii=False),
            candidate.get("caption_source", "youtube"),
            json.dumps(candidate.get("render_quality", {}), ensure_ascii=False),
            json.dumps(candidate.get("cost", {}), ensure_ascii=False),
            json.dumps(candidate.get("quality_gate", {}), ensure_ascii=False),
            json.dumps(candidate.get("caption_corrections", {}), ensure_ascii=False),
            json.dumps(candidate.get("curation_metadata", {}), ensure_ascii=False),
            candidate.get("review_deadline_at", ""),
            candidate.get("status", "rendered"),
            candidate["id"],
        ),
    )
    conn.commit()


def _regenerate_captions(
    candidate: dict[str, Any],
    source_clip: str,
    style: dict[str, Any],
    model_name: str = "medium",
    youtube_url: str = "",
    niche: str = "",
    llm_provider: str = "none",
) -> None:
    caption_source = str(candidate.get("caption_source") or "hybrid")
    if caption_source not in {"whisper", "hybrid"}:
        caption_source = "hybrid"
    build_production_captions(
        candidate,
        source_clip,
        caption_source=caption_source,
        asr_model=model_name,
        speech_language="auto",
        style=style,
        youtube_url=youtube_url,
        llm_provider=llm_provider,
        niche=niche,
        profile_id=str(candidate.get("profile_id") or ""),
    )
    corrections = candidate.get("caption_corrections") if isinstance(candidate.get("caption_corrections"), dict) else {}
    candidate["caption_corrections"] = {
        **corrections,
        "manual_edit_stale": False,
        "regenerated_after_boundary_edit": True,
    }


def _coerce_genres(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _hyperframes_settings(render_metadata: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    curation = candidate.get("curation_metadata") if isinstance(candidate.get("curation_metadata"), dict) else {}
    genres = _coerce_genres(render_metadata.get("genres") or curation.get("genres") or candidate.get("genres"))
    return {
        "hyperframes_template": str(render_metadata.get("hyperframesTemplate") or "auto"),
        "hyperframes_format": str(render_metadata.get("hyperframesFormat") or "auto"),
        "brand_system_template_id": str(render_metadata.get("brandSystemTemplateId") or ""),
        "genres": genres,
    }


def _resolve_rerender_style(
    style_path: str | None,
    render_metadata: dict[str, Any],
    hf_settings: dict[str, Any],
) -> dict[str, Any]:
    saved_style = render_metadata.get("style")
    if isinstance(saved_style, dict) and saved_style:
        return saved_style
    # Short-form re-render should keep the original HyperFrames recipe, not a random brand JSON path.
    effective_path = "auto"
    if style_path and not is_template_only_style(style_path) and not render_metadata.get("hyperframesTemplate"):
        effective_path = style_path
    return load_style_for_render(
        effective_path,
        hyperframes_template=hf_settings["hyperframes_template"],
        hyperframes_format=hf_settings["hyperframes_format"],
        genres=hf_settings["genres"],
    )


def _prepare_timed_captions_for_render(
    candidate: dict[str, Any],
    source_clip: str,
    *,
    style: dict[str, Any],
    source_url: str,
    profile: dict[str, Any],
    regenerate_captions: bool,
) -> bool:
    """Normalize caption timeline and regenerate when missing or mismatched to source media."""
    clip_start = int(candidate.get("start_ms") or 0)
    try:
        video_ms = probe_duration_ms(source_clip)
    except Exception:
        video_ms = 0

    captions = candidate.get("timed_captions")
    if isinstance(captions, list) and captions:
        candidate["timed_captions"] = normalize_caption_timeline_for_render(
            captions,
            clip_start_ms=clip_start,
            video_duration_ms=video_ms or None,
            already_silence_trimmed=source_already_silence_trimmed(candidate, source_clip),
        )

    needs_regen = regenerate_captions or not candidate.get("timed_captions")
    if not needs_regen and captions_out_of_sync(
        candidate.get("timed_captions") or [],
        video_ms,
        clip_start_ms=clip_start,
    ):
        needs_regen = True

    if not needs_regen:
        return False

    _regenerate_captions(
        candidate,
        source_clip,
        style,
        model_name=str(candidate.get("asr_metadata", {}).get("model") or "medium"),
        youtube_url=source_url,
        niche=str(profile.get("niche") or ""),
        llm_provider=str(candidate.get("cost", {}).get("llm_provider") or "none"),
    )
    candidate["timed_captions"] = normalize_caption_timeline_for_render(
        candidate.get("timed_captions") or [],
        clip_start_ms=clip_start,
        video_duration_ms=video_ms or None,
        already_silence_trimmed=source_already_silence_trimmed(candidate, source_clip),
    )
    return True


def _hydrate_timed_captions(candidate: dict[str, Any], render_metadata: dict[str, Any]) -> bool:
    """Load timed captions from manual edits or the latest render contract."""
    corrections = candidate.get("caption_corrections") if isinstance(candidate.get("caption_corrections"), dict) else {}
    edited = corrections.get("edited_captions")
    edited_is_stale = bool(corrections.get("manual_edit_stale"))
    if isinstance(edited, list) and edited and not edited_is_stale:
        candidate["timed_captions"] = edited
        candidate["caption_source"] = "manual_edit"
        return True

    captions = render_metadata.get("captions")
    if isinstance(captions, list) and captions:
        candidate["timed_captions"] = captions
        return True
    return False


def rerender_candidate(
    candidate_id: str,
    renderer: str = "hyperframes",
    quality: str = "production",
    style_path: str | None = None,
    db_path: str | Path = DEFAULT_DB,
    on_progress: Callable[[int, str], None] | None = None,
    force_source_refresh: bool = False,
    regenerate_captions: bool = False,
) -> dict[str, Any]:
    def report(progress: int, message: str) -> None:
        if on_progress:
            on_progress(progress, message)

    conn = connect(db_path)
    initialize(conn)
    report(8, "Loading clip data")
    row = fetch_one(conn, "SELECT * FROM clip_candidates WHERE id = ?", (candidate_id,))
    if not row:
        raise ValueError("candidate not found")
    candidate = _hydrate_candidate(dict(row))
    report(18, "Loading profile and source clip")
    profile = _profile_for_candidate(conn, candidate["profile_id"])
    render_job = _latest_render(conn, candidate_id)
    render_metadata = _loads(render_job.get("metadata_json"))
    _hydrate_timed_captions(candidate, render_metadata)
    if force_source_refresh:
        source_url = _source_url_for_candidate(conn, candidate, render_metadata)
        report(24, "Downloading source for edited boundary")
        source_clip = download_youtube_section(source_url, candidate["profile_id"], candidate)
    else:
        source_clip = _find_source_clip(candidate["profile_id"], candidate_id, render_metadata)
        source_url = str(render_metadata.get("sourceUrl") or "")

    report(27, "Auto-trimming silence on source clip")
    source_clip = apply_silence_trim_for_render(source_clip, candidate)
    hf_settings = _hyperframes_settings(render_metadata, candidate)
    style = _resolve_rerender_style(style_path, render_metadata, hf_settings)

    report(29, "Preparing caption timeline")
    if _prepare_timed_captions_for_render(
        candidate,
        source_clip,
        style=style,
        source_url=source_url,
        profile=profile,
        regenerate_captions=regenerate_captions or not candidate.get("timed_captions"),
    ):
        report(31, "Regenerated captions from source audio")

    source_attribution = str(render_metadata.get("sourceAttribution") or "Source: Channel clip")
    resolved_renderer = "hyperframes" if quality == "production" and renderer == "ffmpeg" else renderer
    report(34, "Preparing render contract")
    if resolved_renderer == "hyperframes":
        report(52, "Rendering video with HyperFrames")
        output_path, contract = render_premium_hyperframes(
            candidate,
            profile,
            source_clip,
            source_url,
            source_attribution,
            style,
            hyperframes_template=hf_settings["hyperframes_template"],
            hyperframes_format=hf_settings["hyperframes_format"],
            brand_system_template_id=hf_settings["brand_system_template_id"],
            genres=hf_settings["genres"],
        )
    elif resolved_renderer == "remotion":
        report(52, "Rendering video with Remotion")
        output_path, contract = render_premium_remotion(candidate, profile, source_clip, source_url, source_attribution, style)
    else:
        report(52, "Rendering video with FFmpeg")
        output_path, contract = render_premium_ffmpeg(candidate, profile, source_clip, source_url, source_attribution, style)

    job_id = Path(output_path).stem
    report(82, "Running render QA checks")
    render_quality = build_render_quality_report(contract, output_path)
    if isinstance(candidate.get("silence_trim"), dict):
        render_quality["silence_trim"] = candidate["silence_trim"]
    if candidate.get("source_height") is not None:
        render_quality["source_height"] = candidate.get("source_height")
    candidate["render_quality"] = render_quality
    candidate["cost"] = estimate_clip_cost(
        int(candidate["end_ms"]) - int(candidate["start_ms"]),
        llm_provider=str(candidate.get("cost", {}).get("llm_provider") or "none"),
        caption_source=candidate.get("caption_source", "manual_edit"),
        renderer=resolved_renderer,
    )
    candidate["score"] = {**candidate.get("score", {}), "render_quality_score": render_quality["quality_score"]}

    protected_statuses = {"approved", "scheduled", "ready_to_publish", "published"}
    gate: dict[str, Any] = {}
    if candidate.get("status") not in protected_statuses:
        gate = finalize_candidate_autonomy(conn, candidate, str(candidate["profile_id"] or "nourbit"))

    report(92, "Saving render metadata")
    conn.execute(
        """
        INSERT INTO render_jobs
          (id, candidate_id, preset, crop_strategy, caption_style, status, output_path, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            candidate["id"],
            PREMIUM_PRESET,
            contract["cropStrategy"],
            contract["captionStyle"],
            "rendered",
            output_path,
            json.dumps(contract, ensure_ascii=False),
        ),
    )
    _update_candidate_after_rerender(conn, candidate)
    if gate:
        complete_autonomy_after_persist(conn, candidate, str(candidate["profile_id"] or "nourbit"), gate)
        if candidate.get("status") == "scheduled":
            conn.execute(
                "UPDATE clip_candidates SET status = 'scheduled', quality_gate_json = ? WHERE id = ?",
                (json.dumps(candidate.get("quality_gate", {}), ensure_ascii=False), candidate["id"]),
            )
            conn.commit()
    report(100, "Render updated")
    return {
        "candidate_id": candidate["id"],
        "status": candidate.get("status", "rendered"),
        "caption_source": candidate.get("caption_source", "manual_edit"),
        "output_path": output_path,
        "render_quality": render_quality,
        "cost": candidate.get("cost", {}),
    }


def _set_job_state(
    conn,
    job_id: str,
    status: str,
    progress: int,
    message: str,
    result: dict[str, Any] | None = None,
    error: str = "",
) -> None:
    conn.execute(
        """
        UPDATE rerender_jobs
        SET status = ?, progress = ?, message = ?, result_json = ?, error = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            status,
            progress,
            message,
            json.dumps(result or {}, ensure_ascii=False),
            error,
            job_id,
        ),
    )
    conn.commit()


def _run_rerender_job(
    job_id: str,
    candidate_id: str,
    renderer: str,
    quality: str,
    style_path: str | None,
    db_path: str | Path,
    force_source_refresh: bool = False,
    regenerate_captions: bool = False,
) -> None:
    conn = connect(db_path)
    initialize(conn)
    def report(progress: int, message: str) -> None:
        _set_job_state(conn, job_id, "running", progress, message)

    try:
        report(4, "Queued worker started")
        result = rerender_candidate(
            candidate_id=candidate_id,
            renderer=renderer,
            quality=quality,
            style_path=style_path,
            db_path=db_path,
            on_progress=report,
            force_source_refresh=force_source_refresh,
            regenerate_captions=regenerate_captions,
        )
        _set_job_state(conn, job_id, "completed", 100, "Render updated", result=result)
    except Exception as exc:  # pragma: no cover - background guard
        _set_job_state(conn, job_id, "failed", 100, "Re-render failed", error=str(exc))
    finally:
        conn.close()


def _job_payload(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["result"] = _loads(item.get("result_json"))
    return item


def get_rerender_job(job_id: str, db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    conn = connect(db_path)
    initialize(conn)
    row = fetch_one(conn, "SELECT * FROM rerender_jobs WHERE id = ?", (job_id,))
    conn.close()
    if not row:
        raise ValueError("rerender job not found")
    return _job_payload(dict(row))


def list_rerender_jobs(
    limit: int = 40,
    candidate_id: str | None = None,
    db_path: str | Path = DEFAULT_DB,
) -> list[dict[str, Any]]:
    conn = connect(db_path)
    initialize(conn)
    if candidate_id:
        rows = conn.execute(
            "SELECT * FROM rerender_jobs WHERE candidate_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
            (candidate_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM rerender_jobs ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [_job_payload(dict(row)) for row in rows]


def attach_active_rerender_jobs(conn, rows: list[dict[str, Any]]) -> None:
    """Attach in-flight rerender job metadata to review rows."""
    if not rows:
        return
    candidate_ids = [str(row["id"]) for row in rows if row.get("id")]
    if not candidate_ids:
        return
    placeholders = ",".join("?" for _ in candidate_ids)
    active_rows = conn.execute(
        f"""
        SELECT id, candidate_id, status, progress, message, error
        FROM rerender_jobs
        WHERE candidate_id IN ({placeholders})
          AND status IN ('queued', 'running')
        ORDER BY created_at DESC, id DESC
        """,
        candidate_ids,
    ).fetchall()
    jobs_by_candidate: dict[str, dict[str, Any]] = {}
    for row in active_rows:
        candidate_id = str(row["candidate_id"])
        if candidate_id in jobs_by_candidate:
            continue
        jobs_by_candidate[candidate_id] = {
            "id": str(row["id"]),
            "status": str(row["status"] or ""),
            "progress": int(row["progress"] or 0),
            "message": str(row["message"] or ""),
            "error": str(row["error"] or ""),
        }
    for row in rows:
        row["rerender_job"] = jobs_by_candidate.get(str(row["id"]))


def create_rerender_job(
    candidate_id: str,
    renderer: str = "hyperframes",
    quality: str = "production",
    style_path: str | None = None,
    force_source_refresh: bool = False,
    regenerate_captions: bool = False,
    start: bool = True,
    db_path: str | Path = DEFAULT_DB,
) -> dict[str, Any]:
    conn = connect(db_path)
    initialize(conn)
    exists = conn.execute("SELECT 1 FROM clip_candidates WHERE id = ?", (candidate_id,)).fetchone()
    if not exists:
        conn.close()
        raise ValueError("candidate not found")

    running = conn.execute(
        "SELECT id FROM rerender_jobs WHERE candidate_id = ? AND status IN ('queued', 'running') ORDER BY created_at DESC LIMIT 1",
        (candidate_id,),
    ).fetchone()
    if running:
        existing = fetch_one(conn, "SELECT * FROM rerender_jobs WHERE id = ?", (running["id"],))
        conn.close()
        return _job_payload(dict(existing))

    job_id = f"rerender_{uuid.uuid4().hex[:12]}"
    conn.execute(
        """
        INSERT INTO rerender_jobs
          (id, candidate_id, renderer, quality, style_path, force_source_refresh, regenerate_captions,
           status, progress, message, result_json, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', 0, 'Queued', '{}', '')
        """,
        (job_id, candidate_id, renderer, quality, style_path or "", int(force_source_refresh), int(regenerate_captions)),
    )
    conn.commit()
    conn.close()
    if start:
        thread = threading.Thread(
            target=_run_rerender_job,
            args=(job_id, candidate_id, renderer, quality, style_path, db_path, force_source_refresh, regenerate_captions),
            daemon=True,
        )
        thread.start()
    return get_rerender_job(job_id, db_path=db_path)


def _candidate_can_rerender(conn, candidate_id: str) -> tuple[bool, str]:
    row = fetch_one(conn, "SELECT * FROM clip_candidates WHERE id = ?", (candidate_id,))
    if not row:
        return False, "candidate not found"
    if str(row.get("status") or "") == "published":
        return False, "published clip is locked"
    metadata = _loads(row.get("curation_metadata_json"))
    kind = str(metadata.get("kind") or "")
    if kind == "explainer":
        return False, "explainer clips use scene editor render"
    if kind == "longform_ingest" or str(row.get("caption_source") or "") == "ingest_longform":
        return False, "long-form ingest cannot re-render from review"
    render_job = conn.execute(
        "SELECT id FROM render_jobs WHERE candidate_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
        (candidate_id,),
    ).fetchone()
    if not render_job:
        return False, "clip has no render job to reuse"
    return True, ""


def create_batch_rerender_jobs(
    candidate_ids: list[str],
    *,
    renderer: str = "hyperframes",
    quality: str = "production",
    style_path: str | None = None,
    force_source_refresh: bool = False,
    regenerate_captions: bool = False,
    db_path: str | Path = DEFAULT_DB,
) -> dict[str, Any]:
    conn = connect(db_path)
    initialize(conn)
    queued: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    for candidate_id in candidate_ids:
        candidate_id = str(candidate_id).strip()
        if not candidate_id:
            continue
        can_rerender, reason = _candidate_can_rerender(conn, candidate_id)
        if not can_rerender:
            skipped.append({"id": candidate_id, "error": reason})
            continue
        try:
            job = create_rerender_job(
                candidate_id,
                renderer=renderer,
                quality=quality,
                style_path=style_path,
                force_source_refresh=force_source_refresh,
                regenerate_captions=regenerate_captions,
                db_path=db_path,
            )
            queued.append(
                {
                    "candidate_id": candidate_id,
                    "job_id": job["id"],
                    "status": str(job.get("status") or ""),
                }
            )
        except Exception as exc:  # noqa: BLE001 - batch should continue on single failures
            failed.append({"id": candidate_id, "error": str(exc)})
    conn.close()
    return {"queued": queued, "skipped": skipped, "failed": failed}


def rerender_from_args(args: Namespace) -> dict[str, Any]:
    return rerender_candidate(
        args.candidate_id,
        renderer=args.renderer,
        quality=args.quality,
        style_path=args.style,
        db_path=args.db,
        force_source_refresh=getattr(args, "force_source_refresh", False),
        regenerate_captions=getattr(args, "regenerate_captions", False),
    )
