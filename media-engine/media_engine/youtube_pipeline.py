"""YouTube transcript and partial-download helpers for local review renders."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .db import ARTIFACTS_DIR
from .rendering import ms_to_timecode


@dataclass(frozen=True)
class TranscriptEntry:
    start_ms: int
    end_ms: int
    text: str


KEYWORDS = (
    "allah",
    "hati",
    "zikir",
    "dzikir",
    "tenang",
    "kesepian",
    "ibadah",
    "amal",
    "dunia",
    "akhirat",
    "taubat",
    "syukur",
    "nikmat",
)


def extract_video_id(url: str) -> str:
    if "youtu.be/" in url:
        return url.split("youtu.be/", 1)[1].split("?", 1)[0].split("/", 1)[0]
    if "/live/" in url:
        return url.split("/live/", 1)[1].split("?", 1)[0].split("/", 1)[0]
    if "v=" in url:
        return url.split("v=", 1)[1].split("&", 1)[0]
    if "/shorts/" in url:
        return url.split("/shorts/", 1)[1].split("?", 1)[0].split("/", 1)[0]
    raise ValueError(f"cannot extract YouTube video id from {url}")


def fetch_youtube_transcript(url: str, languages: list[str] | None = None) -> list[TranscriptEntry]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as exc:
        raise RuntimeError("youtube-transcript-api is required for live YouTube transcript ingestion") from exc

    video_id = extract_video_id(url)
    transcript = YouTubeTranscriptApi().fetch(video_id, languages=languages or ["id", "en"])
    entries: list[TranscriptEntry] = []
    for item in transcript:
        start_ms = int(item.start * 1000)
        end_ms = int((item.start + item.duration) * 1000)
        entries.append(TranscriptEntry(start_ms=start_ms, end_ms=max(end_ms, start_ms + 500), text=item.text.strip()))
    return entries


def choose_nourbit_premium_candidate(profile_id: str, source_id: str, entries: list[TranscriptEntry]) -> dict[str, Any]:
    if len(entries) < 10:
        raise ValueError("transcript is too short for premium candidate selection")

    target_duration_ms = 95_000
    best: tuple[int, int, int, list[TranscriptEntry]] | None = None
    for index, entry in enumerate(entries):
        start_ms = entry.start_ms
        end_ms = start_ms + target_duration_ms
        window = [item for item in entries[index:] if item.start_ms < end_ms]
        if not window:
            continue
        text = " ".join(item.text for item in window)
        lowered = text.lower()
        keyword_score = sum(lowered.count(keyword) for keyword in KEYWORDS)
        length_score = min(len(text) // 120, 12)
        question_score = 3 if "?" in text or "pernahkah" in lowered or "kenapa" in lowered else 0
        score = keyword_score * 3 + length_score + question_score
        if best is None or score > best[0]:
            best = (score, start_ms, window[-1].end_ms, window)

    if best is None:
        raise ValueError("no candidate windows found")

    _score, start_ms, end_ms, window = best
    duration_ms = end_ms - start_ms
    if duration_ms < 90_000:
        end_ms = start_ms + 90_000
    if duration_ms > 150_000:
        end_ms = start_ms + 150_000
        window = [item for item in window if item.start_ms < end_ms]

    span = " ".join(item.text for item in window)
    title = "Allah Tidak Pernah Jauh"
    if "kesepian" in span.lower():
        title = "Kenapa Hati Masih Kesepian?"
    elif "hati" in span.lower() and "tenang" in span.lower():
        title = "Rahasia Hati yang Tenang"

    return {
        "id": f"clip_{uuid.uuid4().hex[:12]}",
        "profile_id": profile_id,
        "source_id": source_id,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "title_hook": title,
        "viral_reason": "Momen ini kuat karena menyentuh keresahan batin dengan jawaban yang sederhana dan mudah direnungkan.",
        "transcript_span": span[:2200],
        "risk_flags": ["public_third_party_review_required"],
        "status": "draft",
    }


def find_ytdlp() -> str:
    preferred = Path("/tmp/media-engine-tools-py313/bin/yt-dlp")
    if preferred.exists():
        return str(preferred)
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        raise RuntimeError("yt-dlp is required for YouTube partial downloads")
    return ytdlp


def download_youtube_section(url: str, profile_id: str, candidate: dict[str, Any]) -> str:
    ytdlp = find_ytdlp()
    out_dir = ARTIFACTS_DIR / profile_id / candidate["id"] / "source"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_template = out_dir / "source_%(id)s.%(ext)s"
    section = f"*{ms_to_timecode(candidate['start_ms'])}-{ms_to_timecode(candidate['end_ms'])}"
    cmd = [
        ytdlp,
        "--download-sections",
        section,
        "-f",
        "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "--merge-output-format",
        "mp4",
        "-o",
        str(output_template),
        url,
    ]
    result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp partial download failed: {result.stderr[-1600:] or result.stdout[-1600:]}")
    matches = sorted(out_dir.glob("source_*.mp4"))
    if not matches:
        raise RuntimeError("yt-dlp finished but no mp4 source clip was produced")
    return str(matches[-1])
