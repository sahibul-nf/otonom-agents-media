<!-- solo-dev-ai-kit:managed -->
# GitHub workflow (Otonom Media delivery)

Solo dev + AI: **Issues**, **Projects**, and agent rules stay in sync.

## Cheatsheet

| You say | AI does |
|---------|---------|
| Describe bug/feature | Triage → issue → **Backlog** → *Ready for AI when authorized?* |
| `Implement #N` | **AI Working** → self-verify (**AC only**) → **AI Review** |
| `sudah work #N` | `gh-close-verified-issue.sh` → closed + **Done** |
| *skip issue* / tiny fix | Fix + verify (no issue) |
| *max 2 rounds* / *5 putaran* | Override verify loops for **this issue only** |
| *test end-to-end full* | Full app regression (you asked — not default) |

**Verify scope:** acceptance criteria only · **Default max rounds:** see `VERIFY_MAX_ROUNDS` in `.workflow-kit.env`  
**Docs:** `AGENTS.md` · `docs/how-to-run.md` · `docs/orchestrator-integration.md` · `docs/troubleshooting.md` · `scripts/README.md`

## Issues

- **One issue = one shippable outcome** with acceptance criteria.
- Labels: `bug`, `enhancement`, `priority:*`, optional `complexity:*`, `ai-blocked`, `ai-needs-human`, `client-facing`.
- **Labels are metadata** — they do **not** authorize AI execution. **Project Status** does.
- Templates: `.github/ISSUE_TEMPLATE/`
- Body template for AI: `docs/issue-body.example.md`
- Link PRs: `Fixes #NNN`

## Project board

Board: **Otonom Media delivery** — (set after ./scripts/gh-setup-project.sh)

### Status (workflow + authorization)

| Status | Meaning |
|--------|---------|
| **Backlog** / **Todo** | Not started — AI must not autonomously execute |
| **Ready for AI** | Human authorized — orchestrators may pick up |
| **AI Working** | Agent implementing (legacy: **In Progress**) |
| **AI Review** | Verify done, PR ready (legacy: **QA**) |
| **Human Review** / **QA** | Human reviews PR |
| **Done** | Merged/closed after human confirmation |

Setup columns (idempotent; does not move existing cards):

```bash
./scripts/gh-ensure-project-status.sh
```

```bash
./scripts/gh-set-issue-status.sh <N> backlog|ready-for-ai|ai-working|ai-review|human-review|done
# Legacy keys still work: progress → ai-working, qa → human-review
```

### Custom fields

| Field | Values |
|-------|--------|
| **Priority** | High · Medium · Low |
| **Focus** | This week · Backlog · Icebox |

Filter **Focus = This week** for your sprint.

## Daily workflow

```
/triage → human moves to Ready for AI (optional) → /implement → /verify → Human Review → merge → /close
```

1. Triage → **Backlog**. Human moves to **Ready for AI** when requirements are clear (or say *Implement #N* in chat).
2. Branch `feat/#N-slug` → implement → self-verify → **AI Review** on board.
3. PR `Fixes #N` → human reviews (**Human Review** / **QA**) → merge when ready.
4. You confirm *works* → AI runs `gh-close-verified-issue.sh` → issue closed + **Done**.

## CI & deploy

| Step | Branch | Action |
|------|--------|--------|
| Production | `main` | CI + deploy on push (single branch) |

No separate integration branch. Do not reference `dev` unless it appears in `git branch -a`.

## Default AI behavior

| You say | AI does |
|---------|---------|
| Describe bug/feature | Triage → issue → **Backlog** |
| *Implement #5* | Code → self-verify → **AI Review** |
| *sudah work #5* | Close issue → **Done** |
| Tiny fix / *skip issue* | Fix + verify (no issue) |

Setup scripts: `./scripts/gh-setup-all.sh`

## AI tools

Configured tools: **Cursor, Antigravity**

Re-run bootstrap from **solo-dev-ai-kit** (`MASTER_PROMPT.md` or `INSTALL_PROMPT.md` — paste to AI; no terminal needed from you).
