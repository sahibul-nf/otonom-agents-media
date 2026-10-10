"""Automated multi-layer sound design and audio ducking for viral video reels."""

from __future__ import annotations

import math
import os
import shutil
import struct
import subprocess
import wave
from pathlib import Path
from typing import Any

from .db import ROOT

ASSETS_AUDIO_DIR = ROOT / "render" / "hyperframes" / "assets" / "audio"


def _generate_wav_file(path: Path, sample_rate: int, duration_s: float, generator_fn) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(sample_rate * duration_s)
    with wave.open(str(path), "w") as wav_file:
        wav_file.setnchannels(2)  # Stereo
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        
        frames = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            left, right = generator_fn(t, duration_s)
            # Clamp to 16-bit signed int range [-32767, 32767]
            i_left = int(max(-1.0, min(1.0, left)) * 32767.0)
            i_right = int(max(-1.0, min(1.0, right)) * 32767.0)
            frames.extend(struct.pack("<hh", i_left, i_right))
        wav_file.writeframes(frames)


def generate_hook_impact_boom(output_path: Path) -> Path:
    """Generate a clean cinematic sub-bass hook boom impact hit (~1.2s)."""
    sample_rate = 44100
    duration = 1.25

    def generator(t: float, total_d: float) -> tuple[float, float]:
        # Fast 15ms attack, exponential sub decay
        if t < 0.015:
            envelope = t / 0.015
        else:
            envelope = math.exp(-3.8 * (t - 0.015))
        
        # Exponential pitch drop from 88 Hz to 36 Hz
        freq = 36.0 + 52.0 * math.exp(-6.0 * t)
        phase = 2.0 * math.pi * freq * t
        
        # Harmonic overtone
        sub = math.sin(phase)
        mid = 0.35 * math.sin(phase * 1.5) * math.exp(-8.0 * t)
        click = 0.25 * math.sin(2.0 * math.pi * 320.0 * t) * math.exp(-40.0 * t)
        
        sample = (sub + mid + click) * envelope * 0.85
        return sample, sample

    _generate_wav_file(output_path, sample_rate, duration, generator)
    return output_path


def generate_transition_whoosh(output_path: Path) -> Path:
    """Generate a quick whoosh / swoosh transition SFX (~0.4s)."""
    sample_rate = 44100
    duration = 0.45

    def generator(t: float, total_d: float) -> tuple[float, float]:
        # Smooth window
        norm_t = t / total_d
        envelope = math.sin(math.pi * norm_t) ** 2
        
        # Frequency sweep up then down (chirp)
        freq = 280.0 + 850.0 * math.sin(math.pi * norm_t)
        phase = 2.0 * math.pi * freq * t
        
        # Add subtle stereo panning
        pan_left = 0.5 + 0.4 * (1.0 - norm_t)
        pan_right = 0.5 + 0.4 * norm_t
        
        sample = (math.sin(phase) + 0.3 * math.sin(phase * 2.1)) * envelope * 0.65
        return sample * pan_left, sample * pan_right

    _generate_wav_file(output_path, sample_rate, duration, generator)
    return output_path


def generate_ambient_music_bed(output_path: Path, duration_s: float = 20.0) -> Path:
    """Generate a warm, mellow, ducking-friendly ambient chord pad (~20s)."""
    sample_rate = 44100

    def generator(t: float, total_d: float) -> tuple[float, float]:
        # Smooth fade in and fade out
        fade_in = min(1.0, t / 1.5)
        fade_out = min(1.0, (total_d - t) / 1.5)
        envelope = fade_in * fade_out * 0.45

        # Warm rich chord (Root 110Hz, Minor 3rd 130.8Hz, 5th 164.8Hz, Octave 220Hz)
        lfo = 1.0 + 0.12 * math.sin(2.0 * math.pi * 0.3 * t)
        c1 = math.sin(2.0 * math.pi * 110.0 * t)
        c2 = 0.7 * math.sin(2.0 * math.pi * 130.81 * t + 0.3)
        c3 = 0.7 * math.sin(2.0 * math.pi * 164.81 * t + 0.6)
        c4 = 0.4 * math.sin(2.0 * math.pi * 220.0 * t)
        
        # Subtle harmonic shimmer
        shimmer = 0.18 * math.sin(2.0 * math.pi * 440.0 * t * lfo)
        
        sample = (c1 + c2 + c3 + c4 + shimmer) * envelope * 0.35
        # Soft stereo difference
        left = sample * (1.0 + 0.08 * math.sin(2.0 * math.pi * 0.2 * t))
        right = sample * (1.0 - 0.08 * math.sin(2.0 * math.pi * 0.2 * t))
        return left, right

    _generate_wav_file(output_path, sample_rate, duration_s, generator)
    return output_path


def ensure_default_sound_assets(target_dir: Path | None = None) -> dict[str, Path]:
    """Ensure standard sound design audio assets exist, creating them if absent."""
    directory = target_dir or ASSETS_AUDIO_DIR
    directory.mkdir(parents=True, exist_ok=True)

    hook_boom = directory / "hook_boom.wav"
    whoosh = directory / "transition_whoosh.wav"
    ambient_bed = directory / "ambient_bed.wav"

    if not hook_boom.exists() or hook_boom.stat().st_size < 100:
        generate_hook_impact_boom(hook_boom)

    if not whoosh.exists() or whoosh.stat().st_size < 100:
        generate_transition_whoosh(whoosh)

    if not ambient_bed.exists() or ambient_bed.stat().st_size < 100:
        generate_ambient_music_bed(ambient_bed)

    return {
        "hook_boom": hook_boom,
        "whoosh": whoosh,
        "ambient_bed": ambient_bed,
    }


def get_sound_design_config(contract: dict[str, Any]) -> dict[str, Any]:
    """Extract sound design configuration from contract or style presets."""
    style = contract.get("style") if isinstance(contract.get("style"), dict) else {}
    sd = contract.get("soundDesign") or style.get("sound_design") or {}
    
    # Check if template explicitly requests sound design
    template_id = str(contract.get("hyperframesTemplate") or (contract.get("style") or {}).get("template") or "")
    is_kinetic_template = template_id in {"studio_kinetic_reel", "volt_lime_kinetic"}
    
    enabled = sd.get("enabled", is_kinetic_template or True)
    music_bed_override = sd.get("music_bed") or os.environ.get("MEDIA_ENGINE_MUSIC_BED")
    
    return {
        "enabled": bool(enabled),
        "music_volume": float(sd.get("music_volume", 0.14)),
        "hook_volume": float(sd.get("hook_volume", 0.60)),
        "ducking_threshold": float(sd.get("ducking_threshold", 0.075)),
        "ducking_ratio": float(sd.get("ducking_ratio", 5.0)),
        "ducking_attack_ms": int(sd.get("ducking_attack_ms", 45)),
        "ducking_release_ms": int(sd.get("ducking_release_ms", 320)),
        "hook_delay_ms": int(sd.get("hook_delay_ms", 80)),
        "music_bed_path": music_bed_override,
    }


def build_audio_ducking_filter_graph(
    speech_label: str = "0:a",
    music_input_index: int = 1,
    hook_input_index: int | None = 2,
    config: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Build FFmpeg complex filter script lines for auto-ducked music bed and hook SFX.
    
    Returns:
        tuple[filter_script_snippet, output_audio_label]
    """
    cfg = config or {}
    music_vol = cfg.get("music_volume", 0.14)
    hook_vol = cfg.get("hook_volume", 0.60)
    thresh = cfg.get("ducking_threshold", 0.075)
    ratio = cfg.get("ducking_ratio", 5.0)
    attack = cfg.get("ducking_attack_ms", 45)
    release = cfg.get("ducking_release_ms", 320)
    hook_delay = cfg.get("hook_delay_ms", 80)

    lines = []
    # 1. Base music volume and looping/conforming
    lines.append(f"[{music_input_index}:a]volume={music_vol:.3f},aloop=loop=-1:size=2e+09[bg_raw]")
    
    # 2. Sidechain ducking of background music against speech track
    lines.append(
        f"[bg_raw][{speech_label}]sidechaincompress="
        f"threshold={thresh:.4f}:ratio={ratio:.1f}:attack={attack}:release={release}[ducked_bg]"
    )

    if hook_input_index is not None:
        # 3. Hook impact SFX with subtle adelay and volume
        lines.append(
            f"[{hook_input_index}:a]volume={hook_vol:.3f},adelay={hook_delay}|{hook_delay}[hook_delayed]"
        )
        # 4. Mix speech, ducked music, and hook hit together
        lines.append(f"[{speech_label}][ducked_bg][hook_delayed]amix=inputs=3:duration=first:dropout_transition=2[a_out]")
    else:
        # Mix speech and ducked music only
        lines.append(f"[{speech_label}][ducked_bg]amix=inputs=2:duration=first:dropout_transition=2[a_out]")

    return ";\n".join(lines), "[a_out]"


def _has_audio_stream(video_path: Path | str) -> bool:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return True
    try:
        res = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(video_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return "audio" in res.stdout
    except Exception:
        return True


def apply_sound_design_to_video(
    input_video_path: Path | str,
    output_video_path: Path | str,
    contract: dict[str, Any],
    work_dir: Path | None = None,
) -> bool:
    """Add ducked music bed and hook impact SFX to a rendered video file via FFmpeg."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False

    config = get_sound_design_config(contract)
    if not config["enabled"]:
        return False

    assets = ensure_default_sound_assets(work_dir)
    music_bed = Path(config["music_bed_path"]) if config["music_bed_path"] else assets["ambient_bed"]
    hook_boom = assets["hook_boom"]

    if not music_bed.exists() or not hook_boom.exists():
        return False

    has_audio = _has_audio_stream(input_video_path)
    if not has_audio:
        m_vol = config.get("music_volume", 0.14)
        h_vol = config.get("hook_volume", 0.60)
        h_delay = config.get("hook_delay_ms", 80)
        filter_graph = (
            f"[1:a]volume={m_vol:.3f},aloop=loop=-1:size=2e+09[bg_raw];"
            f"[2:a]volume={h_vol:.3f},adelay={h_delay}|{h_delay}[hook_delayed];"
            f"[bg_raw][hook_delayed]amix=inputs=2:duration=first:dropout_transition=2[a_out]"
        )
        out_label = "[a_out]"
    else:
        filter_graph, out_label = build_audio_ducking_filter_graph(
            speech_label="0:a",
            music_input_index=1,
            hook_input_index=2,
            config=config,
        )

    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(input_video_path),
        "-i",
        str(music_bed),
        "-i",
        str(hook_boom),
        "-filter_complex",
        filter_graph,
        "-map",
        "0:v",
        "-map",
        out_label,
        "-shortest",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output_video_path),
    ]

    try:
        result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False
