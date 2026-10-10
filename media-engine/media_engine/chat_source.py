"""Chat transcript → sanitized source text for content packages."""

from __future__ import annotations

import re

_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE = re.compile(r"(?<![\w-])\+?\d[\d\s().-]{7,}\d(?![\w-])")
_APIISH = re.compile(
    r"(?i)\b(sk-[a-z0-9_-]{20,}|ghp_[a-z0-9]{20,}|fakekey-[a-z0-9_-]{16,}|api[_-]?key\s*[:=]\s*['\"]?[a-z0-9_-]{16,})"
)
_NOISE_LINES = re.compile(
    r"(?im)^(?:user|assistant|system|tool|cursor|agent)\s*:\s*",
)


def sanitize_chat_transcript(text: str, *, max_chars: int = 24000) -> str:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("chat transcript is empty")
    lines: list[str] = []
    for line in raw.splitlines():
        stripped = _NOISE_LINES.sub("", line).strip()
        if not stripped:
            continue
        if stripped.lower() in {"copy", "paste", "continue", "ok", "thanks"}:
            continue
        lines.append(stripped)
    body = "\n".join(lines)
    body = _EMAIL.sub("[email]", body)
    body = _APIISH.sub("[redacted-secret]", body)
    body = _PHONE.sub("[phone]", body)
    if len(body) > max_chars:
        body = body[:max_chars] + "\n… [truncated]"
    if len(body.split()) < 12:
        raise ValueError("chat transcript too short after cleanup — need more substance")
    return body
