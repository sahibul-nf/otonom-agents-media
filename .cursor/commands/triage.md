<!-- solo-dev-ai-kit:managed -->
Phase 1 only — triage, no coding.

Follow `AGENTS.md` Phase 1:

1. Investigate codebase (read-only).
2. Search open issues for duplicates.
3. Create issue via `./scripts/gh-triage-issue.sh` using `docs/issue-body.example.md`. Set exactly one `reasoning:low|medium|high|xhigh` label (default `reasoning:medium` if unsure). This is model-effort metadata, not board Priority.
4. Set board **Backlog** / **Todo** only: `./scripts/gh-set-issue-status.sh N backlog`
5. **Never** set **Ready for AI** — that is explicit human authorization for orchestrators.
6. Reply with issue URL and stop.

Ask: *"Review the issue; move to Ready for AI when authorized, or tell me which # to implement."*
