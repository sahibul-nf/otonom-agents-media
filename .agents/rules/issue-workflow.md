---
trigger: always_on
---
<!-- solo-dev-ai-kit:managed -->

# Workflow pointer

Follow **`AGENTS.md`** for the full workflow (intent router, triage, implement, self-verify, close-out).

Project **Status** authorizes orchestrators (**Ready for AI** only) — not labels. `/triage` never sets Ready for AI.

PRs target **`dev`**. Orchestrators may merge **`dev`** after a green full test suite. Never merge or push **`main`** / restart PM2.

Do not duplicate rules here. Classify intent first; triage by default for real work without `#N`.

Repo: `sahibul-nf/otonom-agents-media` · Board: https://github.com/users/sahibul-nf/projects/7
