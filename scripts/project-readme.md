<!-- solo-dev-ai-kit:managed -->
# Otonom Media delivery — project board

Dev board for **sahibul-nf/otonom-agents-media** (solo dev + AI workflow).

## Flow

1. **Triage** → issue on board (**Backlog** / **Todo**).
2. Human moves to **Ready for AI** when autonomous work is authorized (or implement via chat).
3. Agent implements → **AI Working** → self-verify → **AI Review** → PR.
4. Human reviews PR → **Human Review** / **QA**.
5. Merge → confirm *works* → close issue → **Done**.

## Status columns

| Status | When |
|--------|------|
| **Backlog** / **Todo** | Triaged, not started |
| **Ready for AI** | Human authorized orchestrator/agent pickup |
| **AI Working** / **In Progress** | Active implementation |
| **AI Review** / **QA** | Automated verify done — PR ready |
| **Human Review** / **QA** | Human reviews diff |
| **Done** | Shipped |

```bash
./scripts/gh-ensure-project-status.sh   # add columns without moving cards
./scripts/gh-set-issue-status.sh N ai-working
```

## Fields

- **Priority:** High · Medium · Low (synced from issue labels)
- **Focus:** This week · Backlog · Icebox

See `AGENTS.md` and `docs/github-workflow.md`.
