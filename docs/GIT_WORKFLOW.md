# Git workflow (Otonom Media)

Canonical delivery flow: **`AGENTS.md`**, **`docs/github-workflow.md`**.

## Branching

- **`main`**: single integration + production branch (`SINGLE_BRANCH=true` in `.workflow-kit.env`).
- Optional short-lived branches: `feat/<short-name>`, `fix/<short-name>` — merge to **`main`**, then `git push origin main`.
- Do **not** use a separate `dev` branch unless it exists in `git branch -a`.

## Commits

- Commit source, docs, tests, templates, and sanitized examples.
- Do not commit runtime data, generated videos, SQLite DBs, logs, `.env`, or tokens.
- Media engine work stays under `media-engine/` unless shared modules are intentionally extracted.
- AI agents commit **only when you ask**.

## Hooks & checks

```bash
git config core.hooksPath .githooks
python3 scripts/secret_scan.py
cd media-engine && PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py'
```

## GitHub board (after push)

```bash
./scripts/gh-sync-project-status.sh --qa N   # shipped, needs staging QA
./scripts/gh-sync-project-status.sh          # closed issues → Done on board
```
