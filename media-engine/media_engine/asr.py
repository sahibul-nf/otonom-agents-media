"""Local ASR helpers for production word-aligned captions."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def extract_audio(source_video_path: str, output_audio_path: str) -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for audio extraction")
    output = Path(output_audio_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        source_video_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(output),
    ]
    result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"audio extraction failed: {result.stderr[-1200:]}")
    return str(output)


def words_from_faster_whisper_segments(segments: Any) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for segment in segments:
        for word in getattr(segment, "words", None) or []:
            text = str(getattr(word, "word", "")).strip()
            if not text:
                continue
            start_ms = int(float(getattr(word, "start", 0)) * 1000)
            end_ms = int(float(getattr(word, "end", 0)) * 1000)
            words.append(
                {
                    "text": text,
                    "startMs": max(0, start_ms),
                    "endMs": max(start_ms + 40, end_ms),
                    "confidence": getattr(word, "probability", None),
                }
            )
    return words


def transcribe_audio_words(audio_path: str, model_name: str = "medium", language: str = "id", initial_prompt: str = "") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is required for --caption-source whisper") from exc

    model = WhisperModel(model_name, device="auto", compute_type="auto")
    segments, info = model.transcribe(
        audio_path,
        language=language,
        word_timestamps=True,
        vad_filter=True,
        initial_prompt=initial_prompt or None,
    )
    words = words_from_faster_whisper_segments(segments)
    metadata = {
        "engine": "faster-whisper",
        "model": model_name,
        "language": getattr(info, "language", language),
        "language_probability": getattr(info, "language_probability", None),
        "word_count": len(words),
    }
    return words, metadata


def load_or_create_asr_words(
    source_video_path: str,
    cache_json_path: str,
    model_name: str = "medium",
    language: str = "id",
    initial_prompt: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cache = Path(cache_json_path)
    if cache.exists():
        payload = json.loads(cache.read_text(encoding="utf-8"))
        return payload["words"], payload["metadata"]
    audio_path = str(cache.with_suffix(".wav"))
    extract_audio(source_video_path, audio_path)
    words, metadata = transcribe_audio_words(audio_path, model_name=model_name, language=language, initial_prompt=initial_prompt)
    cache.write_text(json.dumps({"words": words, "metadata": metadata}, indent=2, ensure_ascii=False), encoding="utf-8")
    return words, metadata
