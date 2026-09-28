# HyperFrames agent skills

Official HyperFrames skills teach coding agents the project format, animation rules, and catalog workflows.

## Install (human or agent)

```bash
npx skills add heygen-com/hyperframes
# Select Core Skills for Cursor / Antigravity
```

Non-interactive refresh:

```bash
npx hyperframes skills update
npx hyperframes skills check
```

## Repo layout

Skills install into `.agents/skills/` (Antigravity-compatible). Cursor discovers them via the skills symlink chain created by the installer.

## When agents should use skills

- Authoring or editing HyperFrames HTML/GSAP compositions
- Choosing catalog blocks/components (captions, overlays, transitions)
- Running `hyperframes lint`, `inspect`, and `render` before shipping template changes

## References

- [HyperFrames skills guide](https://hyperframes.heygen.com/guides/skills)
- [HyperFrames catalog](https://hyperframes.heygen.com/catalog)
- Renderer runtime: `media-engine/render/hyperframes/`
