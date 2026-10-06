<!-- solo-dev-ai-kit:managed -->
# Update workflow kit — paste to your AI agent

Use when **solo-dev-ai-kit** has new releases and your **app project** already has the workflow installed.

After bootstrap, a copy lives in the app project as **`docs/update-prompt.md`** — agents can follow it when you say *update workflow kit* or `/update` without pasting this file.

Open the **app project** in Cursor Agent mode. Paste below. **You run terminal commands** — not the user.

---

Update **solo-dev-ai-kit** in this project to the latest kit version. I will not run terminal myself — you do.

## Kit source (must be up to date)

```bash
# If kit is a local clone — pull latest first:
cd [path/to/solo-dev-ai-kit] && git pull

# Or clone fresh:
git clone https://github.com/sahibul-nf/solo-dev-ai-kit.git /tmp/solo-dev-ai-kit
```

## Before you change anything

1. Read `.workflow-kit/installed` — note `kit_version`, `tools`, `app_stack`.
2. Read `.workflow-kit.env` — especially `GH_PROJECT_NUM`, branches, `CI_TEST_COMMAND`, `VERIFY_MAX_ROUNDS`, `APP_STACK`.
3. Tell me the version jump (e.g. `kit_version=11` → `12`) and summarize what changed (read `CHANGELOG.md` in the kit repo).
4. **Dry-run first** (recommended):

```bash
/path/to/solo-dev-ai-kit/bootstrap.sh --target . --dry-run
```

Review the `[dry-run]` lines. No files are modified.

## Re-bootstrap (safe update)

Run from the **app project root** (not inside the kit repo):

```bash
/path/to/solo-dev-ai-kit/bootstrap.sh --target .
```

**You do not need to repeat every flag.** If `.workflow-kit.env` already exists, bootstrap **merges** it:

| Preserved automatically | Only changed if you pass a CLI flag |
|-------------------------|-------------------------------------|
| `GH_PROJECT_NUM`, `GH_PROJECT_OWNER` | `--repo` |
| `GH_REPO`, branches, `SINGLE_BRANCH` | `--integration-branch`, `--production-branch`, `--main-only` |
| `WORKFLOW_TOOLS`, `CI_TEST_COMMAND` | `--tools`, `--ci-test` |
| `APP_STACK`, `VERIFY_MAX_ROUNDS` | `--app-stack`, `--verify-max-rounds` |
| `EXTRA_LABELS`, `HAS_CLIENT_REPORTS` | `--extra-labels`, `--client-reports` |

Before writing, bootstrap saves `.workflow-kit/env.backup`.

### Without `--force` (default — recommended)

**Updates:** scripts (`scripts/gh-*.sh`), cursor rules/commands, most `docs/*`, issue templates, `.workflow-kit/installed`.

**Preserves (skipped if customized):** `docs/how-to-run.md`.

**`AGENTS.md`:** auto-merges kit workflow sections (intent router, phases, self-verify, Related, etc.) and **preserves** project-specific `##` sections or content in `<!-- workflow-kit:project-specific -->`.

After update: review `git diff AGENTS.md` — project-specific blocks should be intact.

### With `--force` (only if I say so)

Overwrites `AGENTS.md` (including project-specific sections) and `docs/how-to-run.md` with latest templates. Warn me before running `--force`.

## After bootstrap

1. Run `./scripts/gh-check-ui-tools.sh` — report output.
2. Show `git diff --stat` of workflow files.
3. Compare new `kit_version` in `.workflow-kit/installed`.
4. Confirm `GH_PROJECT_NUM` unchanged (grep `.workflow-kit.env`).
5. List any **new files** I should read (e.g. new docs).
6. Do **not** change app feature code.

## GitHub board / env

- Re-bootstrap **preserves** `GH_PROJECT_NUM` and `GH_PROJECT_OWNER` from the existing `.workflow-kit.env`.
- Only run `--run-github-setup` if I ask (labels/board missing).
- Never put secrets in `.workflow-kit.env`.

## Ultra-short

```text
Pull latest solo-dev-ai-kit, dry-run bootstrap (--target . --dry-run), then re-bootstrap (--target ., no --force unless I ask). Report kit_version change, confirm GH_PROJECT_NUM preserved, show git diff. No app coding.
```
