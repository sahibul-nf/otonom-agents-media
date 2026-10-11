"""Optional LLM helpers for strict JSON curation and transcript cleanup."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from typing import Any

from .credential_vault import resolve_env_value


LLM_PROVIDERS = {"none", "openai", "deepseek", "groq", "agent", "auto"}
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
    if provider == "auto":
        from .llm_connectors import load_routing_policy

        policy = load_routing_policy(profile_id or "")
        return {"ready": True, "mode": "routing", "routing": policy, "missing": []}
    if provider == "agent":
        from .llm_connectors import agent_provider_ready

        return agent_provider_ready(profile_id or "")
    if provider not in LLM_API_KEY_ENV:
        return {"ready": False, "mode": "unknown", "missing": [provider]}
    env_key = LLM_API_KEY_ENV[provider]
    key = resolve_env_value(env_key, profile_id=profile_id)
    return {"ready": bool(key), "mode": "api", "missing": [] if key else [env_key]}


def run_agent_shell_command(
    command: str,
    system_prompt: str,
    user_prompt: str,
    *,
    timeout_seconds: int = 120,
) -> Any:
    text = (command or "").strip()
    if not text:
        raise LLMError("agent command is empty")
    payload = json.dumps(
        {"system": system_prompt, "user": user_prompt, "response_format": "json_object"},
        ensure_ascii=False,
    )
    try:
        completed = subprocess.run(
            text,
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


def call_llm_agent_json(system_prompt: str, user_prompt: str, *, profile_id: str | None = None, timeout_seconds: int = 120) -> Any:
    from .llm_connectors import call_agent_json_for_profile

    return call_agent_json_for_profile(
        system_prompt,
        user_prompt,
        profile_id=profile_id,
        timeout_seconds=timeout_seconds,
    )


def _call_llm_api_json(
    provider: str,
    system_prompt: str,
    user_prompt: str,
    timeout_seconds: int,
    *,
    profile_id: str | None,
) -> Any:
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


def call_llm_json_routed(
    system_prompt: str,
    user_prompt: str,
    timeout_seconds: int = 45,
    *,
    profile_id: str | None = None,
) -> Any:
    """Try workspace routing policy (primary then fallbacks)."""
    from .llm_connectors import (
        call_agent_json_for_connector,
        call_agent_json_for_profile,
        routing_chain,
    )

    pid = (profile_id or "").strip()
    if not pid:
        raise LLMError("profile_id is required for llm_provider=auto routing")
    errors: list[str] = []
    for entry in routing_chain(pid):
        try:
            if entry == "none":
                return None
            if entry in {"openai", "deepseek", "groq"}:
                return _call_llm_api_json(
                    entry,
                    system_prompt,
                    user_prompt,
                    timeout_seconds,
                    profile_id=pid,
                )
            if entry == "agent":
                return call_agent_json_for_profile(
                    system_prompt,
                    user_prompt,
                    profile_id=pid,
                    timeout_seconds=timeout_seconds,
                )
            if entry.startswith("agent:"):
                return call_agent_json_for_connector(
                    entry.split(":", 1)[1],
                    system_prompt,
                    user_prompt,
                    profile_id=pid,
                    timeout_seconds=timeout_seconds,
                )
            errors.append(f"{entry}: unknown")
        except (LLMError, ValueError) as exc:
            errors.append(f"{entry}: {exc}")
    raise LLMError("; ".join(errors)[:800] if errors else "routing policy empty")


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
    if provider == "auto":
        return call_llm_json_routed(
            system_prompt,
            user_prompt,
            timeout_seconds,
            profile_id=profile_id,
        )
    if provider == "agent":
        return call_llm_agent_json(system_prompt, user_prompt, profile_id=profile_id, timeout_seconds=timeout_seconds)

    return _call_llm_api_json(
        provider,
        system_prompt,
        user_prompt,
        timeout_seconds,
        profile_id=profile_id,
    )
