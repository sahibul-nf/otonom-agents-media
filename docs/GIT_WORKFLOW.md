# Git workflow (Otonom Media)

Canonical delivery flow: **`AGENTS.md`**, **`docs/github-workflow.md`**.

## Branching

- **`dev`**: integration. Agent PRs target this branch.
- **`main`**: production. PM2 checkout (`otonom-agents-media-ops`). Human merges `main` ← `dev` after review.
- Short-lived: `feat/#N-slug`, `fix/#N-slug` from **`dev`**.
- Contract: `CONTRIBUTING.md`. `SINGLE_BRANCH=false` in `.workflow-kit.env`.

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
