# Otonom Agents Media

Workspace for autonomous media systems across multiple niches.

## Projects

- `media-engine/` — shared local-first multimedia engine, currently focused on Nourbit video clipping, review, render contracts, and multi-platform dry-run publishing.
- `apps/dashboard/` — Next.js SaaS dashboard for media operations, connected to the local `media-engine` review API.
- `techtalk-autonomous/` — existing standalone TechTalk Intel automation.

## Dashboard

Start the local media API first:

```bash
cd media-engine
PYTHONPATH=. python3 -m media_engine.review_server
```

Then start the SaaS dashboard:

```bash
cd apps/dashboard
npm install
npm run dev
```

Open `http://127.0.0.1:3000`. The dashboard proxies local engine calls through `MEDIA_ENGINE_API_BASE`, defaulting to `http://127.0.0.1:8765`.

The dashboard now supports the daily Nourbit production loop:

- Generate a production batch from a YouTube URL, clip count, length preset, renderer, caption source, LLM provider, and brand template.
- Track background generation progress without blocking the browser.
- Review and approve rendered clips.
- Schedule approved clips into the next queue-only Nourbit slot. The V1 cadence is 2 posts per day at 09:00 and 19:30 WIB.
- Publish remains explicit/manual by default; scheduled clips become ready queue items, not automatic live posts.

## Security First

Live credentials are local-only. Start from:

- `.env.example`
- `techtalk-autonomous/config/fb_pages.example.json`
- `docs/SECRETS.md`

Before committing:

```bash
python3 scripts/secret_scan.py
git status --ignored --short
```

Git hooks are configured with:

```bash
git config core.hooksPath .githooks
```

## Tests

```bash
PYTHONPATH=media-engine python3 -m unittest discover -s media-engine/tests -v
```
