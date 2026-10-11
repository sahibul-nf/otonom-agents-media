# Topic engine (#23)

Autonomous **topic + storyboard** proposals from public niche signals, then Path A → Review. Human approval before publish is unchanged.

## Inputs

| Input | Source | Notes |
|-------|--------|--------|
| Niche keywords | Active media profile `niche` + TechTalk edu-finance bias (`ai`, `fintech`, `crypto`, …) | Profile niche tokens (≥3 chars) merge with defaults |
| Hacker News | Algolia front page API | Required; empty/stale feed → clear error |
| GitHub repos | Public search API (best-effort) | Soft-fail if rate-limited; does not block HN |

v1 refresh is **batch/hourly-friendly** — not sub-minute markets data.

Ideas reused from `techtalk-autonomous` (HN/GitHub + weighted niche topics) without forking a second video stack.

## Ranking

1. Fetch signals.
2. Score each item: niche keyword hits ×12 + dampened popularity + small HN boost.
3. Sort descending; attach confidence relative to the top score.
4. Build a short **storyboard** (hook → context → so-what → takeaway + source citations). Storyboard is passed as Path A `script` / talking points — Path A / Cursor + HeyGen MCP still produce the video.

## APIs

| Endpoint | Behavior |
|----------|----------|
| `POST /api/propose-topic` `{profile_id?, limit?}` | Ranked candidates only (no generate) |
| `POST /api/generate-next` `{profile_id?, candidate_id?, start_path_a?}` | Top (or selected) candidate → Path A job |
| `POST /api/path-a-generate` `{topic, …}` | Manual override (unchanged) |
| `POST /api/path-a-generate` `{generate_next: true}` | Empty topic → same as generate-next |

Each Path A job started this way stores `topic_proposal` on `status.json` (sources, confidence, angle) for audit.

## MCP

- `propose_topic` — candidates only
- `generate_next` — pick + optional Path A start

## Dashboard

Explainer / Long video:

- **Generate video** — manual topic (required non-empty brief)
- **Generate next** — empty brief; uses top proposal or a selected Propose result
- **Propose topics** — preview ranked list; click to fill the brief (still Review-gated after generate)

## Failure modes

- Empty HN feed / no niche-relevant hits → `400` with a clear message (widen niche or retry later).
- Cursor / Path A credentials missing → same errors as manual Path A generate.
- **No auto-publish.**

## Related

- `docs/heygen-paths.md` — Path A after the brief exists
- Issue #23
