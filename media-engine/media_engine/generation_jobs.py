"""Background generation jobs launched from the local review dashboard."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

from .db import DEFAULT_DB, ROOT, connect, initialize
from .duration_presets import resolve_duration_preset


VALID_RENDERERS = {"ffmpeg", "remotion"}
VALID_QUALITIES = {"draft", "production"}
VALID_CAPTION_SOURCES = {"youtube", "whisper", "hybrid"}
VALID_ASR_MODELS = {"small", "medium", "large-v3-turbo"}
VALID_LLM_PROVIDERS = {"none", "openai", "deepseek", "groq"}
VALID_LANGUAGES = {"id", "en", "ar", "ms", "auto"}


def _runtime_requirements(config: dict[str, Any]) -> list[str]:
    modules = ["youtube_transcript_api"]
    if config.get("caption_source") in {"whisper", "hybrid"}:
        modules.append("faster_whisper")
    return modules


def _python_has_modules(python_bin: str, modules: list[str]) -> bool:
    if not modules:
        return True
    code = "import importlib.util, sys; sys.exit(0 if all(importlib.util.find_spec(m) for m in sys.argv[1:]) else 1)"
    result = subprocess.run([python_bin, "-c", code, *modules], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0


def _candidate_python_bins() -> list[Path]:
    candidates = []
    if os.environ.get("MEDIA_ENGINE_PYTHON"):
        candidates.append(Path(os.environ["MEDIA_ENGINE_PYTHON"]))
    candidates.extend(
        [
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
    required = _runtime_requirements(config)
    existing = [path for path in _candidate_python_bins() if path.exists()]
    for path in existing:
        if _python_has_modules(str(path), required):
            return str(path)
    checked = ", ".join(str(path) for path in existing) or "none"
    missing = ", ".join(required)
    raise RuntimeError(
        f"Generation runtime is missing required Python modules: {missing}. "
        "Create the local tools environment with `python3.13 -m venv /tmp/media-engine-tools-py313` "
        "and install the media engine dependencies, or set MEDIA_ENGINE_PYTHON to a compatible interpreter. "
        f"Checked: {checked}"
    )


def list_brand_templates() -> list[dict[str, str]]:
    profiles = ROOT / "profiles"
    templates = []
    for path in sorted(profiles.glob("*.json")):
        if path.name == "nourbit.json":
            continue
        label = path.stem.replace("_", " ").replace("-", " ").title()
        templates.append({"id": str(path.relative_to(ROOT)), "label": label, "path": str(path.relative_to(ROOT))})
    if not templates:
        templates.append({"id": "profiles/nourbit_opus_style.json", "label": "Nourbit Opus Style", "path": "profiles/nourbit_opus_style.json"})
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


def _language(value: Any, default: str = "id") -> str:
    text = str(value or default).strip().lower()
    return text if text in VALID_LANGUAGES else default


def _language_list(value: Any, default: str = "id,en") -> str:
    parts = [part.strip().lower() for part in str(value or default).split(",") if part.strip()]
    allowed = [part for part in parts if part in VALID_LANGUAGES and part != "auto"]
    return ",".join(allowed or ["id", "en"])


def normalize_generation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    source_url = str(payload.get("source_url") or "").strip()
    if not source_url:
        raise ValueError("source_url is required")
    brand_template = str(payload.get("brand_template") or "profiles/nourbit_opus_style.json").strip()
    template_path = (ROOT / brand_template).resolve()
    if ROOT.resolve() not in template_path.parents or not template_path.exists():
        raise ValueError("brand_template not found")
    return {
        "profile_id": str(payload.get("profile_id") or "nourbit").strip(),
        "source_id": str(payload.get("source_id") or "nourbit_nouraniyyahofficial").strip(),
        "source_url": source_url,
        "count": _int_range(payload.get("count"), 5, 1, 10),
        "clip_length_preset": resolve_duration_preset(str(payload.get("clip_length_preset") or "deep_context")).id,
        "brand_template": brand_template,
        "renderer": _choice(payload.get("renderer"), VALID_RENDERERS, "remotion"),
        "quality": _choice(payload.get("quality"), VALID_QUALITIES, "production"),
        "caption_source": _choice(payload.get("caption_source"), VALID_CAPTION_SOURCES, "whisper"),
        "asr_model": _choice(payload.get("asr_model"), VALID_ASR_MODELS, "medium"),
        "speech_language": _language(payload.get("speech_language"), "id"),
        "transcript_languages": _language_list(payload.get("transcript_languages"), "id,en"),
        "llm_provider": _choice(payload.get("llm_provider"), VALID_LLM_PROVIDERS, "deepseek"),
        "env_file": str(payload.get("env_file") or "../.env.local").strip(),
    }


def build_generation_command(config: dict[str, Any], validate_runtime: bool = False) -> list[str]:
    python_bin = resolve_generation_python(config) if validate_runtime else str(_candidate_python_bins()[0])
    return [
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
        "--renderer",
        config["renderer"],
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
        "--env-file",
        config["env_file"],
    ]


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
    initialize(conn)
    conn.execute(
        """
        INSERT INTO generation_jobs
          (id, profile_id, source_id, source_url, count, clip_length_preset, brand_template,
           renderer, quality, caption_source, asr_model, speech_language, transcript_languages,
           llm_provider, status, progress, command)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            config["profile_id"],
            config["source_id"],
            config["source_url"],
            config["count"],
            config["clip_length_preset"],
            config["brand_template"],
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
        ),
    )
    conn.commit()
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


def run_generation_job(job_id: str, command: list[str]) -> None:
    conn = connect(DEFAULT_DB)
    initialize(conn)
    conn.execute("UPDATE generation_jobs SET status = 'running', progress = 5, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
    conn.commit()
    output = ""
    try:
        process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONPATH": str(ROOT)},
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
        if code != 0:
            conn.execute(
                """
                UPDATE generation_jobs
                SET status = 'failed', progress = 100, result_json = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(result, ensure_ascii=False), f"premium-batch exited with code {code}", job_id),
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
        conn.close()


def get_generation_job(job_id: str) -> dict[str, Any]:
    conn = connect(DEFAULT_DB)
    initialize(conn)
    row = conn.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        raise ValueError("generation job not found")
    item = dict(row)
    item["result"] = json.loads(item.get("result_json") or "{}")
    return item


def list_generation_jobs(limit: int = 12) -> list[dict[str, Any]]:
    conn = connect(DEFAULT_DB)
    initialize(conn)
    rows = conn.execute(
        "SELECT * FROM generation_jobs ORDER BY created_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    jobs = []
    for row in rows:
        item = dict(row)
        item["result"] = json.loads(item.get("result_json") or "{}")
        jobs.append(item)
    return jobs
