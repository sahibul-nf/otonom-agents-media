# Stock preview sources

Royalty-free MP4 clips for HyperFrames template preview prewarm.

**Note:** `*.mp4` is in the repo `.gitignore` — clips stay on your machine after download.

## Quick download (automated)

**Recommended** — uses `PEXELS_API_KEY` from repo `.env.local` (higher quality, unique per template):

```bash
python3 media-engine/render/hyperframes/stock/download_stock_clips.py --source pexels --rewarm-previews
```

Mixkit fallback (no API key):

```bash
python3 media-engine/render/hyperframes/stock/download_stock_clips.py --source mixkit
```

Default `--source auto` picks Pexels when the key is set. Attribution for Pexels clips is written to `stock_attribution.json`.

## Where to download (free commercial use)

| Site | License | Best for |
|------|---------|----------|
| [Pexels Videos](https://www.pexels.com/videos/) | Pexels License (free, no attribution required) | Talking head, lifestyle, product |
| [Pixabay Videos](https://pixabay.com/videos/) | Pixabay License (free) | B-roll, nature, office |
| [Mixkit](https://mixkit.co/free-stock-video/) | Mixkit License (free) | Short social clips, tech, fitness |
| [Coverr](https://coverr.co/) | Free for commercial use | Cinematic loops, abstract |
| [Videvo](https://www.videvo.net/) | Check per clip (many CC0 / free) | News desk, screens, charts |

**Avoid** unless you have a paid license: random YouTube rips, Getty/Shutterstock watermarked previews, or Captions.ai export files (their ToS).

## Search tips (Pexels / Pixabay)

- Portrait 9:16: `man talking camera vertical`, `podcast vertical`, `woman selfie video vertical`
- Landscape 16:9: `news desk`, `laptop screen data`, `office presentation`
- Mood: add `warm light`, `dark gym`, `neon`, `editorial` to match template vibe

## Filenames (must match `preview_source_video` in templates)

| File | Use for templates |
|------|-------------------|
| `portrait_warm_talk.mp4` | Spiritual Reflective |
| `portrait_social_energy.mp4` | Energy, Arion, Pulse, Kai |
| `portrait_product_demo.mp4` | Cove, Prism Pro |
| `portrait_training_dark.mp4` | Rocket, Grit, Neon, Chalk |
| `portrait_handwritten_story.mp4` | Story, Sonnet, Sketch |
| `landscape_news_desk.mp4` | Byline |
| `landscape_data_screen.mp4` | Velocity, Blueprint |
| `landscape_editorial_grain.mp4` | Quintessence, Archive |

Export **H.264 MP4**, ~10–20s, 1080×1920 (portrait) or 1920×1080 (landscape). Log each clip in `LICENSES.md`.

## After adding files

```bash
export HYPERFRAMES_ENABLED=true
cd media-engine
PYTHONPATH=. python3 -c "from media_engine.hyperframes_previews import prewarm_hyperframes_template_previews; print(prewarm_hyperframes_template_previews(include_brand=False))"
```

If files are missing, previews still render using an ffmpeg test pattern.
