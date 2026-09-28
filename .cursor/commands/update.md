<!-- solo-dev-ai-kit:managed -->
Kit update — refresh solo-dev-ai-kit in this project (not app feature work).

Follow `AGENTS.md` **Kit update** and read `docs/update-prompt.md` + `docs/updating-workflow-kit.md`:

1. Report current `kit_version` and `GH_PROJECT_NUM` from `.workflow-kit/installed` / `.workflow-kit.env`.
2. Pull latest solo-dev-ai-kit repo.
3. Dry-run: `bootstrap.sh --target . --dry-run` from kit path.
4. Apply: `bootstrap.sh --target .` — **no `--force`** unless user explicitly asked.
5. `./scripts/gh-check-ui-tools.sh`; confirm `GH_PROJECT_NUM` preserved; show `git diff --stat`.
6. Confirm `AGENTS.md` merged — kit workflow sections updated, project-specific blocks preserved (unless `--force`).
7. Do not change app feature code.
