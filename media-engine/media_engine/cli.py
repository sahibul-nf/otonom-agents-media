#!/usr/bin/env python3
"""Command-line entry point for the local autonomous media engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .autonomy import evaluate_quality_gate, get_autonomy_settings
from .caption_pipeline import build_production_captions
from .costs import estimate_clip_cost
from .credentials import credential_status
from .curation import SAMPLE_NOURBIT_TRANSCRIPT, curate_dry_run
from .db import DEFAULT_DB, DEFAULT_WORKSPACE_PROFILE_ID, ROOT, connect, ensure_media_profile, ensure_source_manifest, fetch_all, fetch_one, initialize, load_json, seed_profile, seed_source
from .env_loader import load_env_file
from .explainer_pipeline import create_explainer_job, run_explainer
from .explainer_planner import plan_explainer
from .live_publishers import LivePublishError, publish_live_payload
from .genres import normalize_genres
from .hyperframes_previews import list_hyperframes_preview_status, prewarm_hyperframes_template_previews
from .models import PUBLISH_MODES, RIGHTS_MODES, require_choice
from .publishers import create_dry_run_attempt
from .publishers import build_payload
from .render_quality import build_render_quality_report
from .rendering import PREMIUM_PRESET, render_minimal_ffmpeg, render_premium_ffmpeg, render_premium_hyperframes, render_premium_remotion
from .rerender import rerender_from_args
from .schedule_publisher import process_due_publishes
from .silence_trim import apply_silence_trim_for_render
from .styles import load_style
from .youtube_pipeline import choose_nourbit_premium_candidate, choose_nourbit_premium_candidates, download_youtube_section, fetch_youtube_transcript


def progress(message: str) -> None:
    print(f"[media-engine] {message}", file=sys.stderr, flush=True)


class ProgressBar:
    def __init__(self, total: int, width: int = 24) -> None:
        self.total = max(1, total)
        self.width = width
        self.current = 0

    def step(self, message: str) -> None:
        self.current = min(self.total, self.current + 1)
        filled = int((self.current / self.total) * self.width)
        bar = "#" * filled + "-" * (self.width - filled)
        progress(f"[{bar}] {self.current}/{self.total} {message}")


def profile_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "languages": json.loads(row["languages_json"]),
    }


def cmd_init(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    initialize(conn)
    seed_profile(conn, load_json(ROOT / "profiles" / "nourbit.json"))
    seed_source(conn, load_json(ROOT / "sources" / "nourbit_nouraniyyahofficial.json"))
    print(f"initialized {args.db}")


def cmd_hyperframes_previews(args: argparse.Namespace) -> None:
    load_env_file(args.env_file)
    if args.status:
        result = list_hyperframes_preview_status(include_brand=args.include_brand)
    else:
        result = prewarm_hyperframes_template_previews(include_brand=args.include_brand)
    try:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except BrokenPipeError:
        return


def cmd_ingest(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    initialize(conn)
    source = fetch_one(conn, "SELECT * FROM source_manifests WHERE profile_id = ?", (args.profile,))
    if not source:
        raise SystemExit(f"no source manifest found for profile: {args.profile}")
    print(json.dumps({"status": "ready", "source": source}, indent=2, ensure_ascii=False))


def cmd_curate(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    initialize(conn)
    source = fetch_one(conn, "SELECT * FROM source_manifests WHERE id = ?", (args.source_id,))
    if not source:
        raise SystemExit(f"source not found: {args.source_id}")
    transcript = Path(args.transcript).read_text(encoding="utf-8") if args.transcript else SAMPLE_NOURBIT_TRANSCRIPT
    candidate = curate_dry_run(args.profile, args.source_id, transcript)
    conn.execute(
        """
        INSERT INTO clip_candidates
          (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason,
           transcript_span, risk_flags_json, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate["id"],
            candidate["profile_id"],
            candidate["source_id"],
            candidate["start_ms"],
            candidate["end_ms"],
            candidate["title_hook"],
            candidate["viral_reason"],
            candidate["transcript_span"],
            json.dumps(candidate["risk_flags"], ensure_ascii=False),
            candidate["status"],
        ),
    )
    conn.commit()
    print(json.dumps(candidate, indent=2, ensure_ascii=False))


def cmd_explainer_plan(args: argparse.Namespace) -> None:
    sources = [s.strip() for s in (args.sources or "").split("|") if s.strip()]
    plan = plan_explainer(
        args.topic,
        sources=sources,
        llm_provider=args.llm_provider,
        language=args.language,
    )
    if args.output:
        Path(args.output).write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(plan, indent=2, ensure_ascii=False))


def cmd_explainer_create(args: argparse.Namespace) -> None:
    sources = [s.strip() for s in (args.sources or "").split("|") if s.strip()]
    result = create_explainer_job(
        topic=args.topic,
        sources=sources,
        profile_id=args.profile,
        llm_provider=args.llm_provider,
        language=args.language,
        scenes_path=args.scenes,
        db_path=args.db,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_explainer_run(args: argparse.Namespace) -> None:
    sources = [s.strip() for s in (args.sources or "").split("|") if s.strip()]
    prefer_hf = not args.ffmpeg_only
    result = run_explainer(
        topic=args.topic or "",
        scenes_path=args.scenes,
        clips_dir=args.clips_dir,
        job_id=args.job_id,
        profile_id=args.profile,
        llm_provider=args.llm_provider,
        language=args.language,
        sources=sources,
        prefer_hyperframes=prefer_hf,
        register_review=not args.skip_review,
        db_path=args.db,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_render(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    candidate = fetch_one(conn, "SELECT * FROM clip_candidates WHERE id = ?", (args.candidate_id,))
    if not candidate:
        raise SystemExit(f"candidate not found: {args.candidate_id}")
    profile = fetch_one(conn, "SELECT * FROM media_profiles WHERE id = ?", (candidate["profile_id"],))
    if not profile:
        raise SystemExit(f"profile not found: {candidate['profile_id']}")
    output_path, contract = render_minimal_ffmpeg(candidate, profile)
    job_id = Path(output_path).stem
    conn.execute(
        """
        INSERT INTO render_jobs
          (id, candidate_id, preset, crop_strategy, caption_style, status, output_path, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            candidate["id"],
            profile["default_render_preset"],
            "face_or_center_crop",
            contract["caption_style"],
            "rendered",
            output_path,
            json.dumps(contract, ensure_ascii=False),
        ),
    )
    conn.execute("UPDATE clip_candidates SET status = 'rendered' WHERE id = ?", (candidate["id"],))
    conn.commit()
    print(json.dumps({"render_job": job_id, "output_path": output_path}, indent=2, ensure_ascii=False))


def insert_candidate(conn, candidate: dict[str, Any]) -> None:
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
            candidate["id"],
            candidate["profile_id"],
            candidate["source_id"],
            candidate["start_ms"],
            candidate["end_ms"],
            candidate["title_hook"],
            candidate.get("hook_subtitle", ""),
            candidate["viral_reason"],
            candidate["transcript_span"],
            json.dumps(candidate["risk_flags"], ensure_ascii=False),
            json.dumps(candidate.get("score", {}), ensure_ascii=False),
            json.dumps(candidate.get("curation_metadata", {}), ensure_ascii=False),
            candidate.get("caption_source", "youtube"),
            json.dumps(candidate.get("asr_metadata", {}), ensure_ascii=False),
            json.dumps(candidate.get("render_quality", {}), ensure_ascii=False),
            json.dumps(candidate.get("cost", {}), ensure_ascii=False),
            json.dumps(candidate.get("quality_gate", {}), ensure_ascii=False),
            json.dumps(candidate.get("caption_corrections", {}), ensure_ascii=False),
            candidate.get("dedupe_key", ""),
            candidate.get("review_deadline_at", ""),
            candidate["status"],
        ),
    )
    conn.commit()


def update_candidate_metadata(conn, candidate: dict[str, Any]) -> None:
    conn.execute(
        """
        UPDATE clip_candidates
        SET hook_subtitle = ?, score_json = ?, curation_metadata_json = ?, caption_source = ?,
            asr_metadata_json = ?, render_quality_json = ?, cost_json = ?,
            quality_gate_json = ?, caption_corrections_json = ?, dedupe_key = ?,
            review_deadline_at = ?, status = ?
        WHERE id = ?
        """,
        (
            candidate.get("hook_subtitle", ""),
            json.dumps(candidate.get("score", {}), ensure_ascii=False),
            json.dumps(candidate.get("curation_metadata", {}), ensure_ascii=False),
            candidate.get("caption_source", "youtube"),
            json.dumps(candidate.get("asr_metadata", {}), ensure_ascii=False),
            json.dumps(candidate.get("render_quality", {}), ensure_ascii=False),
            json.dumps(candidate.get("cost", {}), ensure_ascii=False),
            json.dumps(candidate.get("quality_gate", {}), ensure_ascii=False),
            json.dumps(candidate.get("caption_corrections", {}), ensure_ascii=False),
            candidate.get("dedupe_key", ""),
            candidate.get("review_deadline_at", ""),
            candidate["status"],
            candidate["id"],
        ),
    )
    conn.commit()


def load_profile_and_source(conn, profile_id: str, source_id: str, source_url: str = "") -> tuple[dict[str, Any], dict[str, Any]]:
    initialize(conn)
    try:
        ensure_media_profile(conn, profile_id)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if source_url.strip():
        ensure_source_manifest(conn, profile_id=profile_id, source_id=source_id, source_url=source_url.strip())
    else:
        source = fetch_one(conn, "SELECT * FROM source_manifests WHERE id = ?", (source_id,))
        if not source:
            nourbit_source = ROOT / "sources" / "nourbit_nouraniyyahofficial.json"
            if nourbit_source.exists():
                seed_source(conn, load_json(nourbit_source))
    profile = fetch_one(conn, "SELECT * FROM media_profiles WHERE id = ?", (profile_id,))
    source = fetch_one(conn, "SELECT * FROM source_manifests WHERE id = ?", (source_id,))
    if not profile or not source:
        raise SystemExit("profile/source seed failed")
    return profile, source


def cmd_premium_test(args: argparse.Namespace) -> None:
    bar = ProgressBar(7)
    bar.step("loading environment and profile")
    load_env_file(args.env_file)
    conn = connect(args.db)
    profile, _source = load_profile_and_source(conn, args.profile, args.source_id, args.youtube_url)

    bar.step("fetching YouTube transcript")
    entries = fetch_youtube_transcript(args.youtube_url, languages=parse_languages(args.transcript_languages))
    style = load_style(args.style)
    bar.step("selecting best short candidate")
    candidate = choose_nourbit_premium_candidates(
        args.profile,
        args.source_id,
        entries,
        style,
        count=1,
        llm_provider=args.llm_provider,
        duration_preset=args.clip_length_preset,
        clip_min_seconds=args.clip_min_seconds,
        clip_max_seconds=args.clip_max_seconds,
        genres=parse_genres(args.genres, args.profile),
        niche=getattr(args, "niche", None) or profile.get("niche"),
        workspace_name=getattr(args, "workspace_name", None) or profile.get("name"),
    )[0]
    insert_candidate(conn, candidate)
    bar.step(f"downloading source clip for {candidate['id']}")
    source_clip = download_youtube_section(args.youtube_url, args.profile, candidate)
    bar.step("auto-trimming silence on source clip")
    source_clip = apply_silence_trim_for_render(source_clip, candidate)
    bar.step(f"preparing captions with {args.caption_source}")
    prepare_production_captions(candidate, source_clip, args, style, profile=profile)
    attribution = args.source_attribution or "Source: Channel clip"
    renderer, renderer_note = resolve_renderer(args.renderer, args.quality)
    if renderer_note:
        bar.step(renderer_note)
    bar.step(f"rendering with {renderer}")
    genre_ids = parse_genres(args.genres, args.profile)
    if renderer == "hyperframes":
        output_path, contract = render_premium_hyperframes(
            candidate,
            profile,
            source_clip,
            args.youtube_url,
            attribution,
            style,
            hyperframes_template=args.hyperframes_template,
            hyperframes_format=getattr(args, "hyperframes_format", "auto"),
            brand_system_template_id=getattr(args, "brand_system_template_id", ""),
            genres=genre_ids,
        )
    elif renderer == "remotion":
        output_path, contract = render_premium_remotion(
            candidate,
            profile,
            source_clip,
            args.youtube_url,
            attribution,
            style,
        )
    else:
        output_path, contract = render_premium_ffmpeg(
            candidate,
            profile,
            source_clip,
            args.youtube_url,
            attribution,
            style,
        )
    job_id = Path(output_path).stem
    finalize_candidate_metadata(candidate, contract, output_path, args, renderer)
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
    conn.execute("UPDATE clip_candidates SET status = 'rendered' WHERE id = ?", (candidate["id"],))
    update_candidate_metadata(conn, candidate)
    conn.commit()
    bar.step("premium test render complete")
    print(
        json.dumps(
            {
                "candidate_id": candidate["id"],
                "start": contract["startTimecode"],
                "end": contract["endTimecode"],
                "title_hook": candidate["title_hook"],
                "source_clip": source_clip,
                "output_path": output_path,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def render_premium_candidate(
    conn,
    candidate: dict[str, Any],
    profile: dict[str, Any],
    youtube_url: str,
    source_attribution: str,
    renderer: str,
    style: dict[str, Any],
    args: argparse.Namespace,
    progress_label: str = "",
    bar: ProgressBar | None = None,
) -> dict[str, Any]:
    prefix = f"{progress_label} " if progress_label else ""
    insert_candidate(conn, candidate)
    (bar.step if bar else progress)(f"{prefix}downloading source clip for {candidate['id']}")
    source_clip = download_youtube_section(youtube_url, profile["id"], candidate)
    (bar.step if bar else progress)(f"{prefix}auto-trimming silence")
    source_clip = apply_silence_trim_for_render(source_clip, candidate)
    (bar.step if bar else progress)(f"{prefix}preparing captions with {getattr(args, 'caption_source', 'youtube')}")
    prepare_production_captions(candidate, source_clip, args, style, profile=profile)
    renderer, renderer_note = resolve_renderer(renderer, args.quality)
    if renderer_note:
        (bar.step if bar else progress)(f"{prefix}{renderer_note}")
    (bar.step if bar else progress)(f"{prefix}rendering {candidate['id']} with {renderer}")
    genre_ids = parse_genres(getattr(args, "genres", ""), getattr(args, "profile", None) or (profile or {}).get("id"))
    if renderer == "hyperframes":
        output_path, contract = render_premium_hyperframes(
            candidate,
            profile,
            source_clip,
            youtube_url,
            source_attribution,
            style,
            hyperframes_template=getattr(args, "hyperframes_template", "auto"),
            hyperframes_format=getattr(args, "hyperframes_format", "auto"),
            brand_system_template_id=getattr(args, "brand_system_template_id", ""),
            genres=genre_ids,
        )
    elif renderer == "remotion":
        output_path, contract = render_premium_remotion(candidate, profile, source_clip, youtube_url, source_attribution, style)
    else:
        output_path, contract = render_premium_ffmpeg(candidate, profile, source_clip, youtube_url, source_attribution, style)
    job_id = Path(output_path).stem
    finalize_candidate_metadata(candidate, contract, output_path, args, renderer)
    quality_gate = evaluate_quality_gate(candidate, get_autonomy_settings(conn, profile["id"]))
    candidate["quality_gate"] = quality_gate
    candidate["review_deadline_at"] = quality_gate.get("review_deadline_at", "")
    candidate["status"] = quality_gate.get("status", "rendered")
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
    update_candidate_metadata(conn, candidate)
    conn.commit()
    (bar.step if bar else progress)(f"{prefix}completed {candidate['id']}")
    return {
        "candidate_id": candidate["id"],
        "start": contract["startTimecode"],
        "end": contract["endTimecode"],
        "title_hook": candidate["title_hook"],
        "overall_score": candidate.get("score", {}).get("overall_score"),
        "cost": candidate.get("cost", {}),
        "render_quality": candidate.get("render_quality", {}),
        "source_clip": source_clip,
        "output_path": output_path,
    }


def resolve_renderer(renderer: str, quality: str) -> tuple[str, str]:
    if quality == "production" and renderer == "ffmpeg":
        return "hyperframes", ""
    return renderer, ""


def _render_not_ready(renderer: str) -> RuntimeError:
    return RuntimeError(
        f"{renderer} renderer is not wired for production publish yet. "
        "Complete HyperFrames runtime setup first, or use a legacy internal fallback."
    )


def prepare_production_captions(
    candidate: dict[str, Any],
    source_clip: str,
    args: argparse.Namespace,
    style: dict[str, Any],
    profile: dict[str, Any] | None = None,
) -> None:
    build_production_captions(
        candidate,
        source_clip,
        caption_source=getattr(args, "caption_source", "youtube"),
        asr_model=getattr(args, "asr_model", "medium"),
        speech_language=getattr(args, "speech_language", "id"),
        style=style,
        youtube_url=getattr(args, "youtube_url", "") or "",
        transcript_languages=getattr(args, "transcript_languages", "id,en"),
        llm_provider=getattr(args, "llm_provider", "none"),
        niche=str((profile or {}).get("niche") or ""),
    )


def finalize_candidate_metadata(candidate: dict[str, Any], contract: dict[str, Any], output_path: str, args: argparse.Namespace, renderer: str) -> None:
    render_quality = build_render_quality_report(contract, output_path)
    if isinstance(candidate.get("silence_trim"), dict):
        render_quality["silence_trim"] = candidate["silence_trim"]
    cost = estimate_clip_cost(
        int(candidate["end_ms"]) - int(candidate["start_ms"]),
        llm_provider=getattr(args, "llm_provider", "none"),
        caption_source=candidate.get("caption_source", getattr(args, "caption_source", "youtube")),
        renderer=renderer,
    )
    candidate["render_quality"] = render_quality
    candidate["cost"] = cost
    candidate["score"] = {
        **candidate.get("score", {}),
        "render_quality_score": render_quality["quality_score"],
    }


def cmd_premium_curate(args: argparse.Namespace) -> None:
    bar = ProgressBar(4)
    bar.step("loading environment and profile")
    load_env_file(args.env_file)
    conn = connect(args.db)
    profile, _source = load_profile_and_source(conn, args.profile, args.source_id, args.youtube_url)
    bar.step("fetching YouTube transcript")
    entries = fetch_youtube_transcript(args.youtube_url, languages=parse_languages(args.transcript_languages))
    style = load_style(args.style)
    bar.step(f"curating {args.count} candidates with llm_provider={args.llm_provider}")
    candidates = choose_nourbit_premium_candidates(
        args.profile,
        args.source_id,
        entries,
        style,
        count=args.count,
        llm_provider=args.llm_provider,
        duration_preset=args.clip_length_preset,
        clip_min_seconds=args.clip_min_seconds,
        clip_max_seconds=args.clip_max_seconds,
        genres=parse_genres(args.genres, args.profile),
        niche=getattr(args, "niche", None) or profile.get("niche"),
        workspace_name=getattr(args, "workspace_name", None) or profile.get("name"),
    )
    for candidate in candidates:
        insert_candidate(conn, candidate)
    bar.step(f"curation complete: {len(candidates)} candidates")
    print(json.dumps({"count": len(candidates), "candidates": candidates}, indent=2, ensure_ascii=False))


def cmd_premium_batch(args: argparse.Namespace) -> None:
    bar = ProgressBar(3 + max(1, args.count) * 5 + 1)
    bar.step("loading environment and profile")
    load_env_file(args.env_file)
    conn = connect(args.db)
    profile, _source = load_profile_and_source(conn, args.profile, args.source_id, args.youtube_url)
    bar.step("fetching YouTube transcript")
    entries = fetch_youtube_transcript(args.youtube_url, languages=parse_languages(args.transcript_languages))
    style = load_style(args.style)
    bar.step(f"selecting top {args.count} candidates with llm_provider={args.llm_provider}")
    candidates = choose_nourbit_premium_candidates(
        args.profile,
        args.source_id,
        entries,
        style,
        count=args.count,
        llm_provider=args.llm_provider,
        duration_preset=args.clip_length_preset,
        clip_min_seconds=args.clip_min_seconds,
        clip_max_seconds=args.clip_max_seconds,
        genres=parse_genres(args.genres, args.profile),
        niche=getattr(args, "niche", None) or profile.get("niche"),
        workspace_name=getattr(args, "workspace_name", None) or profile.get("name"),
    )
    attribution = args.source_attribution or "Source: Channel clip"
    renders = []
    for index, candidate in enumerate(candidates, start=1):
        bar.step(f"[{index}/{len(candidates)}] queued {candidate['id']} - {candidate['title_hook']}")
        renders.append(
            render_premium_candidate(
                conn,
                candidate,
                profile,
                args.youtube_url,
                attribution,
                args.renderer,
                style,
                args,
                progress_label=f"[{index}/{len(candidates)}]",
                bar=bar,
            )
        )
    bar.step(f"batch complete: {len(renders)} renders")
    print(json.dumps({"count": len(renders), "renders": renders}, indent=2, ensure_ascii=False))


def cmd_review(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    rows = fetch_all(
        conn,
        """
        SELECT c.*, r.output_path
        FROM clip_candidates c
        LEFT JOIN render_jobs r ON r.candidate_id = c.id
        WHERE c.profile_id = ?
        ORDER BY c.created_at DESC
        """,
        (args.profile,),
    )
    print(json.dumps(rows, indent=2, ensure_ascii=False))


def cmd_approve(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    conn.execute("UPDATE clip_candidates SET status = 'approved' WHERE id = ?", (args.candidate_id,))
    conn.commit()
    print(json.dumps({"candidate_id": args.candidate_id, "status": "approved"}, indent=2))


def cmd_publish(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    candidate = fetch_one(conn, "SELECT * FROM clip_candidates WHERE id = ?", (args.candidate_id,))
    if not candidate:
        raise SystemExit(f"candidate not found: {args.candidate_id}")
    source = fetch_one(conn, "SELECT * FROM source_manifests WHERE id = ?", (candidate["source_id"],))
    render_job = fetch_one(
        conn,
        "SELECT * FROM render_jobs WHERE candidate_id = ? ORDER BY created_at DESC LIMIT 1",
        (candidate["id"],),
    )
    targets = fetch_all(conn, "SELECT * FROM publish_targets WHERE profile_id = ?", (candidate["profile_id"],))
    attempts = []
    for target in targets:
        if args.platform and target["platform"] != args.platform:
            continue
        attempts.append(create_dry_run_attempt(conn, source, target, candidate, render_job))
    print(json.dumps(attempts, indent=2, ensure_ascii=False))


def cmd_credentials_check(args: argparse.Namespace) -> None:
    load_env_file(args.env_file)
    print(json.dumps(credential_status(), indent=2, ensure_ascii=False))


def cmd_publish_live(args: argparse.Namespace) -> None:
    load_env_file(args.env_file)
    conn = connect(args.db)
    initialize(conn)
    candidate = fetch_one(conn, "SELECT * FROM clip_candidates WHERE id = ?", (args.candidate_id,))
    if not candidate:
        raise SystemExit(f"candidate not found: {args.candidate_id}")
    source = fetch_one(conn, "SELECT * FROM source_manifests WHERE id = ?", (candidate["source_id"],))
    target = fetch_one(
        conn,
        "SELECT * FROM publish_targets WHERE profile_id = ? AND platform = ?",
        (candidate["profile_id"], args.platform),
    )
    render_job = fetch_one(
        conn,
        "SELECT * FROM render_jobs WHERE candidate_id = ? ORDER BY created_at DESC LIMIT 1",
        (candidate["id"],),
    )
    if not source or not target:
        raise SystemExit("source or publish target not found")
    attempt = create_dry_run_attempt(conn, source, target, candidate, render_job)
    if attempt["status"] != "ready":
        print(json.dumps(attempt, indent=2, ensure_ascii=False))
        raise SystemExit(f"publish blocked: {attempt['error']}")

    payload = build_payload(args.platform, candidate, render_job)
    if args.dry_run:
        print(json.dumps({"status": "dry_run", "payload": payload}, indent=2, ensure_ascii=False))
        return
    try:
        result = publish_live_payload(args.platform, payload)
    except LivePublishError as exc:
        conn.execute(
            "UPDATE publish_attempts SET status = ?, error = ? WHERE id = ?",
            ("failed", str(exc), attempt["id"]),
        )
        conn.commit()
        raise SystemExit(str(exc)) from exc
    conn.execute(
        "UPDATE publish_attempts SET status = ?, payload_json = ? WHERE id = ?",
        ("published", json.dumps({**payload, "live_result": result}, ensure_ascii=False), attempt["id"]),
    )
    conn.execute("UPDATE clip_candidates SET status = 'published' WHERE id = ?", (candidate["id"],))
    conn.commit()
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_publish_due(args: argparse.Namespace) -> None:
    result = process_due_publishes(
        db_path=args.db,
        env_file=args.env_file,
        profile_id=args.profile,
        limit=args.limit,
        dry_run=args.dry_run,
        notify=not args.no_notify,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


def parse_languages(value: str | None) -> list[str]:
    languages = [item.strip() for item in str(value or "id,en").split(",") if item.strip()]
    return languages or ["id", "en"]


def parse_genres(value: str | None, profile_id: str | None = None) -> list[str]:
    return normalize_genres(value, profile_id=profile_id)


def cmd_rerender(args: argparse.Namespace) -> None:
    progress(f"rerendering {args.candidate_id} with {args.renderer}/{args.quality}")
    result = rerender_from_args(args)
    progress(f"rerender complete: {result['output_path']}")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_set_target_mode(args: argparse.Namespace) -> None:
    require_choice(args.mode, PUBLISH_MODES, "mode")
    conn = connect(args.db)
    result = conn.execute(
        "UPDATE publish_targets SET mode = ? WHERE profile_id = ? AND platform = ?",
        (args.mode, args.profile, args.platform),
    )
    conn.commit()
    if result.rowcount == 0:
        raise SystemExit(f"publish target not found: {args.profile}/{args.platform}")
    print(json.dumps({"profile": args.profile, "platform": args.platform, "mode": args.mode}, indent=2))


def cmd_watch_poll(args: argparse.Namespace) -> None:
    from .channel_watcher import poll_due_watch_channels, poll_watch_channel

    conn = connect(args.db)
    initialize(conn)
    if args.channel_id:
        result = poll_watch_channel(conn, args.channel_id, enqueue=not args.dry_run, force=True)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return
    results = poll_due_watch_channels(conn, profile_id=args.profile or None, force=args.force)
    print(json.dumps({"results": results}, indent=2, ensure_ascii=False, default=str))


def cmd_authorize_source(args: argparse.Namespace) -> None:
    require_choice(args.permission_status, RIGHTS_MODES, "permission_status")
    conn = connect(args.db)
    result = conn.execute(
        """
        UPDATE source_manifests
        SET permission_status = ?, permission_evidence = ?, monetization_allowed = ?
        WHERE id = ?
        """,
        (
            args.permission_status,
            args.permission_evidence,
            int(args.monetization_allowed),
            args.source_id,
        ),
    )
    conn.commit()
    if result.rowcount == 0:
        raise SystemExit(f"source not found: {args.source_id}")
    print(
        json.dumps(
            {
                "source_id": args.source_id,
                "permission_status": args.permission_status,
                "permission_evidence": args.permission_evidence,
                "monetization_allowed": bool(args.monetization_allowed),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="media-engine")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    sub = parser.add_subparsers(required=True)

    init = sub.add_parser("init")
    init.set_defaults(func=cmd_init)

    hyperframes_previews = sub.add_parser("hyperframes-previews")
    hyperframes_previews.add_argument("--status", action="store_true", help="Print preview readiness without rendering")
    hyperframes_previews.add_argument("--include-brand", action="store_true", help="Include saved Brand System templates")
    hyperframes_previews.add_argument("--env-file", default="../.env.local")
    hyperframes_previews.set_defaults(func=cmd_hyperframes_previews)

    ingest = sub.add_parser("ingest")
    ingest.add_argument("--profile", default="nourbit")
    ingest.set_defaults(func=cmd_ingest)

    curate = sub.add_parser("curate")
    curate.add_argument("--profile", default="nourbit")
    curate.add_argument("--source-id", default="nourbit_nouraniyyahofficial")
    curate.add_argument("--transcript")
    curate.set_defaults(func=cmd_curate)

    render = sub.add_parser("render")
    render.add_argument("--candidate-id", required=True)
    render.set_defaults(func=cmd_render)

    premium_test = sub.add_parser("premium-test")
    premium_test.add_argument("--profile", default="nourbit")
    premium_test.add_argument("--source-id", default="nourbit_nouraniyyahofficial")
    premium_test.add_argument("--youtube-url", required=True)
    premium_test.add_argument("--source-attribution", default="")
    premium_test.add_argument("--renderer", choices=["ffmpeg", "remotion", "hyperframes"], default="hyperframes")
    premium_test.add_argument("--hyperframes-template", default="auto", help="HyperFrames template id or auto")
    premium_test.add_argument("--brand-system-template-id", default="", help="Saved Brand System template id")
    premium_test.add_argument("--hyperframes-format", choices=["auto", "short_9_16", "long_16_9"], default="auto")
    premium_test.add_argument("--quality", choices=["draft", "production"], default="draft")
    premium_test.add_argument("--caption-source", choices=["youtube", "whisper", "hybrid"], default="youtube")
    premium_test.add_argument("--asr-model", choices=["small", "medium", "large-v3-turbo"], default="medium")
    premium_test.add_argument("--speech-language", default="id", help="Spoken language hint for Whisper/faster-whisper, e.g. id, ar, en")
    premium_test.add_argument("--transcript-languages", default="id,en", help="Comma-separated YouTube transcript preference order")
    duration_choices = ["auto", "under_30s", "seconds_30_60", "minutes_1_3", "minutes_3_plus", "custom", "quick_hit", "standard_short", "deep_context", "platform_max", "30-60s", "45-120s", "60-90s"]
    premium_test.add_argument("--clip-length-preset", choices=duration_choices, default="auto")
    premium_test.add_argument("--clip-min-seconds", type=int, default=20)
    premium_test.add_argument("--clip-max-seconds", type=int, default=180)
    premium_test.add_argument("--genres", default="", help="Comma-separated content angles; empty uses workspace defaults")
    premium_test.add_argument("--niche", default="", help="Workspace niche for curation context")
    premium_test.add_argument("--workspace-name", default="", help="Workspace display name for curation context")
    premium_test.add_argument("--style", help="Path to a JSON style override. Defaults to profiles/nourbit_opus_style.json")
    premium_test.add_argument("--llm-provider", choices=["none", "openai", "deepseek", "groq"], default="none")
    premium_test.add_argument("--env-file")
    premium_test.set_defaults(func=cmd_premium_test)

    premium_curate = sub.add_parser("premium-curate")
    premium_curate.add_argument("--profile", default="nourbit")
    premium_curate.add_argument("--source-id", default="nourbit_nouraniyyahofficial")
    premium_curate.add_argument("--youtube-url", required=True)
    premium_curate.add_argument("--count", type=int, default=5)
    premium_curate.add_argument("--clip-length-preset", choices=duration_choices, default="auto")
    premium_curate.add_argument("--clip-min-seconds", type=int, default=20)
    premium_curate.add_argument("--clip-max-seconds", type=int, default=180)
    premium_curate.add_argument("--genres", default="", help="Comma-separated content angles; empty uses workspace defaults")
    premium_curate.add_argument("--niche", default="", help="Workspace niche for curation context")
    premium_curate.add_argument("--workspace-name", default="", help="Workspace display name for curation context")
    premium_curate.add_argument("--style", help="Path to a JSON style override. Defaults to profiles/nourbit_opus_style.json")
    premium_curate.add_argument("--llm-provider", choices=["none", "openai", "deepseek", "groq"], default="none")
    premium_curate.add_argument("--transcript-languages", default="id,en", help="Comma-separated YouTube transcript preference order")
    premium_curate.add_argument("--env-file")
    premium_curate.set_defaults(func=cmd_premium_curate)

    premium_batch = sub.add_parser("premium-batch")
    premium_batch.add_argument("--profile", default="nourbit")
    premium_batch.add_argument("--source-id", default="nourbit_nouraniyyahofficial")
    premium_batch.add_argument("--youtube-url", required=True)
    premium_batch.add_argument("--source-attribution", default="")
    premium_batch.add_argument("--count", type=int, default=5)
    premium_batch.add_argument("--renderer", choices=["ffmpeg", "remotion", "hyperframes"], default="hyperframes")
    premium_batch.add_argument("--hyperframes-template", default="auto", help="HyperFrames template id or auto")
    premium_batch.add_argument("--brand-system-template-id", default="", help="Saved Brand System template id")
    premium_batch.add_argument("--hyperframes-format", choices=["auto", "short_9_16", "long_16_9"], default="auto")
    premium_batch.add_argument("--quality", choices=["draft", "production"], default="draft")
    premium_batch.add_argument("--caption-source", choices=["youtube", "whisper", "hybrid"], default="hybrid")
    premium_batch.add_argument("--asr-model", choices=["small", "medium", "large-v3-turbo"], default="medium")
    premium_batch.add_argument("--speech-language", default="id", help="Spoken language hint for Whisper/faster-whisper, e.g. id, ar, en")
    premium_batch.add_argument("--transcript-languages", default="id,en", help="Comma-separated YouTube transcript preference order")
    premium_batch.add_argument("--clip-length-preset", choices=duration_choices, default="auto")
    premium_batch.add_argument("--clip-min-seconds", type=int, default=20)
    premium_batch.add_argument("--clip-max-seconds", type=int, default=180)
    premium_batch.add_argument("--genres", default="", help="Comma-separated content angles; empty uses workspace defaults")
    premium_batch.add_argument("--niche", default="", help="Workspace niche for curation context")
    premium_batch.add_argument("--workspace-name", default="", help="Workspace display name for curation context")
    premium_batch.add_argument("--style", help="Path to a JSON style override. Defaults to profiles/nourbit_opus_style.json")
    premium_batch.add_argument("--llm-provider", choices=["none", "openai", "deepseek", "groq"], default="none")
    premium_batch.add_argument("--env-file")
    premium_batch.set_defaults(func=cmd_premium_batch)

    review = sub.add_parser("review")
    review.add_argument("--profile", default="nourbit")
    review.set_defaults(func=cmd_review)

    approve = sub.add_parser("approve")
    approve.add_argument("--candidate-id", required=True)
    approve.set_defaults(func=cmd_approve)

    publish = sub.add_parser("publish")
    publish.add_argument("--candidate-id", required=True)
    publish.add_argument("--platform")
    publish.set_defaults(func=cmd_publish)

    credentials_check = sub.add_parser("credentials-check")
    credentials_check.add_argument("--env-file", default="../.env.local")
    credentials_check.set_defaults(func=cmd_credentials_check)

    publish_live = sub.add_parser("publish-live")
    publish_live.add_argument("--candidate-id", required=True)
    publish_live.add_argument("--platform", required=True)
    publish_live.add_argument("--env-file", default="../.env.local")
    publish_live.add_argument("--dry-run", action="store_true")
    publish_live.set_defaults(func=cmd_publish_live)

    publish_due = sub.add_parser("publish-due")
    publish_due.add_argument("--profile", default="nourbit")
    publish_due.add_argument("--env-file", default="../.env.local")
    publish_due.add_argument("--limit", type=int, default=5)
    publish_due.add_argument("--dry-run", action="store_true")
    publish_due.add_argument("--no-notify", action="store_true")
    publish_due.set_defaults(func=cmd_publish_due)

    watch_poll = sub.add_parser("watch-poll", help="Poll watched channels for new uploads and enqueue clip jobs")
    watch_poll.add_argument("--profile", default="", help="Limit to one workspace/profile")
    watch_poll.add_argument("--channel-id", default="", help="Poll a single watch channel id")
    watch_poll.add_argument("--force", action="store_true", help="Ignore poll interval")
    watch_poll.add_argument("--dry-run", action="store_true", help="With --channel-id, detect only (no enqueue)")
    watch_poll.set_defaults(func=cmd_watch_poll)

    rerender = sub.add_parser("rerender")
    rerender.add_argument("--candidate-id", required=True)
    rerender.add_argument("--renderer", choices=["ffmpeg", "remotion", "hyperframes"], default="hyperframes")
    rerender.add_argument("--quality", choices=["draft", "production"], default="production")
    rerender.add_argument("--style", help="Path to a JSON style override. Defaults to profiles/nourbit_opus_style.json")
    rerender.set_defaults(func=cmd_rerender)

    target_mode = sub.add_parser("set-target-mode")
    target_mode.add_argument("--profile", default="nourbit")
    target_mode.add_argument("--platform", required=True)
    target_mode.add_argument("--mode", required=True)
    target_mode.set_defaults(func=cmd_set_target_mode)

    authorize = sub.add_parser("authorize-source")
    authorize.add_argument("--source-id", default="nourbit_nouraniyyahofficial")
    authorize.add_argument("--permission-status", required=True)
    authorize.add_argument("--permission-evidence", required=True)
    authorize.add_argument("--monetization-allowed", action="store_true")
    authorize.set_defaults(func=cmd_authorize_source)

    explainer_plan = sub.add_parser("explainer-plan", help="Plan hybrid explainer scenes from a topic")
    explainer_plan.add_argument("--topic", required=True)
    explainer_plan.add_argument("--sources", default="", help="Pipe-separated source notes")
    explainer_plan.add_argument("--language", default="id")
    explainer_plan.add_argument("--llm-provider", choices=["none", "openai", "deepseek", "groq"], default="none")
    explainer_plan.add_argument("--output", help="Write plan JSON to this path")
    explainer_plan.set_defaults(func=cmd_explainer_plan)

    explainer_create = sub.add_parser("explainer-create", help="Create explainer job + fixtures folder (no stitch)")
    explainer_create.add_argument("--topic", required=True)
    explainer_create.add_argument("--sources", default="")
    explainer_create.add_argument("--language", default="id")
    explainer_create.add_argument("--llm-provider", choices=["none", "openai", "deepseek", "groq"], default="none")
    explainer_create.add_argument("--scenes", help="Optional existing scenes JSON")
    explainer_create.add_argument("--profile", default=DEFAULT_WORKSPACE_PROFILE_ID)
    explainer_create.set_defaults(func=cmd_explainer_create)

    explainer_run = sub.add_parser("explainer-run", help="Stitch explainer from fixtures / scenes into review queue")
    explainer_run.add_argument("--topic", default="", help="Topic when creating a new job inline")
    explainer_run.add_argument("--job-id", help="Existing explainer job id")
    explainer_run.add_argument("--scenes", help="Path to scenes.json")
    explainer_run.add_argument("--clips-dir", help="Directory of avatar fixture MP4s")
    explainer_run.add_argument("--sources", default="")
    explainer_run.add_argument("--language", default="id")
    explainer_run.add_argument("--llm-provider", choices=["none", "openai", "deepseek", "groq"], default="none")
    explainer_run.add_argument("--profile", default=DEFAULT_WORKSPACE_PROFILE_ID)
    explainer_run.add_argument("--ffmpeg-only", action="store_true", help="Skip HyperFrames; use FFmpeg title cards")
    explainer_run.add_argument("--skip-review", action="store_true", help="Do not register in dashboard review queue")
    explainer_run.set_defaults(func=cmd_explainer_run)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
