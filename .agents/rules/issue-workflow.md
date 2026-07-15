---
trigger: always_on
---

# GitHub issue triage & delivery

Canonical detail: **`AGENTS.md`**, `docs/github-workflow.md`

## When this applies

Any **feature**, **bug**, **improvement**, or stakeholder request.

**Skip triage when:** user says *Implement #N*, *skip issue*, *just fix*, or asks a question only.

## Phase 1 — Triage (no coding)

1. Restate outcome in one line.
2. Search codebase; note files and gaps.
3. `gh issue list --repo sahibul-nf/otonom-agents-media --state open --search "…"` — link duplicates.
4. Create issue: `./scripts/gh-triage-issue.sh --title "[Bug]: …" --body-file … --labels "…"`
   - Body: follow `docs/issue-body.example.md` — `## Acceptance criteria` with `- [ ]` · Out of scope
5. Reply with issue URL; **stop**. Ask which # to implement first.

## Phase 2 — Implement

User says *Implement #N* / *kerjakan #N* / *LGTM #N*.

- Follow acceptance criteria; PR `Fixes #N`; commit only when user asks.

## Phase 3 — Close-out

User confirms *works* / *ok* for #N → verify AC → `./scripts/gh-close-verified-issue.sh N --comment-file …`

## Git push order

Merge to **`main`** → **`git push origin main`**. No separate integration branch in this repo.

Before merge/push: **`git branch -a`**. If integration branch from `.workflow-kit.env` is missing, push production branch only (see `AGENTS.md`).

Repo: `sahibul-nf/otonom-agents-media` · Board: https://github.com/users/sahibul-nf/projects/7
