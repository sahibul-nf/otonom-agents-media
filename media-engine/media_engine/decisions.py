"""Optional TypeSafe Jev decisions. Jev does not write copy; it only scores or chooses."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


JEV_ENDPOINT = os.environ.get("TYPESAFE_JEV_URL", "https://api.typesafe.ai/v1/systemone")


def jev_api_key() -> str:
    return (os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API_KEY") or "").strip()


def jev_available() -> bool:
    return bool(jev_api_key())


def jev_decide(state: str, questions: dict[str, Any], timeout_seconds: int = 8) -> dict[str, Any] | None:
    """Return parsed Jev answers, or None when the key is missing or the call fails."""
    key = jev_api_key()
    if not key or not questions:
        return None
    body = json.dumps(
        {"model": "jev", "state": str(state or "")[:8000], "questions": questions},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        JEV_ENDPOINT,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    answers = payload.get("answers")
    if isinstance(answers, dict):
        return answers
    return payload


def answer_score(answer: Any) -> int | None:
    if isinstance(answer, (int, float)):
        return max(0, min(100, int(round(float(answer)))))
    if not isinstance(answer, dict):
        return None
    for key in ("score", "value", "rating"):
        if isinstance(answer.get(key), (int, float)):
            return max(0, min(100, int(round(float(answer[key])))))
    return None


def answer_choice(answer: Any) -> str:
    if isinstance(answer, str):
        return answer.strip()
    if isinstance(answer, dict):
        for key in ("choice", "value", "option", "label"):
            text = str(answer.get(key) or "").strip()
            if text:
                return text
    return ""


def answer_yes(answer: Any) -> bool | None:
    if isinstance(answer, bool):
        return answer
    if isinstance(answer, (int, float)):
        return float(answer) >= 0.5
    if isinstance(answer, dict):
        for key in ("probability", "value", "yes"):
            if key in answer:
                return answer_yes(answer.get(key))
    return None
