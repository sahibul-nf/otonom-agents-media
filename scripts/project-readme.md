# Otonom Media delivery — dev board

Solo dev + AI workflow for **sahibul-nf/otonom-agents-media**.

## Daily rhythm

1. Open **Kanban** — pick **Focus = This week** (or move one from Backlog).
2. Drag **Status** to *In Progress* → branch `feat/…` → PR with `Fixes #N`.
3. After merge or staging deploy, drag to **QA** until you confirm in a real session.
4. **Done** when verified; AI runs `./scripts/gh-close-verified-issue.sh` when you confirm *works* / *ok*.
5. **Push `main` before `main`** when CI tests only run on integration branch.
6. User-visible work → `CHANGELOG.md` when it matters.

## Status (Kanban)

| Status | When |
|--------|------|
| **Backlog** | Not started |
| **In Progress** | Active branch |
| **QA** | On staging — confirming acceptance |
| **Done** | Verified |

If **QA** is missing: `./scripts/gh-ensure-project-status-qa.sh`

## Custom fields

| Field | Values |
|-------|--------|
| **Priority** | High · Medium · Low |
| **Focus** | This week · Backlog · Icebox |

## Links

- [Repo issues](https://github.com/sahibul-nf/otonom-agents-media/issues)
- [github-workflow.md](https://github.com/sahibul-nf/otonom-agents-media/blob/main/docs/github-workflow.md)

## AI prompt

`Implement #N acceptance criteria`
