# Uninstalling the workflow kit (Otonom Media delivery)

Remove **local** solo-dev-ai-kit files from this project. **Does not** delete GitHub Issues, Project board, labels, or PRs.

## Quick uninstall

From a clone of [solo-dev-ai-kit](https://github.com/sahibul-nf/solo-dev-ai-kit):

```bash
# Preview
/path/to/solo-dev-ai-kit/uninstall-workflow-kit.sh --target /path/to/your-app --dry-run

# Apply
/path/to/solo-dev-ai-kit/uninstall-workflow-kit.sh --target /path/to/your-app
```

Or paste **`docs/uninstall-prompt.md`** into Cursor Agent mode (installed copy) or **`UNINSTALL_PROMPT.md`** from the kit repo.

## How removal works (kit v12+)

Bootstrap writes **`.workflow-kit/manifest`** listing every path it installed. Uninstall reads that list and removes a file **only if** it still carries a kit marker:

| Marker | Meaning |
|--------|---------|
| `<!-- solo-dev-ai-kit:managed -->` | Full kit file (docs, scripts, rules, templates) |
| `<!-- solo-dev-ai-kit:partial-managed -->` | `AGENTS.md` — kit sections + your project-specific blocks |
| `# solo-dev-ai-kit:managed` | Shell/Python/YAML/env files |
| `"_solo_dev_ai_kit": { "managed": true }` | `.gemini/settings.json` |

If you edited a file and removed the marker, uninstall **skips** it (treated as yours).

**Always protected:** `docs/how-to-run.md` (even if stamped).

**Pre-v12 installs** (no manifest): use `--legacy-allowlist` or uninstall falls back automatically when manifest is missing.

Audit markers after bootstrap:

```bash
./scripts/verify-kit-managed.sh
```

## What gets removed

| Removed | Kept |
|---------|------|
| `AGENTS.md` (after preserving project-specific → `docs/project-guidelines.md`) | `docs/how-to-run.md` |
| `.workflow-kit.env`, `.workflow-kit/` | App source code |
| `scripts/gh-*.sh`, kit `scripts/README.md` | Custom files in `scripts/` if any |
| `.cursor/rules` + kit slash commands | Non-kit `.cursor/commands` |
| `.agents/rules` (kit files) | GitHub board, issues, labels |
| Kit workflow `docs/*` | `CHANGELOG.md` (unless `--remove-changelog`) |
| `.github/ISSUE_TEMPLATE/` (kit templates) | Custom issue templates if added |

## Options

| Flag | Effect |
|------|--------|
| `--dry-run` | Show what would be removed |
| `--keep-agents` | Do not remove or extract `AGENTS.md` |
| `--remove-changelog` | Also remove `CHANGELOG.md` |
| `--legacy-allowlist` | Ignore markers; use path allowlist (pre-v12) |

## After uninstall

```bash
git diff --stat
git commit -m "chore: remove solo-dev-ai-kit workflow files"
```

Reload Cursor so removed rules/commands stop applying.

## Re-install later

Run bootstrap again from solo-dev-ai-kit — see `docs/updating-workflow-kit.md` / `INSTALL_PROMPT.md`.
