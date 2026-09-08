"""Detect and remove dead-air from short-form source clips before render."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SilenceTrimConfig:
    noise_db: float = -32.0
    min_silence_ms: int = 450
    keep_silence_ms: int = 140
    edge_pad_ms: int = 60
    min_keep_ms: int = 400


DEFAULT_SILENCE_TRIM = SilenceTrimConfig()


def _ffmpeg_bin() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for silence trim")
    return ffmpeg


def _ffprobe_bin() -> str:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe is required for silence trim")
    return ffprobe


def probe_duration_ms(path: str | Path) -> int:
    cmd = [
        _ffprobe_bin(),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[-800:]}")
    try:
        seconds = float((result.stdout or "").strip())
    except ValueError as exc:
        raise RuntimeError(f"ffprobe returned invalid duration: {result.stdout!r}") from exc
    return max(0, int(round(seconds * 1000)))


def detect_silence_intervals(
    path: str | Path,
    config: SilenceTrimConfig = DEFAULT_SILENCE_TRIM,
) -> list[tuple[int, int]]:
    """Return silence [start_ms, end_ms) intervals using ffmpeg silencedetect."""
    noise = f"{config.noise_db}dB"
    duration_s = max(0.05, config.min_silence_ms / 1000)
    cmd = [
        _ffmpeg_bin(),
        "-hide_banner",
        "-i",
        str(path),
        "-af",
        f"silencedetect=noise={noise}:d={duration_s:.3f}",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # silencedetect writes to stderr; non-zero can still contain useful intervals
    stderr = result.stderr or ""
    starts: list[float] = []
    ends: list[float] = []
    for match in re.finditer(r"silence_start:\s*([0-9.]+)", stderr):
        starts.append(float(match.group(1)))
    for match in re.finditer(r"silence_end:\s*([0-9.]+)", stderr):
        ends.append(float(match.group(1)))

    intervals: list[tuple[int, int]] = []
    for index, start_s in enumerate(starts):
        end_s = ends[index] if index < len(ends) else None
        if end_s is None:
            continue
        start_ms = max(0, int(round(start_s * 1000)))
        end_ms = max(start_ms, int(round(end_s * 1000)))
        if end_ms - start_ms >= config.min_silence_ms:
            intervals.append((start_ms, end_ms))
    return intervals


def build_keep_segments(
    duration_ms: int,
    silences: list[tuple[int, int]],
    config: SilenceTrimConfig = DEFAULT_SILENCE_TRIM,
) -> list[tuple[int, int]]:
    """
    Keep speech regions; compress long silences to keep_silence_ms.
    Leading/trailing silence is removed (with small edge pad when speech remains).
    """
    duration_ms = max(0, int(duration_ms))
    if duration_ms <= 0:
        return []

    # Merge overlapping silence
    merged: list[tuple[int, int]] = []
    for start, end in sorted((max(0, s), min(duration_ms, e)) for s, e in silences if e > s):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))

    if not merged:
        return [(0, duration_ms)]

    keep: list[tuple[int, int]] = []
    cursor = 0
    for index, (silence_start, silence_end) in enumerate(merged):
        is_leading = index == 0 and silence_start <= config.edge_pad_ms
        is_trailing = index == len(merged) - 1 and silence_end >= duration_ms - config.edge_pad_ms

        if silence_start > cursor:
            keep.append((cursor, silence_start))

        if is_leading:
            # drop leading silence entirely (speech starts at silence_end, with tiny pad back)
            cursor = max(0, silence_end - config.edge_pad_ms)
            continue
        if is_trailing:
            # drop trailing silence; do not append after
            cursor = silence_start
            break

        # Internal: keep a short breath then jump to end of silence
        breath_end = min(silence_end, silence_start + config.keep_silence_ms)
        if breath_end > silence_start:
            keep.append((silence_start, breath_end))
        cursor = silence_end

    if cursor < duration_ms:
        # If we broke on trailing silence, cursor is silence_start — do not re-add trailing dead air
        trailing = merged[-1] if merged else None
        if trailing and trailing[1] >= duration_ms - config.edge_pad_ms and cursor == trailing[0]:
            pass
        else:
            keep.append((cursor, duration_ms))

    # Normalize / drop tiny keeps
    normalized: list[tuple[int, int]] = []
    for start, end in keep:
        start = max(0, min(duration_ms, start))
        end = max(start, min(duration_ms, end))
        if end - start < 20:
            continue
        if normalized and start <= normalized[-1][1]:
            normalized[-1] = (normalized[-1][0], max(normalized[-1][1], end))
        else:
            normalized.append((start, end))

    if not normalized:
        return [(0, duration_ms)]

    total = sum(end - start for start, end in normalized)
    if total < config.min_keep_ms:
        return [(0, duration_ms)]
    return normalized


def clamp_keep_segments(
    duration_ms: int,
    keep_segments: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Clamp keep windows onto [0, duration_ms] and drop empty slices."""
    duration_ms = max(0, int(duration_ms))
    if duration_ms <= 0:
        return [(0, 0)]
    clamped: list[tuple[int, int]] = []
    for start, end in keep_segments:
        start_i = max(0, min(duration_ms, int(start)))
        end_i = max(start_i, min(duration_ms, int(end)))
        if end_i - start_i < 20:
            continue
        if clamped and start_i <= clamped[-1][1]:
            clamped[-1] = (clamped[-1][0], max(clamped[-1][1], end_i))
        else:
            clamped.append((start_i, end_i))
    if not clamped:
        return [(0, duration_ms)]
    return clamped


def plan_remove_pause(
    duration_ms: int,
    pause_at_ms: int,
    gap_ms: int,
    config: SilenceTrimConfig = DEFAULT_SILENCE_TRIM,
) -> list[tuple[int, int]]:
    """Build keep segments that compress one operator-selected pause window."""
    duration_ms = max(0, int(duration_ms))
    start = max(0, min(duration_ms, int(pause_at_ms)))
    end = max(start, min(duration_ms, start + max(0, int(gap_ms))))
    if end - start < 40:
        return [(0, duration_ms)]
    return build_keep_segments(duration_ms, [(start, end)], config)


def remove_pause_from_captions(
    captions: list[dict[str, Any]],
    duration_ms: int,
    pause_at_ms: int,
    gap_ms: int,
    config: SilenceTrimConfig = DEFAULT_SILENCE_TRIM,
) -> tuple[list[tuple[int, int]], list[dict[str, Any]]]:
    keep = plan_remove_pause(duration_ms, pause_at_ms, gap_ms, config)
    return keep, remap_caption_groups(captions, keep)


def flatten_caption_words(captions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten caption words in timeline order (clip-relative ms)."""
    words: list[dict[str, Any]] = []
    for caption in captions:
        timed = caption.get("words") if isinstance(caption.get("words"), list) else []
        usable = [
            word
            for word in timed
            if isinstance(word, dict) and word.get("startMs") is not None and word.get("endMs") is not None
        ]
        if usable:
            for word in usable:
                words.append(
                    {
                        "text": str(word.get("text") or "").strip(),
                        "startMs": int(word.get("startMs") or 0),
                        "endMs": int(word.get("endMs") or 0),
                    }
                )
            continue
        text = str(caption.get("text") or "").strip()
        if not text:
            continue
        words.append(
            {
                "text": text,
                "startMs": int(caption.get("startMs") or 0),
                "endMs": int(caption.get("endMs") or 0),
            }
        )
    return words


def word_pause_gaps(
    captions: list[dict[str, Any]],
    min_gap_ms: int = 450,
) -> list[dict[str, int]]:
    """List word-level gaps at/above ``min_gap_ms`` (same signal as Pause chips)."""
    min_gap_ms = max(40, int(min_gap_ms))
    words = flatten_caption_words(captions)
    gaps: list[dict[str, int]] = []
    for index in range(len(words) - 1):
        current = words[index]
        nxt = words[index + 1]
        gap_ms = max(0, int(nxt["startMs"]) - int(current["endMs"]))
        if gap_ms < min_gap_ms:
            continue
        at_ms = int(current["endMs"])
        gaps.append({"pause_at_ms": at_ms, "gap_ms": gap_ms, "end_ms": at_ms + gap_ms})
    return gaps


def plan_remove_pauses_batch(
    duration_ms: int,
    gaps: list[dict[str, int]] | list[tuple[int, int]],
    config: SilenceTrimConfig = DEFAULT_SILENCE_TRIM,
) -> list[tuple[int, int]]:
    """Build one keep plan that compresses every selected pause window."""
    duration_ms = max(0, int(duration_ms))
    silences: list[tuple[int, int]] = []
    for item in gaps:
        if isinstance(item, dict):
            start = int(item.get("pause_at_ms") or item.get("at_ms") or 0)
            end = int(item.get("end_ms") or (start + int(item.get("gap_ms") or 0)))
        else:
            start, end = int(item[0]), int(item[1])
        start = max(0, min(duration_ms, start))
        end = max(start, min(duration_ms, end))
        if end - start >= 40:
            silences.append((start, end))
    if not silences:
        return [(0, duration_ms)]
    return build_keep_segments(duration_ms, silences, config)


def remove_pauses_batch_from_captions(
    captions: list[dict[str, Any]],
    duration_ms: int,
    min_gap_ms: int,
    config: SilenceTrimConfig = DEFAULT_SILENCE_TRIM,
) -> tuple[list[tuple[int, int]], list[dict[str, Any]], list[dict[str, int]]]:
    gaps = word_pause_gaps(captions, min_gap_ms)
    keep = plan_remove_pauses_batch(duration_ms, gaps, config)
    return keep, remap_caption_groups(captions, keep), gaps


def captions_duration_ms(captions: list[dict[str, Any]]) -> int:
    if not captions:
        return 0
    return max(int(caption.get("endMs") or 0) for caption in captions)


def remap_time_ms(original_ms: int, keep_segments: list[tuple[int, int]]) -> int | None:
    """Map a timestamp on the original timeline onto the trimmed timeline."""
    t = max(0, int(original_ms))
    out = 0
    for start, end in keep_segments:
        if t < start:
            return out
        if t <= end:
            return out + (t - start)
        out += end - start
    return out


def untrim_time_ms(trimmed_ms: int, keep_segments: list[tuple[int, int]]) -> int:
    """Map a timestamp on the trimmed file back onto the original clip timeline."""
    t = max(0, int(trimmed_ms))
    cursor = 0
    for start, end in keep_segments:
        length = max(0, int(end) - int(start))
        if t <= cursor + length:
            return int(start) + (t - cursor)
        cursor += length
    if not keep_segments:
        return t
    return int(keep_segments[-1][1])


def parse_keep_segments(value: Any) -> list[tuple[int, int]]:
    segments: list[tuple[int, int]] = []
    if not isinstance(value, list):
        return segments
    for pair in value:
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        start = int(pair[0])
        end = int(pair[1])
        if end > start:
            segments.append((start, end))
    return segments


def source_already_silence_trimmed(candidate: dict[str, Any] | None = None, source_path: str | Path = "") -> bool:
    payload = candidate or {}
    trim = payload.get("silence_trim") if isinstance(payload.get("silence_trim"), dict) else {}
    if trim.get("changed") or trim.get("skipped") == "already_trimmed":
        return True
    stem = Path(str(source_path or "")).stem
    return stem.endswith("_silencetrim") or stem.endswith("_cut")


def remap_caption_groups(
    captions: list[dict[str, Any]],
    keep_segments: list[tuple[int, int]],
) -> list[dict[str, Any]]:
    remapped: list[dict[str, Any]] = []
    for caption in captions:
        words_in = caption.get("words") or []
        words_out: list[dict[str, Any]] = []
        for word in words_in:
            start = remap_time_ms(int(word.get("startMs", 0)), keep_segments)
            end = remap_time_ms(int(word.get("endMs", word.get("startMs", 0))), keep_segments)
            if start is None or end is None:
                continue
            if end <= start:
                end = start + 40
            words_out.append({**word, "startMs": start, "endMs": end})

        start = remap_time_ms(int(caption.get("startMs", 0)), keep_segments)
        end = remap_time_ms(int(caption.get("endMs", caption.get("startMs", 0))), keep_segments)
        if words_out:
            start = words_out[0]["startMs"]
            end = max(words_out[-1]["endMs"], start + 40)
            text = " ".join(str(word.get("text", "")).strip() for word in words_out if str(word.get("text", "")).strip())
        else:
            if start is None or end is None:
                continue
            if end <= start:
                end = start + 40
            text = str(caption.get("text", "")).strip()
            if not text:
                continue
            words_out = []

        remapped.append(
            {
                **caption,
                "text": text or str(caption.get("text", "")),
                "startMs": start if start is not None else 0,
                "endMs": end if end is not None else 0,
                "timestampMs": start if start is not None else caption.get("timestampMs"),
                "words": words_out,
            }
        )

    # Re-bridge adjacent cues for burn-in continuity
    for index, group in enumerate(remapped[:-1]):
        next_start = int(remapped[index + 1]["startMs"])
        if next_start > int(group["startMs"]):
            group["endMs"] = next_start
    return remapped


def render_keep_segments(
    input_path: str | Path,
    output_path: str | Path,
    keep_segments: list[tuple[int, int]],
) -> str:
    """Concat kept segments with ffmpeg trim filters (A/V)."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if len(keep_segments) == 1 and keep_segments[0][0] == 0:
        # Fast path when only trailing was cut: still use trim for consistency
        pass

    filter_parts: list[str] = []
    concat_inputs: list[str] = []
    for index, (start_ms, end_ms) in enumerate(keep_segments):
        start_s = start_ms / 1000
        end_s = end_ms / 1000
        filter_parts.append(
            f"[0:v]trim=start={start_s:.3f}:end={end_s:.3f},setpts=PTS-STARTPTS[v{index}];"
            f"[0:a]atrim=start={start_s:.3f}:end={end_s:.3f},asetpts=PTS-STARTPTS[a{index}]"
        )
        concat_inputs.append(f"[v{index}][a{index}]")
    filter_complex = ";".join(filter_parts) + ";" + "".join(concat_inputs) + f"concat=n={len(keep_segments)}:v=1:a=1[outv][outa]"

    cmd = [
        _ffmpeg_bin(),
        "-y",
        "-i",
        str(input_path),
        "-filter_complex",
        filter_complex,
        "-map",
        "[outv]",
        "-map",
        "[outa]",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0 or not output_path.exists():
        raise RuntimeError(f"silence trim encode failed: {result.stderr[-1500:]}")
    return str(output_path)


def trim_source_silence(
    source_clip: str | Path,
    *,
    config: SilenceTrimConfig = DEFAULT_SILENCE_TRIM,
    output_path: str | Path | None = None,
    captions: list[dict[str, Any]] | None = None,
    forced_silences: list[tuple[int, int]] | None = None,
    forced_keep_segments: list[tuple[int, int]] | None = None,
    remap_captions: bool = True,
) -> tuple[str, dict[str, Any], list[dict[str, Any]] | None]:
    """
    Trim dead-air from a source clip.

    Returns (path_to_use, diagnostics, remapped_captions_or_None).
    If nothing meaningful changes, returns the original path unchanged.
    """
    source_clip = Path(source_clip)
    duration_ms = probe_duration_ms(source_clip)

    if forced_keep_segments:
        keep_segments = clamp_keep_segments(
            duration_ms,
            [(int(start), int(end)) for start, end in forced_keep_segments if int(end) > int(start)],
        )
        silences: list[tuple[int, int]] = []
    else:
        silences = detect_silence_intervals(source_clip, config)
        if forced_silences:
            silences = [*silences, *forced_silences]
        keep_segments = build_keep_segments(duration_ms, silences, config)

    kept_ms = sum(end - start for start, end in keep_segments)
    full = [(0, duration_ms)]
    changed = keep_segments != full and kept_ms < duration_ms - 80

    diagnostics: dict[str, Any] = {
        "engine": "silence_trim_v1",
        "config": asdict(config),
        "duration_before_ms": duration_ms,
        "duration_after_ms": kept_ms if changed else duration_ms,
        "silence_interval_count": len(silences),
        "removed_ms": max(0, duration_ms - kept_ms) if changed else 0,
        "keep_segments": keep_segments if changed else [[0, duration_ms]],
        "changed": changed,
        "forced_keep": bool(forced_keep_segments),
    }

    if not changed:
        return str(source_clip), diagnostics, captions

    target = Path(output_path) if output_path else None
    if target is None:
        stem = source_clip.stem
        suffix = "_cut" if stem.endswith(("_silencetrim", "_cut")) else "_silencetrim"
        target = source_clip.with_name(f"{stem}{suffix}{source_clip.suffix}")
    # Allow re-trim of a previously trimmed file when operator forced a keep plan.
    if target.resolve() == source_clip.resolve():
        target = source_clip.with_name(f"{source_clip.stem}_cut{source_clip.suffix}")
    render_keep_segments(source_clip, target, keep_segments)
    diagnostics["output_path"] = str(target)
    remapped = remap_caption_groups(captions, keep_segments) if captions and remap_captions else captions
    return str(target), diagnostics, remapped


def apply_silence_trim_for_render(
    source_clip: str | Path,
    candidate: dict[str, Any],
    *,
    config: SilenceTrimConfig = DEFAULT_SILENCE_TRIM,
) -> str:
    """Trim source clip for short-form render; stash diagnostics on the candidate."""
    source_path = Path(source_clip)
    meta = candidate.get("curation_metadata") if isinstance(candidate.get("curation_metadata"), dict) else {}
    pending_keep = meta.get("manual_silence_keep_segments") if isinstance(meta, dict) else None
    forced_keep: list[tuple[int, int]] | None = None
    if isinstance(pending_keep, list) and pending_keep:
        forced_keep = [(int(pair[0]), int(pair[1])) for pair in pending_keep if len(pair) >= 2]

    if source_path.stem.endswith("_silencetrim") and not forced_keep:
        candidate["silence_trim"] = {
            "engine": "silence_trim_v1",
            "changed": False,
            "skipped": "already_trimmed",
            "output_path": str(source_path),
        }
        return str(source_path)

    captions = candidate.get("timed_captions") if isinstance(candidate.get("timed_captions"), list) else None
    # Captions were already remapped when the operator queued Remove Pause — only cut A/V.
    remap_captions = not bool(forced_keep)
    try:
        path, diagnostics, remapped = trim_source_silence(
            source_path,
            config=config,
            captions=captions,
            forced_keep_segments=forced_keep,
            remap_captions=remap_captions,
        )
    except Exception as exc:  # noqa: BLE001 - never block render on trim failures
        candidate["silence_trim"] = {
            "engine": "silence_trim_v1",
            "changed": False,
            "error": str(exc),
        }
        return str(source_clip)

    candidate["silence_trim"] = diagnostics
    if remapped is not None and remap_captions:
        candidate["timed_captions"] = remapped
    if diagnostics.get("changed") and forced_keep and isinstance(meta, dict):
        # Applied; clear pending so later renders don't re-cut.
        meta = {**meta}
        meta.pop("manual_silence_keep_segments", None)
        cuts = meta.get("manual_silence_cuts")
        if isinstance(cuts, list):
            meta["manual_silence_cuts_applied"] = cuts
            meta.pop("manual_silence_cuts", None)
        candidate["curation_metadata"] = meta
    return path
