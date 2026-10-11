"""Path A jobs: Cursor generate → poll → local ingest → Telegram status."""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cursor_cloud import (
    TERMINAL_RUN_STATUSES,
    CursorCloudConfig,
    CursorCloudError,
    build_path_a_prompt,
    create_agent,
    extract_video_url,
    fire_automation_webhook,
    get_agent,
    get_run,
    parse_agent_run_ids,
)
from .db import ARTIFACTS_DIR, DEFAULT_WORKSPACE_PROFILE_ID
from .ingest_longform import ingest_longform
from .status_notify import send_status_telegram


def path_a_jobs_root(profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID) -> Path:
    path = ARTIFACTS_DIR / profile_id / "path_a_jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def path_a_job_dir(job_id: str, profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID) -> Path:
    path = path_a_jobs_root(profile_id) / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_status(root: Path, status: dict[str, Any]) -> None:
    status = {**status, "updated_at": _now()}
    (root / "status.json").write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")


def read_path_a_status(job_id: str, profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID) -> dict[str, Any]:
    path = path_a_job_dir(job_id, profile_id) / "status.json"
    if not path.exists():
        raise FileNotFoundError(f"Path A job not found: {job_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_path_a_jobs(profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID, limit: int = 20) -> list[dict[str, Any]]:
    root = path_a_jobs_root(profile_id)
    jobs: list[dict[str, Any]] = []
    for path in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        status_file = path / "status.json"
        if not status_file.is_file():
            continue
        try:
            jobs.append(json.loads(status_file.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
        if len(jobs) >= limit:
            break
    return jobs


def start_path_a_generate(
    *,
    topic: str,
    title: str = "",
    script: str = "",
    profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID,
    config: CursorCloudConfig | None = None,
    topic_proposal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a Path A job and run Cursor→ingest→Telegram in a background thread."""
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("topic is required")
    cfg = config or CursorCloudConfig.from_env()
    cfg.require_trigger()

    job_id = f"patha_{uuid.uuid4().hex[:10]}"
    title = (title or topic).strip()
    script = (script or "").strip()
    root = path_a_job_dir(job_id, profile_id)
    prompt = build_path_a_prompt(topic=topic, title=title, script=script, job_id=job_id)

    status: dict[str, Any] = {
        "job_id": job_id,
        "profile_id": profile_id,
        "topic": topic,
        "title": title,
        "script": script,
        "status": "starting",
        "error": "",
        "agent_id": "",
        "run_id": "",
        "agent_url": "",
        "video_url": "",
        "candidate_ids": [],
        "ingest_job_id": "",
        "telegram_notified": False,
        "trigger_mode": "",
        "created_at": _now(),
        "prompt": prompt,
    }
    if topic_proposal:
        status["topic_proposal"] = topic_proposal
    _write_status(root, status)

    def _worker() -> None:
        try:
            _run_path_a_job(job_id=job_id, profile_id=profile_id, config=cfg)
        except Exception as exc:  # noqa: BLE001 — persist any failure
            try:
                current = read_path_a_status(job_id, profile_id)
            except FileNotFoundError:
                current = status
            current["status"] = "failed"
            current["error"] = str(exc)
            _write_status(path_a_job_dir(job_id, profile_id), current)
            _notify_safe(
                f"❌ Path A failed\n<b>{_escape(title)}</b>\n<code>{_escape(job_id)}</code>\n{_escape(str(exc)[:500])}"
            )

    threading.Thread(target=_worker, daemon=True, name=f"path-a-{job_id}").start()
    return status


def _run_path_a_job(
    *,
    job_id: str,
    profile_id: str,
    config: CursorCloudConfig,
) -> dict[str, Any]:
    root = path_a_job_dir(job_id, profile_id)
    status = read_path_a_status(job_id, profile_id)
    prompt = str(status.get("prompt") or "")
    title = str(status.get("title") or status.get("topic") or job_id)

    status["status"] = "triggering"
    _write_status(root, status)

    agent_id, run_id, trigger_mode = _trigger_cursor(job_id=job_id, prompt=prompt, status=status, config=config)
    status["agent_id"] = agent_id or ""
    status["run_id"] = run_id or ""
    status["trigger_mode"] = trigger_mode
    if agent_id:
        status["agent_url"] = f"https://cursor.com/agents/{agent_id}"
    status["status"] = "polling"
    _write_status(root, status)

    if not agent_id or not run_id:
        raise CursorCloudError(
            "Could not resolve Cursor agent/run id after trigger. "
            "Set CURSOR_API_KEY (preferred with webhook) or use CURSOR_API_DRY_RUN=1."
        )

    result_text = _poll_run(agent_id=agent_id, run_id=run_id, status=status, root=root, config=config)
    video_url = extract_video_url(result_text or "")
    if not video_url:
        raise CursorCloudError(
            "Cursor run finished but no video_url found in the final reply. "
            "Ensure the Automation prompt ends with VIDEO_URL: https://..."
        )

    status["video_url"] = video_url
    status["status"] = "ingesting"
    _write_status(root, status)

    ingest = ingest_longform(
        source=video_url,
        mode="review_only",
        title=title,
        profile_id=profile_id,
    )
    candidate_ids = list(ingest.get("candidate_ids") or [])
    status["candidate_ids"] = candidate_ids
    status["ingest_job_id"] = str(ingest.get("job_id") or "")
    status["status"] = "ready"
    status["error"] = ""
    _write_status(root, status)

    first = candidate_ids[0] if candidate_ids else ""
    msg = (
        f"✅ Path A ready for Review\n"
        f"<b>{_escape(title)}</b>\n"
        f"job: <code>{_escape(job_id)}</code>\n"
        f"candidate: <code>{_escape(first or '—')}</code>\n"
        f"Open Otonom → Review to approve (no auto-publish)."
    )
    try:
        send_status_telegram(msg)
        status["telegram_notified"] = True
    except RuntimeError as exc:
        status["telegram_error"] = str(exc)
    _write_status(root, status)
    return status


def _trigger_cursor(
    *,
    job_id: str,
    prompt: str,
    status: dict[str, Any],
    config: CursorCloudConfig,
) -> tuple[str | None, str | None, str]:
    """Return (agent_id, run_id, trigger_mode)."""
    if config.dry_run:
        created = create_agent(prompt, config=config, name=f"Path A {job_id}")
        agent_id, run_id = parse_agent_run_ids(created)
        return agent_id, run_id, "dry_run"

    # Prefer Automation webhook when configured (HeyGen MCP already attached).
    if config.webhook_url:
        payload = {
            "otonom_job_id": job_id,
            "topic": status.get("topic"),
            "title": status.get("title"),
            "script": status.get("script") or "",
            "prompt": prompt,
            "text": prompt,
        }
        webhook_resp = fire_automation_webhook(payload, config=config)
        agent_id, run_id = parse_agent_run_ids(webhook_resp)
        if agent_id and not run_id and config.api_key:
            agent = get_agent(agent_id, config=config)
            run_id = str(agent.get("latestRunId") or "").strip() or None
            agent_id = str(agent.get("id") or agent_id).strip()
        if agent_id and run_id:
            return agent_id, run_id, "webhook"
        raise CursorCloudError(
            "Automation webhook fired but response had no agent/run id to poll. "
            "Ensure the webhook response includes agent id + run id, or unset "
            "CURSOR_AUTOMATION_WEBHOOK_URL and use CURSOR_API_KEY create instead "
            "(Cloud Agent must have HeyGen MCP available)."
        )

    created = create_agent(prompt, config=config, name=f"Path A {job_id}"[:100])
    agent_id, run_id = parse_agent_run_ids(created)
    return agent_id, run_id, "api"

def _poll_run(
    *,
    agent_id: str,
    run_id: str,
    status: dict[str, Any],
    root: Path,
    config: CursorCloudConfig,
) -> str:
    deadline = time.monotonic() + config.timeout_seconds
    last_status = ""
    while time.monotonic() < deadline:
        run = get_run(agent_id, run_id, config=config)
        run_status = str(run.get("status") or "").upper()
        status["cursor_run_status"] = run_status
        if run_status != last_status:
            _write_status(root, status)
            last_status = run_status
        if run_status in TERMINAL_RUN_STATUSES:
            if run_status != "FINISHED":
                raise CursorCloudError(
                    f"Cursor run ended with status={run_status}: {str(run.get('result') or '')[:400]}"
                )
            return str(run.get("result") or "")
        time.sleep(config.poll_interval_seconds)

    raise CursorCloudError(
        f"Timed out after {config.timeout_seconds}s waiting for Cursor run {run_id} "
        f"(last status={last_status or 'unknown'})"
    )


def _notify_safe(message: str) -> None:
    try:
        send_status_telegram(message)
    except RuntimeError:
        return


def _escape(value: str) -> str:
    return (
        (value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
