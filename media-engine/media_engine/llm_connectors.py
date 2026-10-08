"""Discover and connect local LLM agent CLIs (BYO subscription, no API key)."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from .credential_vault import get_profile_secrets, set_profile_secrets
from .llm import LLMError, call_llm_agent_json, llm_provider_ready

CONNECTOR_STATE_UNDETECTED = "undetected"
CONNECTOR_STATE_DETECTED = "detected"
CONNECTOR_STATE_CONFIGURED = "configured"
CONNECTOR_STATE_READY = "ready"
CONNECTOR_STATE_ERROR = "error"
CONNECTOR_STATE_STALE = "stale"

VAULT_CONNECTOR_KEY = "OTONOM_LLM_AGENT_CONNECTOR"
VAULT_LAST_ERROR_KEY = "OTONOM_LLM_AGENT_LAST_ERROR"
VAULT_TEST_OK_KEY = "OTONOM_LLM_AGENT_TEST_OK"
VAULT_COMMAND_KEY = "OTONOM_LLM_AGENT_COMMAND"


@dataclass(frozen=True)
class LlmConnectorSpec:
    id: str
    label: str
    binaries: tuple[str, ...]
    command: str
    auth_hint: str


# Cursor Agent without --trust exits non-interactively with "Workspace Trust Required".
CURSOR_AGENT_COMMAND_LEGACY = "cursor agent --print --output-format json"

# Fixed commands only — UI connect must not accept arbitrary shell from users.
CONNECTOR_SPECS: tuple[LlmConnectorSpec, ...] = (
    LlmConnectorSpec(
        id="cursor_agent",
        label="Cursor Agent",
        binaries=("cursor",),
        command="cursor agent --print --output-format json --trust",
        auth_hint="Sign in to Cursor on this machine. Non-interactive runs need workspace trust (--trust); or run `cursor agent` once in this repo to approve.",
    ),
    LlmConnectorSpec(
        id="antigravity",
        label="Antigravity (agy)",
        binaries=("agy",),
        command="agy -p --output-format json --dangerously-skip-permissions",
        auth_hint="Install the Antigravity CLI (`agy`, often ~/.local/bin) and sign in with Google on this machine.",
    ),
    LlmConnectorSpec(
        id="codex",
        label="Codex CLI",
        binaries=("codex",),
        command="codex exec --json",
        auth_hint="Run `codex login` in a terminal on this machine first.",
    ),
    LlmConnectorSpec(
        id="claude_code",
        label="Claude Code",
        binaries=("claude",),
        command="claude -p --output-format json",
        auth_hint="Run `claude auth login` (or your Claude Code login flow) locally first.",
    ),
    LlmConnectorSpec(
        id="opencode",
        label="OpenCode",
        binaries=("opencode",),
        command="opencode run --format json",
        auth_hint="Run `opencode auth` on this machine first.",
    ),
)

_CONNECTOR_BY_ID = {spec.id: spec for spec in CONNECTOR_SPECS}
_ALLOWED_COMMANDS = frozenset(
    {spec.command for spec in CONNECTOR_SPECS} | {CURSOR_AGENT_COMMAND_LEGACY}
)


def command_matches_connector(spec: LlmConnectorSpec, command: str) -> bool:
    text = (command or "").strip()
    if text == spec.command:
        return True
    if spec.id == "cursor_agent" and text == CURSOR_AGENT_COMMAND_LEGACY:
        return True
    return False


def connector_id_for_command(command: str) -> str:
    text = (command or "").strip()
    if not text:
        return ""
    for spec in CONNECTOR_SPECS:
        if command_matches_connector(spec, text):
            return spec.id
    return "custom"


def merge_llm_agent_credential_updates(profile_id: str, updates: dict[str, str]) -> dict[str, str]:
    """Keep connector id and test flags consistent when the agent command changes."""
    out = dict(updates)
    if VAULT_COMMAND_KEY not in out:
        return out
    new_cmd = out[VAULT_COMMAND_KEY].strip()
    vault = get_profile_secrets(profile_id)
    old_cmd = str(vault.get(VAULT_COMMAND_KEY) or "").strip()
    if new_cmd != old_cmd:
        out[VAULT_TEST_OK_KEY] = ""
        out[VAULT_LAST_ERROR_KEY] = ""
    inferred = connector_id_for_command(new_cmd)
    if inferred and inferred != "custom":
        out[VAULT_CONNECTOR_KEY] = inferred
    elif VAULT_CONNECTOR_KEY not in out and new_cmd:
        out[VAULT_CONNECTOR_KEY] = "custom"
    return out


def connector_spec(connector_id: str) -> LlmConnectorSpec | None:
    return _CONNECTOR_BY_ID.get((connector_id or "").strip())


def is_allowed_agent_command(command: str) -> bool:
    text = (command or "").strip()
    if not text:
        return False
    if text in _ALLOWED_COMMANDS:
        return True
    # Manual custom commands: allow only safe token shapes (no shell metacharacters).
    if any(ch in text for ch in ";|&$`<>()"):
        return False
    return True


def _which(binary: str, path: str | None = None) -> str | None:
    env_path = path if path is not None else os.environ.get("PATH", "")
    return shutil.which(binary, path=env_path)


def probe_binary_version(binary: str, *, path: str | None = None) -> str:
    resolved = _which(binary, path=path)
    if not resolved:
        return ""
    for args in (["--version"], ["-V"], ["version"]):
        try:
            completed = subprocess.run(
                [resolved, *args],
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        line = (completed.stdout or completed.stderr or "").strip().splitlines()
        if line and completed.returncode == 0:
            return line[0][:120]
    return ""


def discover_connectors(*, path: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in CONNECTOR_SPECS:
        found = next((b for b in spec.binaries if _which(b, path=path)), "")
        rows.append(
            {
                "id": spec.id,
                "label": spec.label,
                "binary": found,
                "detected": bool(found),
                "version": probe_binary_version(found, path=path) if found else "",
                "auth_hint": spec.auth_hint,
                "command_preview": spec.command,
            }
        )
    rows.append(
        {
            "id": "custom",
            "label": "Custom CLI",
            "binary": "",
            "detected": True,
            "version": "",
            "auth_hint": "Paste a vetted command below (no shell metacharacters).",
            "command_preview": "",
        }
    )
    return rows


def _active_connector_id(profile_id: str) -> str:
    vault = get_profile_secrets(profile_id)
    return str(vault.get(VAULT_CONNECTOR_KEY) or "").strip()


def _active_command(profile_id: str) -> str:
    vault = get_profile_secrets(profile_id)
    return str(vault.get(VAULT_COMMAND_KEY) or "").strip() or os.environ.get(VAULT_COMMAND_KEY, "").strip()


def _state_for_active_connector(
    profile_id: str,
    *,
    connector_id: str,
    command_matches: bool,
) -> str:
    active_id = _active_connector_id(profile_id)
    if active_id != connector_id or not command_matches:
        return CONNECTOR_STATE_DETECTED
    last_error = str(get_profile_secrets(profile_id).get(VAULT_LAST_ERROR_KEY) or "").strip()
    if last_error:
        return CONNECTOR_STATE_ERROR
    tested = str(get_profile_secrets(profile_id).get(VAULT_TEST_OK_KEY) or "").strip() == "1"
    if tested and llm_provider_ready("agent", profile_id=profile_id).get("ready"):
        return CONNECTOR_STATE_READY
    return CONNECTOR_STATE_CONFIGURED


def connector_status_rows(profile_id: str, *, path: str | None = None) -> list[dict[str, Any]]:
    vault = get_profile_secrets(profile_id)
    active_id = _active_connector_id(profile_id)
    command = _active_command(profile_id)
    vault_last_error = str(vault.get(VAULT_LAST_ERROR_KEY) or "").strip()
    rows: list[dict[str, Any]] = []
    for item in discover_connectors(path=path):
        cid = str(item["id"])
        spec = connector_spec(cid) if cid != "custom" else None
        detected = bool(item.get("detected"))
        is_active = active_id == cid
        last_error = vault_last_error if is_active else ""

        if cid == "custom":
            state = CONNECTOR_STATE_DETECTED
            if is_active and command:
                state = _state_for_active_connector(profile_id, connector_id="custom", command_matches=True)
            rows.append(
                {
                    **item,
                    "state": state,
                    "active": is_active and bool(command),
                    "last_error": last_error,
                    "command_outdated": False,
                }
            )
            continue

        if not detected:
            state = CONNECTOR_STATE_UNDETECTED
            command_outdated = False
        elif is_active and command and spec and not command_matches_connector(spec, command):
            state = CONNECTOR_STATE_STALE
            command_outdated = True
            if not last_error:
                last_error = "Harness command is outdated — Connect again to refresh."
        elif spec and is_active and command_matches_connector(spec, command):
            state = _state_for_active_connector(
                profile_id,
                connector_id=cid,
                command_matches=True,
            )
            command_outdated = False
        else:
            state = CONNECTOR_STATE_DETECTED
            command_outdated = False

        rows.append(
            {
                **item,
                "state": state,
                "active": is_active and bool(command),
                "last_error": last_error,
                "command_outdated": command_outdated,
            }
        )
    return rows


def build_llm_status_payload(profile_id: str, *, path: str | None = None) -> dict[str, Any]:
    from .credential_vault import credential_status_for_profile

    base = credential_status_for_profile(profile_id).get("llm") or {}
    connectors = connector_status_rows(profile_id, path=path)
    agent_ready = dict(llm_provider_ready("agent", profile_id=profile_id))
    active_row = next((row for row in connectors if row.get("active")), None)
    if active_row and str(active_row.get("state") or "") == CONNECTOR_STATE_STALE:
        agent_ready["state"] = CONNECTOR_STATE_STALE
    return {
        "providers": base,
        "agent": {
            **agent_ready,
            "connector_id": _active_connector_id(profile_id),
            "command_set": bool(_active_command(profile_id)),
        },
        "connectors": connectors,
    }


def connect_connector(profile_id: str, connector_id: str) -> dict[str, Any]:
    cid = (connector_id or "").strip()
    if cid == "custom":
        raise ValueError("use llm-credentials to set a custom OTONOM_LLM_AGENT_COMMAND")
    spec = connector_spec(cid)
    if not spec:
        raise ValueError(f"unknown connector: {connector_id}")
    if not any(_which(b) for b in spec.binaries):
        raise ValueError(f"{spec.label} CLI not found on PATH — install it and ensure login first")
    set_profile_secrets(
        profile_id,
        {
            VAULT_COMMAND_KEY: spec.command,
            VAULT_CONNECTOR_KEY: spec.id,
            VAULT_LAST_ERROR_KEY: "",
            VAULT_TEST_OK_KEY: "",
        },
    )
    return {
        "profile_id": profile_id,
        "connector_id": spec.id,
        "command_preview": spec.command,
        "status": "configured",
        "llm_status": build_llm_status_payload(profile_id),
    }


def test_active_connector(profile_id: str, *, timeout_seconds: int = 90) -> dict[str, Any]:
    if not llm_provider_ready("agent", profile_id=profile_id).get("ready"):
        raise ValueError("No agent command configured — connect a harness first")
    system = "You are a test harness. Reply with JSON only."
    user = '{"task":"ping","reply_shape":{"ok":true}}'
    try:
        result = call_llm_agent_json(system, user, profile_id=profile_id, timeout_seconds=timeout_seconds)
    except LLMError as exc:
        set_profile_secrets(
            profile_id,
            {VAULT_LAST_ERROR_KEY: str(exc)[:500], VAULT_TEST_OK_KEY: ""},
        )
        raise ValueError(str(exc)) from exc
    if not isinstance(result, dict):
        set_profile_secrets(
            profile_id,
            {VAULT_LAST_ERROR_KEY: "agent did not return a JSON object", VAULT_TEST_OK_KEY: ""},
        )
        raise ValueError("agent did not return a JSON object")
    set_profile_secrets(profile_id, {VAULT_LAST_ERROR_KEY: "", VAULT_TEST_OK_KEY: "1"})
    return {
        "profile_id": profile_id,
        "status": "ready",
        "sample_keys": sorted(result.keys())[:8],
        "llm_status": build_llm_status_payload(profile_id),
    }
