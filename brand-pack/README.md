# Brand packs

Copy a preset or point `CONTENT_OS_PATH` at a full [content-os](https://github.com/sahibul-nf/content-os) checkout.

| Preset | Use |
|--------|-----|
| `blank` | Empty headings — start a new media company |
| `techtalk` | Tech & finance editorial (sanitized; no page or voice ids) |
| `personal` | Personal kinetic shorts lane (not TechTalk) |

Engine env:

```bash
export OTONOM_BRAND_PRESET=techtalk   # optional default
export CONTENT_OS_PATH=/path/to/content-os   # overrides preset when set
```

## Wordmarks and logos (optional)

Full PNG marks live in **content-os**, not in git. Set `CONTENT_OS_PATH` to your local clone; the engine resolves paths under `techtalk-production/brand/` (see `brand_pack.py` and `brand-pack/techtalk/README.md`).

You can:

- **Reference only** — keep content-os elsewhere; env var is enough for render.
- **Symlink** — `ln -s /path/to/content-os/techtalk-production/brand ./brand-pack/techtalk/assets` for local preview (do not commit symlinks to private paths).
- **Copy** — duplicate PNGs into a private workspace; still prefer `CONTENT_OS_PATH` so one checkout stays canonical.
