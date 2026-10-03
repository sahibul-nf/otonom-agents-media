<!-- solo-dev-ai-kit:managed -->
Re-run verification against acceptance criteria for issue `#N` (user must specify).

Follow `AGENTS.md` self-verify section:

1. **Scope lock** — verify only AC items for `#N`; not full app unless user asked for E2E.
2. List each `- [ ]` and gather one evidence item per AC (tests preferred over screenshots).
3. Classify UI / non-UI / mixed; use web browser or MobAI per `docs/how-to-run.md` and `APP_STACK`.
4. Report pass/fail per AC with evidence.
5. If gaps remain and under loop gate (max rounds from `AGENTS.md` / user override), fix and re-verify.
6. If passed → `./scripts/gh-set-issue-status.sh N ai-review` (chat). Orchestrator merge to **`dev`** is only after the **full** suite exits 0 (`CONTRIBUTING.md`).

Chat: do not merge unless asked. Never merge **`main`**. Do not close the issue unless user confirms *sudah work*.
