# Agent & maintainer guide (Otonom Media delivery)

<!-- solo-dev-ai-kit:partial-managed -->

**Single source of truth** for humans and AI agents. Platform-specific files only point here — they do not duplicate rules.

**Active tools (this repo):** Cursor, Antigravity

| Platform | Official instruction file | Role in this repo |
|----------|---------------------------|-------------------|
| **All / Codex** | `AGENTS.md` | **Canonical** — full workflow (this file) |
| **Cursor** | `AGENTS.md` + `.cursor/rules/*.mdc` | Thin router rule (`alwaysApply: true`) |
| **Antigravity** | `.agents/rules/*.md` | Thin pointer (`trigger: always_on`) |
| **Claude Code** | `CLAUDE.md` | Stub → read `AGENTS.md` |
| **Gemini CLI** | `AGENTS.md` (+ optional `GEMINI.md`) | Auto-discovered; stub optional |

See `docs/agent-platforms.md` for official doc links.

## Git & deploy

- **Branch model:** dual — integration **`dev`** then production **`main`**
- **CI tests:** push to **`dev`** runs `cd media-engine && python3 -m unittest discover -s tests -p 'test_*.py'`
- **Production deploy:** push **`main`** when ready
- **Commits:** Only when the user explicitly asks

### Merge & push order (AI)

CI/tests run on **`git push origin dev`**, not on **`main`** alone.

```text
1. merge feat/* → dev
2. git push origin dev   ← CI / tests
3. merge dev → main
4. git push origin main    ← deploy
```

**Before merge/push:** run `git branch -a` — if **`dev`** does not exist, use single-branch flow below instead of inventing the branch.

## Changelog (`CHANGELOG.md`)

- **`## [Unreleased]`** — user-relevant changes on integration branch.
- Version blocks — what shipped on **`main`**.
- Use `### Added` / `### Changed` / `### Fixed` / `### Removed`.

## Intent router (default)

Classify every user message before acting:

| Intent | Action |
|--------|--------|
| Question / exploration | Answer only — no issue, no code |
| **Tiny** (typo, copy, one-file CSS, obvious fix) | Implement + self-verify; say *skipped issue* |
| Feature / bug / improvement (no `#N`) | **Phase 1 Triage** → stop |
| `Implement #N` / `kerjakan #N` / `LGTM #N` | **Phase 2 Implement** |
| *works* / *ok* / *sudah work* for `#N` | **Phase 3 Close-out** (human QA) |
| `update workflow kit` / `update solo-dev-ai-kit` / `/update` / *perbarui workflow kit* | **Kit update** — follow `docs/updating-workflow-kit.md` + `docs/update-prompt.md` |
| `uninstall workflow kit` / `/uninstall` / *hapus workflow kit* | **Kit uninstall** — follow `docs/uninstalling-workflow-kit.md` + `docs/uninstall-prompt.md` |

**Tiny** = one clear outcome, ≤1–2 files, no new behavior contract. When unsure, triage instead.

**Skip triage:** user names `#N`, says *skip issue* / *just fix*, or asks a question only.

**Orchestrator vs chat:** External orchestrators (e.g. Paperclip) may implement **only** issues whose **Project Status** is **Ready for AI**. Chat triggers (`Implement #N`, `/implement`) are **human authorization in session** — they do not replace board status for autonomous pickup. **Labels are metadata only** — never treat `ai-ready` or any label as authorization to execute.

## Workflow roles

| Concept | Role |
|---------|------|
| **GitHub Issue** | Unit of work + acceptance criteria |
| **Project Status** | Workflow state and **authorization** for autonomous execution |
| **Labels** | Metadata (`bug`, `priority:*`, `complexity:*`, `reasoning:*`, `ai-blocked`) — not execution triggers |
| **Coding agent** | Implements one issue; follows this file |
| **Orchestrator** | Optional control plane — polls board, assigns agent runs |
| **Pull Request** | Reviewable implementation artifact |
| **Human** | Moves issues on board, reviews PRs, merges, closes |

## Project board Status (workflow contract)

**Source of truth:** GitHub Project **Status** field — not issue labels.

Run once per project to add columns: `./scripts/gh-ensure-project-status.sh`

| Status | Who moves here | AI may execute? |
|--------|----------------|-----------------|
| **Backlog** / **Todo** | Human (triage) | **No** — future or unscoped work |
| **Ready for AI** | Human only — explicit authorization | **Yes** (orchestrators) — requirements clear, scope acceptable |
| **AI Working** | Agent during implement | **Yes** — branch/worktree, commits, tests, PR |
| **AI Review** | Agent after self-verify | **No new code** — summarize, link PR, report checks |
| **Human Review** / **QA** | Human or agent after verify | **No** — human reviews diff/PR |
| **Done** | Human after merge + *sudah work* | **No** |

**`/triage` never sets Ready for AI.** Human drags the card when requirements are ready for autonomous work.

Script keys (preferred column → fallback): `backlog` → Backlog\|Todo · `ready-for-ai` → Ready for AI · `ai-working` / `progress` → AI Working\|In Progress · `ai-review` → AI Review\|QA · `human-review` / `qa` → Human Review\|QA · `done` → Done

```bash
./scripts/gh-set-issue-status.sh <N> backlog|ready-for-ai|ai-working|ai-review|human-review|done
```

## Phase 1 — Triage (no coding)

1. Investigate codebase (read-only).
2. `gh issue list --repo sahibul-nf/otonom-agents-media --state open --search "…"`
3. If duplicate → link it; do not create another.
4. New issue via `./scripts/gh-triage-issue.sh`:
   - Title: `[Bug]:` / `[Feature]:`
   - Body: follow `docs/issue-body.example.md` — must include `## Acceptance criteria` with `- [ ]` lines
   - Labels: `bug` / `enhancement`; `priority:high|medium|low`; **exactly one** `reasoning:low|medium|high|xhigh`; optional `complexity:*`, `client-facing`
5. Board: script adds to project; `./scripts/gh-set-issue-status.sh N backlog` if needed. **Never** set **Ready for AI** in triage.
6. Reply with issue URL; **stop**.

End with: *"Review the issue; move to Ready for AI when authorized, or tell me which # to implement."*

## Phase 2 — Implement

Triggers: *Implement #N*, *kerjakan #N*, *LGTM #N* (chat authorization). Orchestrators: only issues in **Ready for AI**.

1. Read acceptance criteria from issue `#N`. If **high-risk** (see AI autonomy boundaries) and requirements ambiguous → stop, comment, label `ai-needs-human` or `ai-blocked`; do not guess.
2. **Plan before code** if >1 file or new user-facing behavior — short plan (files, risks, tests); ask LGTM unless user already said implement.
3. Branch or worktree: `feat/#N-slug` or `fix/#N-slug` — smallest correct change; no unrelated refactors.
4. Focused diff; update `CHANGELOG.md` if user-facing.
5. `./scripts/gh-set-issue-status.sh N ai-working` (falls back to **In Progress** on legacy boards)
6. **Self-verify** (required before claiming done) — see below.
7. `./scripts/gh-set-issue-status.sh N ai-review` when self-verify passes or stops at gate (falls back to **QA**)
8. PR: `Fixes #N`. Commits only when user asks (or user says *commit* / *PR*). **Do not merge** unless explicit future policy says otherwise.

Do **not** close the issue after self-verify. Human moves to **Human Review** / reviews PR; *sudah work* closes it.

## AI autonomy boundaries

When issue is **Ready for AI** (or human said *Implement #N* in chat), AI **may** implement autonomously:

- UI fixes and small UI features
- CRUD, validation, tests, documentation
- Typing improvements, small refactors, small API integrations
- Straightforward bug fixes with clear AC

**Require human input before implementation** (comment + `ai-needs-human` / `ai-blocked`; do not guess):

- Authentication or authorization architecture
- Payment/billing, secrets/credentials, production infrastructure
- Destructive data operations; DB migrations with meaningful production impact
- Major architecture changes, large dependency migrations, irreversible operations
- Unclear requirements or ambiguous acceptance criteria

When blocked, state: (1) what is ambiguous/risky, (2) decision required, (3) options, (4) information needed from human.

## Cost and autonomy principles

- **One issue per execution** — no draining the backlog autonomously
- **No continuous autonomous loops** without human or orchestrator scheduling the next run
- **Smallest capable model**; escalate only when stuck. Issue label `reasoning:*` is the suggested tier (metadata — not a board field, not authorization):
  - `reasoning:low` — copy, typo, obvious one-file fix
  - `reasoning:medium` — typical bug/feature with clear AC (default if unsure)
  - `reasoning:high` — multi-file design, unclear edge cases, cross-cutting behavior
  - `reasoning:xhigh` — architecture, auth, payments, migrations, or high ambiguity — prefer strongest model and human checkpoints
- **Retry cap** — `VERIFY_MAX_ROUNDS` (override per task in chat only)
- **Stop when unclear** — move to Human Review or comment; do not speculate on high-risk decisions
- **Human review before merge** — PR is for review, not auto-merge
- **Minimal context** — AC scope lock; avoid full-app exploration unless asked

## Phase 3 — Close-out (human QA)

Triggers: user confirms *works* / *ok* / *sudah work* for **#N**.

1. Verify AC against code/commits (read-only).
2. Write closing comment using `docs/close-comment.example.md` as template.
3. `./scripts/gh-close-verified-issue.sh N --comment-file …` (checks AC, comments, closes issue, sets board **Done**).

Use `--no-close` only if user explicitly wants comment-only.

## Kit update (solo-dev-ai-kit refresh)

Triggers: *update workflow kit*, *update solo-dev-ai-kit*, `/update`, *perbarui workflow kit*.

**Read first:** `docs/updating-workflow-kit.md` and `docs/update-prompt.md` (step-by-step). Target is **this app project** — not the kit repo.

1. Read `.workflow-kit/installed` and `.workflow-kit.env` — report `kit_version` jump and preserved `GH_PROJECT_NUM`.
2. Pull latest kit repo (`git pull` on local clone, or clone to `/tmp/solo-dev-ai-kit`).
3. **Dry-run:** `/path/to/solo-dev-ai-kit/bootstrap.sh --target . --dry-run` — show `[dry-run]` output; no writes.
4. **Apply:** `bootstrap.sh --target .` — **no `--force`** unless user explicitly asks. Env merges automatically; backup → `.workflow-kit/env.backup`.
5. Run `./scripts/gh-check-ui-tools.sh`.
6. Report: `git diff --stat`, confirm `GH_PROJECT_NUM` unchanged, new `kit_version`, any new docs.
7. **AGENTS.md** — bootstrap auto-merges kit workflow sections (intent router, phases, self-verify, Related, etc.) and preserves content in `<!-- workflow-kit:project-specific -->` or any `##` section not in the kit template (e.g. app-specific guidelines). Use `--force` only to discard project-specific blocks.
8. **Do not** change app feature code. **Do not** run `--run-github-setup` unless user asks.

## Self-verify (agent definition of done)

Required before saying *siap QA* / *implemented*. Two QA layers:

- **Agent DoD** — evidence against AC (this section).
- **Human QA** — user says *sudah work* → Phase 3.

### Scope lock (default)

Verify **only what the issue acceptance criteria require** — one evidence item per `- [ ]` line.

- Do **not** explore the full app, every screen, or unrelated flows unless AC or the user asks.
- Regression checks only when AC explicitly mentions them (e.g. “checkout still works”).
- **Full E2E / regression audit** — only when the user explicitly says e.g. *test end-to-end full*, *regression all flows*, *audit the app*.

Before verifying, list AC items and state: *Scope: AC #N only — not full app.*

### Token-conscious verification

Prefer **automated tests** (text output) over screenshots. Use visual/browser/MobAI evidence **only for AC that need UI interaction** — minimal steps, one proof per AC when possible.

### Classify work

- **UI / UX** — layout, routing, forms, visible state.
- **Non-UI** — API, scripts, data, CI.
- **Mixed** — run tests first, then minimal UI flows for AC that need it.

### Web UI evidence

Screenshot alone is **not** verification. For each AC that needs UI:

1. Open app using `docs/how-to-run.md` (local URL + start command).
2. Run the **minimal flow** that proves that AC (click, type, submit, navigate).
3. Cover edge cases **named in AC** only (empty, error, flags).

**Web tools (priority):**

1. **Cursor IDE browser** (native MCP) — no extra install.
2. **Playwright CLI/MCP** — only if already on device/project; never auto-install.
3. **Existing project tests** — use if present.
4. If none available: nearest substitute + **state what was not verified**.

### Mobile UI evidence (Flutter, RN, native)

Do **not** use Playwright or Cursor browser for native mobile apps.

1. **Automated tests first** — `flutter test`, widget/integration tests per `docs/how-to-run.md`.
2. **MobAI** (optional, recommended for native UI flows) — [mobai.run](https://mobai.run); MCP: `npx mobai-mcp` with MobAI desktop + simulator/device. **Never auto-install**; user installs manually.
3. Use existing Puppeteer/Detox/Maestro only if already in the project.
4. If MobAI unavailable: report test evidence + **what UI was not verified**; board **Human Review** / **QA** for human device check.

### Non-UI evidence

- Run relevant tests (`cd media-engine && python3 -m unittest discover -s tests -p 'test_*.py'` or focused subset tied to changed files).
- Typecheck/lint when contracts change.
- API: real requests (curl/script) including error paths in AC.

### Loop gate (max 3 rounds)

Default: **3** rounds per task (set `VERIFY_MAX_ROUNDS` in `.workflow-kit.env` or bootstrap `--verify-max-rounds N`).

**Override for one task** — when the user says e.g. *max 2 rounds*, *5 putaran untuk #12*, use that number for **this issue only**; do not edit `.workflow-kit.env` unless they ask to change the project default.

**Change project default** — edit `VERIFY_MAX_ROUNDS` in `.workflow-kit.env`, or re-bootstrap with `--verify-max-rounds N`.

One round = implement/patch → verify → pass or fail.

- **Max rounds** = default or per-task override above.
- **Scope lock** — each round only fixes gaps vs AC; no scope creep.
- Stop early if: all AC met; **same failure twice**; blocker (login, env, server/emulator down); remaining gap is **taste** (spacing, tone) — human decides.
- Each round needs a new hypothesis, not random tweaks.
- After stop: report what was proven per AC, gaps vs AC, last evidence, what you need from the user.

## Merge & push (when user asks)

1. Merge to **`dev`** → **`git push origin dev`** first (CI).
2. Then **`main`** → **`git push origin main`**.

If **`dev`** is missing (`git branch -a`), use single branch **`main`** only.

Before merge/push: run `git branch -a`. Use `.workflow-kit.env` (`SINGLE_BRANCH`, `INTEGRATION_BRANCH`, `PRODUCTION_BRANCH`). Never invent branches.

## Orchestrator integration (optional)

Platform-agnostic pattern for external runtimes (e.g. Paperclip, custom workers):

1. Monitor GitHub Project **Status**.
2. Select issues in **Ready for AI** only — ignore Backlog/Todo, In Progress, labels, and `ai-ready` labels.
3. Assign one issue to a coding agent; agent reads `AGENTS.md` and repository instructions.
4. Agent sets **AI Working** → implements → self-verifies → **AI Review** → opens/updates PR.
5. Human reviews PR (**Human Review** / **QA**) → merges → *sudah work* → **Done** via Phase 3.

This workflow works **without** any orchestrator (interactive Cursor/Codex/Claude/Gemini sessions).

## Session start (optional)

If the user has not given a task, briefly list open issues with **Focus = This week** or status **Ready for AI** / **AI Working** on the board.

## Project constants

| Key | Value |
|-----|--------|
| Repo | `sahibul-nf/otonom-agents-media` |
| Project | `Otonom Media delivery` — (set after ./scripts/gh-setup-project.sh) |
| CI test | `cd media-engine && python3 -m unittest discover -s tests -p 'test_*.py'` |
| App stack | `web` (`web` · `mobile` · `both`) |
| Verify max rounds | `3` (override per task in chat) |
| Scripts | See `scripts/README.md` — triage, status, close, validate, UI check |

## Related

- `docs/github-workflow.md` — cheatsheet, board Status, daily flow
- `docs/orchestrator-integration.md` — optional Paperclip-style board polling
- `docs/agent-platforms.md` — per-platform official setup
- `docs/how-to-run.md` — dev URL, emulator, tests (replace all `TBD`)
- `docs/troubleshooting.md` — common script & verify issues
- `docs/updating-workflow-kit.md` — refresh when solo-dev-ai-kit repo updates
- `docs/uninstalling-workflow-kit.md` — remove kit files locally (not GitHub board)
- `docs/uninstall-prompt.md` — agent checklist for uninstall
- `docs/update-prompt.md` — agent checklist for kit update (`/update`)
- `docs/update-prompt.id.md` — same, Bahasa Indonesia
- `docs/close-comment.example.md` — template for Phase 3 close-out
- `scripts/README.md` — all `gh-*.sh` scripts, flags, examples
- `.workflow-kit.env` — repo config (generated by bootstrap)

<!-- workflow-kit:project-specific:start -->
## Issue triage & delivery (AI default)

When the user describes a **feature**, **bug**, or **improvement**, **automatically triage** unless they skip or name `#N`.

### Phase 1 — Triage (no coding)

1. Investigate codebase (read-only).
2. `gh issue list --repo sahibul-nf/otonom-agents-media --state open --search "…"`
3. If duplicate → link it; do not create another.
4. New issue via `./scripts/gh-triage-issue.sh`:
   - Title: `[Bug]:` / `[Feature]:`
   - Body: use `docs/issue-body.example.md` structure — must include `## Acceptance criteria` with `- [ ]` lines
   - Labels: `bug` / `enhancement`; `priority:high|medium|low`; `client-facing` if user-visible
5. Add to project board; reply with URL; **stop**.

End with: *"Review the issue; tell me which # to implement first."*

### Phase 2 — Implement

Triggers: *Implement #N*, *kerjakan #N*, *LGTM #N*.

- Follow acceptance criteria; open PR **into `dev`** with `Fixes #N`; commit only when asked (or when opening the PR). Orchestrators merge to **`dev`** only if the full suite is green. **Never target `main`.**
- Board: `./scripts/gh-set-issue-status.sh N ai-working` when starting; after green merge → `human-review`; if tests fail → `ai-review`.

### Phase 3 — Close-out

Triggers: user confirms *works* / *ok* / *sudah work* for **#N**.

1. Verify AC against code/commits.
2. `./scripts/gh-close-verified-issue.sh N --comment-file …` (closes issue + **Done** on board by default; use `--no-close` for comment-only).
3. Optional hygiene: `./scripts/gh-sync-project-status.sh` (closed issues still not **Done** on the board).

### Otonom constants (this repo)

| Key | Value |
|-----|--------|
| Board | https://github.com/users/sahibul-nf/projects/7 (`GH_PROJECT_NUM=7`) |
| North star | `.cursor/rules/platform-north-star.mdc` |
| PRs / unattended AI | `CONTRIBUTING.md` — PRs target **`dev`**; merge to `dev` after green full suite; never **`main`** or PM2 ops |
| Extra script | `scripts/gh-sync-project-status.sh` (bulk board sync; not in solo-dev-ai-kit) |
| Board hygiene | `scripts/gh-remove-qa-status.sh` — drop redundant **QA** column (use **Human Review** only) |

### Skip triage

- User names `#N` to implement.
- User says *skip issue* / *just fix* (trivial).
- Question-only messages.
<!-- workflow-kit:project-specific:end -->
