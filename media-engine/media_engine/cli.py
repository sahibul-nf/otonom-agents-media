#!/usr/bin/env python3
"""Command-line entry point for the local autonomous media engine."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .curation import SAMPLE_NOURBIT_TRANSCRIPT, curate_dry_run
from .db import DEFAULT_DB, ROOT, connect, fetch_all, fetch_one, initialize, load_json, seed_profile, seed_source
from .models import PUBLISH_MODES, RIGHTS_MODES, require_choice
from .publishers import create_dry_run_attempt
from .rendering import PREMIUM_PRESET, render_minimal_ffmpeg, render_premium_ffmpeg, render_premium_remotion
from .styles import load_style
from .youtube_pipeline import choose_nourbit_premium_candidate, download_youtube_section, fetch_youtube_transcript


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


def cmd_premium_test(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    initialize(conn)
    profile = fetch_one(conn, "SELECT * FROM media_profiles WHERE id = ?", (args.profile,))
    if not profile:
        seed_profile(conn, load_json(ROOT / "profiles" / "nourbit.json"))
        profile = fetch_one(conn, "SELECT * FROM media_profiles WHERE id = ?", (args.profile,))
    source = fetch_one(conn, "SELECT * FROM source_manifests WHERE id = ?", (args.source_id,))
    if not source:
        seed_source(conn, load_json(ROOT / "sources" / "nourbit_nouraniyyahofficial.json"))
        source = fetch_one(conn, "SELECT * FROM source_manifests WHERE id = ?", (args.source_id,))
    if not profile or not source:
        raise SystemExit("profile/source seed failed")

    entries = fetch_youtube_transcript(args.youtube_url, languages=["id"])
    style = load_style(args.style)
    candidate = choose_nourbit_premium_candidate(args.profile, args.source_id, entries, style)
    insert_candidate(conn, candidate)
    source_clip = download_youtube_section(args.youtube_url, args.profile, candidate)
    attribution = args.source_attribution or "Source: Ribath Nouraniyyah Hasyimiyyah"
    if args.renderer == "remotion":
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
    conn.commit()
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
    premium_test.add_argument("--style", help="Path to a JSON style override. Defaults to profiles/nourbit_opus_style.json")
    premium_test.set_defaults(func=cmd_premium_test)

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
