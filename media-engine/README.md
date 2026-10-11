# media-engine

Python factory for Otonom Media: content packages, clip/Explainer render, review API, Postiz publish, MCP tools.

Product overview and dashboard quick start live in the [root README](../README.md). Docs map: [docs/README.md](../docs/README.md).

## Setup

```bash
cd media-engine
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt   # includes explainer/Pillow deps
```

Optional Explainer-only install: `pip install -r requirements-explainer.txt`.

Copy repo-root `.env.example` → `.env.local` (never commit). Secrets layout: [docs/SECRETS.md](../docs/SECRETS.md).

## Run API (review server)

Prefer repo-root `npm run dev` (dashboard `:3100` + engine `:8765`). Engine alone:

```bash
cd media-engine
PYTHONPATH=. python3 -m media_engine.review_server
```

Legacy HTML shell (if needed): `http://127.0.0.1:8765/review.html` — day-to-day UI is the Next dashboard.

## Tests

```bash
cd media-engine
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py'
```

## CLI (common)

```bash
cd media-engine
PYTHONPATH=. python3 -m media_engine.cli init

# Content packages — see docs/FORMATS.md and docs/text-image-posts.md
# Prefer dashboard Generate → Content package, or MCP create_content_package

# Explainer (fixtures → stitch → Review) — docs/explainer-mode.md
python3 -m media_engine.cli explainer-create --topic "Apa itu Bitcoin?"
python3 -m media_engine.cli explainer-run --job-id <job_id> --ffmpeg-only
# Optional Direct API avatars: docs/heygen-paths.md
# python3 -m media_engine.cli explainer-run --job-id <job_id> --heygen-avatars --ffmpeg-only

# Long-form ingest (Path A delivery)
# python3 -m media_engine.cli …  (or MCP ingest_longform / dashboard Explainer)

# Shorts from YouTube (premium / watch pipeline)
python3 -m media_engine.cli premium-curate --youtube-url "https://www.youtube.com/watch?v=…" --count 5 --llm-provider none
python3 -m media_engine.cli premium-batch --youtube-url "https://www.youtube.com/watch?v=…" --count 5 --renderer ffmpeg --llm-provider none

python3 -m media_engine.cli approve --candidate-id <clip_id>
python3 -m media_engine.cli publish-due --profile all
```

Profiles such as `nourbit` / TechTalk styles under `profiles/` are **examples**; use Brand Builder customs (`brand:custom_*`) for your brand.

## MCP

```bash
cd media-engine
PYTHONPATH=. python3 -m media_engine.otonom_mcp
```

Cursor example: [docs/otonom-mcp.cursor.example.json](../docs/otonom-mcp.cursor.example.json).

## LLM providers

Vault / Connect in the dashboard is preferred. For CLI, `--llm-provider none|auto|openai|deepseek|groq|agent` and keys via `.env.local` or workspace vault. See [docs/LLM_CONNECTORS.md](../docs/LLM_CONNECTORS.md).

## Render stacks

| Stack | Role |
|-------|------|
| **HyperFrames + FFmpeg** | Default short-form / Brand Studio / captions |
| **Explainer stitch** | Long-form hybrid from fixtures / avatar clips |
| **Remotion** (`render/remotion`) | Optional; install only when experimenting |

HyperFrames skills: [docs/hyperframes-skills.md](../docs/hyperframes-skills.md). Ops / PM2: [docs/local-ops.md](../docs/local-ops.md).

## Data on disk (gitignored)

`data/` (SQLite + vault), `artifacts/` — never commit. Local-first; each checkout owns its DB unless you set `MEDIA_ENGINE_DB`.
