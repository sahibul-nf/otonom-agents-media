"""Optional LLM helpers for strict JSON curation and transcript cleanup."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from typing import Any

from .credential_vault import resolve_env_value


LLM_PROVIDERS = {"none", "openai", "deepseek", "groq", "agent"}
LLM_API_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "groq": "GROQ_API_KEY",
}


class LLMError(RuntimeError):
    pass


def clean_json_response(text: str) -> str:
    raw = text.strip()
    if raw.startswith("```json"):
        raw = raw[7:].strip()
    if raw.startswith("```"):
        raw = raw[3:].strip()
    if raw.endswith("```"):
        raw = raw[:-3].strip()
    if not raw:
        raise ValueError("empty LLM response")
    if raw[0] not in "[{":
        raise ValueError("LLM response must be raw JSON")
    return raw


def parse_strict_json(text: str) -> Any:
    return json.loads(clean_json_response(text))


def build_chat_payload(model: str, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }


def provider_config(provider: str) -> dict[str, str]:
    if provider == "openai":
        return {
            "api_key_env": "OPENAI_API_KEY",
            "base_url": "https://api.openai.com/v1/chat/completions",
            "model": os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        }
    if provider == "deepseek":
        return {
            "api_key_env": "DEEPSEEK_API_KEY",
            "base_url": "https://api.deepseek.com/chat/completions",
            "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        }
    if provider == "groq":
        return {
            "api_key_env": "GROQ_API_KEY",
            "base_url": "https://api.groq.com/openai/v1/chat/completions",
            "model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        }
    raise ValueError(f"unsupported LLM provider: {provider}")


def llm_provider_ready(provider: str, profile_id: str | None = None) -> dict[str, Any]:
    if provider == "none":
        return {"ready": True, "mode": "stub"}
    if provider == "agent":
        cmd = resolve_env_value("OTONOM_LLM_AGENT_COMMAND", profile_id=profile_id) or os.environ.get(
            "OTONOM_LLM_AGENT_COMMAND", ""
        ).strip()
        connector_id = resolve_env_value("OTONOM_LLM_AGENT_CONNECTOR", profile_id=profile_id) or os.environ.get(
            "OTONOM_LLM_AGENT_CONNECTOR", ""
        ).strip()
        tested = (
            resolve_env_value("OTONOM_LLM_AGENT_TEST_OK", profile_id=profile_id)
            or os.environ.get("OTONOM_LLM_AGENT_TEST_OK", "")
        ).strip() == "1"
        state = "configured" if cmd else "undetected"
        if cmd and tested:
            state = "ready"
        elif cmd:
            state = "configured"
        return {
            "ready": bool(cmd),
            "mode": "agent",
            "state": state,
            "connector_id": connector_id,
            "missing": [] if cmd else ["OTONOM_LLM_AGENT_COMMAND"],
        }
    if provider not in LLM_API_KEY_ENV:
        return {"ready": False, "mode": "unknown", "missing": [provider]}
    env_key = LLM_API_KEY_ENV[provider]
    key = resolve_env_value(env_key, profile_id=profile_id)
    return {"ready": bool(key), "mode": "api", "missing": [] if key else [env_key]}


def call_llm_agent_json(system_prompt: str, user_prompt: str, *, profile_id: str | None = None, timeout_seconds: int = 120) -> Any:
    command = resolve_env_value("OTONOM_LLM_AGENT_COMMAND", profile_id=profile_id) or os.environ.get(
        "OTONOM_LLM_AGENT_COMMAND", ""
    ).strip()
    if not command:
        raise LLMError("OTONOM_LLM_AGENT_COMMAND is not set (local agent CLI)")
    payload = json.dumps(
        {"system": system_prompt, "user": user_prompt, "response_format": "json_object"},
        ensure_ascii=False,
    )
    try:
        completed = subprocess.run(
            command,
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=True,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise LLMError(f"agent CLI failed: {exc}") from exc
    if completed.returncode != 0:
        raise LLMError(f"agent CLI exit {completed.returncode}: {(completed.stderr or completed.stdout)[:500]}")
    return parse_strict_json(completed.stdout or "{}")


def call_llm_json(
    provider: str,
    system_prompt: str,
    user_prompt: str,
    timeout_seconds: int = 45,
    *,
    profile_id: str | None = None,
) -> Any:
    if provider == "none":
        return None
    if provider not in LLM_PROVIDERS:
        raise ValueError(f"unsupported LLM provider: {provider}")
    if provider == "agent":
        return call_llm_agent_json(system_prompt, user_prompt, profile_id=profile_id, timeout_seconds=timeout_seconds)

    config = provider_config(provider)
    provider_secret = resolve_env_value(config["api_key_env"], profile_id=profile_id)
    if not provider_secret:
        raise LLMError(f"{config['api_key_env']} is required for provider {provider}")

    payload = build_chat_payload(config["model"], system_prompt, user_prompt)
    request = urllib.request.Request(
        config["base_url"],
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {provider_secret}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc

    content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    return parse_strict_json(content)
