# TechTalk preset

`BRAND_BRAIN.md` is a **sanitized** editorial fence for git. Page ids, voice ids, and full wordmark PNGs stay in your private [content-os](https://github.com/sahibul-nf/content-os) checkout.

## Optional assets (`CONTENT_OS_PATH`)

When the engine env points at content-os, still and carousel renders overlay the wordmark from:

- `techtalk-production/brand/techtalk-intel-wordmark-cropped.png` (preferred)
- `techtalk-production/brand/techtalk-intel-logo.png` (fallback)

```bash
export CONTENT_OS_PATH=/absolute/path/to/content-os
export OTONOM_BRAND_PRESET=techtalk
```

No PNGs are committed in this repo — only path resolution in `media-engine/media_engine/brand_pack.py`.
