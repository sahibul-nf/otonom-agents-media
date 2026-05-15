# Changelog

## 2026-05-15

- Added canonical clip length strategies for short generation: `quick_hit`, `standard_short`, `deep_context`, and `platform_max`.
- Connected duration strategies through dashboard, local API, generation jobs, CLI curation, LLM prompts, scoring, and candidate metadata.
- Added adaptive duration metadata including selected duration, boundary confidence, and duration reason.
- Replaced legacy generation job default `45-120s` with canonical `deep_context` while keeping legacy aliases readable for older commands.
- Added local API metadata for duration presets so the dashboard no longer owns static preset copy.
- Refined Review Studio filters into human workflow groups.
- Hardened dashboard media API error handling so offline/empty engine responses show actionable messages instead of raw JSON parse errors.
