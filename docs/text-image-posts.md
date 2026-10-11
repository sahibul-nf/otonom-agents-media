# Text + image social posts (#24)

Unify **video + text + still/carousel** in one Otonom dashboard. Video paths (Path A / Explainer / HyperFrames) stay as-is; text/image reuse the same Review → approve → schedule/publish loop.

## Scope (v1)

| Niche | TechTalk edu-finance (workspace `niche` + brand presets) |
|-------|----------------------------------------------------------|
| Formats | `text_only`, `still`, `carousel` (plus video formats on the same Create form) |
| Platforms | Prefer **Postiz**-mapped channels — see publish defaults below |
| Carousel | 3–5 slides (shipped); design-studio / Canva clone out of scope |

### Publish defaults (`docs/FORMATS.md`)

| Format | Default destination |
|--------|---------------------|
| `text_only` | `telegram_channel` |
| `still` / `carousel` | mapped `instagram` (fallback Telegram) |
| video packages | `telegram_channel` unless overridden |

**Gaps:** TikTok native OAuth unsupported (Postiz-only when ready). LinkedIn / X need a mapped Postiz integration — no separate Otonom OAuth client. Clickable subscribe overlays remain non-interactive (same as HyperFrames OSS).

## Dashboard surface

Generate → **Content package** (`ContentPackageCreateSection`): outcome-first format chips (text / still / carousel / short / long / clip), source = YouTube / chat paste / topic brief, brand preset, writing model (incl. agent / routing `auto`). Packages land in Review with status `planned` → `approved` → `published`. **No auto-publish.**

## Research & prompts (no second video stack)

- Topic / signal ideas: `techtalk-autonomous` patterns + `docs/topic-engine.md` (#23) for briefs
- Text patterns: prefer `sahibul-nf/social-media-content-ai-generation` prompt style when editing LLM copy (do not fork a parallel render pipeline)
- Brand / six formats: `docs/FORMATS.md`, `docs/BRAND.md`, content-os editorial catalog

## Related

- North star: `.cursor/rules/platform-north-star.mdc` (priority: unify text/image after weekly video loop)
- Issues: #24 (this), #108–#111 (Create / still / explainer hook / publish), #23 (topic briefs)
- Ops: `docs/local-ops.md` (Postiz delivery)
