# Otonom Media

**The system for a one-person media company.**

Open-source brand brain plus factory: turn a source into publish-ready social content in your voice — text, stills, carousels, shorts, long-form, and clips. A human approves. A connector publishes.

```text
source → generate package → Review → schedule → Postiz (or legacy connectors)
         ↑ brand pack          ↑ you            ↑ OAuth stays off-repo
         ↑ MCP for agents
```

[MIT](LICENSE) · [Brand](docs/BRAND.md) · [Formats](docs/FORMATS.md) · [Secrets](docs/SECRETS.md)

## Who it is for

Solo media operators and the agents that help them (Cursor, Antigravity, OpenMausBot). HeyGen and NotebookLM stay **upstream tools** — optional sources or engines, not the product.

Maintainer case studies (TechTalk Intel, Nourbit, personal brand) are documented in [content-os](https://github.com/sahibul-nf/content-os). This repo ships **brand presets** in `brand-pack/` so you do not rebuild that editorial system from scratch.

## Layout

| Path | Role |
|------|------|
| `media-engine/` | Python factory: packages, review API, clip/explainer render, Postiz publisher |
| `apps/dashboard/` | Review and operations UI |
| `brand-pack/` | Starter brand brains (`techtalk`, `personal`, `blank`) |
| `techtalk-autonomous/` | Legacy text automation |
| `docs/` | Product and ops |

## Quick start

```bash
git clone https://github.com/sahibul-nf/otonom-agents-media.git
cd otonom-agents-media
cp .env.example .env.local   # never commit real keys
npm install && cd apps/dashboard && npm install && cd ../..
npm run dev
```

- Dashboard: [http://127.0.0.1:3100](http://127.0.0.1:3100)
- Engine API: `http://127.0.0.1:8765` (`MEDIA_ENGINE_API_BASE`)
- Health: `npm run health`

Optional full brain from a local [content-os](https://github.com/sahibul-nf/content-os) checkout:

```bash
export CONTENT_OS_PATH=/path/to/content-os
```

## MCP (agents)

```bash
cd media-engine && PYTHONPATH=. python3 -m media_engine.otonom_mcp
```

Example config: [docs/otonom-mcp.cursor.example.json](docs/otonom-mcp.cursor.example.json). Tools include `create_content_package`, `get_content_package`, explainer ingest, and review queue.

## Tests

```bash
pip install -r media-engine/requirements-dev.txt
cd media-engine && PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py'
```

## Related experiments (not merged)

- [social-media-content-ai-generation](https://github.com/sahibul-nf/social-media-content-ai-generation) — multi-format UI prototype
- [chat-to-content](https://github.com/sahibul-nf/chat-to-content) — chat → post prototype

Patterns from those repos inform packages here; code stays in this factory.

## Contributing

PRs target `dev`. See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/how-to-run.md](docs/how-to-run.md).

`package.json` `"private": true` only blocks npm publish, not GitHub visibility.
