"""Cursor Cloud Agents API + Automation webhook helpers (Path A)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_API_BASE = "https://api.cursor.com"
TERMINAL_RUN_STATUSES = frozenset({"FINISHED", "ERROR", "CANCELLED", "EXPIRED"})
VIDEO_URL_LINE_RE = re.compile(
    r"(?im)^\s*(?:VIDEO_URL|video_url)\s*[:=]\s*(?P<url>https?://\S+)"
)
HEYGEN_URL_RE = re.compile(
    r"(?i)(?P<url>https?://(?:files\d*\.)?heygen\.ai/[^\s\"'<>]+|(?:https?://[^\s\"'<>]*heygen[^\s\"'<>]+\.mp4[^\s\"'<>]*))"
)
GENERIC_MP4_URL_RE = re.compile(r"(?i)(?P<url>https?://[^\s\"'<>]+\.mp4(?:\?[^\s\"'<>]*)?)")


class CursorCloudError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status = status
        self.payload = payload


@dataclass(frozen=True)
class CursorCloudConfig:
    api_key: str
    api_base: str = DEFAULT_API_BASE
    webhook_url: str = ""
    webhook_token: str = ""
    dry_run: bool = False
    dry_run_video_url: str = ""
    timeout_seconds: int = 1800
    poll_interval_seconds: float = 15.0

    @classmethod
    def from_env(cls) -> CursorCloudConfig:
        dry = (os.environ.get("CURSOR_API_DRY_RUN") or "").strip().lower() in {"1", "true", "yes"}
        try:
            timeout = int(os.environ.get("CURSOR_PATH_A_TIMEOUT_SECONDS") or "1800")
        except ValueError:
            timeout = 1800
        try:
            poll = float(os.environ.get("CURSOR_PATH_A_POLL_INTERVAL_SECONDS") or "15")
        except ValueError:
            poll = 15.0
        raw_key = os.environ.get("CURSOR_API_KEY") or ""
        api_key = raw_key.strip()
        raw_webhook_token = os.environ.get("CURSOR_AUTOMATION_WEBHOOK_TOKEN") or ""
        webhook_token = raw_webhook_token.strip() or api_key
        return cls(
            api_key=api_key,
            api_base=(os.environ.get("CURSOR_API_BASE") or DEFAULT_API_BASE).rstrip("/"),
            webhook_url=(os.environ.get("CURSOR_AUTOMATION_WEBHOOK_URL") or "").strip(),
            webhook_token=webhook_token,
            dry_run=dry,
            dry_run_video_url=(os.environ.get("CURSOR_DRY_RUN_VIDEO_URL") or "").strip(),
            timeout_seconds=max(60, timeout),
            poll_interval_seconds=max(2.0, poll),
        )

    def require_trigger(self) -> None:
        if self.dry_run:
            return
        if not self.api_key and not self.webhook_url:
            raise CursorCloudError(
                "Set CURSOR_API_KEY and/or CURSOR_AUTOMATION_WEBHOOK_URL "
                "(or CURSOR_API_DRY_RUN=1 for local tests)."
            )
        if self.webhook_url and not self.webhook_token:
            raise CursorCloudError(
                "CURSOR_AUTOMATION_WEBHOOK_URL requires CURSOR_AUTOMATION_WEBHOOK_TOKEN "
                "or CURSOR_API_KEY (Bearer)."
            )
        if not self.webhook_url and not self.api_key:
            raise CursorCloudError("CURSOR_API_KEY is required when no automation webhook is set.")


def build_path_a_prompt(
    *,
    topic: str,
    title: str = "",
    script: str = "",
    job_id: str = "",
    voice_id: str | None = None,
    avatar_look_id: str | None = None,
) -> str:
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("topic is required")
    voice = (voice_id or os.environ.get("HEYGEN_VOICE_ID") or "0e0c18c072cf4ab6b617dd981f271670").strip()
    look = (
        avatar_look_id
        or os.environ.get("HEYGEN_AVATAR_LOOK_ID")
        or "3ad1d28c72c14ac7940be96b896cac60"
    ).strip()
    title_line = (title or topic).strip()
    script_block = (script or "").strip()
    parts = [
        "You are generating ONE landscape TechTalk edu-finance video via HeyGen MCP Video Agent.",
        f"OTONOM_JOB_ID: {job_id}" if job_id else "",
        f"Topic: {topic}",
        f"Title: {title_line}",
        f"Avatar look_id (avatarId): {look}",
        f"voice_id: {voice}",
        "Use create_video_agent with mode=generate, orientation=landscape.",
        "Poll until status=completed and video_url is set.",
        "Do NOT approve, publish, or call Otonom ingest (Otonom will poll and ingest locally).",
        "When done, your FINAL reply MUST include exactly one line:",
        "VIDEO_URL: https://...",
        "Also include the title on a line: TITLE: ...",
    ]
    if script_block:
        parts.insert(4, f"Script / brief:\n{script_block}")
    return "\n".join(line for line in parts if line)


def extract_video_url(text: str) -> str | None:
    raw = text or ""
    match = VIDEO_URL_LINE_RE.search(raw)
    if match:
        return _clean_url(match.group("url"))
    for pattern in (HEYGEN_URL_RE, GENERIC_MP4_URL_RE):
        found = pattern.search(raw)
        if found:
            return _clean_url(found.group("url"))
    return None


def _clean_url(url: str) -> str:
    return url.rstrip(").,];>\"'")


def _auth_header(token: str) -> str:
    # Cursor accepts Basic (key as username) or Bearer.
    return f"Bearer {token}"


def _request_json(
    method: str,
    url: str,
    *,
    token: str,
    body: dict[str, Any] | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    data = None
    headers = {
        "Authorization": _auth_header(token),
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        payload: Any = err_body
        try:
            payload = json.loads(err_body) if err_body else None
        except json.JSONDecodeError:
            payload = err_body
        raise CursorCloudError(
            f"Cursor API {method} {url} failed ({exc.code}): {err_body[:800]}",
            status=exc.code,
            payload=payload,
        ) from exc
    except urllib.error.URLError as exc:
        raise CursorCloudError(f"Cursor API network error: {exc}") from exc

    if not raw:
        return {}
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, dict) else {"result": parsed}


def create_agent(
    prompt: str,
    *,
    config: CursorCloudConfig,
    name: str | None = None,
) -> dict[str, Any]:
    """POST /v1/agents — no-repo agent with initial run."""
    config.require_trigger()
    if config.dry_run:
        return {
            "dry_run": True,
            "agent": {"id": "bc-dry-run", "name": name or "Path A dry run"},
            "run": {
                "id": "run-dry-run",
                "agentId": "bc-dry-run",
                "status": "FINISHED",
                "result": f"VIDEO_URL: {config.dry_run_video_url or 'https://example.com/dry-run.mp4'}\nTITLE: dry-run",
            },
        }
    if not config.api_key:
        raise CursorCloudError("CURSOR_API_KEY is required to create a Cloud Agent")
    body: dict[str, Any] = {
        "prompt": {"text": prompt},
        "repos": [],
        "autoCreatePR": False,
    }
    if name:
        body["name"] = name[:100]
    return _request_json(
        "POST",
        f"{config.api_base}/v1/agents",
        token=config.api_key,
        body=body,
    )


def get_run(agent_id: str, run_id: str, *, config: CursorCloudConfig) -> dict[str, Any]:
    if config.dry_run:
        return {
            "id": run_id,
            "agentId": agent_id,
            "status": "FINISHED",
            "result": f"VIDEO_URL: {config.dry_run_video_url or 'https://example.com/dry-run.mp4'}",
        }
    if not config.api_key:
        raise CursorCloudError("CURSOR_API_KEY is required to poll runs")
    return _request_json(
        "GET",
        f"{config.api_base}/v1/agents/{urllib.parse.quote(agent_id)}/runs/{urllib.parse.quote(run_id)}",
        token=config.api_key,
    )


def get_agent(agent_id: str, *, config: CursorCloudConfig) -> dict[str, Any]:
    if config.dry_run:
        return {"id": agent_id, "latestRunId": "run-dry-run", "status": "ACTIVE"}
    if not config.api_key:
        raise CursorCloudError("CURSOR_API_KEY is required to fetch agent")
    return _request_json(
        "GET",
        f"{config.api_base}/v1/agents/{urllib.parse.quote(agent_id)}",
        token=config.api_key,
    )


def fire_automation_webhook(
    payload: dict[str, Any],
    *,
    config: CursorCloudConfig,
) -> dict[str, Any]:
    """POST Cursor Automation webhook. Payload is appended to the automation prompt."""
    config.require_trigger()
    if config.dry_run:
        return {
            "dry_run": True,
            "id": "bc-dry-run",
            "agentId": "bc-dry-run",
            "runId": "run-dry-run",
        }
    if not config.webhook_url:
        raise CursorCloudError("CURSOR_AUTOMATION_WEBHOOK_URL is not set")
    return _request_json(
        "POST",
        config.webhook_url,
        token=config.webhook_token,
        body=payload,
    )


def parse_agent_run_ids(payload: Any) -> tuple[str | None, str | None]:
    """Best-effort extract (agent_id, run_id) from API or webhook responses."""
    if not isinstance(payload, dict):
        return None, None

    agent_id: str | None = None
    run_id: str | None = None

    run = payload.get("run")
    if isinstance(run, dict):
        run_id = _normalize_id(_first_str(run, ("id", "runId")))
        agent_id = _normalize_id(_first_str(run, ("agentId", "agent_id")))

    agent = payload.get("agent")
    if isinstance(agent, dict):
        agent_id = agent_id or _normalize_id(_first_str(agent, ("id", "agentId")))
        run_id = run_id or _normalize_id(_first_str(agent, ("latestRunId", "runId")))

    agent_id = agent_id or _normalize_id(
        _first_str(payload, ("agentId", "agent_id"))
    )
    run_id = run_id or _normalize_id(
        _first_str(payload, ("runId", "run_id", "latestRunId"))
    )

    top_id = str(payload.get("id") or "").strip()
    if top_id.startswith("bc-") or top_id.startswith("bc_"):
        agent_id = agent_id or _normalize_id(top_id)
    if top_id.startswith("run-"):
        run_id = run_id or top_id

    return agent_id, run_id


def _normalize_id(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if text.startswith("bc_"):
        return "bc-" + text[3:]
    return text


def _first_str(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None