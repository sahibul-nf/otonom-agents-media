# Otonom Media — brand

## Name and mark

**Otonom Media** is the public product name. In the dashboard UI the word *Otonom* is set in italic with a cyan accent; **Media** stays upright.

## Tagline

The system for a one-person media company.

## One-liner

Open-source brand brain plus factory. It turns a source into publish-ready social content in your voice, across text, stills, carousels, shorts, long-form, and clips. A human approves. A connector publishes.

## Audience

Solo operators who run a media brand without a full team: builders, creators, and founders who want formats, QA, review, and publish wired together instead of gluing HeyGen, NotebookLM, and a scheduler by hand.

Agents (Cursor, Antigravity, OpenMausBot, and similar) call the same factory over MCP. A future Virtuals Protocol agent would use the same tool surface; that integration is not part of the core repo yet.

## What we are / are not

| Otonom Media | Not |
|--------------|-----|
| Brand brain + six social formats + review | A social OAuth client (use Postiz) |
| Native faceless / audio-visual video (`av_explainer`, `motion`) | A HeyGen clone |
| Optional HeyGen avatar as one `video_engine` | Video-only SaaS |
| Clip factory from long-form | NotebookLM replacement |

**NotebookLM** can produce infographics, slides, video, or audio from sources. Otonom can ingest that output as a **source** and shape it into a channel-ready **package** with your brand fences.

**HeyGen** is an optional avatar engine. Production does not depend on it.

## Case studies (maintainer)

TechTalk Intel, Nourbit, and Sahibul’s personal brand are real media built with this stack. Editorial canon and production packages live in [content-os](https://github.com/sahibul-nf/content-os). This repo ships **presets** under `brand-pack/` (`techtalk`, `personal`, `blank`) so new users start from the same shape, not from zero.

Nourbit remains a **profile** inside Otonom (clip workflow), not a content-os preset.

## Connectors

- **Model connector** — OpenAI, DeepSeek, Groq, or stub (`none`) for generation.
- **Publish connector** — [Postiz](https://postiz.com) (self-hosted or cloud) for OAuth and delivery. See [docs/local-ops.md](local-ops.md).

## Related

- [docs/FORMATS.md](FORMATS.md) — six delivery formats
- [docs/SECRETS.md](SECRETS.md) — credentials
- [README.md](../README.md) — quick start
