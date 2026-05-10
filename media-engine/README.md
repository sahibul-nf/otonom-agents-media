# Autonomous Media Engine

Local-first V1 for autonomous short-form media production. This first slice focuses on Nourbit video clipping while keeping the architecture reusable for TechTalk and future niches.

## What is implemented

- SQLite schema for profiles, source manifests, candidates, render jobs, publish targets, and publish attempts.
- Nourbit profile with Facebook Reels, YouTube Shorts, TikTok, and Instagram Reels targets.
- Rights guardrails that block auto-publish for public third-party sources.
- Dry-run curation from a timestamped transcript.
- Minimal FFmpeg 1080x1920 renderer for fast local verification.
- Premium Nourbit render path for source-video shorts with animated hook, word-timed kinetic captions, CTA, watermark, attribution, and review-safe metadata.
- Opus-style Nourbit brand template in `profiles/nourbit_opus_style.json`.
- Remotion premium template scaffold for the next browser-render iteration.
- Review UI shell with platform mode switches.
- Dry-run publisher payload builders.
- V2 multi-clip Nourbit curation with deterministic quality scoring, glossary cleanup for Arabic/Indonesian terms, and optional OpenAI/DeepSeek JSON curation.

## Commands

```bash
python3 -m media_engine.cli init
python3 -m media_engine.cli ingest --profile nourbit
python3 -m media_engine.cli curate --profile nourbit --source-id nourbit_nouraniyyahofficial
python3 -m media_engine.cli review --profile nourbit
python3 -m media_engine.cli render --candidate-id <clip_id>
python3 -m media_engine.cli premium-test --youtube-url "https://www.youtube.com/live/WSg7MGv4_Fs" --renderer ffmpeg
python3 -m media_engine.cli premium-test --youtube-url "https://www.youtube.com/live/WSg7MGv4_Fs" --renderer ffmpeg --style profiles/nourbit_opus_style.json
python3 -m media_engine.cli premium-test --youtube-url "https://www.youtube.com/live/WSg7MGv4_Fs" --renderer remotion
python3 -m media_engine.cli premium-curate --youtube-url "https://www.youtube.com/live/WSg7MGv4_Fs" --count 5 --llm-provider none
python3 -m media_engine.cli premium-batch --youtube-url "https://www.youtube.com/live/WSg7MGv4_Fs" --count 5 --renderer ffmpeg --style profiles/nourbit_opus_style.json --llm-provider none
python3 -m media_engine.cli approve --candidate-id <clip_id>
python3 -m media_engine.cli publish --candidate-id <clip_id>
python3 -m media_engine.cli set-target-mode --platform tiktok --mode review_required
python3 -m media_engine.cli authorize-source --source-id nourbit_nouraniyyahofficial --permission-status authorized_community --permission-evidence "approval note"
python3 -m media_engine.review_server
```

Open the review UI at `http://127.0.0.1:8765/review.html`. The UI includes the current Nourbit style baseline and a ready-to-run local production test command.

## LLM curation

`--llm-provider none` is the default and uses local heuristic scoring only. To use optional LLM curation, set one of these ignored environment variables before running `premium-curate`, `premium-batch`, or `premium-test`:

```bash
export OPENAI_API_KEY="..."
export DEEPSEEK_API_KEY="..."
```

Supported provider values are `none`, `openai`, and `deepseek`. LLM output is parsed as strict JSON and falls back to deterministic heuristics if a provider call fails.

## Rights default

`https://www.youtube.com/@nouraniyyahofficial` is seeded as `public_third_party`. That means exports and review are allowed, but auto-publish and monetization remain blocked until permission evidence is recorded in the source manifest.

## Remotion note

The Remotion template is intentionally isolated under `render/remotion`. Install dependencies there only when you are ready to preview or render animated templates:

```bash
cd render/remotion
npm install
npm run studio
```

The Remotion path uses the `NourbitPremiumShort` composition and copies the prepared source clip into `render/remotion/public/runtime/`, which is ignored by git. The default premium test renderer is currently FFmpeg because it is deterministic on the local Mac while the Remotion composition remains available for further browser-render tuning.

Before using this in SaaS, review Remotion licensing and platform API approval requirements.
