# Contributing (humans + AI agents)

Otonom Media is a **solo-dev + AI** repo. GitHub Project **Status** authorizes autonomous work. This file is the **PR and deploy safety contract**.

Canonical workflow: `AGENTS.md`. Board cheatsheet: `docs/github-workflow.md`. Orchestrators: `docs/orchestrator-integration.md`.

## Two checkouts (do not mix)

| Folder (typical) | Git branch | Role |
|------------------|------------|------|
| `otonom-agents-media` | **`dev`** | Cursor / coding agents. Open PRs from here. |
| `otonom-agents-media-ops` | **`main`** | PM2 production (`:8765` API, `:3100` dashboard). Live `data/` + `artifacts/`. |

Agents **must clone or work in a `dev` checkout**. Never write, commit, or restart PM2 in the ops folder.

## Branch model

```text
feat/#N-slug  or  fix/#N-slug
        │
        ▼  pull request (required)
       dev     ← integration (human review here)
        │
        ▼  human merge only, after Human Review
       main    ← production / PM2
```

- **`dev`** — integration branch. All agent PRs target **`dev`**.
- **`main`** — production. PM2 deploys from this clone. **Agents never merge to `main`.**
- Feature branches: `feat/#N-slug` / `fix/#N-slug` from **current `dev`**, not from `main`.

`.workflow-kit.env`: `INTEGRATION_BRANCH=dev`, `PRODUCTION_BRANCH=main`, `SINGLE_BRANCH=false`.

## Ready for AI (unattended)

Human moves an issue to board Status **Ready for AI**. An orchestrator (or later session) may then:

1. Pick **one** issue (do not drain the column).
2. Set Status **AI Working**.
3. Branch from `origin/dev`, implement, self-verify (`AGENTS.md`).
4. Open a PR **into `dev`** with `Fixes #N`.
5. Set Status **AI Review**. **Stop.** Do not merge.

Labels (`ai-ready`, etc.) are metadata only — they do **not** authorize pickup.

## Hard rules for agents

1. **PR base = `dev`.** Never open a PR against `main`. Never `git push origin main`.
2. **Do not merge** any PR (including into `dev`) unless the human later says to merge.
3. **Do not touch production:** no `pm2 restart`, no edits under the ops clone, no writing live `data/` or `artifacts/` used by PM2.
4. **Do not steal ops ports** (`8765` / `3100`). Isolated dev: `npm run dev:isolated` → `:8766` / `:3101`.
5. **Do not close issues.** Human says *sudah work* → Phase 3 (`gh-close-verified-issue.sh`).
6. **One issue per run.** If blocked, comment + `ai-needs-human` / `ai-blocked`; leave Status at **Human Review** or **Todo**.

## After human review

1. Human reviews the PR (**Human Review**).
2. Human merges **`dev` ← feature branch**.
3. When ready to ship, human merges **`main` ← `dev`** and pulls on the **ops** clone (`git pull` on `main`), then rebuilds/restarts PM2 there.
4. Human confirms *sudah work #N* → **Done**.

## Commits

Commit only when the human asks (or when an orchestrator run must push a PR). Never commit `.env`, credentials, SQLite, or generated media.

## Related

- `docs/local-ops.md` — PM2 vs isolated dev ports
- `.github/pull_request_template.md` — PR checklist
- `scripts/gh-set-issue-status.sh` — board Status keys
