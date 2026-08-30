"""Ingest external long-form MP4 (HeyGen CDN / local) into Review (+ optional shorts curation).

Path A delivery step: after Cursor + HeyGen MCP generates a video, land it in Otonom
without OpusClip-style glue work. Does not auto-approve or auto-publish.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse
from urllib.request import urlretrieve

from .asr import load_or_create_asr_words
from .db import (
    ARTIFACTS_DIR,
    DEFAULT_DB,
    DEFAULT_WORKSPACE_PROFILE_ID,
    connect,
    ensure_media_profile,
    ensure_source_manifest,
    initialize,
)
from .explainer_stitch import probe_duration_seconds
from .metadata_refresh import available_metadata_provider, enrich_candidate_metadata
from .youtube_pipeline import TranscriptEntry, choose_nourbit_premium_candidates

IngestMode = Literal["review_only", "clip_batch"]


def _ffmpeg_bin() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    for candidate in (Path("/opt/homebrew/bin/ffmpeg"), Path("/usr/local/bin/ffmpeg")):
        if candidate.exists():
            return str(candidate)
    raise RuntimeError("ffmpeg is required for long-form ingest")


def _job_id() -> str:
    return f"ingest_{uuid.uuid4().hex[:12]}"


def materialize_longform_source(
    source: str,
    *,
    profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID,
    job_id: str | None = None,
) -> tuple[str, Path, str]:
    """Download or copy source into artifacts. Returns (job_id, local_mp4, canonical_source)."""
    source = (source or "").strip()
    if not source:
        raise ValueError("source path or URL is required")

    job_id = job_id or _job_id()
    root = ARTIFACTS_DIR / profile_id / "ingest" / job_id
    root.mkdir(parents=True, exist_ok=True)
    dest = root / "source.mp4"

    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        urlretrieve(source, dest)  # noqa: S310 — operator-controlled CDN / HeyGen URLs
        canonical = source
    else:
        src_path = Path(source).expanduser().resolve()
        if not src_path.exists():
            raise FileNotFoundError(f"source not found: {src_path}")
        if src_path.suffix.lower() not in {".mp4", ".mov", ".webm", ".mkv", ".m4v"}:
            raise ValueError("source must be a video file (mp4/mov/webm/mkv)")
        shutil.copy2(src_path, dest)
        canonical = str(src_path)

    if dest.stat().st_size < 1000:
        raise RuntimeError("downloaded/copied source is empty or too small")

    (root / "manifest.json").write_text(
        json.dumps({"job_id": job_id, "source": canonical, "path": str(dest)}, indent=2),
        encoding="utf-8",
    )
    return job_id, dest, canonical


def _cut_section(source: Path, output: Path, start_ms: int, end_ms: int) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    start_s = max(0.0, start_ms / 1000)
    duration_s = max(0.2, (end_ms - start_ms) / 1000)
    cmd = [
        _ffmpeg_bin(),
        "-y",
        "-ss",
        f"{start_s:.3f}",
        "-i",
        str(source),
        "-t",
        f"{duration_s:.3f}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output),
    ]
    result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg cut failed: {result.stderr[-1200:]}")
    return output


def _words_to_transcript_entries(words: list[dict[str, Any]]) -> list[TranscriptEntry]:
    entries: list[TranscriptEntry] = []
    bucket: list[dict[str, Any]] = []
    bucket_start = 0
    for word in words:
        if not bucket:
            bucket_start = int(word.get("startMs") or 0)
        bucket.append(word)
        end_ms = int(word.get("endMs") or bucket_start)
        # ~2.5s buckets approximate YouTube caption lines
        if end_ms - bucket_start >= 2500 or len(bucket) >= 12:
            text = " ".join(str(w.get("text") or "").strip() for w in bucket).strip()
            if text:
                entries.append(TranscriptEntry(start_ms=bucket_start, end_ms=end_ms, text=text))
            bucket = []
    if bucket:
        end_ms = int(bucket[-1].get("endMs") or bucket_start)
        text = " ".join(str(w.get("text") or "").strip() for w in bucket).strip()
        if text:
            entries.append(TranscriptEntry(start_ms=bucket_start, end_ms=max(bucket_start + 40, end_ms), text=text))
    return entries


def _insert_candidate_and_render(
    conn,
    *,
    candidate_id: str,
    profile_id: str,
    source_id: str,
    title: str,
    subtitle: str,
    viral_reason: str,
    transcript: str,
    start_ms: int,
    end_ms: int,
    output_path: Path,
    caption_source: str,
    kind: str,
    extra_meta: dict[str, Any] | None = None,
) -> None:
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
            start_ms,
            end_ms,
            title[:200],
            subtitle[:200],
            viral_reason,
            transcript[:4000],
            "[]",
            json.dumps({"ingest": True}, ensure_ascii=False),
            json.dumps({"kind": kind, **(extra_meta or {})}, ensure_ascii=False),
            caption_source,
            "{}",
            json.dumps(
                {
                    "output_path": str(output_path),
                    "renderer": "ingest_longform",
                    "duration_ms": max(0, end_ms - start_ms),
                },
                ensure_ascii=False,
            ),
            "{}",
            "{}",
            "{}",
            f"ingest:{candidate_id}",
            "",
            "rendered",
        ),
    )
    preset = "explainer_long_16_9" if kind == "longform_ingest" else "standard_short"
    conn.execute(
        """
        INSERT OR REPLACE INTO render_jobs
          (id, candidate_id, preset, crop_strategy, caption_style, status, output_path, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"render_{candidate_id}",
            candidate_id,
            preset,
            "none",
            caption_source,
            "rendered",
            str(output_path),
            json.dumps({"kind": kind, "title": title}, ensure_ascii=False),
        ),
    )


def clip_batch_from_local_path(
    *,
    local_path: str | Path,
    profile_id: str,
    source_id: str,
    title: str = "",
    count: int = 5,
    language: str = "id",
    db_path: str | Path = DEFAULT_DB,
    parent_candidate_id: str | None = None,
    job_id: str | None = None,
    conn=None,
) -> dict[str, Any]:
    """Cut short candidates from an on-disk long-form file into Review."""
    local_path = Path(local_path).expanduser().resolve()
    if not local_path.exists():
        raise FileNotFoundError(f"source not found: {local_path}")

    owns_conn = conn is None
    if owns_conn:
        conn = connect(db_path)
        initialize(conn)
        ensure_media_profile(conn, profile_id)

    profile_row = conn.execute("SELECT niche, name FROM media_profiles WHERE id = ?", (profile_id,)).fetchone()
    niche = str(profile_row["niche"] or "") if profile_row else ""
    workspace_name = str(profile_row["name"] or "") if profile_row else ""
    llm_provider = available_metadata_provider("deepseek")

    batch_job_id = (job_id or "").strip() or _job_id()
    cache_root = ARTIFACTS_DIR / profile_id / "ingest" / batch_job_id
    cache = cache_root / "asr_words.json"
    words, asr_meta = load_or_create_asr_words(str(local_path), str(cache), language=language)
    entries = _words_to_transcript_entries(words)
    if len(entries) < 10:
        raise ValueError("transcript too short for clip_batch — try a longer video or publish to YouTube first")

    curated = choose_nourbit_premium_candidates(
        profile_id,
        source_id,
        entries,
        count=max(1, min(int(count), 12)),
        llm_provider=llm_provider if llm_provider != "none" else "none",
        duration_preset="standard_short",
        niche=niche,
        workspace_name=workspace_name,
    )
    for cand in curated:
        enrich_candidate_metadata(
            cand,
            llm_provider=llm_provider,
            workspace_id=profile_id,
            niche=niche,
            workspace_name=workspace_name,
        )
    clips_dir = cache_root / "clips"
    candidate_ids: list[str] = []
    parent_meta = {"parent_candidate_id": parent_candidate_id} if parent_candidate_id else {}
    for index, cand in enumerate(curated, start=1):
        cid = str(cand.get("id") or f"cand_{batch_job_id}_{index:02d}")
        out = clips_dir / f"{cid}.mp4"
        _cut_section(local_path, out, int(cand["start_ms"]), int(cand["end_ms"]))
        _insert_candidate_and_render(
            conn,
            candidate_id=cid,
            profile_id=profile_id,
            source_id=source_id,
            title=str(cand.get("title_hook") or title or f"Clip {index}"),
            subtitle=str(cand.get("hook_subtitle") or "Short from long-form"),
            viral_reason=str(cand.get("viral_reason") or "longform_shorts"),
            transcript=str(cand.get("transcript_span") or ""),
            start_ms=int(cand["start_ms"]),
            end_ms=int(cand["end_ms"]),
            output_path=out,
            caption_source="whisper",
            kind="ingest_clip",
            extra_meta={
                "job_id": batch_job_id,
                "asr": asr_meta,
                "path_a": bool(parent_meta),
                "shorts_from_longform": True,
                **parent_meta,
            },
        )
        candidate_ids.append(cid)

    if owns_conn:
        conn.commit()
    return {
        "ok": True,
        "candidate_ids": candidate_ids,
        "source_id": source_id,
        "job_id": batch_job_id,
        "local_path": str(local_path),
    }


def ingest_longform(
    *,
    source: str,
    mode: IngestMode = "review_only",
    title: str = "",
    profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID,
    count: int = 5,
    language: str = "id",
    db_path: str | Path = DEFAULT_DB,
) -> dict[str, Any]:
    """
    Materialize long-form media and register Review candidate(s).

    mode=review_only — whole file as one long-form candidate (Path A default).
    mode=clip_batch — Whisper + heuristic/LLM-free curation → cut shorts into Review.
    """
    if mode not in {"review_only", "clip_batch"}:
        raise ValueError("mode must be review_only or clip_batch")

    conn = connect(db_path)
    initialize(conn)
    ensure_media_profile(conn, profile_id)

    job_id, local_path, canonical = materialize_longform_source(source, profile_id=profile_id)
    duration_s = probe_duration_seconds(local_path)
    end_ms = max(1000, int(duration_s * 1000))
    display_title = (title or Path(urlparse(canonical).path).name or "Long-form ingest").strip() or "Long-form ingest"
    source_id = f"ingest_{job_id}"
    ensure_source_manifest(
        conn,
        profile_id=profile_id,
        source_id=source_id,
        source_url=canonical if canonical.startswith("http") else f"file://{canonical}",
    )

    candidate_ids: list[str] = []

    if mode == "review_only":
        candidate_id = f"cand_{job_id}"
        _insert_candidate_and_render(
            conn,
            candidate_id=candidate_id,
            profile_id=profile_id,
            source_id=source_id,
            title=display_title,
            subtitle="Path A long-form ingest (HeyGen / external MP4)",
            viral_reason="operator ingest_longform",
            transcript=display_title,
            start_ms=0,
            end_ms=end_ms,
            output_path=local_path,
            caption_source="ingest_longform",
            kind="longform_ingest",
            extra_meta={"job_id": job_id, "path_a": True},
        )
        candidate_ids.append(candidate_id)
    else:
        batch = clip_batch_from_local_path(
            local_path=local_path,
            profile_id=profile_id,
            source_id=source_id,
            title=display_title,
            count=count,
            language=language,
            db_path=db_path,
            job_id=job_id,
            conn=conn,
        )
        candidate_ids.extend(batch["candidate_ids"])

    conn.commit()
    return {
        "ok": True,
        "job_id": job_id,
        "mode": mode,
        "profile_id": profile_id,
        "source_id": source_id,
        "source": canonical,
        "local_path": str(local_path),
        "duration_seconds": duration_s,
        "title": display_title,
        "candidate_ids": candidate_ids,
        "status": "rendered",
        "note": "Approve in Review, then schedule/publish. No auto-publish.",
    }
