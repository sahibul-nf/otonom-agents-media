# Otonom Media

**The system for a one-person media company.**

Open-source brand brain plus factory: turn a source into publish-ready social content in your voice — text, stills, carousels, shorts, long-form, and clips. A human approves. A connector publishes.

```text
source → generate package → Review → schedule → Postiz (or legacy connectors)
         ↑ brand pack          ↑ you            ↑ OAuth stays off-repo
         ↑ MCP for agents
```

[MIT](LICENSE) · [Docs index](docs/README.md) · [Brand](docs/BRAND.md) · [Formats](docs/FORMATS.md) · [Secrets](docs/SECRETS.md)

## Who it is for

Solo media operators and the agents that help them (Cursor, Antigravity, OpenMausBot). HeyGen and NotebookLM stay **upstream tools** — optional sources or engines, not the product.

Maintainer case studies (TechTalk Intel, Nourbit, personal brand) are documented in [content-os](https://github.com/sahibul-nf/content-os). This repo ships **brand presets** in `brand-pack/` so you do not rebuild that editorial system from scratch.

## Start here

| Goal | Doc / entry |
|------|-------------|
| Run locally | [docs/how-to-run.md](docs/how-to-run.md) (this README quick start) |
| Text / still / carousel | [docs/text-image-posts.md](docs/text-image-posts.md) — Generate → Content package |
| Long-form (Path A / HeyGen) | [docs/heygen-paths.md](docs/heygen-paths.md) — Explainer → Generate video / Generate next |
| Autopick topic | [docs/topic-engine.md](docs/topic-engine.md) |
| Explainer (local fixtures) | [docs/explainer-mode.md](docs/explainer-mode.md) |
| Brand look from a prompt | Brand Builder → “Describe a look” ([architecture](docs/explainer-saas-architecture.md)) |
| Mac Mini / PM2 ops | [docs/local-ops.md](docs/local-ops.md) on branch **`main`** |
| Full docs map | [docs/README.md](docs/README.md) |

**North star:** automate glue work; keep human approve before publish. Do not rebuild HeyGen Video Agent in FFmpeg.

## Layout

| Path | Role |
|------|------|
| `media-engine/` | Python factory: packages, review API, clip/explainer render, Postiz publisher |
| `apps/dashboard/` | Review and operations UI |
| `brand-pack/` | Starter brand brains (`techtalk`, `personal`, `blank`) |
| `techtalk-autonomous/` | Legacy text automation |
| `docs/` | Product and ops — [index](docs/README.md) |

## Quick start

Requires **Node 20+** and **Python 3.11+**.

```bash
git clone https://github.com/sahibul-nf/otonom-agents-media.git
cd otonom-agents-media
git checkout dev          # integration branch for contributors
cp .env.example .env.local   # never commit real keys

python3 -m venv media-engine/.venv
source media-engine/.venv/bin/activate
pip install -r media-engine/requirements-dev.txt

npm install && cd apps/dashboard && npm install && cd ../..
npm run dev
```

- Dashboard: [http://127.0.0.1:3100](http://127.0.0.1:3100)
- Engine API: `http://127.0.0.1:8765` (`MEDIA_ENGINE_API_BASE`)
- Health: `npm run health`

Coding next to a live PM2 checkout? Use `npm run dev:isolated` → API `:8766`, dashboard `:3101` (see [how-to-run](docs/how-to-run.md)).

Optional full brain from a local [content-os](https://github.com/sahibul-nf/content-os) checkout:

```bash
export CONTENT_OS_PATH=/path/to/content-os
```

## MCP (agents)

```bash
cd media-engine && source .venv/bin/activate
PYTHONPATH=. python3 -m media_engine.otonom_mcp
```

Example config: [docs/otonom-mcp.cursor.example.json](docs/otonom-mcp.cursor.example.json). Tools include content packages, topic propose/generate-next, explainer ingest, and review queue.

## Tests

```bash
source media-engine/.venv/bin/activate
cd media-engine && PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py'
```

## PM2 (Mac Mini ops)

Ops checkout on **`main`** only — see [docs/local-ops.md](docs/local-ops.md). Ecosystem: `scripts/media-engine-pm2.config.cjs`.

| App | Role |
|-----|------|
| `otonom-media-api` | media-engine `:8765` |
| `otonom-media-dashboard` | Next `:3100` |
| `otonom-media-health` | health monitor |
| `otonom-media-publisher` | `publish-due` loop |
| `otonom-media-watch` | channel `watch-poll` (~daily) |

## Related experiments (not merged)

- [social-media-content-ai-generation](https://github.com/sahibul-nf/social-media-content-ai-generation) — multi-format UI prototype
- [chat-to-content](https://github.com/sahibul-nf/chat-to-content) — chat → post prototype

Patterns from those repos inform packages here; code stays in this factory.

## Contributing

PRs target **`dev`**. Never push **`main`** from agents. See [CONTRIBUTING.md](CONTRIBUTING.md), [AGENTS.md](AGENTS.md), and [docs/how-to-run.md](docs/how-to-run.md).

`package.json` `"private": true` only blocks npm publish — this GitHub repo is public under [MIT](LICENSE).
