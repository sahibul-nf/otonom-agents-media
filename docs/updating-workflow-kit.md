# Updating the workflow kit (Otonom Media delivery)

When [solo-dev-ai-kit](https://github.com/sahibul-nf/solo-dev-ai-kit) releases updates, refresh this project with **re-bootstrap** — there is no separate updater binary.

## Check your version

```bash
cat .workflow-kit/installed
# kit_version=12
# tools=cursor,antigravity
# app_stack=mobile
```

Compare with the latest kit repo after `git pull`.

## Safe update (recommended)

```bash
cd /path/to/solo-dev-ai-kit && git pull

cd /path/to/your-app

# Preview changes (no writes):
/path/to/solo-dev-ai-kit/bootstrap.sh --target . --dry-run

# Apply:
/path/to/solo-dev-ai-kit/bootstrap.sh --target .
```

If `.workflow-kit.env` exists, bootstrap **merges** your settings automatically (`GH_PROJECT_NUM`, branches, tools, `CI_TEST_COMMAND`, `APP_STACK`, `VERIFY_MAX_ROUNDS`, etc.). Pass CLI flags only when you want to **override** a value.

A backup is saved to `.workflow-kit/env.backup` before the env file is rewritten.

**Without `--force`:**

| Always refreshed | Preserved if you customized |
|------------------|----------------------------|
| `scripts/*.sh`, `scripts/README.md` | `docs/how-to-run.md` |
| `.cursor/rules`, `.cursor/commands` | |
| `docs/github-workflow.md`, `docs/troubleshooting.md` | |
| `docs/updating-workflow-kit.md`, `docs/update-prompt.md` | |
| `docs/close-comment.example.md`, issue templates | |
| `AGENTS.md` — **kit workflow sections merged**; project-specific `##` blocks kept | |
| `.workflow-kit/installed` (`kit_version`) | |
| `.workflow-kit/manifest` + `solo-dev-ai-kit:managed` markers on kit files | |

After update: review `git diff`. Custom app guidelines under `<!-- workflow-kit:project-specific -->` (or unknown `##` headings) stay in place; kit sections (intent router, self-verify, etc.) refresh automatically.

Verify managed markers (optional):

```bash
./scripts/verify-kit-managed.sh
```

## Full overwrite

Only if you want the latest kanon and are OK losing local edits to workflow docs:

```bash
./bootstrap.sh --target . --force
```

## Via AI (no terminal yourself)

Any of these work in Cursor Agent mode:

- Say **update workflow kit** or **perbarui workflow kit** (routed in `AGENTS.md`).
- Run slash command **`/update`** (if Cursor commands installed).
- Paste **`docs/update-prompt.md`** (English) or **`docs/update-prompt.id.md`** (Bahasa Indonesia).

The agent reads this file + `docs/update-prompt.md`, dry-runs bootstrap, then applies without `--force`.

## What re-bootstrap does **not** do

- Does **not** reset `GH_PROJECT_NUM` or `GH_PROJECT_OWNER` (merged from existing env).
- Does not re-detect git branches if they were already configured (unless you pass branch flags or `--main-only`).
- Does not run GitHub setup unless you pass `--run-github-setup`.
- Does not change your app source code.

## After updating

```bash
grep GH_PROJECT_NUM .workflow-kit.env
./scripts/gh-check-ui-tools.sh
git diff AGENTS.md docs/ scripts/
```

See also `docs/troubleshooting.md`.
