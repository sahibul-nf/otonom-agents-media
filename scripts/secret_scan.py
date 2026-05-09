#!/usr/bin/env python3
"""Small local secret scanner for pre-commit and manual checks."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

BLOCKED_PATH_PARTS = {
    ".env",
    "fb_pages.json",
}

KEY_VALUE_PATTERN = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|app[_-]?secret|page[_-]?token)\s*[:=]\s*['\"]?([^'\"\s,;]+)"
)
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-./=]{20,}", re.IGNORECASE),
]

ALLOWLIST_SUFFIXES = {
    ".env.example",
    "SECRETS.md",
    "secret_scan.py",
}

SKIP_DIRS = {
    ".git",
    "node_modules",
    "artifacts",
    "archives",
    "data",
    "__pycache__",
}


def staged_files() -> list[Path]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [ROOT / line.strip() for line in result.stdout.splitlines() if line.strip()]


def all_project_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(ROOT).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        files.append(path)
    return files


def should_allow(path: Path) -> bool:
    return any(str(path).endswith(suffix) for suffix in ALLOWLIST_SUFFIXES)


def scan_file(path: Path) -> list[str]:
    rel = path.relative_to(ROOT)
    issues: list[str] = []
    rel_str = str(rel)

    if not should_allow(path):
        if path.name in BLOCKED_PATH_PARTS or any(part in BLOCKED_PATH_PARTS for part in rel.parts):
            issues.append(f"{rel_str}: blocked sensitive filename")

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return issues

    if should_allow(path):
        return issues

    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            issues.append(f"{rel_str}: possible secret pattern")
            break
    for match in KEY_VALUE_PATTERN.finditer(text):
        value = match.group(2).strip()
        if not value or value.startswith(("process.env", "os.environ", "your_", "YOUR_", "$", "''", '""')):
            continue
        if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$.]*", value):
            continue
        if len(value) >= 16:
            issues.append(f"{rel_str}: possible key/token assignment")
            break
    return issues


def main() -> int:
    scan_all = "--all" in sys.argv[1:]
    paths = all_project_files() if scan_all else staged_files()
    if not paths:
        print("Secret scan passed. No staged files to scan.")
        return 0

    issues: list[str] = []
    for path in paths:
        if path.exists():
            issues.extend(scan_file(path))

    if issues:
        print("Secret scan failed:")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print("Secret scan passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
