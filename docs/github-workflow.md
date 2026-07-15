# GitHub workflow (Otonom Media delivery)

Solo dev + AI: **Issues**, **Projects**, and agent rules stay in sync.

## Issues

- **One issue = one shippable outcome** with acceptance criteria.
- Labels: `bug`, `enhancement`, `priority:high|medium|low`, `client-facing` (optional).
- Templates: `.github/ISSUE_TEMPLATE/`
- Link PRs: `Fixes #NNN`

## Project board

Board: **Otonom Media delivery** — https://github.com/users/sahibul-nf/projects/7

### Kanban Status

**Backlog → In Progress → QA → Done**

Run once if QA column missing:

```bash
./scripts/gh-ensure-project-status-qa.sh
```

### Custom fields

| Field | Values |
|-------|--------|
| **Priority** | High · Medium · Low |
| **Focus** | This week · Backlog · Icebox |

Filter **Focus = This week** for your sprint.

## Daily workflow

1. Pick **This week** issue → **In Progress**.
2. Branch → PR `Fixes #N` → merge when ready.
3. **QA** on staging until verified.
4. Confirm *works* → AI runs `gh-close-verified-issue.sh` → **Done**.

## CI & deploy

| Step | Branch | Action |
|------|--------|--------|
| Production | `main` | CI + deploy on push (single branch) |

No separate integration branch. Do not reference `dev` unless it appears in `git branch -a`.

## Default AI behavior

**You:** describe a bug or feature.

**AI:** triage → issue → board → *"Review #N; which first?"*

**You:** *Implement #5.*

**AI:** code + PR (no new issue).

Setup scripts: `./scripts/gh-setup-all.sh`

## AI tools

Configured tools: **Cursor, Antigravity**

See `AGENTS.md` for triage phases. Re-bootstrap from **solo-dev-ai-kit** (`MASTER_PROMPT.md`).
