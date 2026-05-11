"""Optional LLM helpers for strict JSON curation and transcript cleanup."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


LLM_PROVIDERS = {"none", "openai", "deepseek", "groq"}


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


def call_llm_json(provider: str, system_prompt: str, user_prompt: str, timeout_seconds: int = 45) -> Any:
    if provider == "none":
        return None
    if provider not in LLM_PROVIDERS:
        raise ValueError(f"unsupported LLM provider: {provider}")

    config = provider_config(provider)
    api_key = os.environ.get(config["api_key_env"])
    if not api_key:
        raise LLMError(f"{config['api_key_env']} is required for provider {provider}")

    payload = build_chat_payload(config["model"], system_prompt, user_prompt)
    request = urllib.request.Request(
        config["base_url"],
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
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
