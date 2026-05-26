# Video Tooling Notes

## Current Decision

Use a HyperFrames-first render strategy:

- FFmpeg for deterministic trimming, encoding, audio normalization, and cheap smoke renders.
- HyperFrames as the primary HTML/GSAP renderer behind `HYPERFRAMES_ENABLED=true`, especially for kinetic captions, overlays, and fast AI-agent-authored compositions.
- Remotion remains in the repo as hidden legacy fallback for old jobs, not as a user-facing renderer choice.

## HyperFrames Notes

HyperFrames uses HTML as the composition source and GSAP timelines for animation. Its quickstart requires Node.js 22+ and FFmpeg, and renders with `npx hyperframes render --output output.mp4`.

Before enabling HyperFrames for live batches:

- set `HYPERFRAMES_ENABLED=true`,
- run `npm exec --yes --package hyperframes@0.6.40 -- hyperframes doctor`,
- verify `lint`, `inspect`, and render metadata under the clip artifact folder,
- keep legacy renderer paths available only for compatibility with old jobs.

Source references:

- https://hyperframes.heygen.com/quickstart
- https://github.com/heygen-com/hyperframes

## YouTube Download Notes

For public YouTube sources that reject normal `yt-dlp` downloads with HTTP 403, use the PO Token workflow in [YTDLP_PO_TOKEN_SETUP.md](YTDLP_PO_TOKEN_SETUP.md). Keep cookies, browser exports, and generated token files outside git.
