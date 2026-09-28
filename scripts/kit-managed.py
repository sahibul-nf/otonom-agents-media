#!/usr/bin/env python3
"""Stamp and verify solo-dev-ai-kit managed files."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MARKER = "solo-dev-ai-kit:managed"
PARTIAL_MARKER = "solo-dev-ai-kit:partial-managed"
MARKER_HTML = f"<!-- {MARKER} -->"
MARKER_HASH = f"# {MARKER}"
MANIFEST_HEADER = "# solo-dev-ai-kit manifest — paths installed by bootstrap"
JSON_KEY = "_solo_dev_ai_kit"


def has_marker(text: str) -> bool:
    if JSON_KEY in text:
        return True
    if PARTIAL_MARKER in text:
        return True
    # Avoid matching partial-managed when checking full managed marker
    return MARKER in text and PARTIAL_MARKER not in text


def has_partial_marker(text: str) -> bool:
    return PARTIAL_MARKER in text


def has_marker_file(path: Path) -> bool:
    if not path.is_file():
        return False
    return has_marker(path.read_text(encoding="utf-8", errors="replace"))


def _insert_after_frontmatter(text: str, line: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            insert_at = end + len("\n---\n")
            return text[:insert_at] + line + "\n" + text[insert_at:]
    return line + "\n" + text


def stamp_file(path: Path) -> bool:
    """Add managed marker if missing. Returns True if file was modified."""
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    if has_marker(text):
        return False

    suffix = path.suffix.lower()
    name = path.name.lower()

    if suffix == ".json" or name == "settings.json":
        data = json.loads(text)
        if isinstance(data, dict):
            data[JSON_KEY] = {"managed": True}
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            return True
        return False

    if suffix == ".sh":
        lines = text.splitlines(keepends=True)
        if lines and lines[0].startswith("#!"):
            lines.insert(1, MARKER_HASH + "\n")
        else:
            lines.insert(0, MARKER_HASH + "\n")
        path.write_text("".join(lines), encoding="utf-8")
        return True

    if suffix == ".py":
        lines = text.splitlines(keepends=True)
        insert_at = 0
        if lines and lines[0].startswith("#!"):
            insert_at = 1
        if insert_at < len(lines) and lines[insert_at].startswith('"""'):
            end = insert_at + 1
            while end < len(lines):
                if '"""' in lines[end]:
                    insert_at = end + 1
                    break
                end += 1
        lines.insert(insert_at, MARKER_HASH + "\n")
        path.write_text("".join(lines), encoding="utf-8")
        return True

    if suffix in {".yml", ".yaml"}:
        path.write_text(MARKER_HASH + "\n" + text, encoding="utf-8")
        return True

    if suffix in {".md", ".mdc"}:
        path.write_text(_insert_after_frontmatter(text, MARKER_HTML), encoding="utf-8")
        return True

    if suffix == ".env" or name == ".workflow-kit.env":
        if text.startswith("#"):
            lines = text.splitlines(keepends=True)
            lines.insert(1, MARKER_HASH + "\n")
            path.write_text("".join(lines), encoding="utf-8")
        else:
            path.write_text(MARKER_HASH + "\n" + text, encoding="utf-8")
        return True

    path.write_text(MARKER_HASH + "\n" + text, encoding="utf-8")
    return True


def parse_manifest(text: str) -> tuple[int | None, list[str], list[str]]:
    kit_version: int | None = None
    paths: list[str] = []
    manifest_only: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("kit_version="):
            kit_version = int(line.split("=", 1)[1])
        elif line.startswith("path="):
            paths.append(line.split("=", 1)[1])
        elif line.startswith("manifest_only="):
            manifest_only.append(line.split("=", 1)[1])
    return kit_version, paths, manifest_only


def write_manifest(
    path: Path,
    kit_version: int,
    paths: list[str],
    manifest_only: list[str] | None = None,
) -> None:
    lines = [
        MANIFEST_HEADER,
        f"kit_version={kit_version}",
        f"generated_at={__import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
    ]
    for rel in sorted(set(paths)):
        lines.append(f"path={rel}")
    for rel in sorted(set(manifest_only or [])):
        lines.append(f"manifest_only={rel}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    stamp_file(path)


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "usage: kit-managed.py stamp|has-marker <file> | write-manifest <out> <version> <paths...>",
            file=sys.stderr,
        )
        sys.exit(2)

    cmd = sys.argv[1]
    if cmd == "stamp":
        path = Path(sys.argv[2])
        stamp_file(path)
        return
    if cmd == "has-marker":
        path = Path(sys.argv[2])
        sys.exit(0 if has_marker_file(path) else 1)
    if cmd == "write-manifest":
        out = Path(sys.argv[2])
        version = int(sys.argv[3])
        paths = sys.argv[4:]
        write_manifest(out, version, paths)
        return
    print(f"unknown command: {cmd}", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
