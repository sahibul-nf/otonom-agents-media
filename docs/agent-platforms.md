# AI agent platforms — official setup

This project uses **one canonical file** (`AGENTS.md`) plus **platform-native** config files where each tool expects them. Stubs do not duplicate rules — they point to `AGENTS.md`.

**Installed for this repo:** Cursor, Antigravity

## Summary

| Platform | Official file(s) | What bootstrap installs |
|----------|------------------|-------------------------|
| **Codex** | `AGENTS.md` | Nothing extra — Codex reads `AGENTS.md` natively |
| **Cursor** | `AGENTS.md`, `.cursor/rules/*.mdc` | `AGENTS.md` + `github-issue-workflow.mdc` (`alwaysApply: true`) |
| **Antigravity** | `.agents/rules/*.md` | `issue-workflow.md` (`trigger: always_on`) |
| **Claude Code** | `CLAUDE.md` or `.claude/CLAUDE.md` | Minimal `CLAUDE.md` → `AGENTS.md` |
| **Gemini CLI** | `GEMINI.md`, `AGENTS.md` | `.gemini/settings.json` + optional `GEMINI.md` stub |

## Official documentation

| Platform | Docs |
|----------|------|
| **AGENTS.md** (cross-tool) | [agents.md](https://agents.md/) |
| **Cursor** | [cursor.com/docs/context/rules](https://cursor.com/docs/context/rules) — `AGENTS.md` and `.cursor/rules` |
| **Antigravity** | `.agents/rules/` with YAML frontmatter (`trigger: always_on`) |
| **OpenAI Codex** | Reads `AGENTS.md` from project root ([Codex AGENTS.md](https://github.com/openai/codex)) |
| **Claude Code** | [code.claude.com/docs/en/memory](https://code.claude.com/docs/en/memory) — `CLAUDE.md` |
| **Gemini CLI** | [gemini-cli GEMINI.md](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md) — also discovers `AGENTS.md` |

## Add or remove a platform later

Re-run bootstrap from `solo-dev-ai-kit`:

```bash
/path/to/solo-dev-ai-kit/bootstrap.sh --target . --repo sahibul-nf/otonom-agents-media --tools cursor,antigravity,claude
```

`AGENTS.md` is always refreshed. Platform files are added/updated per `--tools`.

## Why both `AGENTS.md` and `.cursor/rules`?

- **`AGENTS.md`** — canonical content; read by Codex, Cursor, and Gemini CLI.
- **`.cursor/rules/*.mdc`** — Cursor-native `alwaysApply` rules for triage (recommended when triage must run every session without `@AGENTS.md`).

Same content strategy for Antigravity: `.agents/rules/` with `trigger: always_on`.
