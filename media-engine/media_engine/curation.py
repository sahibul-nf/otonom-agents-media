"""Dry-run transcript ingestion and deterministic clip curation."""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass


SAMPLE_NOURBIT_TRANSCRIPT = """
00:00:00 Bismillah. Banyak orang mencari ketenangan dari sesuatu yang jauh,
00:00:05 padahal hati pertama kali harus diajak pulang kepada Allah.
00:00:12 Ketika seseorang memperbaiki niat, amal yang kecil bisa menjadi besar.
00:00:20 Dan ketika niat rusak, amal yang terlihat besar bisa kehilangan cahaya.
00:00:30 Maka jangan hanya bertanya seberapa banyak ibadah kita,
00:00:36 tapi tanyakan juga untuk siapa ibadah itu dilakukan.
00:00:44 Di situlah manusia belajar jujur kepada dirinya sendiri.
00:00:52 Kalau hati mulai jujur, nasihat yang sederhana pun bisa mengubah arah hidup.
00:01:02 Karena hidayah sering datang bukan dari kalimat yang panjang,
00:01:08 tetapi dari satu kalimat yang tepat menyentuh hati.
"""


@dataclass(frozen=True)
class TranscriptLine:
    start_ms: int
    text: str


def parse_timecode(value: str) -> int:
    hours, minutes, seconds = value.split(":")
    return (int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000


def parse_transcript(text: str) -> list[TranscriptLine]:
    lines: list[TranscriptLine] = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        match = re.match(r"^(\d{2}:\d{2}:\d{2})\s+(.+)$", raw)
        if match:
            lines.append(TranscriptLine(parse_timecode(match.group(1)), match.group(2).strip()))
    return lines


def transcript_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def curate_dry_run(profile_id: str, source_id: str, transcript: str) -> dict[str, object]:
    lines = parse_transcript(transcript)
    if len(lines) < 3:
        raise ValueError("transcript needs at least 3 timestamped lines")

    start_ms = lines[1].start_ms
    end_ms = min(lines[-1].start_ms + 4000, start_ms + 90000)
    span = " ".join(line.text for line in lines[1:])

    return {
        "id": f"clip_{uuid.uuid4().hex[:12]}",
        "profile_id": profile_id,
        "source_id": source_id,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "title_hook": "Untuk Siapa Ibadah Kita?",
        "viral_reason": "Potongan ini kuat karena membahas niat dengan kalimat sederhana dan mudah direnungkan.",
        "transcript_span": span[:1200],
        "risk_flags": [],
        "transcript_hash": transcript_hash(transcript),
        "status": "draft",
    }
