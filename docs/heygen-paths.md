# HeyGen Path A & Path B

How Otonom Media uses HeyGen without rebuilding Video Agent locally.

**North star:** closed loop generate/import → Review → schedule → publish (replace OpusClip glue work).

---

## Path A (default near-term) — Creator credits

```text
[Tombol Otonom: Generate via Cursor]
  → POST Automation webhook  and/or  Cloud Agents API create (no-repo)
  → Otonom poll Cursor run until FINISHED
  → parse VIDEO_URL from agent final reply
  → local ingest_longform (review_only)
  → Telegram status: “ready for Review”
  → operator Approve → Schedule / publish
```

No public URL / tunnel required: **Otonom pulls** Cursor results; Cloud Agent never calls localhost.

| Piece | Pays from |
|-------|-----------|
| Video Agent generate | **Creator** premium credits (~20/min on web/MCP) |
| Cursor Automation / Cloud Agent | Cursor Pro included usage (then on-demand) |
| Otonom Review/publish | Local / your VPS |

### Env (`.env.local`)

| Variable | Purpose |
|----------|---------|
| `CURSOR_API_KEY` | Cloud Agents API — **required to poll** run status (also Bearer for webhook if token unset) |
| `CURSOR_AUTOMATION_WEBHOOK_URL` | Preferred trigger: Automation with HeyGen MCP already attached |
| `CURSOR_AUTOMATION_WEBHOOK_TOKEN` | Bearer for webhook (`crsr_…`); falls back to `CURSOR_API_KEY` |
| `CURSOR_API_BASE` | Default `https://api.cursor.com` |
| `CURSOR_PATH_A_TIMEOUT_SECONDS` | Poll timeout (default `1800`) |
| `CURSOR_PATH_A_POLL_INTERVAL_SECONDS` | Poll interval (default `15`) |
| `CURSOR_API_DRY_RUN=1` | Local test without calling Cursor |
| `CURSOR_DRY_RUN_VIDEO_URL` | Fake `VIDEO_URL` for dry-run |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_STATUS_CHAT_ID` (or `TELEGRAM_CHAT_ID`) | Status ping when ready / failed |
| `HEYGEN_VOICE_ID` / `HEYGEN_AVATAR_LOOK_ID` | Defaults baked into generate prompt |

### Dashboard

Explainer → **Generate via Cursor (Path A)** → topic / optional title + script → button.

API:

- `POST /api/path-a-generate` `{topic, title?, script?}` → `202` job
- `GET /api/path-a-jobs` / `GET /api/path-a-status?job_id=`

### Cursor Automation setup

1. Enable **on-demand** usage so Automations can start.
2. Create Automation: trigger **Webhook**, repo **No repository**, tools **HeyGen MCP**.
3. Paste prompt (webhook JSON/`text` is appended automatically):

```text
Generate one landscape TechTalk edu-finance Video Agent video with HeyGen MCP:
- avatar look_id (avatarId): 3ad1d28c72c14ac7940be96b896cac60
- voice_id: 0e0c18c072cf4ab6b617dd981f271670
- mode=generate, orientation=landscape
Use topic/script from the webhook payload (or OTONOM prompt text).

When status=completed and video_url is set, your FINAL reply MUST include:
VIDEO_URL: https://...
TITLE: ...

Do NOT call Otonom ingest and do NOT approve/publish.
```

4. Copy webhook URL + auth token into `.env.local`.
5. Also set `CURSOR_API_KEY` so Otonom can **poll** (`GET /v1/agents/{id}/runs/{runId}`). The webhook response must include agent/run ids (or agent id + `latestRunId` via API). If the webhook body has no ids, unset the webhook URL and use **API-only** create (`CURSOR_API_KEY` with no-repo agent) — then ensure HeyGen MCP is available to that Cloud Agent.

### Manual ingest (fallback)

Paste `video_url` into Explainer → Ingest, or MCP `ingest_longform`.

### `clip_batch` mode

Whisper ASR + short window curation + ffmpeg cuts into Review as 9:16-ready candidates (basic cuts; re-render with HyperFrames later if needed). Requires `faster-whisper` in the media-engine env. Not auto-run after Path A generate.

**Make shorts (Review):** On an approved landscape long-form item, use **Make shorts** in Review — no URL paste. If the clip was published to YouTube, Otonom queues the full Create pipeline (`generation_jobs`) against that URL; otherwise it runs local `clip_batch` cuts from the on-disk source. Path A ingest still defaults to `review_only`; pass `mode=clip_batch` on `ingest_longform` / `POST /api/ingest-longform` when you want shorts at ingest time.

---

## Path B (future) — Direct API / USD wallet

Scaffold: `media-engine/media_engine/heygen_client.py`

| Env | Purpose |
|-----|---------|
| `HEYGEN_API_KEY` | Direct API (`X-Api-Key`) |
| `HEYGEN_API_DRY_RUN=1` | No network; returns dry-run payload |
| `HEYGEN_VOICE_ID` | Default Sahibul voice |
| `HEYGEN_AVATAR_LOOK_ID` | Default look (not group id) |

MCP tools (Path B only): `heygen_video_agent_create`, `heygen_video_agent_status`.

**Creator avatar/voice IDs still work** on the API. **Creator premium credits do not pay for API calls** — top up the API wallet (from ~$5). Video Agent API ≈ **$0.0333/sec (~$2/min)**.

Default product path stays Path A until Creator is exhausted or multi-tenant BYOK is required.

Related: issue #7 (avatar clip Direct API), #19 (Path A ingest), #20 (Path B scaffold), #21 (manual Cursor trigger + poll + Telegram).

---

## Cost reminder

| Volume | Prefer |
|--------|--------|
| ≤ ~25–30 min VA / month | Path A + Creator $29 |
| More / no Cursor in the loop | Path B API wallet |
| Keep Creator + also API | Usually wasteful — pick one generate path |
