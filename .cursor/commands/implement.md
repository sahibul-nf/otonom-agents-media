<!-- solo-dev-ai-kit:managed -->
Phase 2 — implement issue `#N` (user must specify number in chat, or orchestrator: Status = Ready for AI).

Follow `AGENTS.md` Phase 2:

1. Read acceptance criteria for the issue. Stop with `ai-needs-human` if high-risk/ambiguous (see AI autonomy boundaries).
2. Plan if non-trivial (>1 file or new user-facing behavior).
3. Branch or worktree `feat/#N-slug` or `fix/#N-slug` — smallest correct change.
4. Implement focused diff.
5. `./scripts/gh-set-issue-status.sh N ai-working` (legacy: **In Progress**)
6. **Self-verify** per `AGENTS.md` — AC scope only; max rounds from `VERIFY_MAX_ROUNDS` or user override.
7. `./scripts/gh-set-issue-status.sh N ai-review` when ready (legacy: **QA**)
8. PR `Fixes #N`. Commit only when user asks. **Do not merge.**

Do not close the issue — wait for human *sudah work*.
