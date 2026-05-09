# yt-dlp PO Token Setup

This project should prefer public transcript ingestion first. Use video download only after rights/source policy passes.

## Why This Exists

Some YouTube videos now reject normal `yt-dlp` video downloads with HTTP 403 even when transcript access works. Browser cookies can help in some cases, but for the Nourbit real-video smoke test, cookies were not enough. The working path was `yt-dlp` nightly/dev plus a local PO Token provider.

## Local Tooling

Use Python 3.13+ for this stack. Python 3.9 fails with `yt-dlp-getpot-wpc` dependencies that use newer type syntax.

```bash
python3.13 -m venv /tmp/media-engine-tools-py313
/tmp/media-engine-tools-py313/bin/python -m pip install -U pip
/tmp/media-engine-tools-py313/bin/python -m pip install -U --pre "yt-dlp[default]" bgutil-ytdlp-pot-provider yt-dlp-getpot-wpc youtube-transcript-api pillow
```

Clone and run the bgutil HTTP provider outside the repository:

```bash
git clone --depth 1 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /tmp/bgutil-ytdlp-pot-provider
cd /tmp/bgutil-ytdlp-pot-provider/server
npm install
npx tsc
node build/main.js
```

Leave that server running in one terminal only while downloading.

## Download Command

Run from `media-engine/`:

```bash
/tmp/media-engine-tools-py313/bin/yt-dlp \
  -f "bestvideo[height<=360]+bestaudio/best[height<=360]/best" \
  --merge-output-format mp4 \
  -o "artifacts/nourbit/live_youtube_test/full_%(id)s.%(ext)s" \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

For production jobs, prefer partial section downloads instead of full long videos:

```bash
/tmp/media-engine-tools-py313/bin/yt-dlp \
  --download-sections "*00:19:30-00:20:30" \
  -f "bestvideo[height<=720]+bestaudio/best[height<=720]/best" \
  --merge-output-format mp4 \
  -o "artifacts/nourbit/live_youtube_test/clip_%(id)s.%(ext)s" \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

## Secrets Rules

Do not commit:

- `.env` files,
- browser cookie exports,
- OAuth credentials,
- service account JSON,
- generated PO token files,
- platform access tokens.

The root `.gitignore` already blocks common secret and cookie patterns. Put local-only sensitive files under `media-engine/secrets/` if a tool needs a stable path.
