"""YouTube transcript and partial-download helpers for local review renders."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .autonomy import is_duplicate_candidate
from .captions import build_word_timeline, group_word_captions
from .db import ARTIFACTS_DIR, ROOT
from .duration_presets import DurationPreset, duration_prompt_phrase, resolve_duration_strategy
from .genres import (
    GENRE_OPTIONS,
    genre_catalog_labels,
    genre_prompt_phrase,
    genres_is_auto,
    normalize_genres,
    uses_devotional_tone,
    workspace_curation_context,
)
from .llm import LLMError, call_llm_json
from .overlay_copy import overlay_slots_for_candidate
from .rendering import ms_to_timecode
from .scoring import score_candidate_text
from .transcript_quality import correct_transcript_entries, resolve_glossary


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

TITLE_STOPWORDS = {
    "ada",
    "adalah",
    "agar",
    "akan",
    "aku",
    "anda",
    "apa",
    "baik",
    "bahwa",
    "bagi",
    "bisa",
    "dalam",
    "dan",
    "dari",
    "dengan",
    "di",
    "dia",
    "ini",
    "itu",
    "jadi",
    "jika",
    "juga",
    "kalau",
    "kami",
    "kan",
    "karena",
    "ke",
    "kita",
    "lah",
    "lagi",
    "maka",
    "mereka",
    "nah",
    "nggak",
    "tidak",
    "orang",
    "pada",
    "pun",
    "saat",
    "saja",
    "sebagai",
    "sebab",
    "secara",
    "sehingga",
    "seperti",
    "supaya",
    "tapi",
    "telah",
    "terus",
    "untuk",
    "wa",
    "ya",
    "yang",
}

SPECIAL_TITLE_WORDS = {
    "allah": "Allah",
    "rasulullah": "Rasulullah",
    "dzikir": "Dzikir",
    "zikir": "Zikir",
    "qalbu": "Qalbu",
    "hajar": "Hajar",
    "aswad": "Aswad",
}

STATIC_FALLBACK_TITLES = {"allah tidak pernah jauh", "inti nasihat singkat"}

STATIC_FALLBACK_SUBTITLES = {
    "potongan singkat untuk menenangkan hati dan meluruskan arah.",
    "cuplikan reflektif dengan pesan utama yang perlu ditinjau sebelum publish.",
}

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

BLESSING_LITANY_TOKENS = {
    "berkahi",
    "keluarga",
    "pasangan",
    "keturunan",
}

ASR_NOISE_TOKENS = {
    "hadratu",
    "qutblah",
    "quthblah",
    "qutb",
    "warfal",
    "hujub",
    "azzahir",
    "allahumma",
    "rabbana",
    "ighfirna",
    "samadaniyatik",
}

LITURGICAL_TOKENS = {
    "allahumma",
    "rabbana",
    "warfal",
    "hujub",
    "hijab",
    "azzahir",
    "batin",
    "annuriyah",
    "azzulmaniyah",
    "subhanahu",
    "wa",
    "taala",
    "salli",
    "salam",
    "rahman",
    "rahim",
}

TOKEN_ALIASES = {
    "hujub": "hijab",
    "hijab": "hijab",
    "azzahir": "zahir",
    "zahir": "zahir",
    "batin": "batin",
    "kenal": "kenal",
    "dunia": "dunia",
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


def humanize_youtube_transcript_error(exc: BaseException) -> str:
    name = exc.__class__.__name__
    text = str(exc or "").strip()
    lower = text.lower()
    if name in {"TranscriptsDisabled"}:
        return "This video has captions disabled on YouTube. Enable subtitles on the channel or use Transcribe from audio."
    if name in {"NoTranscriptFound"}:
        return (
            "No YouTube subtitles are available for this video yet. "
            "Fresh live replays often need 12–48 hours before auto-captions appear. "
            "Try again later or use Transcribe from audio."
        )
    if name in {"VideoUnavailable", "VideoUnplayable", "InvalidVideoId"}:
        return "This video is unavailable to the transcript service. Check the link or try Transcribe from audio."
    if name in {"AgeRestricted"} or "age-restricted" in lower or "confirm your age" in lower:
        return "This video is age-restricted. Export browser cookies or use Transcribe from audio."
    if name in {"IpBlocked", "RequestBlocked", "PoTokenRequired"}:
        return "YouTube blocked automated transcript access. Try again later or use Transcribe from audio."
    if "could not retrieve a transcript" in lower or "no transcript" in lower:
        return (
            "No usable YouTube subtitles were found for this video. "
            "Try again after captions appear on YouTube, or use Transcribe from audio."
        )
    if "github.com/jdepoix/youtube-transcript-api" in lower:
        return (
            "No YouTube subtitles are available for this video yet. "
            "Try again after captions appear on YouTube, or use Transcribe from audio."
        )
    return text[:500] or "Could not fetch YouTube subtitles for this video."


def probe_youtube_transcript(
    video_id: str,
    languages: list[str] | None = None,
) -> dict[str, Any]:
    requested = languages or ["id", "en"]
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            AgeRestricted,
            NoTranscriptFound,
            TranscriptsDisabled,
            VideoUnavailable,
        )
    except ImportError as exc:
        return {
            "status": "unknown",
            "message": "youtube-transcript-api is not installed on the media engine.",
            "languages": [],
            "requested_languages": requested,
            "error": str(exc),
        }

    api = YouTubeTranscriptApi()
    try:
        listing = api.list(video_id)
    except TranscriptsDisabled:
        return {
            "status": "disabled",
            "message": humanize_youtube_transcript_error(TranscriptsDisabled(video_id)),
            "languages": [],
            "requested_languages": requested,
        }
    except NoTranscriptFound:
        return {
            "status": "missing",
            "message": (
                "No YouTube subtitles are available for this video yet. "
                "Fresh live replays often need 12–48 hours before auto-captions appear. "
                "Try again later or use Transcribe from audio."
            ),
            "languages": [],
            "requested_languages": requested,
        }
    except VideoUnavailable:
        return {
            "status": "restricted",
            "message": humanize_youtube_transcript_error(VideoUnavailable(video_id)),
            "languages": [],
            "requested_languages": requested,
        }
    except AgeRestricted:
        return {
            "status": "restricted",
            "message": humanize_youtube_transcript_error(AgeRestricted(video_id)),
            "languages": [],
            "requested_languages": requested,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "unknown",
            "message": humanize_youtube_transcript_error(exc),
            "languages": [],
            "requested_languages": requested,
            "error": exc.__class__.__name__,
        }

    available = []
    for transcript in listing:
        language = str(getattr(transcript, "language_code", "") or getattr(transcript, "language", "") or "").strip()
        if language:
            available.append(language)
    if not available:
        return {
            "status": "missing",
            "message": (
                "No YouTube subtitles are available for this video yet. "
                "Fresh live replays often need 12–48 hours before auto-captions appear. "
                "Try again later or use Transcribe from audio."
            ),
            "languages": [],
            "requested_languages": requested,
        }
    return {
        "status": "available",
        "message": "YouTube subtitles are available.",
        "languages": available[:12],
        "requested_languages": requested,
    }


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

    try:
        transcript = YouTubeTranscriptApi().fetch(video_id, languages=requested_languages)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(humanize_youtube_transcript_error(exc)) from exc
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


def _span_words(span: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9']+", span.lower())


def _content_words(span: str) -> list[str]:
    return [word for word in _span_words(span) if word not in TITLE_STOPWORDS and len(word) > 2]


def _normalize_match_token(word: str) -> str:
    token = word.lower().strip("'")
    return TOKEN_ALIASES.get(token, token)


def _is_blessing_litany(clause: str) -> bool:
    words = set(_span_words(clause))
    family = {"keluarga", "pasangan", "keturunan"}
    if "berkahi" in words and words & family:
        return True
    return len(words & family) >= 2


def _is_noisy_asr_text(text: str) -> bool:
    words = set(_span_words(text))
    return bool(words & ASR_NOISE_TOKENS)


def _is_repeated_allah_title(text: str) -> bool:
    return _span_words(text).count("allah") >= 3


def _is_liturgical_clause(clause: str) -> bool:
    words = _span_words(clause)
    if not words:
        return True
    if _is_blessing_litany(clause) or _is_noisy_asr_text(clause):
        return True
    hits = sum(
        1
        for word in words
        if word in LITURGICAL_TOKENS or (word.startswith("al") and len(word) > 4 and word != "allah")
    )
    if hits >= 2 and hits >= max(2, len(words) // 3):
        return True
    lowered = clause.lower()
    if lowered.startswith(("ya allah", "allahumma", "rabbana", "warfal", "hujub")):
        return True
    return False


def _title_case_words(words: list[str]) -> str:
    title_words = [SPECIAL_TITLE_WORDS.get(word, word.capitalize()) for word in words]
    return " ".join(title_words)


def _split_clauses(span: str) -> list[str]:
    text = " ".join(str(span or "").split())
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    clauses: list[str] = []
    for sentence in sentences:
        chunk = sentence.strip()
        if not chunk:
            continue
        parts = re.split(r"[,;:]\s+", chunk)
        clauses.extend(part.strip() for part in parts if part.strip())
    return clauses or [text]


def _title_from_words(words: list[str], min_words: int, max_words: int) -> str:
    if not words:
        return ""
    phrase = words[:max_words]
    if len(phrase) < min_words:
        phrase = (words + words)[:max_words]
        phrase = phrase[: max(min_words, len(words))]
    return _title_case_words(phrase[:max_words])


def _title_window_score(window: list[str], *, question: bool = False, offset: int = 0, total: int = 0) -> int:
    if not window:
        return -10_000
    if _is_blessing_litany(" ".join(window)) or _is_repeated_allah_title(" ".join(window)):
        return -10_000
    score = len(set(window))
    if window[0] in HOOK_START_WORDS and window[0] != "allah":
        score += 8
    unique_keywords = {word for word in window if word in KEYWORDS}
    score += len(unique_keywords) * 4
    score += sum(4 for word in ("kenal", "berjumpa", "rasulullah") if word in window)
    score -= sum(1 for word in window if word in LITURGICAL_TOKENS) * 4
    score -= window.count("allah") * 2 if window.count("allah") > 1 else 0
    score -= sum(1 for word in window if word in BLESSING_LITANY_TOKENS) * 6
    if question:
        score += 6
    if total >= 16:
        score += min(offset // 4, 4)
    return score


def _best_title_phrase(span: str, min_words: int = 4, max_words: int = 8) -> str:
    clauses = _split_clauses(span)
    if not clauses:
        return "Inti Nasihat Singkat"

    usable = [clause for clause in clauses if not _is_liturgical_clause(clause)] or clauses

    question_best = ""
    question_score = -10_000
    for clause in usable:
        if "?" not in clause:
            continue
        words = _content_words(clause.replace("?", ""))
        title = _title_from_words(words, min_words, max_words)
        if not title:
            continue
        score = _title_window_score(words[:max_words], question=True)
        if score > question_score:
            question_score = score
            question_best = title if title.endswith("?") else f"{title}?"
    if question_best:
        return question_best

    words = _content_words(" ".join(usable))
    if not words:
        return "Inti Nasihat Singkat"
    deduped: list[str] = []
    for word in words:
        if not deduped or deduped[-1] != word:
            deduped.append(word)
    best_window = deduped[:max_words]
    best_score = -10_000
    for index in range(len(deduped)):
        window = deduped[index : index + max_words]
        if len(window) < min_words:
            break
        score = _title_window_score(window, offset=index, total=len(deduped))
        if score > best_score:
            best_score = score
            best_window = window
    return _title_from_words(best_window, min_words, max_words)


def _trim_hook_words(text: str, max_words: int = 18) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(",;:") + "…"


def title_for_span(span: str) -> str:
    return _best_title_phrase(span)


def _finish_subtitle(text: str) -> str:
    subtitle = _trim_hook_words(text.strip())
    if not subtitle:
        return ""
    if not subtitle.endswith((".", "!", "?", "…")):
        subtitle += "."
    return subtitle[0].upper() + subtitle[1:]


def hook_subtitle_for_span(span: str, title: str) -> str:
    clauses = _split_clauses(span)
    usable = [clause for clause in clauses if not _is_liturgical_clause(clause)]
    source_clauses = usable or clauses
    title_l = title.strip().lower().rstrip("?")

    ranked = sorted(
        source_clauses,
        key=lambda clause: (
            0 if title_l and title_l in clause.lower() else 1,
            len(_content_words(clause)),
        ),
        reverse=True,
    )
    for clause in ranked:
        if title_l and title_l in clause.lower() and len(source_clauses) > 1:
            continue
        if _is_blessing_litany(clause) or _is_noisy_asr_text(clause) or _is_repeated_allah_title(clause):
            continue
        if len(_content_words(clause)) < 4:
            continue
        finished = _finish_subtitle(clause)
        if finished:
            return finished

    words = _content_words(" ".join(usable) if usable else span)
    title_words = _content_words(title.replace("?", ""))
    tail = words[len(title_words) : len(title_words) + 18]
    if len(tail) >= 5:
        return _finish_subtitle(" ".join(tail))

    if _best_title_phrase(span, min_words=3, max_words=5).lower() == "inti nasihat singkat":
        return "Ringkasan singkat dari isi clip ini. Perlu refresh metadata agar lebih spesifik."
    fallback = _trim_hook_words(" ".join(words[:12]))
    return _finish_subtitle(fallback)


def _title_is_relevant(title: str, span: str) -> bool:
    normalized_title = title.strip().lower()
    if not normalized_title:
        return False
    title_words = [_normalize_match_token(word) for word in _span_words(title) if word not in TITLE_STOPWORDS and len(word) > 2]
    if not title_words:
        return False
    span_word_set = {_normalize_match_token(word) for word in _span_words(span)}
    overlap = sum(1 for word in title_words if word in span_word_set)
    if normalized_title in STATIC_FALLBACK_TITLES and overlap < 2:
        return False
    return overlap >= max(1, min(2, len(title_words) // 2))


def _looks_like_transcript_slice(title: str, span: str) -> bool:
    """Reject LLM hooks that are just a copied stretch of the transcript."""
    normalized_title = " ".join(str(title or "").lower().split())
    normalized_span = " ".join(str(span or "").lower().split())
    if len(normalized_title.split()) < 6 or not normalized_span:
        return False
    return normalized_title in normalized_span


def _subtitle_is_relevant(subtitle: str, span: str) -> bool:
    normalized_subtitle = subtitle.strip().lower()
    if not normalized_subtitle or normalized_subtitle in STATIC_FALLBACK_SUBTITLES:
        return False
    if normalized_subtitle.startswith("ringkasan isi clip:"):
        return False
    subtitle_words = [_normalize_match_token(word) for word in _span_words(subtitle) if word not in TITLE_STOPWORDS and len(word) > 3]
    if not subtitle_words:
        return False
    span_word_set = {_normalize_match_token(word) for word in _span_words(span)}
    return any(word in span_word_set for word in subtitle_words)


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
    pre_refine_window = [item for item in entries if item.start_ms < original_end_ms and item.end_ms > original_start_ms]
    pre_refine_span = " ".join(item.text for item in pre_refine_window)
    relevance_span = pre_refine_span if llm_suggestion else span
    suggested_title = str((llm_suggestion or {}).get("title_hook") or "").strip()
    if (
        suggested_title
        and _title_is_relevant(suggested_title, relevance_span)
        and not _looks_like_transcript_slice(suggested_title, relevance_span)
    ):
        title = suggested_title
        title_source = "llm"
    else:
        title = title_for_span(span)
        title_source = "heuristic_span"
    suggested_subtitle = str((llm_suggestion or {}).get("hook_subtitle") or "").strip()
    if suggested_subtitle and _subtitle_is_relevant(suggested_subtitle, relevance_span):
        hook_subtitle = suggested_subtitle
        subtitle_source = "llm"
    else:
        hook_subtitle = hook_subtitle_for_span(span, title)
        subtitle_source = "heuristic_span"
    suggested_reason = str((llm_suggestion or {}).get("viral_reason") or "").strip()
    reason_key = suggested_reason.casefold()
    copies_hook = reason_key in {hook_subtitle.strip().casefold(), title.strip().casefold()}
    if suggested_reason and not copies_hook and _subtitle_is_relevant(suggested_reason, relevance_span):
        viral_reason = suggested_reason
        reason_source = "llm"
    else:
        from .metadata_refresh import distinct_viral_reason

        viral_reason = distinct_viral_reason(title, hook_subtitle)
        reason_source = "heuristic_reason"
    content_angle = str((llm_suggestion or {}).get("content_angle") or "").strip().lower()
    if content_angle not in GENRE_OPTIONS:
        content_angle = ""
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
        profile_id=profile_id,
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
        "content_angle": content_angle,
        "boundary_confidence": boundary_score,
        "opening_strength": opening_score,
        "title_source": title_source,
        "subtitle_source": subtitle_source,
        "reason_source": reason_source,
    }
    overlay_slots = overlay_slots_for_candidate(
        {"title_hook": title, "hook_subtitle": hook_subtitle},
        llm_suggestion,
    )
    metadata["overlay_slots"] = overlay_slots
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
        "overlay_slots": overlay_slots,
        "caption_source": "youtube_glossary",
        "status": "draft",
    }


def llm_rank_suggestions(
    entries: list[TranscriptEntry],
    count: int,
    provider: str,
    duration_preset: DurationPreset | None = None,
    genres: list[str] | str | None = None,
    profile_id: str | None = None,
    niche: str | None = None,
    workspace_name: str | None = None,
) -> list[dict[str, Any]]:
    if provider == "none":
        return []
    duration_preset = duration_preset or resolve_duration_strategy("auto")
    genres = normalize_genres(genres, profile_id=profile_id, niche=niche)
    auto_angles = genres_is_auto(genres)
    transcript = "\n".join(f"{ms_to_timecode(entry.start_ms)} {entry.text}" for entry in entries[:600])
    system_prompt = (
        "Anda adalah kurator clip pendek. Balas hanya JSON murni dengan key clips. "
        "Setiap clip berisi start_time, end_time, title_hook, hook_subtitle, viral_reason, "
        + (
            "content_angle (pilih satu id dari katalog: story, advice, opinion, explainer, social_commentary, history, tutorial), "
            if auto_angles
            else ""
        )
        + "dan overlay {kicker, headline, subhead, stamp, line_a, line_b} dari transcript clip itu. "
        "Batas karakter overlay: kicker 28, headline 56, subhead 80, stamp 22, line_a 32, line_b 32. "
        "Jangan pakai copy dummy katalog (contoh More clarity, MUSTARD MODE, LEVEL UP, BOOST YOUR BUSINESS). "
        "title_hook harus opini atau ketegangan 4-8 kata, bukan potongan kalimat pertama transkrip. "
        "viral_reason satu kalimat kenapa layak diposting, dan tidak boleh menyalin title atau subtitle. "
        "Tolak momen yang hanya mengulang pembukaan tanpa poin. "
        "Niche dan brand voice datang dari workspace, bukan dari daftar genre kustom."
    )
    angle_line = genre_prompt_phrase(genres)
    context = workspace_curation_context(workspace_name, niche)
    tone = (
        "Utamakan konteks utuh dan hook spiritual/reflektif bila sesuai niche dan sumber. "
        if uses_devotional_tone(genres, profile_id, niche)
        else "Utamakan konteks utuh, opini yang jelas, dan bahasa natural sesuai sumber. Jangan memaksa hook iman/devotional."
    )
    angle_instruction = (
        f"Pilih content_angle terbaik per clip dari katalog ini: {genre_catalog_labels()}. "
        if auto_angles
        else (f"Content angles for this batch: {angle_line}. " if angle_line else "")
    )
    user_prompt = (
        f"Pilih hingga {count} momen terbaik (jangan lebih dari {count}) "
        f"berdurasi {duration_prompt_phrase(duration_preset)} untuk short/reels dari transcript ini. "
        + (f"{context} " if context else "")
        + angle_instruction
        + "Lebih sedikit clip yang utuh lebih baik daripada memaksa kuota. "
        + tone
        + " hook_subtitle harus terasa hangat, singkat, tidak kaku, maksimal 18 kata.\n\n"
        f"{transcript}"
    )
    try:
        payload = call_llm_json(provider, system_prompt, user_prompt)
    except LLMError:
        return []
    clips = payload.get("clips", []) if isinstance(payload, dict) else payload
    return [clip for clip in clips if isinstance(clip, dict)]


def timecode_to_ms(value: str) -> int:
    """Parse LLM timestamps: `HH:MM:SS`, `H:MM:SS`, `MM:SS`, or `M:SS`."""
    raw = (value or "").strip()
    parts = raw.split(":")
    if not raw or len(parts) not in (2, 3):
        raise ValueError(f"invalid timecode: {value}")
    try:
        if len(parts) == 2:
            minutes, seconds = parts
            hours = "0"
        else:
            hours, minutes, seconds = parts
        return int((int(hours) * 3600 + int(minutes) * 60 + float(seconds)) * 1000)
    except ValueError as exc:
        raise ValueError(f"invalid timecode: {value}") from exc


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
    niche: str | None = None,
    workspace_name: str | None = None,
) -> list[dict[str, Any]]:
    if len(entries) < 10:
        raise ValueError("transcript is too short for premium candidate selection")
    style = style or {}
    preset = resolve_duration_strategy(duration_preset, clip_min_seconds, clip_max_seconds)
    genres = normalize_genres(genres, profile_id=profile_id, niche=niche)
    corrected_entries = correct_transcript_entries(entries, resolve_glossary(profile_id=profile_id, niche=niche or ""))
    llm_suggestions = llm_rank_suggestions(
        corrected_entries,
        count,
        llm_provider,
        preset,
        genres,
        profile_id=profile_id,
        niche=niche,
        workspace_name=workspace_name,
    )
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
        raise ValueError(
            "Couldn't find a usable clip in this video. "
            "Try a longer source or a looser duration range. Clip count is a maximum, not a quota."
        )
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
    runtime_hint = os.environ.get("MEDIA_ENGINE_YTDLP", "").strip()
    if runtime_hint and Path(runtime_hint).exists() and os.access(runtime_hint, os.X_OK):
        return runtime_hint
    preferred_paths = [
        ROOT / ".venv-tools" / "bin" / "yt-dlp",
        Path("/tmp/media-engine-tools-py313/bin/yt-dlp"),
    ]
    runtime_python_bin = Path(sys.executable).resolve().parent
    preferred_paths.insert(0, runtime_python_bin / "yt-dlp")
    preferred_paths.insert(0, runtime_python_bin / "yt_dlp")
    media_engine_python = os.environ.get("MEDIA_ENGINE_PYTHON")
    if media_engine_python:
        preferred_paths.insert(0, Path(media_engine_python).resolve().parent / "yt-dlp")
        preferred_paths.insert(0, Path(media_engine_python).resolve().parent / "yt_dlp")
    for preferred in preferred_paths:
        if preferred.exists() and os.access(preferred, os.X_OK):
            return str(preferred)
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        ytdlp = shutil.which("yt_dlp")
    if not ytdlp:
        raise RuntimeError("yt-dlp is required for YouTube partial downloads")
    return ytdlp


def humanize_youtube_download_error(stderr: str) -> str:
    """Operator-facing download failure (Create UI), not raw ffmpeg/yt-dlp noise."""
    text = (stderr or "").strip()
    lower = text.lower()
    if "403" in lower or "forbidden" in lower or "access denied" in lower:
        return (
            "YouTube blocked the clip download (HTTP 403). "
            "Update yt-dlp in media-engine/.venv-tools, or set MEDIA_ENGINE_YTDLP_COOKIES "
            "to a cookies.txt export from a signed-in browser, then retry."
        )
    if "sign in" in lower or "confirm your age" in lower or "age-restricted" in lower:
        return (
            "This video is restricted. Set MEDIA_ENGINE_YTDLP_COOKIES to a signed-in "
            "browser cookies.txt and retry."
        )
    if "private video" in lower:
        return "This video is private, so it can’t be downloaded."
    if "video unavailable" in lower:
        return "This video is unavailable."
    cleaned = re.sub(r"\s+", " ", text)[-400:]
    if cleaned:
        return f"YouTube clip download failed: {cleaned}"
    return "YouTube clip download failed."


def _ytdlp_cookies_path() -> str:
    return (
        os.environ.get("MEDIA_ENGINE_YTDLP_COOKIES", "").strip()
        or os.environ.get("YTDLP_COOKIES", "").strip()
    )


PREFERRED_SOURCE_MIN_HEIGHT = 720


def _ffprobe_bin() -> str | None:
    path = shutil.which("ffprobe")
    if path:
        return path
    for candidate in (Path("/opt/homebrew/bin/ffprobe"), Path("/usr/local/bin/ffprobe"), Path("/usr/bin/ffprobe")):
        if candidate.exists():
            return str(candidate)
    return None


def probe_video_height(path: str | Path) -> int | None:
    ffprobe = _ffprobe_bin()
    if not ffprobe:
        return None
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=height",
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        height = int((result.stdout or "").strip().splitlines()[0])
    except (ValueError, IndexError):
        return None
    return height if height > 0 else None


def _ffmpeg_bin() -> str | None:
    path = shutil.which("ffmpeg")
    if path:
        return path
    for candidate in (Path("/opt/homebrew/bin/ffmpeg"), Path("/usr/local/bin/ffmpeg"), Path("/usr/bin/ffmpeg")):
        if candidate.exists():
            return str(candidate)
    return None


def _yt_dlp_path_prefixes() -> list[str]:
    prefixes = [
        "/opt/homebrew/opt/node/bin",
        "/opt/homebrew/opt/node@24/bin",
        "/opt/homebrew/bin",
        "/usr/local/bin",
    ]
    return [item for item in prefixes if Path(item).is_dir()]


def _yt_dlp_tool_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = ":".join([*_yt_dlp_path_prefixes(), env.get("PATH", "")])
    return env


def _resolve_js_runtime(name: str) -> str:
    which_found = shutil.which(name, path=_yt_dlp_tool_env().get("PATH", ""))
    if which_found:
        return which_found
    for prefix in _yt_dlp_path_prefixes():
        candidate = Path(prefix) / name
        if candidate.exists():
            return str(candidate)
    return ""


def _yt_dlp_js_runtime_args() -> list[str]:
    args: list[str] = []
    for name in ("deno", "node"):
        found = _resolve_js_runtime(name)
        if found:
            args.extend(["--js-runtimes", f"{name}:{found}"])
    return args


HD_SOURCE_FORMAT = (
    "bestvideo[height>=720][height<=1080][vcodec^=avc1]+bestaudio[ext=m4a]/"
    "bestvideo[height>=720][height<=1080]+bestaudio/"
    "best[height>=720]"
)


def _download_section_attempts() -> list[dict[str, str]]:
    """Default yt-dlp clients (visionos/tv) still serve DASH 720p/1080p.

    android / android_vr HTTPS formats now need a GVS PO token; without it
    those clients only expose progressive itag 18 (360p). Keep 360p last.
    """
    return [
        {"format": HD_SOURCE_FORMAT, "extractor_args": ""},
        {
            "format": HD_SOURCE_FORMAT,
            "extractor_args": "youtube:player_client=tv,visionos,mweb",
        },
        {
            "format": HD_SOURCE_FORMAT,
            "extractor_args": "youtube:player_client=android_vr",
        },
        {
            "format": "18/best[height<=480]/best",
            "extractor_args": "youtube:player_client=android",
        },
    ]


def _stamp_source_probe(candidate: dict[str, Any], path: str) -> int | None:
    height = probe_video_height(path)
    candidate["source_height"] = height
    if height is not None and height < PREFERRED_SOURCE_MIN_HEIGHT:
        print(
            f"[media-engine] source clip is {height}p (wanted ≥{PREFERRED_SOURCE_MIN_HEIGHT}p). "
            "Export will look soft. Set MEDIA_ENGINE_YTDLP_COOKIES to a signed-in browser cookies.txt "
            "and retry generate.",
            file=sys.stderr,
        )
    return height


def _clear_section_outputs(out_dir: Path) -> None:
    for stale in out_dir.glob("source_*.*"):
        try:
            stale.unlink()
        except OSError:
            pass


def download_youtube_section(url: str, profile_id: str, candidate: dict[str, Any]) -> str:
    ytdlp = find_ytdlp()
    out_dir = ARTIFACTS_DIR / profile_id / candidate["id"] / "source"
    out_dir.mkdir(parents=True, exist_ok=True)
    _clear_section_outputs(out_dir)
    output_template = out_dir / "source_%(id)s.%(ext)s"
    section = f"*{ms_to_timecode(candidate['start_ms'])}-{ms_to_timecode(candidate['end_ms'])}"
    cookies = _ytdlp_cookies_path()
    last_stderr = ""
    attempts = _download_section_attempts()
    last_usable = ""
    ffmpeg = _ffmpeg_bin()
    js_args = _yt_dlp_js_runtime_args()
    tool_env = _yt_dlp_tool_env()
    for index, attempt in enumerate(attempts):
        cmd = [
            ytdlp,
            "--no-update",
            "--download-sections",
            section,
            "-f",
            attempt["format"],
            "--merge-output-format",
            "mp4",
            "-o",
            str(output_template),
        ]
        extractor_args = (attempt.get("extractor_args") or "").strip()
        if extractor_args:
            cmd.extend(["--extractor-args", extractor_args])
        if ffmpeg:
            cmd.extend(["--ffmpeg-location", ffmpeg])
        cmd.extend(js_args)
        if cookies and Path(cookies).is_file():
            cmd.extend(["--cookies", cookies])
        cmd.append(url)
        before = {path.resolve() for path in out_dir.glob("source_*.mp4")}
        result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=tool_env)
        combined = f"{result.stderr or ''}\n{result.stdout or ''}"
        last_stderr = combined
        if result.returncode == 0:
            matches = list(out_dir.glob("source_*.mp4"))
            created = [path for path in matches if path.resolve() not in before]
            chosen = created or matches
            if not chosen:
                last_stderr = combined + "\nyt-dlp finished but no mp4 source clip was produced"
                continue
            path = str(max(chosen, key=lambda item: item.stat().st_mtime))
            last_usable = path
            height = _stamp_source_probe(candidate, path)
            remaining = index < len(attempts) - 1
            if remaining and (height is None or height < PREFERRED_SOURCE_MIN_HEIGHT):
                continue
            return path
        lower = combined.lower()
        if "403" in lower or "forbidden" in lower or "access denied" in lower:
            continue
        if "requested format is not available" in lower or "format is not available" in lower:
            continue
        if last_usable:
            _stamp_source_probe(candidate, last_usable)
            return last_usable
        continue
    if last_usable:
        _stamp_source_probe(candidate, last_usable)
        return last_usable
    raise RuntimeError(humanize_youtube_download_error(last_stderr))


def download_youtube_media_for_transcription(url: str, profile_id: str, video_id: str) -> str:
    """Download source media for Whisper curation when YouTube captions are missing."""
    ytdlp = find_ytdlp()
    out_dir = ARTIFACTS_DIR / profile_id / "_cache" / "curation_asr" / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("source.*"):
        try:
            stale.unlink()
        except OSError:
            pass
    output_template = out_dir / "source.%(ext)s"
    cookies = _ytdlp_cookies_path()
    ffmpeg = _ffmpeg_bin()
    js_args = _yt_dlp_js_runtime_args()
    tool_env = _yt_dlp_tool_env()
    cmd = [
        ytdlp,
        "--no-update",
        "-f",
        "bestaudio[ext=m4a]/bestaudio/best[height<=720]/best",
        "--merge-output-format",
        "m4a",
        "-o",
        str(output_template),
    ]
    cmd.extend(js_args)
    if ffmpeg:
        cmd.extend(["--ffmpeg-location", ffmpeg])
    if cookies and Path(cookies).is_file():
        cmd.extend(["--cookies", cookies])
    cmd.append(url)
    result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=tool_env)
    if result.returncode != 0:
        raise RuntimeError(humanize_youtube_download_error(f"{result.stderr or ''}\n{result.stdout or ''}"))
    matches = sorted(out_dir.glob("source.*"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not matches:
        raise RuntimeError("Download finished but no source media file was created.")
    return str(matches[0])


def fetch_curation_transcript_entries(
    url: str,
    *,
    languages: list[str] | None,
    curation_source: str = "youtube",
    profile_id: str = "nourbit",
    asr_model: str = "medium",
    speech_language: str = "auto",
    niche: str = "",
) -> tuple[list[TranscriptEntry], dict[str, Any]]:
    """Resolve clip-curation transcript from YouTube captions or local Whisper ASR."""
    from .asr import load_or_create_asr_words
    from .caption_pipeline import asr_initial_prompt
    from .ingest_longform import words_to_transcript_entries

    mode = (curation_source or "youtube").strip().lower()
    if mode not in {"youtube", "audio", "auto"}:
        mode = "youtube"
    requested_languages = languages or ["id", "en"]
    meta: dict[str, Any] = {"curation_source": mode, "requested_languages": requested_languages}

    if mode in {"youtube", "auto"}:
        try:
            entries = fetch_youtube_transcript(url, languages=requested_languages)
            if entries:
                meta["resolved_via"] = "youtube"
                return entries, meta
        except RuntimeError as exc:
            meta["youtube_error"] = str(exc)
            if mode == "youtube":
                raise

    video_id = extract_video_id(url)
    meta["resolved_via"] = "audio"
    media_path = download_youtube_media_for_transcription(url, profile_id, video_id)
    cache_json = ARTIFACTS_DIR / profile_id / "_cache" / "curation_asr" / video_id / f"{asr_model}_{speech_language}_words.json"
    prompt = asr_initial_prompt(None, niche=niche, profile_id=profile_id, source_title="", source_channel="")
    words, asr_meta = load_or_create_asr_words(
        media_path,
        str(cache_json),
        model_name=asr_model,
        language=speech_language,
        initial_prompt=prompt,
    )
    entries = words_to_transcript_entries(words)
    if len(entries) < 10:
        raise RuntimeError(
            "Audio transcription was too short to pick clip candidates. "
            "Try a longer source video or wait for YouTube subtitles."
        )
    meta["asr"] = asr_meta
    meta["media_path"] = media_path
    return entries, meta
