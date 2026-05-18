# Otonom Agents Media

Workspace for autonomous media systems across multiple niches.

## Projects

- `media-engine/` — shared local-first multimedia engine, currently focused on Nourbit video clipping, review, render contracts, scheduled publishing, and multi-platform publish adapters.
- `apps/dashboard/` — Next.js SaaS dashboard for media operations, connected to the local `media-engine` review API.
- `techtalk-autonomous/` — existing standalone TechTalk Intel automation.

## Dashboard

Start both local services together from the workspace root:

```bash
npm run dev
```

Check system health/status:

```bash
npm run health
```

This prints a JSON summary for:

- backend port + review API
- frontend port + HTTP response
- configured publish credentials detected by the local media engine

If you still want to run them separately:

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

## PM2 Auto-Restart

For Mac Mini uptime, you can run the stack under PM2 so it comes back after reboot or power loss:

```bash
cd "/Volumes/XPG SSD 1T/projects/otonom-agents-media"
npm run pm2:start
pm2 save
pm2 startup
```

This ecosystem starts:

- `otonom-media-api`
- `otonom-media-dashboard`
- `otonom-media-health`
- `otonom-media-publisher`

Useful commands:

```bash
npm run pm2:status
npm run pm2:logs
npm run health
```

The health monitor checks backend/frontend every 60 seconds and sends Telegram alerts on:

- monitor online / boot
- unhealthy / degraded state
- recovery back to healthy

Telegram notification target resolution:

1. `TELEGRAM_STATUS_CHAT_ID`
2. `TELEGRAM_CHAT_ID`
3. `TELEGRAM_CHANNEL_ID`

Optional thread fallback:

1. `TELEGRAM_STATUS_THREAD_ID`
2. `TELEGRAM_THREAD_ID`

PM2 uses `.env.local` automatically through the wrapper scripts in `scripts/`.

The dashboard now supports the daily Nourbit production loop:

- Generate a production batch from a YouTube URL, clip count, length preset, renderer, caption source, LLM provider, and brand template.
- Track background generation progress without blocking the browser.
- Review and approve rendered clips.
- Schedule approved clips into the next Nourbit publish slot. The V1 cadence is 2 posts per day at 09:00 and 19:30 WIB.
- Publish due clips automatically through the PM2 publisher worker, with Telegram, YouTube Shorts, Facebook Reels, and TikTok attempts recorded per platform.

Clip length uses canonical strategy presets rather than raw second ranges:

- `quick_hit` — fast 20-60s clips for news, sports, quotes, and visual moments.
- `standard_short` — balanced 35-90s clips for tech updates and explainers.
- `deep_context` — Nourbit default, 45-120s clips for kajian, podcasts, and reflective content.
- `platform_max` — 90-180s clips for deeper shorts when the topic can sustain retention.

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
