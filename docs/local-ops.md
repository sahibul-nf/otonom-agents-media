# Local ops on Mac Mini (PM2 + worktree)

Otonom generate/render stays **native on macOS**. Postiz (OAuth + delivery) stays **Docker or `postiz.nourdaily.com`**. Do not put Whisper/HyperFrames in the Postiz container.

## Topology

```text
Postiz API  https://api-postiz.nourdaily.com  (OAuth + send)
Otonom ops (PM2 on this Mini)
  :8765  media-engine API
  :3100  dashboard (next start)
  publisher worker  publish-due every 60s → Postiz Public API
  watch worker      watch-poll ~daily (no --force; channel interval gates)

Dev (optional git worktree)
  :8766 / :3101  own SQLite + artifacts
```

## First-time ops

From the **ops checkout** on **`main`** (`otonom-agents-media-ops`). Do not run PM2 from the Cursor **`dev`** folder.

Agent PRs land on **`dev`** first (`CONTRIBUTING.md`). Pull `main` on this clone only after you merge `main` ← `dev`.

```bash
cd apps/dashboard && npm install && npm run build
cd ../..
npm run pm2:start
pm2 save
pm2 startup
```

UI: `http://127.0.0.1:3100`. Engine: `http://127.0.0.1:8765`.

## Postiz delivery

Connect in the dashboard **Publish** tab (per workspace). Default API host: [https://api-postiz.nourdaily.com/](https://api-postiz.nourdaily.com/) (normalized to `/public/v1`). The API key is stored in the workspace credential vault — not `.env`.

Then map each destination to a Postiz integration. Unmapped platforms still use native tokens (legacy).

TikTok posts as `SELF_ONLY` until you change `settings_for_platform` — first ship is conservative.

## Develop without stopping ops

Do **not** run `npm run dev` in the ops checkout. `scripts/dev.sh` refuses to bind `:8765` / `:3100` when those ports are already listening (PM2 or a leftover process). Override only on purpose: `ALLOW_STEAL_OPS_PORTS=1 npm run dev`.

```bash
git worktree add ../otonom-agents-media-dev
cd ../otonom-agents-media-dev
npm run dev:isolated
```

That starts engine `:8766`, dashboard `:3101`, DB `media-engine/data/media_engine.dev.sqlite`, artifacts in `media-engine/artifacts-dev`.

Promote: merge to ops `main`, `cd` ops checkout, `npm run pm2:restart` (includes publisher + watch). Rebuild dashboard if UI changed: `(cd apps/dashboard && npm run build) && pm2 restart otonom-media-dashboard`.

## Watch poll worker (`otonom-media-watch`)

Background channel watch is a first-class PM2 app (`scripts/media-engine-pm2.config.cjs` → `run_watch_poll_worker_pm2.sh`).

| Knob | Default | Meaning |
|------|---------|---------|
| `WATCH_POLL_INTERVAL_SECONDS` | `86400` (24h) | Sleep between worker loop iterations |
| `WATCH_POLL_PROFILE` | empty (all workspaces) | Optional single `profile_id` |
| Per-channel `poll_interval_minutes` | **1440** for new channels | Gate inside `watch-poll` (worker does **not** pass `--force`) |

UI **Poll now** still calls `/api/watch-poll` with `force: true` for an immediate check.

**Existing DB rows:** on `initialize()`, rows still at the old default **30** minutes are one-shot migrated to **1440**. If you intentionally want sub-daily polling, edit the channel after upgrade (min 5, max 1440).

Ad-hoc (no PM2): `bash scripts/run_watch_poll_worker.sh`.

## Ports vs Postiz

Otonom dashboard is **3100** so it does not collide with Postiz (`3000` / `4200`).
