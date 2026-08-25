"""Background generation jobs launched from the local review dashboard."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

from .db import DEFAULT_DB, ROOT, connect, ensure_media_profile, ensure_source_manifest, initialize
from .duration_presets import resolve_duration_strategy
from .genres import normalize_genres
from .hyperframes_renderer import check_hyperframes_runtime
from .hyperframes_templates import normalize_hyperframes_template
from .styles import is_template_only_style, normalize_brand_template_ref
from .shell_components import normalize_shell_components


VALID_RENDERERS = {"ffmpeg", "remotion", "hyperframes"}
VALID_HYPERFRAMES_FORMATS = {"auto", "short_9_16", "long_16_9"}
VALID_QUALITIES = {"draft", "production"}
VALID_CAPTION_SOURCES = {"youtube", "whisper", "hybrid"}
VALID_ASR_MODELS = {"small", "medium", "large-v3-turbo"}
VALID_LLM_PROVIDERS = {"none", "openai", "deepseek", "groq"}
VALID_LANGUAGES = {"id", "en", "ar", "ms", "auto"}
GENERATION_JOB_HEARTBEAT_SECONDS = max(5, int(os.environ.get("GENERATION_JOB_HEARTBEAT_SECONDS", "10")))
GENERATION_JOB_STALE_MINUTES = max(2, int(os.environ.get("GENERATION_JOB_STALE_MINUTES", "15")))
MODULE_TO_PIP_PACKAGE = {
    "youtube_transcript_api": "youtube-transcript-api",
    "faster_whisper": "faster-whisper",
    "yt_dlp_ejs": "yt-dlp-ejs",
}


def _runtime_requirements(config: dict[str, Any]) -> list[str]:
    modules = ["youtube_transcript_api", "yt_dlp_ejs"]
    if config.get("caption_source") in {"whisper", "hybrid"}:
        modules.append("faster_whisper")
    return modules


def _runtime_tools(config: dict[str, Any]) -> list[str]:
    # All generation paths require section download from YouTube.
    tools = ["yt-dlp"]
    # Whisper + yt-dlp merge path both rely on ffmpeg being present.
    if config.get("caption_source") in {"whisper", "hybrid"}:
        tools.append("ffmpeg")
    return tools


def _python_has_modules(python_bin: str, modules: list[str]) -> bool:
    if not modules:
        return True
    code = "import importlib.util, sys; sys.exit(0 if all(importlib.util.find_spec(m) for m in sys.argv[1:]) else 1)"
    result = subprocess.run([python_bin, "-c", code, *modules], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0


def _resolve_tool_for_python(python_bin: str, tool: str) -> str | None:
    # Keep virtualenv bin path (do not resolve symlink to global python),
    # so sibling scripts like `yt-dlp` in the same venv are discoverable.
    python_dir = Path(python_bin).parent
    sibling = python_dir / tool
    if sibling.exists() and os.access(sibling, os.X_OK):
        return str(sibling)
    system_tool = shutil.which(tool)
    if system_tool:
        return system_tool
    return None


def _bootstrap_tools_env(required_modules: list[str], required_tools: list[str]) -> None:
    if os.environ.get("MEDIA_ENGINE_SKIP_RUNTIME_BOOTSTRAP") == "1":
        return
    tools_dir = ROOT / ".venv-tools"
    tools_python = tools_dir / "bin" / "python"
    if not tools_python.exists():
        creator = shutil.which("python3.13") or shutil.which("python3") or sys.executable
        subprocess.run([creator, "-m", "venv", str(tools_dir)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not tools_python.exists():
        return
    missing_modules = [module for module in required_modules if not _python_has_modules(str(tools_python), [module])]
    missing_tools = [tool for tool in required_tools if not _resolve_tool_for_python(str(tools_python), tool)]
    pip_packages = {MODULE_TO_PIP_PACKAGE.get(module, module) for module in missing_modules}
    if "yt-dlp" in missing_tools:
        pip_packages.add("yt-dlp")
    if not pip_packages:
        return
    subprocess.run([str(tools_python), "-m", "pip", "install", "-U", *sorted(pip_packages)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _candidate_python_bins() -> list[Path]:
    candidates = []
    if os.environ.get("MEDIA_ENGINE_PYTHON"):
        candidates.append(Path(os.environ["MEDIA_ENGINE_PYTHON"]))
    candidates.extend(
        [
            ROOT / ".venv-tools" / "bin" / "python",
            Path("/tmp/media-engine-tools-py313/bin/python"),
            ROOT / ".venv" / "bin" / "python",
            ROOT / "venv" / "bin" / "python",
            Path(sys.executable),
        ]
    )
    seen: set[str] = set()
    unique = []
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def resolve_generation_python(config: dict[str, Any]) -> str:
    if config.get("renderer") == "hyperframes":
        hyperframes = check_hyperframes_runtime(run_doctor=False)
        if not hyperframes["ready"]:
            raise RuntimeError(f"HyperFrames runtime is not ready: {hyperframes['reason']}")
    required_modules = _runtime_requirements(config)
    required_tools = _runtime_tools(config)
    _bootstrap_tools_env(required_modules, required_tools)
    existing = [path for path in _candidate_python_bins() if path.exists()]
    diagnostics: list[str] = []
    for path in existing:
        python_bin = str(path)
        missing_modules = [module for module in required_modules if not _python_has_modules(python_bin, [module])]
        missing_tools = [tool for tool in required_tools if not _resolve_tool_for_python(python_bin, tool)]
        if not missing_modules and not missing_tools:
            return str(path)
        details: list[str] = []
        if missing_modules:
            details.append(f"modules: {', '.join(missing_modules)}")
        if missing_tools:
            details.append(f"tools: {', '.join(missing_tools)}")
        diagnostics.append(f"{path} -> {', '.join(details)}")
    checked = ", ".join(str(path) for path in existing) or "none"
    missing_modules = ", ".join(required_modules) if required_modules else "-"
    missing_tools = ", ".join(required_tools) if required_tools else "-"
    diagnostic_text = " | ".join(diagnostics) if diagnostics else "none"
    raise RuntimeError(
        f"Generation runtime is missing dependencies. Required modules: {missing_modules}. Required tools: {missing_tools}. "
        "Create a persistent tools env with "
        "`python3.13 -m venv media-engine/.venv-tools && media-engine/.venv-tools/bin/python -m pip install -U youtube-transcript-api faster-whisper yt-dlp`, "
        "and make sure `ffmpeg` is installed (`brew install ffmpeg` on macOS), "
        "or set MEDIA_ENGINE_PYTHON to a compatible interpreter. "
        "Note: `/tmp/media-engine-tools-py313` can disappear after reboot/cleanup. "
        f"Checked: {checked}. Details: {diagnostic_text}"
    )


def _preferred_python_for_command() -> str:
    for path in _candidate_python_bins():
        if path.exists():
            return str(path)
    return "python3"


def list_brand_templates() -> list[dict[str, str]]:
    profiles = ROOT / "profiles"
    templates = []
    for path in sorted(profiles.glob("*.json")):
        if "nourbit" in path.name.lower():
            continue
        # Brand library: default baseline + saved custom brand systems only.
        if path.name != "default_workspace_style.json" and not path.name.startswith("custom_"):
            continue
        label = path.stem.replace("_", " ").replace("-", " ").title()
        has_brand_system = False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            label = str(payload.get("label") or label)
            has_brand_system = isinstance(payload.get("brand_system"), dict) and bool(payload.get("brand_system"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if path.name.startswith("custom_") and not has_brand_system:
            continue
        if path.name == "default_workspace_style.json":
            label = "Platform default"
        templates.append(
            {
                "id": str(path.relative_to(ROOT)),
                "label": label,
                "path": str(path.relative_to(ROOT)),
                "has_brand_system": "1" if has_brand_system else "0",
            }
        )
    if not templates:
        templates.append({"id": "profiles/default_workspace_style.json", "label": "Platform default", "path": "profiles/default_workspace_style.json", "has_brand_system": "0"})
    return templates


def _choice(value: Any, allowed: set[str], default: str) -> str:
    text = str(value or default).strip()
    return text if text in allowed else default


def _int_range(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)


def _duration_seconds(payload: dict[str, Any]) -> tuple[int, int, str]:
    preset_id = str(payload.get("clip_length_preset") or "auto").strip()
    min_seconds = _int_range(payload.get("clip_min_seconds"), 20, 0, 600)
    max_seconds = _int_range(payload.get("clip_max_seconds"), 180, 0, 600)
    preset = resolve_duration_strategy(preset_id, min_seconds if preset_id == "custom" else None, max_seconds if preset_id == "custom" else None)
    if preset.id == "custom" and min_seconds > max_seconds:
        raise ValueError("clip_min_seconds must be less than or equal to clip_max_seconds")
    return preset.min_ms // 1000, preset.max_ms // 1000, preset.id


def _language(value: Any, default: str = "auto") -> str:
    text = str(value or default).strip().lower()
    return text if text in VALID_LANGUAGES else default


def _language_list(value: Any, default: str = "auto") -> str:
    text = str(value or default).strip().lower()
    if text in {"", "auto"}:
        return "auto"
    parts = [part.strip().lower() for part in text.split(",") if part.strip()]
    allowed = [part for part in parts if part in VALID_LANGUAGES and part != "auto"]
    return ",".join(allowed or ["auto"])


def normalize_generation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    source_url = str(payload.get("source_url") or "").strip()
    if not source_url:
        raise ValueError("source_url is required")
    brand_template = normalize_brand_template_ref(payload.get("brand_template"))
    brand_system_template_id = str(payload.get("brand_system_template_id") or "").strip()
    hyperframes_template = normalize_hyperframes_template(payload.get("hyperframes_template"))

    # Closed loop: brand:* selection carries its style file + starter recipe.
    if brand_system_template_id.startswith("brand:") or hyperframes_template.startswith("brand:"):
        brand_id = brand_system_template_id if brand_system_template_id.startswith("brand:") else hyperframes_template
        from .hyperframes_templates import _saved_brand_template_by_id

        saved = _saved_brand_template_by_id(brand_id)
        if saved:
            hyperframes_template = brand_id
            brand_system_template_id = brand_id
            style_path = str(saved.get("brand_template_path") or "").strip()
            if style_path and (
                is_template_only_style(brand_template)
                or not (ROOT / brand_template).exists()
            ):
                brand_template = style_path

    if not is_template_only_style(brand_template):
        template_path = (ROOT / brand_template).resolve()
        if ROOT.resolve() not in template_path.parents or not template_path.exists():
            raise ValueError("brand_template not found")
    min_seconds, max_seconds, preset_id = _duration_seconds(payload)
    profile_id = str(payload.get("profile_id") or "workspace").strip()
    genres = normalize_genres(
        payload.get("genres"),
        profile_id=profile_id,
        niche=str(payload.get("niche") or "").strip() or None,
    )
    source_id = str(payload.get("source_id") or "").strip()
    source_metadata = payload.get("source_metadata")
    if not isinstance(source_metadata, dict):
        source_metadata = {}
    video_id = str(source_metadata.get("video_id") or "").strip()
    # Prefer per-video source ids so Review can group siblings (#58).
    if not source_id or source_id in {"workspace_source", f"{profile_id}_source"}:
        if video_id:
            source_id = f"{profile_id}_{video_id}"
        else:
            source_id = f"{profile_id}_source"
    canonical_url = str(source_metadata.get("canonical_url") or source_metadata.get("source_url") or "").strip()
    if canonical_url:
        source_url = canonical_url
    return {
        "profile_id": profile_id,
        "source_id": source_id,
        "source_url": source_url,
        "source_metadata": {
            "video_id": video_id,
            "title": str(source_metadata.get("title") or "").strip(),
            "channel": str(source_metadata.get("channel") or "").strip(),
            "duration_seconds": source_metadata.get("duration_seconds"),
            "thumbnail_url": str(source_metadata.get("thumbnail_url") or "").strip(),
            "canonical_url": source_url,
            "provider": str(source_metadata.get("provider") or "youtube").strip() or "youtube",
        },
        "count": _int_range(payload.get("count"), 5, 1, 10),
        "clip_length_preset": preset_id,
        "clip_min_seconds": min_seconds,
        "clip_max_seconds": max_seconds,
        "genres": genres,
        "brand_template": brand_template,
        "hyperframes_template": hyperframes_template,
        "brand_system_template_id": brand_system_template_id,
        "hyperframes_format": _choice(payload.get("hyperframes_format"), VALID_HYPERFRAMES_FORMATS, "auto"),
        "renderer": _choice(payload.get("renderer"), VALID_RENDERERS, "hyperframes"),
        "quality": _choice(payload.get("quality"), VALID_QUALITIES, "production"),
        "caption_source": _choice(payload.get("caption_source"), VALID_CAPTION_SOURCES, "hybrid"),
        "asr_model": _choice(payload.get("asr_model"), VALID_ASR_MODELS, "medium"),
        "speech_language": _language(payload.get("speech_language"), "auto"),
        "transcript_languages": _language_list(payload.get("transcript_languages"), "auto"),
        "llm_provider": _choice(payload.get("llm_provider"), VALID_LLM_PROVIDERS, "deepseek"),
        "env_file": str(payload.get("env_file") or "../.env.local").strip(),
        "niche": str(payload.get("niche") or "").strip(),
        "workspace_name": str(payload.get("workspace_name") or "").strip(),
        "shell_components": (
            {}
            if is_template_only_style(brand_template)
            else normalize_shell_components(payload.get("shell_components"))
        ),
    }


def build_generation_command(config: dict[str, Any], validate_runtime: bool = False) -> list[str]:
    python_bin = resolve_generation_python(config) if validate_runtime else _preferred_python_for_command()
    command = [
        python_bin,
        "-m",
        "media_engine.cli",
        "premium-batch",
        "--profile",
        config["profile_id"],
        "--source-id",
        config["source_id"],
        "--youtube-url",
        config["source_url"],
        "--count",
        str(config["count"]),
        "--clip-length-preset",
        config["clip_length_preset"],
        "--clip-min-seconds",
        str(config["clip_min_seconds"]),
        "--clip-max-seconds",
        str(config["clip_max_seconds"]),
        "--genres",
        ",".join(config["genres"]),
        "--renderer",
        config["renderer"],
        "--hyperframes-template",
        config["hyperframes_template"],
        "--brand-system-template-id",
        config["brand_system_template_id"],
        "--hyperframes-format",
        config["hyperframes_format"],
        "--quality",
        config["quality"],
        "--caption-source",
        config["caption_source"],
        "--asr-model",
        config["asr_model"],
        "--speech-language",
        config["speech_language"],
        "--transcript-languages",
        config["transcript_languages"],
        "--style",
        config["brand_template"],
        "--llm-provider",
        config["llm_provider"],
        "--niche",
        config.get("niche") or "",
        "--workspace-name",
        config.get("workspace_name") or "",
        "--env-file",
        config["env_file"],
    ]
    if config.get("shell_components"):
        command.extend(
            ["--shell-components", json.dumps(config["shell_components"], separators=(",", ":"))]
        )
    return command


def _shell_command(command: list[str]) -> str:
    return " ".join(subprocess.list2cmdline([part]) for part in command)


def _extract_json(text: str) -> dict[str, Any]:
    marker = text.rfind("\n{")
    start = marker + 1 if marker >= 0 else text.find("{")
    if start < 0:
        return {}
    try:
        return json.loads(text[start:].strip())
    except json.JSONDecodeError:
        return {}


def create_generation_job(payload: dict[str, Any], start: bool = True) -> dict[str, Any]:
    config = normalize_generation_payload(payload)
    job_id = f"gen_{uuid.uuid4().hex[:12]}"
    command = build_generation_command(config, validate_runtime=True)
    conn = connect(DEFAULT_DB)
    try:
        initialize(conn)
        ensure_media_profile(conn, config["profile_id"])
        ensure_source_manifest(
            conn,
            profile_id=config["profile_id"],
            source_id=config["source_id"],
            source_url=config["source_url"],
        )
        seed_result = {"source_metadata": config.get("source_metadata") or {}}
        conn.execute(
            """
            INSERT INTO generation_jobs
              (id, profile_id, source_id, source_url, count, clip_length_preset, clip_min_seconds,
               clip_max_seconds, genres_json, brand_template, hyperframes_template,
               brand_system_template_id, hyperframes_format, renderer, quality, caption_source, asr_model, speech_language, transcript_languages,
               llm_provider, status, progress, command, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                config["profile_id"],
                config["source_id"],
                config["source_url"],
                config["count"],
                config["clip_length_preset"],
                config["clip_min_seconds"],
                config["clip_max_seconds"],
                json.dumps(config["genres"], ensure_ascii=False),
                config["brand_template"],
                config["hyperframes_template"],
                config["brand_system_template_id"],
                config["hyperframes_format"],
                config["renderer"],
                config["quality"],
                config["caption_source"],
                config["asr_model"],
                config["speech_language"],
                config["transcript_languages"],
                config["llm_provider"],
                "queued",
                0,
                _shell_command(command),
                json.dumps(seed_result, ensure_ascii=False),
            ),
        )
        conn.commit()
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc).lower():
            raise RuntimeError("Database is busy. Wait a moment and try again.") from exc
        raise
    finally:
        conn.close()
    if start:
        thread = threading.Thread(target=run_generation_job, args=(job_id, command), daemon=True)
        thread.start()
    return get_generation_job(job_id)


def append_job_log(conn, job_id: str, line: str, progress: int | None = None) -> None:
    if progress is None:
        conn.execute(
            """
            UPDATE generation_jobs
            SET log_text = substr(log_text || ?, -24000), updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (line, job_id),
        )
    else:
        conn.execute(
            """
            UPDATE generation_jobs
            SET log_text = substr(log_text || ?, -24000), progress = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (line, progress, job_id),
        )
    conn.commit()


def touch_generation_job(job_id: str) -> None:
    conn = connect(DEFAULT_DB)
    initialize(conn)
    conn.execute(
        """
        UPDATE generation_jobs
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status IN ('queued', 'running')
        """,
        (job_id,),
    )
    conn.commit()
    conn.close()


def reconcile_generation_jobs(conn, stale_minutes: int = GENERATION_JOB_STALE_MINUTES) -> int:
    note = "\n[media-engine] job marked failed after stale heartbeat timeout\n"
    result = conn.execute(
        """
        UPDATE generation_jobs
        SET status = 'failed',
            progress = 100,
            error = CASE
              WHEN trim(error) != '' THEN error
              ELSE 'Generation job lost heartbeat. The worker likely stopped, crashed, or was interrupted.'
            END,
            log_text = substr(log_text || ?, -24000),
            updated_at = CURRENT_TIMESTAMP
        WHERE status IN ('queued', 'running')
          AND updated_at < datetime('now', ?)
        """,
        (note, f"-{max(2, stale_minutes)} minutes"),
    )
    conn.commit()
    return result.rowcount


def _heartbeat_generation_job(job_id: str, stop_event: threading.Event) -> None:
    while not stop_event.wait(GENERATION_JOB_HEARTBEAT_SECONDS):
        touch_generation_job(job_id)


def _humanize_engine_exception(line: str) -> str:
    """Strip traceback class prefixes and map known curation fails to operator copy."""
    cleaned = re.sub(r"^(ValueError|RuntimeError|FileNotFoundError):\s*", "", line.strip(), flags=re.I)
    lower = cleaned.lower()
    if "did not produce enough valid" in lower or "returned no valid clip" in lower or "no candidate windows" in lower:
        return (
            "Couldn't find a usable clip in this video. "
            "Try a longer source or a looser duration range. Clip count is a maximum, not a quota."
        )
    if "transcript is too short" in lower:
        return "This video’s transcript is too short to pick clip candidates. Try a longer source video."
    return cleaned


def _failure_summary(output: str, code: int) -> str:
    """Prefer the last actionable exception/message over a bare exit code."""
    text = (output or "").strip()
    if not text:
        return f"premium-batch exited with code {code}"

    lower_full = text.lower()
    # Prefer operator-facing download blocks over "ERROR: ffmpeg exited with code 8".
    if "youtube blocked the clip download" in lower_full or (
        ("403" in lower_full or "forbidden" in lower_full) and ("googlevideo" in lower_full or "yt-dlp" in lower_full or "download" in lower_full)
    ):
        for line in text.splitlines():
            stripped = line.strip()
            if "YouTube blocked the clip download" in stripped:
                return stripped[:500]
        return (
            "YouTube blocked the clip download (HTTP 403). "
            "Update yt-dlp or set MEDIA_ENGINE_YTDLP_COOKIES, then retry."
        )

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        lower = line.lower()
        if lower.startswith("traceback"):
            continue
        # Bare ffmpeg exit is usually a symptom of a CDN/yt-dlp failure above.
        if "ffmpeg exited with code" in lower and ("403" in lower_full or "forbidden" in lower_full):
            continue
        if line.startswith("RuntimeError:") or line.startswith("ValueError:") or line.startswith("FileNotFoundError:"):
            return _humanize_engine_exception(line)[:500]
        if lower.startswith("runtimeerror:") or lower.startswith("valueerror:") or lower.startswith("filenotfounderror:"):
            return _humanize_engine_exception(line)[:500]
        if "error:" in lower and "ffmpeg exited" not in lower:
            return line[:500]
    # Fall back to last non-progress line
    for line in reversed(lines):
        if "[media-engine]" in line:
            continue
        if line.startswith("File ") or line.startswith("~~"):
            continue
        return f"premium-batch exited with code {code}: {line[:400]}"
    return f"premium-batch exited with code {code}"


def run_generation_job(job_id: str, command: list[str]) -> None:
    conn = connect(DEFAULT_DB)
    initialize(conn)
    conn.execute("UPDATE generation_jobs SET status = 'running', progress = 5, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
    conn.commit()
    output = ""
    heartbeat_stop = threading.Event()
    heartbeat_thread = threading.Thread(target=_heartbeat_generation_job, args=(job_id, heartbeat_stop), daemon=True)
    heartbeat_thread.start()
    try:
        python_bin = command[0]
        python_dir = str(Path(python_bin).parent)
        resolved_ytdlp = _resolve_tool_for_python(python_bin, "yt-dlp") or _resolve_tool_for_python(python_bin, "yt_dlp") or ""
        runtime_env = {**os.environ, "PYTHONPATH": str(ROOT), "MEDIA_ENGINE_PYTHON": python_bin}
        if resolved_ytdlp:
            runtime_env["MEDIA_ENGINE_YTDLP"] = resolved_ytdlp
        runtime_env["PATH"] = ":".join(
            [
                python_dir,
                "/opt/homebrew/opt/node/bin",
                "/opt/homebrew/bin",
                "/usr/local/bin",
                os.environ.get("PATH", ""),
            ]
        )
        process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=runtime_env,
        )
        assert process.stdout is not None
        for line in process.stdout:
            output += line
            progress = None
            if "[media-engine]" in line:
                progress = min(95, 10 + output.count("[media-engine]") * 4)
            append_job_log(conn, job_id, line, progress)
        code = process.wait()
        result = _extract_json(output)
        existing_row = conn.execute("SELECT result_json FROM generation_jobs WHERE id = ?", (job_id,)).fetchone()
        try:
            existing_result = json.loads((existing_row["result_json"] if existing_row else None) or "{}")
        except (TypeError, json.JSONDecodeError, KeyError):
            existing_result = {}
        if isinstance(existing_result, dict) and existing_result.get("source_metadata") and isinstance(result, dict):
            result = {**result, "source_metadata": existing_result.get("source_metadata")}
        elif isinstance(existing_result, dict) and existing_result.get("source_metadata") and not result:
            result = {"source_metadata": existing_result.get("source_metadata")}
        if code != 0:
            conn.execute(
                """
                UPDATE generation_jobs
                SET status = 'failed', progress = 100, result_json = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(result, ensure_ascii=False), _failure_summary(output, code), job_id),
            )
        else:
            conn.execute(
                """
                UPDATE generation_jobs
                SET status = 'completed', progress = 100, result_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(result, ensure_ascii=False), job_id),
            )
        conn.commit()
    except Exception as exc:  # pragma: no cover - defensive background guard
        conn.execute(
            """
            UPDATE generation_jobs
            SET status = 'failed', progress = 100, error = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (str(exc), job_id),
        )
        conn.commit()
    finally:
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=1)
        conn.close()


def get_generation_job(job_id: str) -> dict[str, Any]:
    conn = connect(DEFAULT_DB)
    initialize(conn)
    reconcile_generation_jobs(conn)
    row = conn.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        raise ValueError("generation job not found")
    item = dict(row)
    item["result"] = json.loads(item.get("result_json") or "{}")
    item["genres"] = json.loads(item.get("genres_json") or "[]")
    return item


def list_generation_jobs(limit: int = 12) -> list[dict[str, Any]]:
    conn = connect(DEFAULT_DB)
    initialize(conn)
    reconcile_generation_jobs(conn)
    rows = conn.execute(
        "SELECT * FROM generation_jobs ORDER BY created_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    jobs = []
    for row in rows:
        item = dict(row)
        item["result"] = json.loads(item.get("result_json") or "{}")
        item["genres"] = json.loads(item.get("genres_json") or "[]")
        jobs.append(item)
    return jobs
