# Uninstall workflow kit — paste to your AI agent

Remove **solo-dev-ai-kit** from this **app project** (local files only). **You run terminal** — not the user.

**Does NOT delete:** GitHub Issues, Project board, labels, PRs, or app feature code.

---

Uninstall **solo-dev-ai-kit** from this project. I will not run terminal myself — you do.

## Before you remove anything

1. Confirm this is the **app project** (not the kit repo).
2. Run **dry-run** first:

```bash
/path/to/solo-dev-ai-kit/uninstall-workflow-kit.sh --target . --dry-run
```

3. Show me the `[dry-run]` / `would remove` list.

## Uninstall

```bash
/path/to/solo-dev-ai-kit/uninstall-workflow-kit.sh --target .
```

Default behavior (kit v12+):

- Reads `.workflow-kit/manifest` and removes paths **only if** they still have a kit marker (`solo-dev-ai-kit:managed` or `partial-managed` on `AGENTS.md`).
- Files you customized (marker removed) are **skipped**.
- **Keeps** `docs/how-to-run.md` always.
- Extracts project-specific content from `AGENTS.md` → `docs/project-guidelines.md`, then removes `AGENTS.md`.
- **Does not** touch GitHub board, issues, or labels.

Pre-v12 installs: script falls back to legacy allowlist (or pass `--legacy-allowlist`).

Use `--keep-agents` only if I ask to leave `AGENTS.md` untouched.

## After uninstall

1. Show `git diff --stat`.
2. Confirm GitHub Project/issues were **not** modified.
3. Tell me to reload Cursor.
4. Do **not** change app feature code.

## Ultra-short

```text
Dry-run uninstall-workflow-kit.sh (--target .), then apply. Keep how-to-run.md; preserve AGENTS project-specific to docs/project-guidelines.md. No GitHub board changes. Show git diff.
```
