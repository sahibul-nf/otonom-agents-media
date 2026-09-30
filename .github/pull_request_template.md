## Summary

<!-- What this PR does and why. One issue: Fixes #N -->

Fixes #

## Base branch (required)

- [ ] This PR targets **`dev`**, not `main`
- [ ] Branch was created from **`dev`** (`feat/#N-slug` or `fix/#N-slug`)
- [ ] I did **not** push to `main` or restart PM2 / the ops checkout

## Test plan

- [ ] Self-verify against issue **Acceptance criteria** only (`AGENTS.md`)
- [ ] Tests / command: `cd media-engine && python3 -m unittest discover -s tests -p 'test_*.py'` (or focused subset)

## Deploy safety

- [ ] No production ports stolen (`8765` / `3100`)
- [ ] No live `data/` or `artifacts/` from the ops clone

**Do not merge** until a human reviews. Agents stop at board **AI Review**.
