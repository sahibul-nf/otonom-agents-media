# Delivery formats

Every generated **content package** has exactly one format. Editorial catalog aligns with [content-os `FORMATS.md`](https://github.com/sahibul-nf/content-os/blob/main/content-ai-system/FORMATS.md).

| Format | Deliverable | Typical job |
|--------|-------------|-------------|
| `text_only` | Caption only | Take, reflection (`inform`) |
| `still` | Caption + one PNG (HTML/CSS → headless render) | One thesis (`inform`) |
| `carousel` | Caption + 3–5 slide PNGs | Framework, checklist (`teach`, `save_for_later`) |
| `short` | 30–60s vertical video + caption | Hook, impact (`inform`) |
| `long_form` | 3–12 min video + title, description, caption | Deep dive (`teach`) |
| `clip` | Short cut from approved `long_form` + caption | Distribution wedge |

**Postiz publish (Review):** `text_only` and video packages default to `telegram_channel`. `still` and `carousel` default to the first mapped channel among `instagram`, `instagram_reels`, and `telegram_channel` (UI sends `instagram` when mapped).

## Video engines (`short` / `long_form` only)

| Engine | Role |
|--------|------|
| `av_explainer` | **Default.** Faceless audio-visual: voice + diagrams/motion (explainer + HyperFrames in this repo). |
| `motion` | Kinetic HTML→video without full explainer structure. |
| `heygen` | Optional on-camera avatar when the brand pack requests it. |

`clip` uses `clip_cut` (ffmpeg) and requires `parent_package_id` pointing at an approved long-form parent.

## Package status

1. `draft` — missing required artifacts or QA failed.
2. `ready_for_review` — schema + QA pass; waiting in Review.
3. `approved` — human approved; may schedule/publish via Postiz.
4. `published` — delivery recorded.

Human approve is always required before publish.

## Batch create (one action, many packages)

Create UI and `POST /api/content-package-create` accept **`formats`: string[]** (minimum one). The server resolves the source **once**, then creates **one package per format**. Each package’s `meta` includes **`batch_id`** and **`batch_formats`** so Review can show related outputs together. Single-format clients may still send **`format`** only (unchanged response shape).

`clip` requires **`parent_package_id`**; enable it in the UI only after the parent id is set. MCP `create_content_package` accepts the same `formats` array.

## QA (built-in)

- Claims and sources present when the format needs them.
- Carousel: 3–5 slides.
- Clip: valid parent id.
- Short / long_form: video artifact path set.
- `av_explainer`: visual-first gate flags on the package (`qa.visual_approved` before TTS in production workflows).

Brand-specific fences load from `brand-pack/<preset>/` or `CONTENT_OS_PATH`.
