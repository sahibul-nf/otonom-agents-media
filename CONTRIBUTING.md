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
       dev     ← integration (agent may merge after green full test suite)
        │
        ▼  human only
       main    ← production / PM2
```

- **`dev`** — integration. All agent PRs target **`dev`**. After tests pass, the agent **may merge** the PR into `dev`.
- **`main`** — production. **Agents never merge or push `main`.**
- Feature branches: `feat/#N-slug` / `fix/#N-slug` from **current `dev`**.

`.workflow-kit.env`: `INTEGRATION_BRANCH=dev`, `PRODUCTION_BRANCH=main`, `SINGLE_BRANCH=false`.

## Ready for AI (unattended)

Human moves an issue to board Status **Ready for AI**. An orchestrator (e.g. FORGE) may then:

1. Pick **one** issue (do not drain the column).
2. Set Status **AI Working**.
3. Branch from `origin/dev`, implement.
4. **Tests first for new contracts:** if the change has no lock (no unittest covering the AC), add tests before finishing. Cover the changed module as far as the suite can (unit/API), not a new E2E stack unless the issue asks for it.
5. Run the **full** media-engine suite:
   `cd media-engine && PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py'`
6. Open a PR **into `dev`** with `Fixes #N` and a **How to test (UI)** section for Sahibul.
7. **If the full suite exits 0:** merge the PR into **`dev`**, `git push origin dev`, set board **Human Review**. Do **not** push `main`.
8. **If the suite is red:** do **not** merge. Fix failures caused by this change. Pre-existing failures: fix them if cheap and in-scope; otherwise stop, comment the command output, label `ai-needs-human`, leave the PR open on **AI Review**.

Labels (`ai-ready`, etc.) are metadata only — they do **not** authorize pickup.

## Hard rules for agents

1. **PR base = `dev`.** Never open a PR against `main`. Never `git push origin main`.
2. **Merge to `dev` only** after the **full** unittest suite exits 0. Never merge to `main`.
3. **Do not touch production:** no `pm2 restart`, no edits under the ops clone, no writing live `data/` or `artifacts/` used by PM2.
4. **Do not steal ops ports** (`8765` / `3100`). Isolated dev: `npm run dev:isolated` → `:8766` / `:3101`.
5. **Do not close issues.** Human says *sudah work* after a quick UI check → Phase 3 (`gh-close-verified-issue.sh`).
6. **One issue per run.** If blocked, comment + `ai-needs-human` / `ai-blocked`.

## After merge to `dev` (human)

1. Follow the PR **How to test (UI)** on the dashboard (ops `:3100` only after you ship `main`; otherwise isolated `:3101` or local `dev`).
2. If it works: *sudah work #N* → **Done**.
3. To ship production: merge **`main` ← `dev`**, `git pull` on the ops clone, rebuild dashboard if needed, restart PM2.

## Commits

Commit when opening/updating the PR (orchestrator) or when the human asks. Never commit `.env`, credentials, SQLite, or generated media.

## Related

- `docs/local-ops.md` — PM2 vs isolated dev ports
- `.github/pull_request_template.md` — PR checklist
- `scripts/gh-set-issue-status.sh` — board Status keys
