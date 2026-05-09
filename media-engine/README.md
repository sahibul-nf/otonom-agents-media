# Autonomous Media Engine

Local-first V1 for autonomous short-form media production. This first slice focuses on Nourbit video clipping while keeping the architecture reusable for TechTalk and future niches.

## What is implemented

- SQLite schema for profiles, source manifests, candidates, render jobs, publish targets, and publish attempts.
- Nourbit profile with Facebook Reels, YouTube Shorts, TikTok, and Instagram Reels targets.
- Rights guardrails that block auto-publish for public third-party sources.
- Dry-run curation from a timestamped transcript.
- Minimal FFmpeg 1080x1920 renderer for fast local verification.
- Remotion template contract for animated text, captions, CTA, watermark, and SFX.
- Review UI shell with platform mode switches.
- Dry-run publisher payload builders.

## Commands

```bash
python3 -m media_engine.cli init
python3 -m media_engine.cli ingest --profile nourbit
python3 -m media_engine.cli curate --profile nourbit --source-id nourbit_nouraniyyahofficial
python3 -m media_engine.cli review --profile nourbit
python3 -m media_engine.cli render --candidate-id <clip_id>
python3 -m media_engine.cli approve --candidate-id <clip_id>
python3 -m media_engine.cli publish --candidate-id <clip_id>
python3 -m media_engine.cli set-target-mode --platform tiktok --mode review_required
python3 -m media_engine.cli authorize-source --source-id nourbit_nouraniyyahofficial --permission-status authorized_community --permission-evidence "approval note"
python3 -m media_engine.review_server
```

Open the review UI at `http://127.0.0.1:8765/review.html`.

## Rights default

`https://www.youtube.com/@nouraniyyahofficial` is seeded as `public_third_party`. That means exports and review are allowed, but auto-publish and monetization remain blocked until permission evidence is recorded in the source manifest.

## Remotion note

The Remotion template is intentionally isolated under `render/remotion`. Install dependencies there only when you are ready to preview or render animated templates:

```bash
cd render/remotion
npm install
npm run studio
```

Before using this in SaaS, review Remotion licensing and platform API approval requirements.
