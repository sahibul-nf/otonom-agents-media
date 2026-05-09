# Video Tooling Notes

## Current Decision

Use a hybrid render strategy:

- FFmpeg for deterministic trimming, encoding, audio normalization, and cheap smoke renders.
- Remotion for React-based motion templates already scaffolded in `media-engine/render/remotion`.
- HyperFrames as an evaluation candidate for HTML/GSAP-first templates, especially kinetic captions, overlays, and fast AI-agent-authored compositions.

## HyperFrames Notes

HyperFrames uses HTML as the composition source and GSAP timelines for animation. Its quickstart requires Node.js 22+ and FFmpeg, and renders with `npx hyperframes render --output output.mp4`.

Do not add HyperFrames to the production path until we have:

- a dedicated `DESIGN.md` or visual style file for Nourbit,
- a tiny proof composition,
- lint/render checks in CI or local smoke scripts,
- a license/dependency review for SaaS use.

Source references:

- https://hyperframes.heygen.com/quickstart
- https://github.com/heygen-com/hyperframes

## YouTube Download Notes

For public YouTube sources that reject normal `yt-dlp` downloads with HTTP 403, use the PO Token workflow in [YTDLP_PO_TOKEN_SETUP.md](YTDLP_PO_TOKEN_SETUP.md). Keep cookies, browser exports, and generated token files outside git.
