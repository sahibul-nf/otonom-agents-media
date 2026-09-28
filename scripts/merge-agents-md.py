#!/usr/bin/env python3
# solo-dev-ai-kit:managed
"""Merge kit-managed AGENTS.md sections; preserve project-specific content."""
from __future__ import annotations

import re
import sys
from pathlib import Path

MARKER_START = "<!-- workflow-kit:project-specific:start -->"
MARKER_END = "<!-- workflow-kit:project-specific:end -->"


def normalize_heading(title: str) -> str:
    return title.strip().lower()


def split_h2(text: str) -> tuple[str, list[tuple[str, str]]]:
    pattern = re.compile(r"^## (.+)$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if not matches:
        return text, []
    preamble = text[: matches[0].start()]
    sections: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        title = match.group(1)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((title, text[start:end]))
    return preamble, sections


def extract_marker_block(text: str) -> str | None:
    if MARKER_START not in text or MARKER_END not in text:
        return None
    start = text.index(MARKER_START) + len(MARKER_START)
    end = text.index(MARKER_END)
    return text[start:end].strip()


def format_custom_sections(sections: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    for title, body in sections:
        block = f"## {title}{body}".rstrip()
        parts.append(block)
    return "\n\n".join(parts).strip()


def inject_marker_block(template: str, content: str) -> str:
    if MARKER_START not in template or MARKER_END not in template:
        if not content:
            return template
        return (
            template.rstrip()
            + "\n\n"
            + MARKER_START
            + "\n"
            + content
            + "\n"
            + MARKER_END
            + "\n"
        )
    inner = f"\n{content}\n" if content else "\n"
    before, rest = template.split(MARKER_START, 1)
    _, after = rest.split(MARKER_END, 1)
    return before + MARKER_START + inner + MARKER_END + after


def merge(existing_path: Path, new_path: Path) -> str:
    existing = existing_path.read_text()
    new = new_path.read_text()

    kit_titles = {normalize_heading(title) for title, _ in split_h2(new)[1]}

    marker_content = extract_marker_block(existing)
    if marker_content is None:
        _, old_sections = split_h2(existing)
        custom = [
            (title, body)
            for title, body in old_sections
            if normalize_heading(title) not in kit_titles
        ]
        marker_content = format_custom_sections(custom)

    return inject_marker_block(new, marker_content)


def main() -> None:
    if len(sys.argv) != 4:
        print(
            "usage: merge-agents-md.py <existing> <new-from-template> <output>",
            file=sys.stderr,
        )
        sys.exit(1)
    existing, new, output = (Path(p) for p in sys.argv[1:4])
    output.write_text(merge(existing, new))


if __name__ == "__main__":
    main()
