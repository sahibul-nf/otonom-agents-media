"""Resolve / validate YouTube video URLs for Create UI metadata."""

from __future__ import annotations

import re
import subprocess
from typing import Any
from urllib.parse import parse_qs, urlparse

from .youtube_pipeline import find_ytdlp, probe_youtube_transcript

# Soft guidance only — ASR transcript length is still checked later.
SHORT_DURATION_WARNING_SECONDS = 180
VERY_SHORT_DURATION_SECONDS = 60
YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _require_video_id(video_id: str) -> str:
    cleaned = (video_id or "").strip()
    if not cleaned or cleaned in {"watch", "shorts", "live"}:
        raise ValueError("That YouTube link is missing a video id.")
    if not YOUTUBE_VIDEO_ID_RE.fullmatch(cleaned):
        raise ValueError("That YouTube link looks incomplete. Paste the full video URL.")
    return cleaned


def normalize_youtube_video_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        raise ValueError("Paste a YouTube link to continue.")
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower().replace("www.", "")
    if host not in {"youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}:
        raise ValueError("Only YouTube video links are supported.")

    path = parsed.path or ""
    query = parse_qs(parsed.query or "")

    if host == "youtu.be":
        video_id = _require_video_id(path.strip("/").split("/", 1)[0])
        return f"https://www.youtube.com/watch?v={video_id}"

    if path.startswith("/watch"):
        video_id = _require_video_id((query.get("v") or [""])[0])
        return f"https://www.youtube.com/watch?v={video_id}"

    for prefix in ("/shorts/", "/live/", "/embed/", "/v/"):
        if path.startswith(prefix):
            video_id = _require_video_id(path[len(prefix) :].split("/", 1)[0])
            return f"https://www.youtube.com/watch?v={video_id}"

    if path.startswith("/@"):
        raise ValueError("That looks like a channel link. Paste a single video URL, or use Watch YouTube sources.")
    if path.startswith("/channel/") or path.startswith("/c/") or path.startswith("/user/") or path.endswith("/videos"):
        raise ValueError("That looks like a channel link. Paste a single video URL, or use Watch YouTube sources.")
    if "/playlist" in path or ("list=" in (parsed.query or "") and "v=" not in (parsed.query or "")):
        raise ValueError("Playlist links aren’t supported here. Paste a single video URL.")

    raise ValueError("Couldn’t recognize that YouTube video link.")


def _humanize_ytdlp_error(stderr: str) -> str:
    text = (stderr or "").strip()
    lower = text.lower()
    if "incomplete youtube id" in lower or "looks truncated" in lower or "truncated_id" in lower:
        return "That YouTube link looks incomplete. Paste the full video URL."
    if "private video" in lower:
        return "This video is private, so it can’t be used."
    if "video unavailable" in lower or "unavailable" in lower:
        return "This video is unavailable."
    if "sign in" in lower or "confirm your age" in lower or "age-restricted" in lower:
        return "This video is restricted and can’t be resolved automatically."
    if "not a valid url" in lower or "unsupported url" in lower:
        return "That doesn’t look like a valid YouTube video URL."
    # Never surface raw yt-dlp ERROR: lines in the Create UI.
    if text.upper().startswith("ERROR:") or "[youtube" in lower:
        return "Couldn’t resolve this YouTube video. Check the link and try again."
    cleaned = re.sub(r"\s+", " ", text)
    return cleaned[:180] or "Couldn’t resolve this YouTube video."


def resolve_youtube_source(url: str, *, timeout_seconds: int = 45) -> dict[str, Any]:
    """Return structured metadata for a single YouTube video URL."""
    canonical = normalize_youtube_video_url(url)
    ytdlp = find_ytdlp()
    cmd = [
        ytdlp,
        "--skip-download",
        "--no-warnings",
        "--print",
        "%(id)s\t%(title)s\t%(channel)s\t%(uploader)s\t%(duration)s\t%(thumbnail)s\t%(webpage_url)s",
        canonical,
    ]
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=timeout_seconds)
    if completed.returncode != 0:
        raise ValueError(_humanize_ytdlp_error(completed.stderr or completed.stdout or ""))

    line = ""
    for candidate in (completed.stdout or "").splitlines():
        if candidate.strip():
            line = candidate.strip()
            break
    if not line:
        raise ValueError("Couldn’t read metadata for this YouTube video.")

    parts = line.split("\t")
    video_id = (parts[0] if len(parts) > 0 else "").strip()
    title = (parts[1] if len(parts) > 1 else "").strip()
    channel = (parts[2] if len(parts) > 2 else "").strip() or (parts[3] if len(parts) > 3 else "").strip()
    duration_raw = (parts[4] if len(parts) > 4 else "").strip()
    thumbnail = (parts[5] if len(parts) > 5 else "").strip()
    webpage = (parts[6] if len(parts) > 6 else "").strip() or canonical

    if not video_id or video_id in {"NA", "None"}:
        raise ValueError("Couldn’t read a video id from that link.")

    duration_seconds: int | None
    try:
        duration_seconds = int(float(duration_raw)) if duration_raw and duration_raw not in {"NA", "None"} else None
    except ValueError:
        duration_seconds = None

    warnings: list[str] = []
    if duration_seconds is not None and duration_seconds < VERY_SHORT_DURATION_SECONDS:
        warnings.append("This video is very short — clip picks may be weak or fail.")
    elif duration_seconds is not None and duration_seconds < SHORT_DURATION_WARNING_SECONDS:
        warnings.append("This video is under 3 minutes — fewer strong clip candidates are likely.")

    transcript = probe_youtube_transcript(video_id, languages=["id", "en", "ar"])
    if transcript.get("status") == "missing":
        warnings.append(
            "No YouTube subtitles yet. Fresh live replays often need 12–48 hours for auto-captions. "
            "Use Transcribe from audio when creating clips."
        )
    elif transcript.get("status") == "disabled":
        warnings.append("YouTube captions are disabled on this video. Use Transcribe from audio when creating clips.")
    elif transcript.get("status") == "restricted":
        warnings.append(str(transcript.get("message") or "Transcript access is restricted for this video."))

    return {
        "ok": True,
        "provider": "youtube",
        "video_id": video_id,
        "title": title or "YouTube video",
        "channel": channel or "",
        "duration_seconds": duration_seconds,
        "thumbnail_url": thumbnail if thumbnail not in {"", "NA", "None"} else "",
        "canonical_url": webpage.split("&", 1)[0] if "watch?v=" in webpage else canonical,
        "source_url": canonical,
        "warnings": warnings,
        "transcript": transcript,
    }
