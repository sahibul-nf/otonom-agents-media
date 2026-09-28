# Workflow scripts

Shell helpers for GitHub Issues + Project board. All scripts load `.workflow-kit.env` from the repo root.

**Full workflow:** `AGENTS.md` · **Daily flow:** `docs/github-workflow.md` · **Orchestrators:** `docs/orchestrator-integration.md` · **Problems:** `docs/troubleshooting.md`

## Quick reference

| Script | When to use |
|--------|-------------|
| `gh-triage-issue.sh` | Create issue + add to board (Phase 1 triage) |
| `gh-validate-issue-body.sh` | Check body has `## Acceptance criteria` + `- [ ]` (called by triage) |
| `gh-set-issue-status.sh` | Set Project **Status** (authorization gate — not labels) |
| `gh-close-verified-issue.sh` | After human QA: check AC, comment, close issue, set **Done** |
| `gh-check-ui-tools.sh` | Report web/mobile verify tools (check only — never installs) |
| `merge-agents-md.py` | Bootstrap: refresh kit sections in `AGENTS.md`; keep project-specific blocks |
| `kit-managed.py` | Bootstrap: stamp `solo-dev-ai-kit:managed` markers; write `.workflow-kit/manifest` |
| `verify-kit-managed.sh` | Audit manifest paths — report missing markers before uninstall |
| `extract-agents-project-specific.py` | Uninstall: save custom `AGENTS.md` blocks → `docs/project-guidelines.md` |
| `gh-ensure-project-status.sh` | Add Ready for AI / AI Working / AI Review / Human Review columns |
| `gh-setup-all.sh` | One-shot: labels + project board + status columns |
| `gh-setup-project.sh` | Create/link project; writes `GH_PROJECT_NUM` to `.workflow-kit.env` |
| `gh-configure-project.sh` | Board title, Priority/Focus fields, sync from labels |
| `gh-create-labels.sh` | Standard labels (`bug`, `enhancement`, `priority:*`, `complexity:*`, `ai-blocked`) |
| `gh-ensure-project-status-qa.sh` | Legacy wrapper → `gh-ensure-project-status.sh` |

## Examples

```bash
# Triage → Backlog only (never Ready for AI)
./scripts/gh-triage-issue.sh \
  --title "[Bug]: Login redirect loop" \
  --body-file /tmp/issue-body.md \
  --labels "bug,priority:high,complexity:medium"

# Board status
./scripts/gh-set-issue-status.sh 12 ready-for-ai   # human authorization
./scripts/gh-set-issue-status.sh 12 ai-working     # implement
./scripts/gh-set-issue-status.sh 12 ai-review      # after verify
./scripts/gh-set-issue-status.sh 12 human-review   # human PR review

# Legacy keys (still supported)
./scripts/gh-set-issue-status.sh 12 progress
./scripts/gh-set-issue-status.sh 12 qa

# Close after user says "sudah work #12"
./scripts/gh-close-verified-issue.sh 12 --comment-file /tmp/close-12.md

# Ensure board columns
./scripts/gh-ensure-project-status.sh
```

## Flags & behavior

### `gh-close-verified-issue.sh`

| Flag | Effect |
|------|--------|
| `--comment-file PATH` | Closing comment from file (use `docs/close-comment.example.md` as template) |
| `--comment "text"` | Closing comment inline |
| `--no-check-ac` | Skip checking AC boxes in issue body |
| `--no-close` | Comment only — do not close issue or set board Done |

**Exit:** `0` on success; `1` on missing args or `gh` failure.

### `gh-set-issue-status.sh`

| Key | Preferred column | Fallback |
|-----|------------------|----------|
| `backlog` | Backlog | Todo |
| `ready-for-ai` | Ready for AI | *(none — run ensure script)* |
| `progress`, `ai-working` | AI Working | In Progress |
| `ai-review` | AI Review | QA |
| `qa`, `human-review` | Human Review | QA |
| `done` | Done | Done |

**Project Status authorizes orchestrators — not labels.** An `ai-ready` label does not trigger execution.

If `GH_PROJECT_NUM` is unset: prints a note and **exits 0** (no-op).

### `gh-triage-issue.sh`

Runs `gh-validate-issue-body.sh` before create. Duplicate open issues with the same title return existing URL and exit `0`.

## Prerequisites

```bash
brew install gh jq
gh auth login
gh auth refresh -h github.com -s repo,project,read:project
```

See `docs/troubleshooting.md` if something fails.
