# HyperFrames Evaluation

HyperFrames is not installed in the production path yet. Keep it here as an evaluation lane for HTML/GSAP-first vertical short templates.

## Why evaluate it

- HTML compositions are easy for agents to author and review.
- GSAP timelines are a natural fit for kinetic captions, overlays, click/typing effects, and transitions.
- It can complement the existing FFmpeg and Remotion paths.

## Manual scaffold when ready

```bash
npx hyperframes init nourbit-hyperframes --non-interactive --example blank
cd nourbit-hyperframes
npx hyperframes preview
npx hyperframes render --output output.mp4
```

## Gate before adoption

- Create a Nourbit `DESIGN.md`.
- Build one 9:16 proof composition.
- Verify render output and text-safe layout.
- Review licensing and dependency impact before SaaS use.
