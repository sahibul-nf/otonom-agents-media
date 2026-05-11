"""YouTube transcript and partial-download helpers for local review renders."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .captions import build_word_timeline, group_word_captions
from .db import ARTIFACTS_DIR
from .llm import LLMError, call_llm_json
from .rendering import ms_to_timecode
from .scoring import score_candidate_text
from .transcript_quality import correct_transcript_entries


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

MIN_PREMIUM_DURATION_MS = 45_000
TARGET_PREMIUM_DURATION_MS = 95_000
MAX_PREMIUM_DURATION_MS = 120_000
END_EXTENSION_GRACE_MS = 8_000
RISKY_TERMINAL_WORDS = {
    "agar",
    "atau",
    "bahwa",
    "berarti",
    "dalam",
    "dan",
    "dengan",
    "ini",
    "itu",
    "jadi",
    "kalau",
    "karena",
    "kepada",
    "maka",
    "sebab",
    "sehingga",
    "subhanahu",
    "supaya",
    "untuk",
    "wa",
    "yang",
}


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


def title_for_span(span: str) -> str:
    lowered = span.lower()
    if "kesepian" in lowered:
        return "Kenapa Hati Masih Kesepian?"
    if "hati" in lowered and "tenang" in lowered:
        return "Rahasia Hati yang Tenang"
    if "ibadah" in lowered or "amal" in lowered:
        return "Untuk Siapa Ibadah Kita?"
    return "Allah Tidak Pernah Jauh"


def hook_subtitle_for_span(span: str, title: str) -> str:
    lowered = f"{title} {span}".lower()
    if "kesepian" in lowered:
        return "Saat hati terasa jauh, jawabannya sering lebih dekat dari yang kita kira."
    if "takut" in lowered and ("netizen" in lowered or "allah" in lowered):
        return "Tentang arah takut kita: manusia yang menilai, atau Allah yang melihat."
    if "zikir" in lowered or "dzikir" in lowered:
        return "Satu kalimat zikir yang mengubah cara kita menutup hari."
    if "bahagia" in lowered:
        return "Bahagia yang tidak sibuk mencari validasi dari makhluk."
    if "mesra" in lowered or "galak" in lowered:
        return "Cara memandang Allah yang membuat hati lebih pulang."
    if "ibadah" in lowered or "amal" in lowered:
        return "Pengingat lembut tentang niat yang sering diam-diam bergeser."
    return "Potongan singkat untuk menenangkan hati dan meluruskan arah."


def heuristic_window_score(text: str, title: str, duration_ms: int) -> int:
    lowered = text.lower()
    keyword_score = sum(lowered.count(keyword) for keyword in KEYWORDS)
    length_score = min(len(text) // 120, 12)
    question_score = 3 if "?" in text or "pernahkah" in lowered or "kenapa" in lowered else 0
    quality = score_candidate_text(text, title, duration_ms)
    return keyword_score * 3 + length_score + question_score + quality["overall_score"]


def is_non_overlapping(start_ms: int, end_ms: int, selected: list[dict[str, Any]], padding_ms: int = 12_000) -> bool:
    for candidate in selected:
        if start_ms < int(candidate["end_ms"]) + padding_ms and end_ms > int(candidate["start_ms"]) - padding_ms:
            return False
    return True


def _last_word(text: str) -> str:
    return text.strip().lower().strip(".,!?;:()[]{}\"'“”‘’").split()[-1] if text.strip().split() else ""


def refine_end_boundary(entries: list[TranscriptEntry], start_ms: int, end_ms: int) -> int:
    window = [item for item in entries if item.start_ms < end_ms and item.end_ms > start_ms]
    if len(window) < 2:
        return end_ms

    max_end_ms = start_ms + MAX_PREMIUM_DURATION_MS
    crossing_end = [item for item in window if item.end_ms > end_ms]
    risky_tail = _last_word(" ".join(item.text for item in window)) in RISKY_TERMINAL_WORDS
    if crossing_end or risky_tail:
        extended_end_ms = end_ms
        for item in crossing_end:
            extended_end_ms = max(extended_end_ms, item.end_ms)
        if risky_tail and not crossing_end:
            following = [item for item in entries if end_ms <= item.start_ms <= end_ms + END_EXTENSION_GRACE_MS]
            if following:
                extended_end_ms = max(extended_end_ms, following[0].end_ms)
        if extended_end_ms > end_ms and extended_end_ms <= max_end_ms:
            end_ms = extended_end_ms
            window = [item for item in entries if item.start_ms < end_ms and item.end_ms > start_ms]

    last = window[-1]
    last_text = last.text.strip().lower()
    starts_new_thought = last_text.startswith(
        (
            "jadi ",
            "maka ",
            "kalau ",
            "kalo ",
            "nah ",
            "dan ",
            "terus ",
            "kemudian ",
            "sementara ",
            "berikutnya ",
        )
    )
    last_is_late_opener = last.start_ms >= end_ms - 3_500 and starts_new_thought
    last_is_tiny_tail = last.start_ms >= end_ms - 2_000 and len(last_text.split()) <= 5

    previous = window[-2]
    trim_to = previous.end_ms if previous.end_ms > last.start_ms and previous.end_ms <= end_ms else last.start_ms
    refined_end_ms = trim_to if last_is_late_opener or last_is_tiny_tail else end_ms
    if refined_end_ms - start_ms < MIN_PREMIUM_DURATION_MS:
        return end_ms
    return refined_end_ms


def build_candidate(
    profile_id: str,
    source_id: str,
    entries: list[TranscriptEntry],
    start_ms: int,
    end_ms: int,
    score_rank: int,
    style: dict[str, Any],
    llm_provider: str = "none",
    llm_suggestion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    original_end_ms = end_ms
    end_ms = refine_end_boundary(entries, start_ms, end_ms)
    window = [item for item in entries if item.start_ms < end_ms and item.end_ms > start_ms]
    span = " ".join(item.text for item in window)
    title = str((llm_suggestion or {}).get("title_hook") or title_for_span(span))
    hook_subtitle = str((llm_suggestion or {}).get("hook_subtitle") or hook_subtitle_for_span(span, title))
    viral_reason = str(
        (llm_suggestion or {}).get("viral_reason")
        or hook_subtitle
    )
    caption_style = style.get("caption", {})
    ai_style = style.get("ai", {})
    word_timeline = build_word_timeline(
        entries,
        start_ms,
        end_ms,
        remove_filler_words=bool(ai_style.get("remove_filler_words", False)),
    )
    timed_captions = group_word_captions(
        word_timeline,
        max_words_per_caption=int(caption_style.get("max_words_per_caption", 3)),
    )
    score = score_candidate_text(span, title, end_ms - start_ms, rights_risk=True)
    metadata = {
        "rank": score_rank,
        "selector": "heuristic_v2",
        "llm_provider": llm_provider,
        "llm_used": bool(llm_suggestion),
        "window_entry_count": len(window),
        "original_end_ms": original_end_ms,
        "end_refined_ms": end_ms,
    }
    return {
        "id": f"clip_{uuid.uuid4().hex[:12]}",
        "profile_id": profile_id,
        "source_id": source_id,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "title_hook": title,
        "hook_subtitle": hook_subtitle,
        "viral_reason": viral_reason,
        "transcript_span": span[:2200],
        "timed_captions": timed_captions,
        "risk_flags": ["public_third_party_review_required"],
        "score": score,
        "curation_metadata": metadata,
        "caption_source": "youtube_glossary",
        "status": "draft",
    }


def llm_rank_suggestions(entries: list[TranscriptEntry], count: int, provider: str) -> list[dict[str, Any]]:
    if provider == "none":
        return []
    transcript = "\n".join(f"{ms_to_timecode(entry.start_ms)} {entry.text}" for entry in entries[:600])
    system_prompt = (
        "Anda adalah kurator video pendek Nourbit. Balas hanya JSON murni dengan key clips. "
        "Setiap clip berisi start_time, end_time, title_hook, hook_subtitle, viral_reason."
    )
    user_prompt = (
        f"Pilih {count} momen terbaik berdurasi 45-120 detik untuk short/reels dari transcript ini. "
        "Utamakan konteks utuh, hook spiritual/reflektif, dan bahasa Indonesia natural. "
        "hook_subtitle harus terasa hangat, singkat, tidak kaku, maksimal 18 kata.\n\n"
        f"{transcript}"
    )
    try:
        payload = call_llm_json(provider, system_prompt, user_prompt)
    except LLMError:
        return []
    clips = payload.get("clips", []) if isinstance(payload, dict) else payload
    return [clip for clip in clips if isinstance(clip, dict)]


def timecode_to_ms(value: str) -> int:
    parts = value.strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"invalid timecode: {value}")
    hours, minutes, seconds = parts
    return (int(hours) * 3600 + int(minutes) * 60 + int(float(seconds))) * 1000


def choose_nourbit_premium_candidates(
    profile_id: str,
    source_id: str,
    entries: list[TranscriptEntry],
    style: dict[str, Any] | None = None,
    count: int = 5,
    llm_provider: str = "none",
) -> list[dict[str, Any]]:
    if len(entries) < 10:
        raise ValueError("transcript is too short for premium candidate selection")
    style = style or {}
    corrected_entries = correct_transcript_entries(entries)
    llm_suggestions = llm_rank_suggestions(corrected_entries, count, llm_provider)
    selected: list[dict[str, Any]] = []

    for suggestion in llm_suggestions:
        try:
            start_ms = timecode_to_ms(str(suggestion.get("start_time", "")))
            end_ms = timecode_to_ms(str(suggestion.get("end_time", "")))
        except ValueError:
            continue
        duration = end_ms - start_ms
        if duration < MIN_PREMIUM_DURATION_MS or duration > MAX_PREMIUM_DURATION_MS:
            continue
        if not is_non_overlapping(start_ms, end_ms, selected):
            continue
        selected.append(build_candidate(profile_id, source_id, corrected_entries, start_ms, end_ms, len(selected) + 1, style, llm_provider, suggestion))
        if len(selected) >= count:
            return selected

    windows: list[tuple[int, int, int, str]] = []
    step = max(1, len(corrected_entries) // 80)
    for index in range(0, len(corrected_entries), step):
        entry = corrected_entries[index]
        start_ms = entry.start_ms
        end_ms = start_ms + TARGET_PREMIUM_DURATION_MS
        window = [item for item in corrected_entries[index:] if item.start_ms < end_ms]
        if not window:
            continue
        end_ms = min(window[-1].end_ms, start_ms + MAX_PREMIUM_DURATION_MS)
        if end_ms - start_ms < MIN_PREMIUM_DURATION_MS:
            continue
        text = " ".join(item.text for item in window)
        title = title_for_span(text)
        windows.append((heuristic_window_score(text, title, end_ms - start_ms), start_ms, end_ms, text))

    for _score, start_ms, end_ms, _text in sorted(windows, reverse=True):
        if not is_non_overlapping(start_ms, end_ms, selected):
            continue
        selected.append(build_candidate(profile_id, source_id, corrected_entries, start_ms, end_ms, len(selected) + 1, style, llm_provider))
        if len(selected) >= count:
            break

    if not selected:
        raise ValueError("no candidate windows found")
    selected.sort(key=lambda candidate: candidate["score"]["overall_score"], reverse=True)
    for rank, candidate in enumerate(selected, start=1):
        candidate["curation_metadata"]["rank"] = rank
    return selected


def choose_nourbit_premium_candidate(
    profile_id: str,
    source_id: str,
    entries: list[TranscriptEntry],
    style: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return choose_nourbit_premium_candidates(profile_id, source_id, entries, style, count=1)[0]


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
