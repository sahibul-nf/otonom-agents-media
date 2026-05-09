# Git Workflow

## Branching

- `main`: stable local baseline.
- `feature/<short-name>`: implementation work.
- `ops/<short-name>`: deployment or credential plumbing.

## Commit Rules

- Commit source, docs, tests, templates, and sanitized examples.
- Do not commit runtime data, generated videos, archives, SQLite databases, logs, `.env` files, or platform tokens.
- Keep media engine work isolated under `media-engine/` until shared modules are intentionally extracted.

## Useful Commands

```bash
git status --short
python3 scripts/secret_scan.py
PYTHONPATH=media-engine python3 -m unittest discover -s media-engine/tests -v
```

## First Setup

```bash
git config core.hooksPath .githooks
git status --short
```
