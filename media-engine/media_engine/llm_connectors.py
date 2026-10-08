"""Discover and connect local LLM agent CLIs (BYO subscription, no API key)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from .credential_vault import get_profile_secrets, set_profile_secrets
from .llm import LLMError, run_agent_shell_command

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
VAULT_CONNECTORS_REGISTRY_KEY = "OTONOM_LLM_CONNECTORS_JSON"


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


def _normalize_registry_entry(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    enabled = str(raw.get("enabled") or "").strip()
    if not enabled:
        enabled = "1"
    return {
        "command": str(raw.get("command") or "").strip(),
        "test_ok": str(raw.get("test_ok") or "").strip(),
        "last_error": str(raw.get("last_error") or "").strip(),
        "enabled": enabled,
    }


def load_connectors_registry(profile_id: str) -> dict[str, dict[str, str]]:
    vault = get_profile_secrets(profile_id)
    raw = str(vault.get(VAULT_CONNECTORS_REGISTRY_KEY) or "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return {str(k): _normalize_registry_entry(v) for k, v in parsed.items() if _normalize_registry_entry(v).get("command")}
        except json.JSONDecodeError:
            pass
    cid = str(vault.get(VAULT_CONNECTOR_KEY) or "").strip()
    cmd = str(vault.get(VAULT_COMMAND_KEY) or "").strip()
    if cid and cmd:
        return {
            cid: {
                "command": cmd,
                "test_ok": str(vault.get(VAULT_TEST_OK_KEY) or "").strip(),
                "last_error": str(vault.get(VAULT_LAST_ERROR_KEY) or "").strip(),
                "enabled": "1",
            }
        }
    return {}


def _enabled_ids_from_registry(registry: dict[str, dict[str, str]]) -> list[str]:
    enabled: list[str] = []
    for spec in CONNECTOR_SPECS:
        entry = registry.get(spec.id, {})
        if entry.get("command") and entry.get("enabled", "1") == "1":
            enabled.append(spec.id)
    custom = registry.get("custom", {})
    if custom.get("command") and custom.get("enabled", "1") == "1":
        enabled.append("custom")
    return enabled


def enabled_connector_ids(profile_id: str) -> list[str]:
    return _enabled_ids_from_registry(load_connectors_registry(profile_id))


def agent_provider_ready(profile_id: str) -> dict[str, Any]:
    registry = load_connectors_registry(profile_id)
    enabled = _enabled_ids_from_registry(registry)
    if not enabled:
        cmd = str(get_profile_secrets(profile_id).get(VAULT_COMMAND_KEY) or "").strip()
        if not cmd:
            return {
                "ready": False,
                "mode": "agent",
                "state": CONNECTOR_STATE_UNDETECTED,
                "connector_id": "",
                "connector_ids": [],
                "missing": ["OTONOM_LLM_AGENT_COMMAND"],
            }
        return {
            "ready": True,
            "mode": "agent",
            "state": CONNECTOR_STATE_CONFIGURED,
            "connector_id": str(get_profile_secrets(profile_id).get(VAULT_CONNECTOR_KEY) or ""),
            "connector_ids": [],
            "missing": [],
        }
    any_tested = any(registry.get(cid, {}).get("test_ok") == "1" for cid in enabled)
    any_stale = False
    for cid in enabled:
        spec = connector_spec(cid)
        entry = registry.get(cid, {})
        if spec and not command_matches_connector(spec, entry.get("command", "")):
            any_stale = True
            break
    state = CONNECTOR_STATE_CONFIGURED
    if any_stale:
        state = CONNECTOR_STATE_STALE
    elif any_tested:
        state = CONNECTOR_STATE_READY
    return {
        "ready": True,
        "mode": "agent",
        "state": state,
        "connector_id": ",".join(enabled),
        "connector_ids": enabled,
        "missing": [],
    }


def call_agent_json_for_profile(
    system_prompt: str,
    user_prompt: str,
    *,
    profile_id: str | None,
    timeout_seconds: int = 120,
) -> Any:
    pid = (profile_id or "").strip()
    registry = load_connectors_registry(pid) if pid else {}
    enabled = _enabled_ids_from_registry(registry)
    errors: list[str] = []
    for cid in enabled:
        cmd = registry.get(cid, {}).get("command", "")
        try:
            return run_agent_shell_command(
                cmd,
                system_prompt,
                user_prompt,
                timeout_seconds=timeout_seconds,
            )
        except LLMError as exc:
            errors.append(f"{cid}: {exc}")
    if errors:
        raise LLMError("; ".join(errors)[:800])
    command = os.environ.get("OTONOM_LLM_AGENT_COMMAND", "").strip()
    if pid:
        command = str(get_profile_secrets(pid).get(VAULT_COMMAND_KEY) or "").strip() or command
    if not command:
        raise LLMError("No enabled agent harness — connect at least one in Publish → LLM connectors")
    return run_agent_shell_command(
        command,
        system_prompt,
        user_prompt,
        timeout_seconds=timeout_seconds,
    )


def _persist_connectors_registry(profile_id: str, registry: dict[str, dict[str, str]]) -> None:
    enabled = _enabled_ids_from_registry(registry)
    primary = enabled[0] if enabled else ""
    primary_entry = registry.get(primary, {}) if primary else {}
    any_tested = any(registry.get(cid, {}).get("test_ok") == "1" for cid in enabled)
    set_profile_secrets(
        profile_id,
        {
            VAULT_CONNECTORS_REGISTRY_KEY: json.dumps(registry, ensure_ascii=False),
            VAULT_CONNECTOR_KEY: ",".join(enabled),
            VAULT_COMMAND_KEY: primary_entry.get("command", ""),
            VAULT_TEST_OK_KEY: "1" if any_tested else "",
            VAULT_LAST_ERROR_KEY: primary_entry.get("last_error", ""),
        },
    )


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
    registry = load_connectors_registry(profile_id)
    cid = out.get(VAULT_CONNECTOR_KEY) or inferred or "custom"
    registry[cid] = {
        "command": new_cmd,
        "test_ok": out.get(VAULT_TEST_OK_KEY, ""),
        "last_error": out.get(VAULT_LAST_ERROR_KEY, ""),
        "enabled": registry.get(cid, {}).get("enabled", "1"),
    }
    out[VAULT_CONNECTORS_REGISTRY_KEY] = json.dumps(registry, ensure_ascii=False)
    return out


def connector_spec(connector_id: str) -> LlmConnectorSpec | None:
    return _CONNECTOR_BY_ID.get((connector_id or "").strip())


def is_allowed_agent_command(command: str) -> bool:
    text = (command or "").strip()
    if not text:
        return False
    if text in _ALLOWED_COMMANDS:
        return True
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


def _state_for_registry_entry(
    entry: dict[str, str],
    *,
    spec: LlmConnectorSpec | None,
) -> str:
    cmd = entry.get("command", "")
    if spec and not command_matches_connector(spec, cmd):
        return CONNECTOR_STATE_STALE
    if entry.get("last_error"):
        return CONNECTOR_STATE_ERROR
    if entry.get("test_ok") == "1":
        return CONNECTOR_STATE_READY
    return CONNECTOR_STATE_CONFIGURED


def connector_status_rows(profile_id: str, *, path: str | None = None) -> list[dict[str, Any]]:
    registry = load_connectors_registry(profile_id)
    rows: list[dict[str, Any]] = []
    for item in discover_connectors(path=path):
        cid = str(item["id"])
        spec = connector_spec(cid) if cid != "custom" else None
        detected = bool(item.get("detected"))
        entry = registry.get(cid, {})
        connected = bool(entry.get("command"))
        is_active = connected and entry.get("enabled", "1") == "1"
        last_error = entry.get("last_error", "") if connected else ""

        if cid == "custom":
            state = CONNECTOR_STATE_DETECTED
            if connected:
                state = _state_for_registry_entry(entry, spec=None)
            rows.append(
                {
                    **item,
                    "state": state,
                    "active": is_active,
                    "connected": connected,
                    "last_error": last_error,
                    "command_outdated": state == CONNECTOR_STATE_STALE,
                }
            )
            continue

        if not detected:
            state = CONNECTOR_STATE_UNDETECTED
            command_outdated = False
        elif connected and spec:
            state = _state_for_registry_entry(entry, spec=spec)
            command_outdated = state == CONNECTOR_STATE_STALE
            if command_outdated and not last_error:
                last_error = "Harness command is outdated — Connect again to refresh."
        else:
            state = CONNECTOR_STATE_DETECTED
            command_outdated = False

        rows.append(
            {
                **item,
                "state": state,
                "active": is_active,
                "connected": connected,
                "last_error": last_error,
                "command_outdated": command_outdated,
            }
        )
    return rows


def build_llm_status_payload(profile_id: str, *, path: str | None = None) -> dict[str, Any]:
    from .credential_vault import credential_status_for_profile

    base = credential_status_for_profile(profile_id).get("llm") or {}
    connectors = connector_status_rows(profile_id, path=path)
    agent_ready = agent_provider_ready(profile_id)
    connected_ids = [str(row["id"]) for row in connectors if row.get("connected")]
    active_ids = [str(row["id"]) for row in connectors if row.get("active")]
    return {
        "providers": base,
        "agent": {
            **agent_ready,
            "command_set": bool(agent_ready.get("ready")),
            "connected_connector_ids": connected_ids,
            "active_connector_ids": active_ids,
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

    registry = load_connectors_registry(profile_id)
    existing = registry.get(spec.id, {})
    if existing.get("command") and command_matches_connector(spec, existing.get("command", "")):
        registry[spec.id] = {**existing, "enabled": "1"}
    else:
        registry[spec.id] = {"command": spec.command, "test_ok": "", "last_error": "", "enabled": "1"}
    _persist_connectors_registry(profile_id, registry)

    return {
        "profile_id": profile_id,
        "connector_id": spec.id,
        "command_preview": spec.command,
        "status": "configured",
        "llm_status": build_llm_status_payload(profile_id),
    }


def activate_connector(profile_id: str, connector_id: str) -> dict[str, Any]:
    cid = (connector_id or "").strip()
    registry = load_connectors_registry(profile_id)
    entry = registry.get(cid)
    if not entry or not entry.get("command"):
        raise ValueError(f"{cid} is not connected — use Connect first")
    registry[cid] = {**entry, "enabled": "1"}
    _persist_connectors_registry(profile_id, registry)
    return {
        "profile_id": profile_id,
        "connector_id": cid,
        "status": "active",
        "llm_status": build_llm_status_payload(profile_id),
    }


def deactivate_connector(profile_id: str, connector_id: str) -> dict[str, Any]:
    cid = (connector_id or "").strip()
    registry = load_connectors_registry(profile_id)
    entry = registry.get(cid)
    if not entry or not entry.get("command"):
        raise ValueError(f"{cid} is not connected")
    registry[cid] = {**entry, "enabled": "0"}
    _persist_connectors_registry(profile_id, registry)
    return {
        "profile_id": profile_id,
        "connector_id": cid,
        "status": "inactive",
        "llm_status": build_llm_status_payload(profile_id),
    }


def test_active_connector(profile_id: str, *, timeout_seconds: int = 90) -> dict[str, Any]:
    enabled = enabled_connector_ids(profile_id)
    if not enabled:
        raise ValueError("No active agent harness — connect at least one harness first")
    system = "You are a test harness. Reply with JSON only."
    user = '{"task":"ping","reply_shape":{"ok":true}}'
    registry = load_connectors_registry(profile_id)
    tested: list[str] = []
    failures: list[str] = []
    sample_keys: list[str] = []
    for cid in enabled:
        cmd = registry.get(cid, {}).get("command", "")
        try:
            result = run_agent_shell_command(
                cmd,
                system,
                user,
                timeout_seconds=timeout_seconds,
            )
        except LLMError as exc:
            registry[cid]["last_error"] = str(exc)[:500]
            registry[cid]["test_ok"] = ""
            failures.append(f"{cid}: {exc}")
            continue
        if not isinstance(result, dict):
            msg = "agent did not return a JSON object"
            registry[cid]["last_error"] = msg
            registry[cid]["test_ok"] = ""
            failures.append(f"{cid}: {msg}")
            continue
        registry[cid]["last_error"] = ""
        registry[cid]["test_ok"] = "1"
        tested.append(cid)
        sample_keys = sorted(result.keys())[:8]
    _persist_connectors_registry(profile_id, registry)
    if not tested:
        raise ValueError(failures[0] if failures else "all harness tests failed")
    return {
        "profile_id": profile_id,
        "status": "ready",
        "connector_id": ",".join(tested),
        "tested_connector_ids": tested,
        "failures": failures,
        "sample_keys": sample_keys,
        "llm_status": build_llm_status_payload(profile_id),
    }
