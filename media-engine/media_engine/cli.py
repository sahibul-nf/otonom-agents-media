#!/usr/bin/env python3
"""Command-line entry point for the local autonomous media engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .asr import load_or_create_asr_words
from .autonomy import evaluate_quality_gate, get_autonomy_settings
from .caption_composer import compose_caption_groups
from .costs import estimate_clip_cost
from .credentials import credential_status
from .curation import SAMPLE_NOURBIT_TRANSCRIPT, curate_dry_run
from .db import DEFAULT_DB, ROOT, connect, fetch_all, fetch_one, initialize, load_json, seed_profile, seed_source
from .env_loader import load_env_file
from .live_publishers import LivePublishError, publish_telegram_video
from .genres import normalize_genres
from .models import PUBLISH_MODES, RIGHTS_MODES, require_choice
from .publishers import create_dry_run_attempt
from .publishers import build_payload
from .render_quality import build_render_quality_report
from .rendering import PREMIUM_PRESET, render_minimal_ffmpeg, render_premium_ffmpeg, render_premium_remotion
from .rerender import rerender_from_args
from .styles import load_style
from .transcript_quality import correct_asr_words
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
          (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason,
           transcript_span, risk_flags_json, score_json, curation_metadata_json,
           caption_source, asr_metadata_json, render_quality_json, cost_json,
           quality_gate_json, caption_corrections_json, dedupe_key, review_deadline_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        SET score_json = ?, curation_metadata_json = ?, caption_source = ?,
            asr_metadata_json = ?, render_quality_json = ?, cost_json = ?,
            quality_gate_json = ?, caption_corrections_json = ?, dedupe_key = ?,
            review_deadline_at = ?, status = ?
        WHERE id = ?
        """,
        (
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


def load_profile_and_source(conn, profile_id: str, source_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    initialize(conn)
    profile = fetch_one(conn, "SELECT * FROM media_profiles WHERE id = ?", (profile_id,))
    if not profile:
        seed_profile(conn, load_json(ROOT / "profiles" / "nourbit.json"))
        profile = fetch_one(conn, "SELECT * FROM media_profiles WHERE id = ?", (profile_id,))
    source = fetch_one(conn, "SELECT * FROM source_manifests WHERE id = ?", (source_id,))
    if not source:
        seed_source(conn, load_json(ROOT / "sources" / "nourbit_nouraniyyahofficial.json"))
        source = fetch_one(conn, "SELECT * FROM source_manifests WHERE id = ?", (source_id,))
    if not profile or not source:
        raise SystemExit("profile/source seed failed")
    return profile, source


def cmd_premium_test(args: argparse.Namespace) -> None:
    bar = ProgressBar(7)
    bar.step("loading environment and profile")
    load_env_file(args.env_file)
    conn = connect(args.db)
    profile, _source = load_profile_and_source(conn, args.profile, args.source_id)

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
        genres=parse_genres(args.genres),
    )[0]
    insert_candidate(conn, candidate)
    bar.step(f"downloading source clip for {candidate['id']}")
    source_clip = download_youtube_section(args.youtube_url, args.profile, candidate)
    bar.step(f"preparing captions with {args.caption_source}")
    prepare_production_captions(candidate, source_clip, args, style)
    attribution = args.source_attribution or "Source: Ribath Nouraniyyah Hasyimiyyah"
    renderer = resolve_renderer(args.renderer, args.quality)
    bar.step(f"rendering with {renderer}")
    if renderer == "remotion":
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
    (bar.step if bar else progress)(f"{prefix}preparing captions with {getattr(args, 'caption_source', 'youtube')}")
    prepare_production_captions(candidate, source_clip, args, style)
    renderer = resolve_renderer(renderer, args.quality)
    (bar.step if bar else progress)(f"{prefix}rendering {candidate['id']} with {renderer}")
    if renderer == "remotion":
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


def resolve_renderer(renderer: str, quality: str) -> str:
    if quality == "production" and renderer == "ffmpeg":
        return "remotion"
    return renderer


def prepare_production_captions(candidate: dict[str, Any], source_clip: str, args: argparse.Namespace, style: dict[str, Any]) -> None:
    caption_source = getattr(args, "caption_source", "youtube")
    if caption_source not in {"whisper", "hybrid"}:
        candidate["caption_source"] = caption_source
        return
    asr_path = Path(source_clip).resolve().parents[1] / f"{Path(source_clip).stem}_{args.asr_model}_asr.json"
    prompt = "Allah, Rasulullah, dzikir, zikir, qalbu, sholawat, istighfar, ma'rifat, taubat, syukur"
    words, asr_metadata = load_or_create_asr_words(
        source_clip,
        str(asr_path),
        model_name=args.asr_model,
        language=getattr(args, "speech_language", "id"),
        initial_prompt=prompt,
    )
    words, correction_metadata = correct_asr_words(words)
    captions, composer_metadata = compose_caption_groups(
        words,
        max_words_per_caption=int(style.get("caption", {}).get("max_words_per_caption", 3)),
    )
    if captions:
        candidate["timed_captions"] = captions
        candidate["caption_source"] = "whisper"
        candidate["asr_metadata"] = {**asr_metadata, **correction_metadata, "caption_composer": {**composer_metadata, "low_confidence_word_count": correction_metadata["low_confidence_word_count"]}}
        candidate["caption_corrections"] = correction_metadata
        candidate["score"] = {
            **candidate.get("score", {}),
            "asr_confidence": int(round((composer_metadata.get("avg_word_confidence") or 0.82) * 100)),
            "caption_sync_score": 95 if composer_metadata.get("caption_count", 0) else 0,
        }


def finalize_candidate_metadata(candidate: dict[str, Any], contract: dict[str, Any], output_path: str, args: argparse.Namespace, renderer: str) -> None:
    render_quality = build_render_quality_report(contract, output_path)
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
    load_profile_and_source(conn, args.profile, args.source_id)
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
        genres=parse_genres(args.genres),
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
    profile, _source = load_profile_and_source(conn, args.profile, args.source_id)
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
        genres=parse_genres(args.genres),
    )
    attribution = args.source_attribution or "Source: Ribath Nouraniyyah Hasyimiyyah"
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
    if args.platform != "telegram_channel":
        raise SystemExit("live publishing is currently enabled for telegram_channel only")
    try:
        result = publish_telegram_video(payload)
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


def parse_languages(value: str | None) -> list[str]:
    languages = [item.strip() for item in str(value or "id,en").split(",") if item.strip()]
    return languages or ["id", "en"]


def parse_genres(value: str | None) -> list[str]:
    return normalize_genres(value)


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
    premium_test.add_argument("--renderer", choices=["ffmpeg", "remotion"], default="ffmpeg")
    premium_test.add_argument("--quality", choices=["draft", "production"], default="draft")
    premium_test.add_argument("--caption-source", choices=["youtube", "whisper", "hybrid"], default="youtube")
    premium_test.add_argument("--asr-model", choices=["small", "medium", "large-v3-turbo"], default="medium")
    premium_test.add_argument("--speech-language", default="id", help="Spoken language hint for Whisper/faster-whisper, e.g. id, ar, en")
    premium_test.add_argument("--transcript-languages", default="id,en", help="Comma-separated YouTube transcript preference order")
    duration_choices = ["auto", "under_30s", "seconds_30_60", "minutes_1_3", "minutes_3_plus", "custom", "quick_hit", "standard_short", "deep_context", "platform_max", "30-60s", "45-120s", "60-90s"]
    premium_test.add_argument("--clip-length-preset", choices=duration_choices, default="auto")
    premium_test.add_argument("--clip-min-seconds", type=int, default=20)
    premium_test.add_argument("--clip-max-seconds", type=int, default=180)
    premium_test.add_argument("--genres", default="kajian,spiritual_reflection,advice")
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
    premium_curate.add_argument("--genres", default="kajian,spiritual_reflection,advice")
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
    premium_batch.add_argument("--renderer", choices=["ffmpeg", "remotion"], default="ffmpeg")
    premium_batch.add_argument("--quality", choices=["draft", "production"], default="draft")
    premium_batch.add_argument("--caption-source", choices=["youtube", "whisper", "hybrid"], default="youtube")
    premium_batch.add_argument("--asr-model", choices=["small", "medium", "large-v3-turbo"], default="medium")
    premium_batch.add_argument("--speech-language", default="id", help="Spoken language hint for Whisper/faster-whisper, e.g. id, ar, en")
    premium_batch.add_argument("--transcript-languages", default="id,en", help="Comma-separated YouTube transcript preference order")
    premium_batch.add_argument("--clip-length-preset", choices=duration_choices, default="auto")
    premium_batch.add_argument("--clip-min-seconds", type=int, default=20)
    premium_batch.add_argument("--clip-max-seconds", type=int, default=180)
    premium_batch.add_argument("--genres", default="kajian,spiritual_reflection,advice")
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

    rerender = sub.add_parser("rerender")
    rerender.add_argument("--candidate-id", required=True)
    rerender.add_argument("--renderer", choices=["ffmpeg", "remotion"], default="remotion")
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
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
