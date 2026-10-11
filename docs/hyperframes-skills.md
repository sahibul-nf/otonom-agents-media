# HyperFrames agent skills

Official HyperFrames skills teach coding agents the project format, animation rules, and catalog workflows.

## Install (human or agent)

```bash
npx skills add heygen-com/hyperframes
# Select Core Skills for Cursor / Antigravity
```

Non-interactive refresh (verified for #100):

```bash
npx hyperframes skills update
npx hyperframes skills check
# Expect: "Installed skills are up to date" (skills live under ~/.claude/skills + agent links)
```

## Repo layout

Skills install into the operator agent directories (`~/.claude/skills`, `~/.agents/skills`, Cursor skill links) — not into this app git tree. Catalog/runtime assets for renders live in `media-engine/render/hyperframes/`.

## When agents should use skills

- Authoring or editing HyperFrames HTML/GSAP compositions
- Choosing catalog blocks/components (captions, overlays, transitions)
- Running `hyperframes lint`, `inspect`, and `render` before shipping template changes

## References

- [HyperFrames skills guide](https://hyperframes.heygen.com/guides/skills)
- [HyperFrames catalog](https://hyperframes.heygen.com/catalog)
- Renderer runtime: `media-engine/render/hyperframes/`
