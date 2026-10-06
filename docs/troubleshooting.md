<!-- solo-dev-ai-kit:managed -->
# Troubleshooting (Otonom Media delivery)

Common issues when using solo-dev + AI workflow scripts.

## `gh` authentication

**Symptom:** `gh: authentication required` or missing `project` scope.

```bash
gh auth status
gh auth refresh -h github.com -s repo,project,read:project
```

## `GH_PROJECT_NUM` unset / issue not on board

**Symptom:** `Note: GH_PROJECT_NUM unset` or `gh-set-issue-status.sh` does nothing.

```bash
./scripts/gh-setup-project.sh sahibul-nf/otonom-agents-media
# or full setup:
./scripts/gh-setup-all.sh
```

Check `.workflow-kit.env` — `GH_PROJECT_NUM` should be a number. Re-run setup if empty.

## Status column missing on board

**Symptom:** Cannot set status to `ai-review`, `ready-for-ai`, or `qa`.

```bash
./scripts/gh-ensure-project-status.sh
```

Adds **Ready for AI**, **AI Working**, **AI Review**, **Human Review**, and **QA** without moving existing cards. Reorder columns in GitHub: Project → … → Fields → Status if needed.

## Orchestrator picked up wrong issue

**Symptom:** Agent ran on Backlog / In Progress / label `ai-ready`.

Only **Project Status = Ready for AI** authorizes autonomous orchestrator pickup. Labels are metadata. Move the card explicitly; do not rely on labels.

## Triage fails: acceptance criteria

**Symptom:** `body must include '## Acceptance criteria'`.

Issue body must match `docs/issue-body.example.md`:

```markdown
## Acceptance criteria

- [ ] First criterion
```

Use `./scripts/gh-validate-issue-body.sh --body-file /tmp/body.md` before create.

## UI verification

### Web — browser cannot reach app

1. Fill `docs/how-to-run.md` — **Local URL** and **Start command** (replace all `TBD`).
2. Start dev server before verify.
3. Run `./scripts/gh-check-ui-tools.sh`.

Kit **never** auto-installs Playwright. Cursor IDE browser is default in Cursor.

### Mobile — Flutter / native

1. Set `APP_STACK=mobile` in `.workflow-kit.env` (or bootstrap `--app-stack mobile`).
2. Fill emulator + test commands in `docs/how-to-run.md`.
3. **MobAI** (optional): install from [mobai.run](https://mobai.run), open simulator, run `npx mobai-mcp`. Not installed by kit.

### Agent verifies too much (token usage)

- Default: **AC scope only** — not full app.
- Say *max 2 rounds* for one issue, or set `VERIFY_MAX_ROUNDS` in `.workflow-kit.env`.
- Full E2E only when you explicitly ask.

## Re-bootstrap without losing custom docs

See **`docs/updating-workflow-kit.md`** for the full update flow when the kit repo has new releases.

```bash
/path/to/solo-dev-ai-kit/bootstrap.sh --target . --repo sahibul-nf/otonom-agents-media --tools cursor,antigravity
```

Without `--force`: merges kit workflow sections into `AGENTS.md` and keeps project-specific blocks; keeps your `docs/how-to-run.md`. Use `--force` to overwrite both completely.

## Board URL still placeholder in docs

Run GitHub setup, then re-render or edit `AGENTS.md` / `docs/github-workflow.md` so `(set after ./scripts/gh-setup-project.sh)` is replaced — or run bootstrap with `--run-github-setup` once.

## Still stuck?

1. `cat .workflow-kit.env`
2. `./scripts/gh-check-ui-tools.sh`
3. `gh issue view N --repo sahibul-nf/otonom-agents-media`
4. See `scripts/README.md` for script flags
