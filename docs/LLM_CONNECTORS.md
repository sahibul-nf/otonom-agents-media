# LLM connectors (OpenMausBot-style)

Otonom can generate content packages with:

1. **API keys** — paste into the dashboard (stored in the workspace vault, like publish credentials) or set in `.env.local`.
2. **Local agent CLI** — subprocess that returns JSON on stdout (Cursor Agent, Codex, custom wrapper).

## API providers

| Provider | Vault / env key | Default model env |
|----------|-----------------|-------------------|
| `openai` | `OPENAI_API_KEY` | `OPENAI_MODEL` |
| `deepseek` | `DEEPSEEK_API_KEY` | `DEEPSEEK_MODEL` |
| `groq` | `GROQ_API_KEY` | `GROQ_MODEL` |

Dashboard: **Channels → LLM keys** (or `POST /api/llm-credentials`).

```bash
curl -s -X POST http://127.0.0.1:8765/api/llm-credentials \
  -H 'Content-Type: application/json' \
  -d '{"profile_id":"workspace","values":{"DEEPSEEK_API_KEY":"sk-…"}}'
```

Keys never belong in git. See [docs/SECRETS.md](SECRETS.md).

## Agent CLI (`llm_provider=agent`)

Set a command template that receives the user prompt on stdin and must print **raw JSON** on stdout:

```bash
export OTONOM_LLM_AGENT_COMMAND='cursor agent --print --output-format json'
# or a thin wrapper script that calls your local CLI
```

Optional per-workspace override in vault: `OTONOM_LLM_AGENT_COMMAND`.

If the command is missing, package creation falls back to `none` (stub) and records the error in package QA.

## MCP / API

`create_content_package` accepts `llm_provider`: `none` | `openai` | `deepseek` | `groq` | `agent`.

Same providers as clip generation on the Create tab.
