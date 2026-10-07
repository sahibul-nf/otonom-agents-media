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
