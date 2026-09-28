#!/usr/bin/env python3
# solo-dev-ai-kit:managed
"""Extract project-specific content from AGENTS.md before kit uninstall."""
from __future__ import annotations

import re
import sys
from pathlib import Path

MARKER_START = "<!-- workflow-kit:project-specific:start -->"
MARKER_END = "<!-- workflow-kit:project-specific:end -->"
PLACEHOLDER = "Add app-specific rules below"


def split_h2(text: str) -> list[tuple[str, str]]:
    pattern = re.compile(r"^## (.+)$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if not matches:
        return []
    sections: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        title = match.group(1)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((title, text[start:end]))
    return sections


def kit_section_titles(kit_template: Path) -> set[str]:
    if not kit_template.is_file():
        return set()
    _, sections = split_h2(kit_template.read_text())
    return {title.strip().lower() for title, _ in sections}


def extract_marker_block(text: str) -> str:
    if MARKER_START not in text or MARKER_END not in text:
        return ""
    start = text.index(MARKER_START) + len(MARKER_START)
    end = text.index(MARKER_END)
    block = text[start:end].strip()
    if not block or PLACEHOLDER in block:
        return ""
    return block


def extract_custom_sections(text: str, kit_titles: set[str]) -> str:
    sections = split_h2(text)
    parts: list[str] = []
    for title, body in sections:
        if title.strip().lower() not in kit_titles:
            parts.append(f"## {title}{body}".rstrip())
    return "\n\n".join(parts).strip()


def extract(agents_path: Path, kit_template: Path | None) -> str:
    text = agents_path.read_text()
    marker = extract_marker_block(text)
    kit_titles = kit_section_titles(kit_template) if kit_template else set()
    custom = extract_custom_sections(text, kit_titles) if kit_titles else ""
    if marker and custom:
        return f"{marker}\n\n{custom}".strip()
    return marker or custom


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: extract-agents-project-specific.py <AGENTS.md> [kit/AGENTS.md.tpl]", file=sys.stderr)
        sys.exit(1)
    agents = Path(sys.argv[1])
    kit_tpl = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if not agents.is_file():
        sys.exit(0)
    content = extract(agents, kit_tpl)
    if content:
        sys.stdout.write(content)


if __name__ == "__main__":
    main()
