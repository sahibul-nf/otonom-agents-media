<!-- solo-dev-ai-kit:managed -->
# Orchestrator integration (Otonom Media delivery)

Optional guide for external AI execution systems (Paperclip, custom workers, CI agents). **This repository does not ship orchestrator code** — GitHub Issues + Project Status remain the source of truth.

**Any orchestrator** that implements this contract is supported — Paperclip is one example, not a dependency. To switch tools later, keep GitHub as the source of truth and rewire only the control plane (poll/webhook, spawn agent, update Status). Coding agents (Cursor, Codex, Claude, Gemini, OpenCode, Hermes, etc.) keep reading `AGENTS.md`; no kit changes required.

## Concepts

| Piece | Role |
|-------|------|
| GitHub Issue | Unit of work + acceptance criteria |
| Project **Status** | Workflow state + **authorization** for autonomous runs |
| Labels | Metadata only (`complexity:*`, `ai-blocked`) — **not** execution triggers |
| Coding agent | Cursor, Codex, Claude, Gemini, OpenCode, etc. — reads `AGENTS.md` |
| Orchestrator | Polls board, assigns one issue per run |
| Pull Request | Reviewable output — agent may merge to **`dev`** after green full suite; human merges **`main`** |

**Never** use an `ai-ready` **label** as the primary trigger. Only **Ready for AI** on the Project board authorizes orchestrator pickup.

## Board setup

```bash
./scripts/gh-ensure-project-status.sh
```

Adds **Ready for AI**, **AI Working**, **AI Review**, **Human Review** without moving existing cards (Todo / In Progress / Done stay put). Remove legacy **QA** with `./scripts/gh-remove-qa-status.sh`.

## Orchestrator loop

1. Poll GitHub Project for items with Status = **Ready for AI**.
2. Pick **one** issue (respect cost principles — no backlog drain).
3. Spawn coding agent with: issue URL, clone on **`dev`**, `AGENTS.md` + `CONTRIBUTING.md`.
4. Agent moves issue → **AI Working**, implements on `feat/#N-slug` from **`dev`**, adds tests for the AC if missing, runs the **full** unittest suite.
5. Agent opens PR **into `dev`** (never `main`) with How to test (UI). **Green suite → merge to `dev`**, board **Human Review**. **Red suite → do not merge**, board **AI Review**.
6. Human UI-checks, later ships **`main`** on ops.
7. Human confirms *sudah work* → agent or human runs `gh-close-verified-issue.sh` → **Done**.

## Status script keys

```bash
./scripts/gh-set-issue-status.sh <N> ready-for-ai   # human only
./scripts/gh-set-issue-status.sh <N> ai-working     # agent start
./scripts/gh-set-issue-status.sh <N> ai-review      # suite red / blocked
./scripts/gh-set-issue-status.sh <N> human-review   # after merge to dev (UI check)
./scripts/gh-set-issue-status.sh <N> done
```

Legacy boards: `ai-working` → **In Progress** when **AI Working** is missing.

## Interactive Cursor (no orchestrator)

Humans can still say *Implement #N* or `/implement` — that is **chat authorization**, not board authorization. Orchestrators must still require **Ready for AI**.

## Blocked work

If the agent cannot proceed, comment on the issue with:

1. What is ambiguous or risky
2. What decision is required
3. Options
4. What information is needed

Add label `ai-needs-human` or `ai-blocked` (metadata). Do **not** merge or close without human direction.

## Paperclip (example)

Paperclip or similar tools can:

- Watch the linked GitHub Project
- Filter `Status == Ready for AI`
- Delegate to a configured coding agent runtime
- Respect `VERIFY_MAX_ROUNDS` and autonomy boundaries in `AGENTS.md`

No Paperclip-specific configuration lives in this kit — wire your orchestrator to the Status field above.

See also `AGENTS.md` and `docs/github-workflow.md`.
