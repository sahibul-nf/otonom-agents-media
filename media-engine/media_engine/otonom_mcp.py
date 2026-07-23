"""Thin Otonom MCP server (stdio JSON-RPC) for Cursor / Claude / Codex agents.

Tools wrap Explainer Phase 0 — no HeyGen Direct API required.
Approve/publish stay dashboard-first.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .db import DEFAULT_DB, DEFAULT_WORKSPACE_PROFILE_ID
from .explainer_pipeline import (
    create_explainer_job,
    import_avatar_clip,
    list_explainer_jobs,
    list_review_queue,
    read_explainer_status,
    run_explainer,
)

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "otonom-media", "version": "0.1.0"}

TOOLS = [
    {
        "name": "create_explainer",
        "description": (
            "Create an Explainer job (scene plan + fixtures folder) and optionally stitch "
            "when avatar fixtures are already present. Returns job_id and paths."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Explainer topic / title"},
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional source notes or URLs",
                },
                "language": {"type": "string", "default": "id"},
                "llm_provider": {
                    "type": "string",
                    "enum": ["none", "openai", "deepseek", "groq"],
                    "default": "none",
                },
                "profile_id": {"type": "string", "default": DEFAULT_WORKSPACE_PROFILE_ID},
                "run_now": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, stitch immediately (requires avatar fixtures for avatar scenes)",
                },
                "ffmpeg_only": {
                    "type": "boolean",
                    "default": True,
                    "description": "Prefer FFmpeg title cards over HyperFrames for text/broll",
                },
            },
            "required": ["topic"],
        },
    },
    {
        "name": "get_explainer_status",
        "description": "Get status / artifact paths for an explainer job_id",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string"},
                "profile_id": {"type": "string", "default": DEFAULT_WORKSPACE_PROFILE_ID},
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "list_review_queue",
        "description": "List non-archived clip candidates ready for human review in the dashboard",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 30},
            },
        },
    },
    {
        "name": "import_avatar_clip",
        "description": (
            "Register a local MP4 path or HTTPS URL (e.g. HeyGen download) into an explainer "
            "job fixtures folder. No HeyGen Direct API key required."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string"},
                "dest_name": {
                    "type": "string",
                    "description": "Filename in fixtures/, e.g. scene_01.mp4",
                },
                "source": {
                    "type": "string",
                    "description": "Local filesystem path or https URL",
                },
                "profile_id": {"type": "string", "default": DEFAULT_WORKSPACE_PROFILE_ID},
            },
            "required": ["job_id", "dest_name", "source"],
        },
    },
    {
        "name": "run_explainer",
        "description": "Stitch an existing explainer job (after fixtures imported) into review queue",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string"},
                "profile_id": {"type": "string", "default": DEFAULT_WORKSPACE_PROFILE_ID},
                "ffmpeg_only": {"type": "boolean", "default": True},
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "list_explainer_jobs",
        "description": "List recent explainer jobs for a profile",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile_id": {"type": "string", "default": DEFAULT_WORKSPACE_PROFILE_ID},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
]


def _tool_result(payload: Any, *, is_error: bool = False) -> dict[str, Any]:
    text = payload if isinstance(payload, str) else json.dumps(payload, indent=2, ensure_ascii=False)
    return {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }


def call_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    args = arguments or {}
    try:
        if name == "create_explainer":
            topic = str(args.get("topic") or "").strip()
            if not topic:
                raise ValueError("topic is required")
            profile_id = str(args.get("profile_id") or DEFAULT_WORKSPACE_PROFILE_ID)
            sources = args.get("sources") if isinstance(args.get("sources"), list) else []
            created = create_explainer_job(
                topic=topic,
                sources=[str(s) for s in sources],
                profile_id=profile_id,
                llm_provider=str(args.get("llm_provider") or "none"),
                language=str(args.get("language") or "id"),
                db_path=DEFAULT_DB,
            )
            if args.get("run_now"):
                created = run_explainer(
                    job_id=created["job_id"],
                    profile_id=profile_id,
                    prefer_hyperframes=not bool(args.get("ffmpeg_only", True)),
                    db_path=DEFAULT_DB,
                )
            return _tool_result(created)

        if name == "get_explainer_status":
            job_id = str(args.get("job_id") or "").strip()
            profile_id = str(args.get("profile_id") or DEFAULT_WORKSPACE_PROFILE_ID)
            return _tool_result(read_explainer_status(job_id, profile_id=profile_id))

        if name == "list_review_queue":
            limit = int(args.get("limit") or 30)
            return _tool_result(list_review_queue(db_path=DEFAULT_DB, limit=limit))

        if name == "import_avatar_clip":
            path = import_avatar_clip(
                job_id=str(args.get("job_id") or "").strip(),
                dest_name=str(args.get("dest_name") or "").strip(),
                source=str(args.get("source") or "").strip(),
                profile_id=str(args.get("profile_id") or DEFAULT_WORKSPACE_PROFILE_ID),
            )
            return _tool_result({"ok": True, "path": str(path)})

        if name == "run_explainer":
            job_id = str(args.get("job_id") or "").strip()
            profile_id = str(args.get("profile_id") or DEFAULT_WORKSPACE_PROFILE_ID)
            result = run_explainer(
                job_id=job_id,
                profile_id=profile_id,
                prefer_hyperframes=not bool(args.get("ffmpeg_only", True)),
                db_path=DEFAULT_DB,
            )
            return _tool_result(result)

        if name == "list_explainer_jobs":
            profile_id = str(args.get("profile_id") or DEFAULT_WORKSPACE_PROFILE_ID)
            limit = int(args.get("limit") or 20)
            return _tool_result(list_explainer_jobs(profile_id=profile_id, limit=limit))

        return _tool_result(f"Unknown tool: {name}", is_error=True)
    except Exception as exc:
        return _tool_result({"error": str(exc)}, is_error=True)


def handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        return {"jsonrpc": "2.0", "id": msg_id, "result": call_tool(name, arguments)}

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if msg_id is None:
        return None

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> None:
    # Ensure media-engine root is importable when launched as module from repo root.
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle_message(message)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
