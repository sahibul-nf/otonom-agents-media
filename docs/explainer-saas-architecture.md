# Explainer Mode & SaaS Render Architecture

**Status:** Design note (pre-implementation)  
**Related issue:** [#4 — Explainer Mode](https://github.com/sahibul-nf/otonom-agents-media/issues/4)  
**Last updated:** 2026-07-21

---

## Summary

Otonom Media becomes a **light orchestrator SaaS**: workflow + templates + review + multi-platform publish. It does **not** rebuild HeyGen or GPU avatar models. Heavy avatar generation stays on HeyGen (user BYOK). Local render stays on **HyperFrames + FFmpeg** (CPU, flat cost).

Target volume (personal / early SaaS): **≤ 4 long-form videos/month** per operator, each 5–10 minutes, then auto-clip to shorts via the existing pipeline.

---

## Content flywheel

```text
Topic + sources
  → Scene planner (LLM): script + scene breakdown
  → HeyGen: short avatar clips only (5–15 s each, ~60–120 s total per long-form)
  → HyperFrames (local/VPS): text, diagram, kinetic caption, b-roll scenes
  → FFmpeg stitch: one MP4 (5–10 min, 16:9)
  → Review queue (human approve)
  → Schedule + publish (YouTube, TikTok, Telegram, …)
  → Ingest own long-form URL → curate → short-form clips → publish
```

### Hybrid scene pattern (reference: [LOHYl1egXKU](https://www.youtube.com/watch?v=LOHYl1egXKU))

Repeat per section:

1. Avatar on camera (5–15 s) — hook or transition  
2. Text / title card + narration  
3. B-roll + diagram / bullet overlay  
4. (repeat)

Not full talking-head for the entire duration.

---

## Render layers (who does what)

| Layer | Provider | GPU needed? | Billed how |
|-------|----------|-------------|------------|
| Avatar clips | HeyGen API or Web ($29 Creator) | HeyGen-side | Per second / credits |
| TTS / voice | HeyGen built-in (Indonesian voices) | HeyGen-side | Included in HeyGen |
| Script / scene plan | Groq / DeepSeek (existing `llm.py`) | No | ~$1–5/mo at low volume |
| Template visuals | HyperFrames OSS on worker | No | Flat VPS |
| Stitch / encode / clip | FFmpeg on worker | No | Flat VPS |
| Publish | YouTube / TikTok / Telegram APIs (existing) | No | Free (OAuth) |

**Do not** run self-hosted lip-sync or Avatar V — out of scope and poor ROI.

---

## HeyGen product choice

| Product | Use when | Cost (API, approx.) |
|---------|----------|---------------------|
| **Avatar III** clips | Production (4 long-form/mo) — cheapest avatar engine | ~$1/min avatar footage |
| **Avatar IV / V** | Higher fidelity when credits allow | ~$3–4/min |
| **Video Agent** | Prototypes, format validation, one-shot ~1 min demos | ~$2/min |

Validated demo (2026-07-20): Video Agent produced a ~59 s Indonesian Bitcoin explainer with avatar + b-roll + text in one pass. Production at scale should prefer **Avatar III short clips + HyperFrames stitch** to stay within **≤ $29/month** HeyGen Web budget.

### Personal cost target (early phase)

| Item | Cost |
|------|------|
| HeyGen Web Creator | $24/mo (annual) or $29/mo — primary for experiment + MCP |
| Avatar footage via web/MCP | Within 600 credits (annual: credits roll over until plan end) |
| Direct API wallet | $5–15 only when wiring app → HeyGen |
| HyperFrames + FFmpeg + LLM | $0 on Mac Mini / included in VPS |
| **Total early phase** | **≈ Creator only; API optional later** |

No ElevenLabs or separate TTS in phase 1.

### Agreed billing split (2026-07-22)

Creator web credits and Direct API wallet are **separate**. Do not assume Creator pays for `X-Api-Key` calls.

| Phase | Spend | How we generate avatar footage |
|-------|-------|--------------------------------|
| Foundation + visual try-error | **Creator $24–29/mo** | Cursor + HeyGen MCP / web app |
| Pipeline code without API burn | $0 HeyGen API | Import MCP/web MP4s as local fixtures → HyperFrames + FFmpeg stitch |
| App↔HeyGen integration test | **API top-up $5–15** | Direct API from media-engine only when ready |

**Why this order:** building the system needs many “generate → look → revise” loops. Those loops run on Creator+MCP. Direct API proves the production path later — not for early visual experimentation.

---

## SaaS architecture

```text
┌─────────────────────────────────────────┐
│  Otonom Media (SaaS)                    │
│  Dashboard, templates, review, schedule │
│  Scene planner, job queue, analytics    │
├─────────────────────────────────────────┤
│  User BYOK                              │
│  HeyGen API key / subscription          │
│  YouTube (and other) channel OAuth      │
├─────────────────────────────────────────┤
│  Operator infra (cheap, flat)           │
│  API VPS + render workers               │
│  HyperFrames + FFmpeg (CPU)             │
│  Object storage (R2 / S3)               │
└─────────────────────────────────────────┘
```

### Value proposition (what we sell)

- End-to-end workflow: topic → long-form → shorts → publish  
- HyperFrames template library (brand systems)  
- Review guardrails before publish  
- Multi-platform scheduling (already in `schedule_publisher.py`)  

### What we do not sell

- Avatar generation infra (HeyGen handles that)  
- Per-minute render markup on GPU farms  

---

## Render infra: VPS + FFmpeg (yes) vs Render Network (no)

### Recommended: VPS workers + job queue

HyperFrames needs **Node 22+**, headless browser, and FFmpeg — a **CPU + RAM** workload, not Octane/3D GPU rendering.

| Phase | Users | Infra |
|-------|-------|-------|
| Now | 1 (personal) | Mac Mini + PM2 |
| MVP SaaS | 5–20 | 1× VPS (e.g. Hetzner CX42, ~€15/mo) |
| Growth | 50–200 | API VPS + 2+ render workers + Redis queue |
| Scale | 200+ | Add Modal / Fly Machines for burst; keep dedicated workers |

Rough SaaS infra at 100 light users: **~$25–50/month** (VPS + R2 storage + LLM), because HyperFrames render is **not** billed per minute.

### Not recommended: Render Network

[Render Network](https://rendernetwork.com/pricing) targets decentralized **GPU** work (3D/OctaneBench, AI training). It does not match FFmpeg concat or HyperFrames HTML→video pipelines. Wrong tool for this product.

### Not recommended at scale: Shotstack / Creatomate API

~$0.05–0.15/min output — erodes margin when templates already exist in HyperFrames OSS.

### GPU VPS

Only needed if we add local Whisper-large at scale or self-hosted avatars. With HeyGen BYOK, **no GPU required** on our workers.

---

## Automation & publish

| Mode | Flow | Recommendation |
|------|------|----------------|
| Full auto | Topic → publish with no human step | ❌ Too risky for educational content |
| Semi-auto | Generate → **review queue** → approve → schedule → publish | ✅ Matches existing app |

Already implemented (reuse for Explainer Mode):

- `live_publishers.py` — YouTube Shorts, TikTok, Telegram, Meta  
- `schedule_publisher.py` — PM2 worker for due posts  
- `oauth_flow.py` — channel connections  
- Dashboard review studio  

### MCP + Cursor / Antigravity / Codex

Useful as **operator tooling** during development (HeyGen MCP demos, scripts). Not the production product. Production = platform + PM2/cron workers on VPS.

---

## SaaS business model (draft)

| Tier | Price to user | Our cost | Notes |
|------|---------------|----------|-------|
| Free | $0 | ~$0 | User BYOK HeyGen; limited templates |
| Pro | $19–49/mo | VPS ~$10–30 + LLM ~$3 | Workflow + templates + scheduling |
| HeyGen | — | $0 for us | User pays HeyGen directly (BYOK) |

Margin comes from orchestration and templates, not from reselling render minutes.

---

## Implementation phases

### Phase 0 — Foundation (no Direct API required)

Build Explainer Mode **around local assets**:

1. `explainer_planner.py` — topic → scene JSON (`avatar` | `text` | `broll`)
2. `explainer_stitch.py` — FFmpeg concat + audio bed
3. HyperFrames recipes for text/b-roll scenes (reuse `data_market_explainer` / brand templates)
4. CLI: `explainer run --scenes scenes.json --clips-dir ./fixtures/`
5. Drop avatar MP4s from Cursor+MCP / web download into `fixtures/` (manual import step)

**Exit criteria:** one ~3–5 min hybrid video from fixture clips + HyperFrames, viewable in review queue.

### Phase 1 — Visual experiment (Creator + MCP)

- Subscribe Creator ($24 yearly / $29 monthly)
- Generate avatar clips via Cursor + HeyGen MCP (avatar look `0f4dca86…`, voice `LXpG1p9h…`)
- Iterate script/pacing/look; feed winners into Phase 0 pipeline
- Optional: short Video Agent demos for format reference only

**Exit criteria:** 1–2 topics look “good enough” for TechTalk; scene pattern locked.

### Phase 2 — Wire Direct API (small top-up)

- Top-up API **$5–15** when Phase 0+1 stable
- `heygen_client.py` — batch short clips with Avatar III
- Replace manual fixture import with automated download
- Cost guardrails (max seconds/job)

**Exit criteria:** one end-to-end run from CLI without hand-dropping MP4s.

### Phase 3 — Productize

- Dashboard Explainer Mode + generation job
- Review → schedule → publish (existing)
- Own-channel ingest → shorts flywheel
- BYOK for SaaS users (later)

Note: **Thin Otonom MCP** ships with / right after Phase 0 (not deferred to Phase 3).

### Phase 4 — SaaS scale

- VPS workers + queue (see render infra above)
- Multi-tenant; skip Composio-as-core (optional later)

---

## References

- Epic + children: https://github.com/sahibul-nf/otonom-agents-media/issues/4  
- Operator guide: `docs/explainer-mode.md`  
- MCP Cursor example: `docs/otonom-mcp.cursor.example.json`  
- HeyGen API pricing: https://developers.heygen.com/docs/pricing  
- HyperFrames renderer: `media-engine/media_engine/hyperframes_renderer.py`  
- Publish adapters: `media-engine/media_engine/live_publishers.py`  
- Schedule worker: `media-engine/media_engine/schedule_publisher.py`  
- Video tooling: `docs/VIDEO_TOOLING.md`  
- Demo (Video Agent, ~59 s): https://app.heygen.com/videos/be976aac8f334a14a64d6be09e6adac3  
