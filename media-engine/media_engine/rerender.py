"""Single-clip rerender workflow for reviewed caption edits."""

from __future__ import annotations

import json
import threading
import uuid
from argparse import Namespace
from pathlib import Path
from typing import Any, Callable

from .autonomy import evaluate_quality_gate, get_autonomy_settings
from .asr import load_or_create_asr_words
from .caption_composer import compose_caption_groups
from .costs import estimate_clip_cost
from .db import ARTIFACTS_DIR, DEFAULT_DB, ROOT, connect, fetch_one, initialize, load_json, seed_profile
from .render_quality import build_render_quality_report
from .rendering import PREMIUM_PRESET, render_premium_ffmpeg, render_premium_hyperframes, render_premium_remotion
from .silence_trim import apply_silence_trim_for_render, remap_caption_groups
from .styles import load_style
from .transcript_quality import correct_asr_words
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


def _regenerate_captions(candidate: dict[str, Any], source_clip: str, style: dict[str, Any], model_name: str = "medium") -> None:
    asr_path = Path(source_clip).resolve().parents[1] / f"{Path(source_clip).stem}_{model_name}_asr.json"
    prompt = "Allah, Rasulullah, dzikir, zikir, qalbu, sholawat, istighfar, ma'rifat, taubat, syukur"
    words, asr_metadata = load_or_create_asr_words(
        source_clip,
        str(asr_path),
        model_name=model_name,
        language="id",
        initial_prompt=prompt,
    )
    words, correction_metadata = correct_asr_words(words)
    captions, composer_metadata = compose_caption_groups(
        words,
        max_words_per_caption=int(style.get("caption", {}).get("max_words_per_caption", 3)),
    )
    if not captions:
        return
    candidate["timed_captions"] = captions
    candidate["caption_source"] = "whisper"
    candidate["asr_metadata"] = {
        **asr_metadata,
        **correction_metadata,
        "caption_composer": {
            **composer_metadata,
            "low_confidence_word_count": correction_metadata.get("low_confidence_word_count", 0),
        },
    }
    candidate["caption_corrections"] = {
        **correction_metadata,
        "manual_edit_stale": False,
        "regenerated_after_boundary_edit": True,
    }
    candidate["score"] = {
        **candidate.get("score", {}),
        "asr_confidence": int(round((composer_metadata.get("avg_word_confidence") or 0.82) * 100)),
        "caption_sync_score": 95 if composer_metadata.get("caption_count", 0) else 0,
    }


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
    if force_source_refresh:
        source_url = _source_url_for_candidate(conn, candidate, render_metadata)
        report(24, "Downloading source for edited boundary")
        source_clip = download_youtube_section(source_url, candidate["profile_id"], candidate)
    else:
        source_clip = _find_source_clip(candidate["profile_id"], candidate_id, render_metadata)
        source_url = str(render_metadata.get("sourceUrl") or "")

    edited = candidate.get("caption_corrections", {}).get("edited_captions")
    edited_is_stale = bool(candidate.get("caption_corrections", {}).get("manual_edit_stale"))
    pending_keep = (candidate.get("curation_metadata") or {}).get("manual_silence_keep_segments")
    if isinstance(edited, list) and edited and not edited_is_stale:
        candidate["timed_captions"] = edited
        candidate["caption_source"] = "manual_edit"

    report(27, "Auto-trimming silence on source clip")
    source_clip = apply_silence_trim_for_render(source_clip, candidate)
    style = load_style(style_path)

    if regenerate_captions:
        report(30, "Regenerating captions for edited boundary")
        _regenerate_captions(
            candidate,
            source_clip,
            style,
            model_name=str(candidate.get("asr_metadata", {}).get("model") or "medium"),
        )
    elif isinstance(edited, list) and edited and not edited_is_stale:
        # Prefer already-remapped manual captions when Remove Pause queued a keep plan.
        if not pending_keep:
            candidate["timed_captions"] = edited
            candidate["caption_source"] = "manual_edit"
            trim = candidate.get("silence_trim") if isinstance(candidate.get("silence_trim"), dict) else {}
            keep = trim.get("keep_segments") if trim.get("changed") else None
            if isinstance(keep, list) and keep:
                segments = [(int(pair[0]), int(pair[1])) for pair in keep]
                candidate["timed_captions"] = remap_caption_groups(candidate["timed_captions"], segments)
        else:
            candidate["timed_captions"] = edited
            candidate["caption_source"] = "manual_edit"

    source_attribution = str(render_metadata.get("sourceAttribution") or "Source: Channel clip")
    resolved_renderer = "hyperframes" if quality == "production" and renderer == "ffmpeg" else renderer
    report(34, "Preparing render contract")
    if resolved_renderer == "hyperframes":
        report(52, "Rendering video with HyperFrames")
        output_path, contract = render_premium_hyperframes(candidate, profile, source_clip, source_url, source_attribution, style)
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
    candidate["render_quality"] = render_quality
    candidate["cost"] = estimate_clip_cost(
        int(candidate["end_ms"]) - int(candidate["start_ms"]),
        llm_provider=str(candidate.get("cost", {}).get("llm_provider") or "none"),
        caption_source=candidate.get("caption_source", "manual_edit"),
        renderer=resolved_renderer,
    )
    candidate["score"] = {**candidate.get("score", {}), "render_quality_score": render_quality["quality_score"]}

    protected_statuses = {"approved", "scheduled", "ready_to_publish", "published"}
    if candidate.get("status") not in protected_statuses:
        gate = evaluate_quality_gate(candidate, get_autonomy_settings(conn, candidate["profile_id"]))
        candidate["quality_gate"] = gate
        candidate["review_deadline_at"] = gate.get("review_deadline_at", "")
        candidate["status"] = gate.get("status", "rendered")

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
