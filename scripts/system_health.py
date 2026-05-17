#!/usr/bin/env python3
from __future__ import annotations

import json
import socket
import os
import sys
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.request import urlopen


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.2):
            return True
    except OSError:
        return False


def fetch_json(url: str) -> tuple[bool, Any]:
    try:
        with urlopen(url, timeout=3) as response:
            payload = response.read().decode("utf-8")
            return True, json.loads(payload)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return False, str(exc)


def fetch_text(url: str) -> tuple[bool, str]:
    try:
        with urlopen(url, timeout=3) as response:
            payload = response.read(2400).decode("utf-8", errors="replace")
            return True, payload
    except (HTTPError, URLError, TimeoutError) as exc:
        return False, str(exc)


def collect_status() -> dict[str, Any]:
    backend_port = int(os.environ.get("MEDIA_ENGINE_PORT", "8765"))
    frontend_port = int(os.environ.get("DASHBOARD_PORT", "3000"))
    backend_base = f"http://127.0.0.1:{backend_port}"
    frontend_base = f"http://127.0.0.1:{frontend_port}"

    backend_ok, backend_review = fetch_json(f"{backend_base}/api/review")
    credentials_ok, credentials = fetch_json(f"{backend_base}/api/credentials")
    frontend_ok, frontend_body = fetch_text(frontend_base)

    status = {
        "backend": {
            "port_open": port_open("127.0.0.1", backend_port),
            "url": backend_base,
            "review_api_ok": backend_ok,
            "clip_count": len(backend_review) if backend_ok and isinstance(backend_review, list) else None,
            "credentials_api_ok": credentials_ok,
        },
        "frontend": {
            "port_open": port_open("127.0.0.1", frontend_port),
            "url": frontend_base,
            "http_ok": frontend_ok,
            "looks_like_dashboard": frontend_ok and ("Otonom Media Dashboard" in frontend_body or "Media Operations Studio" in frontend_body),
        },
    }

    if credentials_ok and isinstance(credentials, dict):
        connected = [key for key, value in credentials.items() if isinstance(value, dict) and value.get("configured")]
        status["backend"]["configured_credentials"] = connected

    healthy = (
        status["backend"]["port_open"]
        and status["backend"]["review_api_ok"]
        and status["frontend"]["port_open"]
        and status["frontend"]["http_ok"]
    )
    status["healthy"] = healthy
    return status


def main() -> int:
    status = collect_status()
    print(json.dumps(status, indent=2))
    return 0 if status.get("healthy") else 1


if __name__ == "__main__":
    raise SystemExit(main())
