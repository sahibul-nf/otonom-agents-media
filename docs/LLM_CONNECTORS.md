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

## Local harness (BYO subscription, no API key)

Same model as [OpenMausBot](https://github.com/sahibul-nf/openmausbot) and [T3 Code](https://t3.codes): Otonom **does not** resell tokens or scrape ChatGPT/Gemini web UIs. You install the vendor CLI, log in on the machine (`codex login`, Cursor app, Antigravity/Google, `claude auth login`, etc.), then connect from the dashboard.

**Publish → LLM connectors**

1. **Connect** — registers a fixed allowlisted command per harness (`cursor_agent`, `antigravity`, …) in `OTONOM_LLM_CONNECTORS_JSON`. Each connect also **enables** that harness. Multiple rows can be **Active** at once.
2. **Pause** — disables a harness without forgetting its command (re-enable with **Enable**).
3. **Test** — JSON ping through every **Active** harness (per-harness pass/fail in vault).
4. **Runtime** — `llm_provider=agent` tries enabled harnesses in catalog order; first successful JSON response wins.
5. **Custom** — paste `OTONOM_LLM_AGENT_COMMAND` under *API keys / custom CLI* (no shell metacharacters).

Connector state (`GET /api/llm-status`): `undetected` → `detected` → `configured` → `ready` (after test), `error` (last test failed), or `stale` (active connector id no longer matches the stored command — use **Reconnect**).

Connect, Test, and Save LLM settings responses include `llm_status` so the dashboard can refresh without a race. Agent pills on `/api/credentials` use the same `state` field (`configured` vs `ready`) as the connector list.

```bash
curl -s "http://127.0.0.1:8765/api/llm-status?profile_id=workspace" | jq .
curl -s -X POST http://127.0.0.1:8765/api/llm-connector-connect \
  -H 'Content-Type: application/json' \
  -d '{"profile_id":"workspace","connector_id":"cursor_agent"}'
curl -s -X POST http://127.0.0.1:8765/api/llm-connector-test \
  -H 'Content-Type: application/json' \
  -d '{"profile_id":"workspace"}'
```

Vault keys: `OTONOM_LLM_AGENT_COMMAND`, `OTONOM_LLM_AGENT_CONNECTOR`, `OTONOM_LLM_AGENT_TEST_OK`, `OTONOM_LLM_AGENT_LAST_ERROR`.

## Agent CLI (`llm_provider=agent`)

The command receives a JSON payload on stdin (`system`, `user`, `response_format`) and must print **raw JSON** on stdout.

Manual env (optional):

```bash
export OTONOM_LLM_AGENT_COMMAND='cursor agent --print --output-format json --trust'
```

### Cursor: "Workspace Trust Required"

When the review engine runs `cursor agent` non-interactively, Cursor refuses to run until the workspace is trusted. The bundled connector adds **`--trust`** (same as `-f` / `--yolo` in the CLI hint). Alternatively, run `cursor agent` once interactively in the repo root and approve the prompt.

Re-**Connect** Cursor in the dashboard if you connected before this flag was added (vault may still hold the old command without `--trust`).

### Antigravity (`agy`)

Binary name is usually **`agy`** (add `~/.local/bin` to `PATH` if Connect says "not found"). Connect stores `agy -p --output-format json --dangerously-skip-permissions` so tool approvals do not block headless Test/Create.

If the command is missing, package creation falls back to `none` (stub) and records the error in package QA.

## MCP / API

`create_content_package` accepts `llm_provider`: `none` | `openai` | `deepseek` | `groq` | `agent`.

Same providers as clip generation on the Create tab.
