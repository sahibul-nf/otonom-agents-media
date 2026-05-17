"""Single-clip rerender workflow for reviewed caption edits."""

from __future__ import annotations

import json
import threading
import uuid
from argparse import Namespace
from pathlib import Path
from typing import Any, Callable

from .autonomy import evaluate_quality_gate, get_autonomy_settings
from .costs import estimate_clip_cost
from .db import ARTIFACTS_DIR, DEFAULT_DB, ROOT, connect, fetch_one, initialize, load_json, seed_profile
from .render_quality import build_render_quality_report
from .rendering import PREMIUM_PRESET, render_premium_ffmpeg, render_premium_remotion
from .styles import load_style


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
            quality_gate_json = ?, caption_corrections_json = ?, review_deadline_at = ?, status = ?
        WHERE id = ?
        """,
        (
            json.dumps(candidate.get("score", {}), ensure_ascii=False),
            candidate.get("caption_source", "youtube"),
            json.dumps(candidate.get("render_quality", {}), ensure_ascii=False),
            json.dumps(candidate.get("cost", {}), ensure_ascii=False),
            json.dumps(candidate.get("quality_gate", {}), ensure_ascii=False),
            json.dumps(candidate.get("caption_corrections", {}), ensure_ascii=False),
            candidate.get("review_deadline_at", ""),
            candidate.get("status", "rendered"),
            candidate["id"],
        ),
    )
    conn.commit()


def rerender_candidate(
    candidate_id: str,
    renderer: str = "remotion",
    quality: str = "production",
    style_path: str | None = None,
    db_path: str | Path = DEFAULT_DB,
    on_progress: Callable[[int, str], None] | None = None,
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
    source_clip = _find_source_clip(candidate["profile_id"], candidate_id, render_metadata)
    style = load_style(style_path)

    edited = candidate.get("caption_corrections", {}).get("edited_captions")
    if isinstance(edited, list) and edited:
        candidate["timed_captions"] = edited
        candidate["caption_source"] = "manual_edit"

    source_url = str(render_metadata.get("sourceUrl") or "")
    source_attribution = str(render_metadata.get("sourceAttribution") or "Source: Ribath Nouraniyyah Hasyimiyyah")
    resolved_renderer = "remotion" if quality == "production" and renderer == "ffmpeg" else renderer
    report(34, "Preparing render contract")
    if resolved_renderer == "remotion":
        report(52, "Rendering video with Remotion")
        output_path, contract = render_premium_remotion(candidate, profile, source_clip, source_url, source_attribution, style)
    else:
        report(52, "Rendering video with FFmpeg")
        output_path, contract = render_premium_ffmpeg(candidate, profile, source_clip, source_url, source_attribution, style)

    job_id = Path(output_path).stem
    report(82, "Running render QA checks")
    render_quality = build_render_quality_report(contract, output_path)
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
    renderer: str = "remotion",
    quality: str = "production",
    style_path: str | None = None,
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
          (id, candidate_id, renderer, quality, style_path, status, progress, message, result_json, error)
        VALUES (?, ?, ?, ?, ?, 'queued', 0, 'Queued', '{}', '')
        """,
        (job_id, candidate_id, renderer, quality, style_path or ""),
    )
    conn.commit()
    conn.close()
    if start:
        thread = threading.Thread(
            target=_run_rerender_job,
            args=(job_id, candidate_id, renderer, quality, style_path, db_path),
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
    )
