"""YouTube transcript and partial-download helpers for local review renders."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .autonomy import is_duplicate_candidate
from .captions import build_word_timeline, group_word_captions
from .db import ARTIFACTS_DIR
from .duration_presets import DurationPreset, duration_prompt_phrase, resolve_duration_strategy
from .genres import genre_prompt_phrase, normalize_genres
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
WEAK_STARTERS = {
    "baik",
    "dan",
    "jadi",
    "kalau",
    "kalo",
    "kemudian",
    "maka",
    "nah",
    "terus",
}
HOOK_START_WORDS = {
    "allah",
    "apa",
    "bagaimana",
    "bahagia",
    "hati",
    "jangan",
    "kenapa",
    "mengapa",
    "pernahkah",
    "rahasia",
    "takut",
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


def _transcript_cache_path(video_id: str, languages: list[str]) -> Path:
    safe_languages = "-".join(language.replace("/", "_") for language in languages)
    return ARTIFACTS_DIR / "_cache" / "youtube_transcripts" / f"{video_id}_{safe_languages}.json"


def fetch_youtube_transcript(url: str, languages: list[str] | None = None, use_cache: bool = True) -> list[TranscriptEntry]:
    video_id = extract_video_id(url)
    requested_languages = languages or ["id", "en"]
    cache_path = _transcript_cache_path(video_id, requested_languages)
    if use_cache and cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        return [TranscriptEntry(int(item["start_ms"]), int(item["end_ms"]), str(item["text"])) for item in payload]

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as exc:
        raise RuntimeError("youtube-transcript-api is required for live YouTube transcript ingestion") from exc

    transcript = YouTubeTranscriptApi().fetch(video_id, languages=requested_languages)
    entries: list[TranscriptEntry] = []
    for item in transcript:
        start_ms = int(item.start * 1000)
        end_ms = int((item.start + item.duration) * 1000)
        entries.append(TranscriptEntry(start_ms=start_ms, end_ms=max(end_ms, start_ms + 500), text=item.text.strip()))
    if use_cache:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps([entry.__dict__ for entry in entries], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
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


def heuristic_window_score(text: str, title: str, duration_ms: int, duration_preset: DurationPreset | None = None) -> int:
    lowered = text.lower()
    keyword_score = sum(lowered.count(keyword) for keyword in KEYWORDS)
    length_score = min(len(text) // 120, 12)
    question_score = 3 if "?" in text or "pernahkah" in lowered or "kenapa" in lowered else 0
    duration_preset = duration_preset or resolve_duration_strategy("auto")
    quality = score_candidate_text(
        text,
        title,
        duration_ms,
        ideal_min_ms=duration_preset.min_ms,
        ideal_target_ms=duration_preset.target_ms,
        ideal_max_ms=duration_preset.max_ms,
    )
    return keyword_score * 3 + length_score + question_score + quality["overall_score"]


def is_non_overlapping(start_ms: int, end_ms: int, selected: list[dict[str, Any]], padding_ms: int = 12_000) -> bool:
    for candidate in selected:
        if start_ms < int(candidate["end_ms"]) + padding_ms and end_ms > int(candidate["start_ms"]) - padding_ms:
            return False
    return True


def _last_word(text: str) -> str:
    return text.strip().lower().strip(".,!?;:()[]{}\"'“”‘’").split()[-1] if text.strip().split() else ""


def refine_end_boundary(
    entries: list[TranscriptEntry],
    start_ms: int,
    end_ms: int,
    max_duration_ms: int = MAX_PREMIUM_DURATION_MS,
    min_duration_ms: int = MIN_PREMIUM_DURATION_MS,
) -> int:
    window = [item for item in entries if item.start_ms < end_ms and item.end_ms > start_ms]
    if len(window) < 2:
        return end_ms

    max_end_ms = start_ms + max_duration_ms
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
    if refined_end_ms - start_ms < min_duration_ms:
        return end_ms
    return refined_end_ms


def opening_strength(entries: list[TranscriptEntry], start_ms: int, lookahead_ms: int = 9_000) -> int:
    window = [item for item in entries if start_ms <= item.start_ms < start_ms + lookahead_ms]
    text = " ".join(item.text for item in window[:4]).strip().lower()
    if not text:
        return 35
    first = _last_word(text.split(maxsplit=1)[0])
    score = 56
    if first in WEAK_STARTERS:
        score -= 18
    if any(word in text for word in HOOK_START_WORDS):
        score += 24
    if "?" in text or "pernahkah" in text or "kenapa" in text or "mengapa" in text:
        score += 12
    if len(text.split()) >= 18:
        score += 8
    return max(0, min(100, score))


def refine_start_boundary(
    entries: list[TranscriptEntry],
    start_ms: int,
    end_ms: int,
    min_duration_ms: int = MIN_PREMIUM_DURATION_MS,
    search_ms: int = 14_000,
) -> int:
    current_score = opening_strength(entries, start_ms)
    if current_score >= 86:
        return start_ms
    candidates = [
        item.start_ms
        for item in entries
        if start_ms < item.start_ms <= min(end_ms - min_duration_ms, start_ms + search_ms)
    ]
    best_start = start_ms
    best_score = current_score
    for candidate_start in candidates:
        score = opening_strength(entries, candidate_start)
        if score >= best_score + 14:
            best_start = candidate_start
            best_score = score
    return best_start


def boundary_confidence(entries: list[TranscriptEntry], start_ms: int, end_ms: int, original_end_ms: int) -> int:
    window = [item for item in entries if item.start_ms < end_ms and item.end_ms > start_ms]
    if not window:
        return 35
    text = " ".join(item.text for item in window)
    last = _last_word(text)
    score = 78
    if last in RISKY_TERMINAL_WORDS:
        score -= 28
    if end_ms != original_end_ms:
        score += 8
    if any(text.rstrip().endswith(mark) for mark in (".", "?", "!", "؟")):
        score += 8
    tail = window[-1].text.strip().lower()
    if tail.startswith(("jadi ", "maka ", "kalau ", "nah ", "berikutnya ")):
        score -= 18
    return max(0, min(100, score))


def duration_reason(preset: DurationPreset, duration_ms: int, confidence: int) -> str:
    seconds = round(duration_ms / 1000)
    target = round(preset.target_ms / 1000)
    if confidence >= 85:
        boundary = "clean ending"
    elif confidence >= 65:
        boundary = "acceptable boundary"
    else:
        boundary = "needs review"
    return f"{preset.label} selected {seconds}s near {target}s target with {boundary}."


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
    duration_preset: DurationPreset | None = None,
    genres: list[str] | str | None = None,
) -> dict[str, Any]:
    duration_preset = duration_preset or resolve_duration_strategy("auto")
    genres = normalize_genres(genres)
    original_start_ms = start_ms
    start_ms = refine_start_boundary(entries, start_ms, end_ms, duration_preset.min_ms)
    original_end_ms = end_ms
    end_ms = refine_end_boundary(entries, start_ms, end_ms, duration_preset.max_ms, duration_preset.min_ms)
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
    boundary_score = boundary_confidence(entries, start_ms, end_ms, original_end_ms)
    opening_score = opening_strength(entries, start_ms)
    score = score_candidate_text(
        span,
        title,
        end_ms - start_ms,
        rights_risk=True,
        ideal_min_ms=duration_preset.min_ms,
        ideal_target_ms=duration_preset.target_ms,
        ideal_max_ms=duration_preset.max_ms,
        boundary_confidence=boundary_score,
        opening_strength=opening_score,
    )
    metadata = {
        "rank": score_rank,
        "selector": "heuristic_v2",
        "llm_provider": llm_provider,
        "llm_used": bool(llm_suggestion),
        "window_entry_count": len(window),
        "original_start_ms": original_start_ms,
        "start_refined_ms": start_ms,
        "original_end_ms": original_end_ms,
        "end_refined_ms": end_ms,
        "duration_preset": duration_preset.id,
        "duration_label": duration_preset.label,
        "duration_min_ms": duration_preset.min_ms,
        "duration_target_ms": duration_preset.target_ms,
        "duration_max_ms": duration_preset.max_ms,
        "duration_strategy": "preset_guardrail_with_adaptive_boundary",
        "selected_duration_ms": end_ms - start_ms,
        "duration_reason": duration_reason(duration_preset, end_ms - start_ms, boundary_score),
        "genres": genres,
        "boundary_confidence": boundary_score,
        "opening_strength": opening_score,
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


def llm_rank_suggestions(entries: list[TranscriptEntry], count: int, provider: str, duration_preset: DurationPreset | None = None, genres: list[str] | str | None = None) -> list[dict[str, Any]]:
    if provider == "none":
        return []
    duration_preset = duration_preset or resolve_duration_strategy("auto")
    genres = normalize_genres(genres)
    transcript = "\n".join(f"{ms_to_timecode(entry.start_ms)} {entry.text}" for entry in entries[:600])
    system_prompt = (
        "Anda adalah kurator video pendek Nourbit. Balas hanya JSON murni dengan key clips. "
        "Setiap clip berisi start_time, end_time, title_hook, hook_subtitle, viral_reason."
    )
    user_prompt = (
        f"Pilih {count} momen terbaik berdurasi {duration_prompt_phrase(duration_preset)} untuk short/reels dari transcript ini. "
        f"Prioritaskan genre batch: {genre_prompt_phrase(genres)}. "
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
    duration_preset: str = "auto",
    clip_min_seconds: int | None = None,
    clip_max_seconds: int | None = None,
    genres: list[str] | str | None = None,
) -> list[dict[str, Any]]:
    if len(entries) < 10:
        raise ValueError("transcript is too short for premium candidate selection")
    style = style or {}
    preset = resolve_duration_strategy(duration_preset, clip_min_seconds, clip_max_seconds)
    genres = normalize_genres(genres)
    corrected_entries = correct_transcript_entries(entries)
    llm_suggestions = llm_rank_suggestions(corrected_entries, count, llm_provider, preset, genres)
    selected: list[dict[str, Any]] = []

    for suggestion in llm_suggestions:
        try:
            start_ms = timecode_to_ms(str(suggestion.get("start_time", "")))
            end_ms = timecode_to_ms(str(suggestion.get("end_time", "")))
        except ValueError:
            continue
        duration = end_ms - start_ms
        if duration < preset.min_ms or duration > preset.max_ms:
            continue
        if not is_non_overlapping(start_ms, end_ms, selected):
            continue
        candidate = build_candidate(profile_id, source_id, corrected_entries, start_ms, end_ms, len(selected) + 1, style, llm_provider, suggestion, preset, genres)
        if is_duplicate_candidate(candidate, selected):
            continue
        selected.append(candidate)
        if len(selected) >= count:
            return selected

    windows: list[tuple[int, int, int, str]] = []
    step = max(1, len(corrected_entries) // 80)
    for index in range(0, len(corrected_entries), step):
        entry = corrected_entries[index]
        start_ms = entry.start_ms
        end_ms = start_ms + preset.target_ms
        window = [item for item in corrected_entries[index:] if item.start_ms < end_ms]
        if not window:
            continue
        end_ms = min(window[-1].end_ms, start_ms + preset.max_ms)
        if end_ms - start_ms < preset.min_ms:
            continue
        text = " ".join(item.text for item in window)
        title = title_for_span(text)
        windows.append((heuristic_window_score(text, title, end_ms - start_ms, preset), start_ms, end_ms, text))

    for _score, start_ms, end_ms, _text in sorted(windows, reverse=True):
        if not is_non_overlapping(start_ms, end_ms, selected):
            continue
        candidate = build_candidate(profile_id, source_id, corrected_entries, start_ms, end_ms, len(selected) + 1, style, llm_provider, duration_preset=preset, genres=genres)
        if is_duplicate_candidate(candidate, selected):
            candidate["curation_metadata"]["duplicate_warning"] = True
        selected.append(candidate)
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
