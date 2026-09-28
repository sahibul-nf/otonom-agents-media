<!-- solo-dev-ai-kit:managed -->
Kit uninstall — remove solo-dev-ai-kit local files from this project (not app code; not GitHub board).

Follow `docs/uninstalling-workflow-kit.md` and `docs/uninstall-prompt.md`:

1. Dry-run: `/path/to/solo-dev-ai-kit/uninstall-workflow-kit.sh --target . --dry-run`
2. Apply: `uninstall-workflow-kit.sh --target .`
3. Preserves `docs/how-to-run.md`; extracts project-specific `AGENTS.md` → `docs/project-guidelines.md`
4. Show `git diff --stat`. Do not delete GitHub issues, project, or labels.
