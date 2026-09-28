# HyperFrames Renderer

HyperFrames is the primary renderer for HTML/GSAP-first short and landscape templates. It is intentionally gated by `HYPERFRAMES_ENABLED=true` so local runtime readiness is explicit before production jobs run.

## Why use it

- HTML compositions are easy for agents to author and review.
- GSAP timelines are a natural fit for kinetic captions, overlays, click/typing effects, and transitions.
- It powers the public template library and Brand System Template builder.

## Runtime commands

```bash
npm install
npm run doctor
npm run lint
npm run inspect
npm run render -- --output output.mp4
```

## Vendored OSS catalog

Official HyperFrames blocks and components are installed under `compositions/` (see `oss-manifest.json`). Refresh or extend the pack:

```bash
npx hyperframes add yt-lower-third tiktok-follow grain-overlay caption-editorial-emphasis
```

After adding items, update `oss-manifest.json` and run `python3 -m unittest tests.test_hyperframes_oss`.

## Agent skills

Install official HyperFrames skills so agents follow composition and catalog rules:

```bash
npx skills add heygen-com/hyperframes
npx hyperframes skills check
```

See `docs/hyperframes-skills.md`.

## Production gate

- Set `HYPERFRAMES_ENABLED=true`.
- Keep Node.js 22+ and FFmpeg available.
- Verify the generated artifact folder contains `*_hyperframes.mp4`, `*_hyperframes.json`, and a `*_hyperframes/index.html` project.
- Review lint and inspect output in render metadata before using it for publishing.
