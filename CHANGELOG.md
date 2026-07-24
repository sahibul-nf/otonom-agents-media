# Changelog

## [Unreleased]

- Polished Explainer non-avatar text/b-roll cards (TechTalk gradient takeaways, signal bars, gentle Ken Burns) so FFmpeg-only stitches look less like draft title slides.
- Fixed Review Studio so Explainer long-form candidates use 16:9 preview and long-form timing readiness instead of shorts-only 9:16 / 20s–3min gates.
- Added TechTalk HyperFrames brand pack (`techtalk_intel_brief` / `techtalk_explainer`) as the Explainer Mode default for text/b-roll scenes, plus `profiles/techtalk_style.json`.
- Added dashboard **Explainer** tab plus `/api/explainers` and `/api/explainer-run` for plan → stitch → Review, with documented own-channel long-form → shorts flywheel.
- Hardened `scripts/dev.sh` so a backend missing `/api/explainers` is treated as stale and restarted.

## 2026-05-18

- Removed the remaining publish permission blocker from the auto-publish guard and hid legacy blocked attempts from current dashboard state.
- Added per-schedule and default platform target selection for Telegram, YouTube Shorts, Facebook Reels, and TikTok.
- Improved Publish Center with target on/off controls, clearer connection status, connection verification actions, latest-attempt summaries, and recovery hints.
- Fixed live publish failure recording so adapter errors update the publish attempt instead of leaving stale `ready` attempts behind.
- Added recovery for stalled scheduled publish rows so interrupted workers can retry instead of leaving clips stuck in `publishing`.
- Added environment alias support for Telegram and Meta credentials used by the local `.env.local` setup.

## 2026-05-17

- Hardened local dev startup so a stale backend process missing new API endpoints is restarted instead of reused.
- Added due-schedule publishing across Telegram, YouTube Shorts, Facebook Reels, and TikTok with idempotent publish attempts, platform result tracking, and a PM2 publisher worker.
- Removed the `public_third_party` permission-evidence blocker from platform publishing while keeping approval and schedule gates in place.
- Upgraded Calendar and Publish Center to show scheduled publish status, platform chips, due publish actions, credential readiness, and last attempt errors.
- Improved Review Studio re-render progress with real per-stage percentages, clearer stage copy, and a visible inline progress bar instead of an ambiguous pulse line.
- Added generation-job heartbeat and stale-job recovery so interrupted batch runs no longer remain stuck in `running` after network drops, crashes, or server restarts.
- Finished the dashboard component split by moving Review Studio and Brand Settings into dedicated modules and removing duplicated legacy blocks from `MediaStudioApp`.
- Fixed a brand preview rendering bug caused by an unterminated template literal in `BrandSection`, restoring successful dashboard build output.
- Kept seek interaction only in the native 9:16 player controls and preserved persisted per-clip rerender job status across refresh.
- Fixed dashboard video preview seeking by forwarding HTTP `Range` requests through the Next media proxy and serving byte-range artifact responses from the review server.
- Fixed Review Studio clip action menus being clipped by the list row container when opened near the lower edge.
- Improved Review Studio row responsiveness so clip titles stay readable on normal desktop widths.
- Moved Generate into a single-column layout until extra-wide screens so source, duration, genre, and command controls have enough working room.
- Added root-level PM2 operations scripts, ecosystem config, and Telegram-backed health monitoring for reboot-safe local service recovery.

## 2026-05-15

- Added brand template loading in the editor so a user can preview and customize from any saved template.
- Added video seek controls to the 9:16 review preview for faster QA at specific timestamps.
- Added per-clip re-render progress states in Review Studio so item-level re-rendering is visible without blocking the full queue.
- Replaced free-form caption background input with a hex color picker and normalized saved colors to hex values.
- Added custom clip length generation controls with a production default of 20-180 seconds while keeping legacy duration presets available.
- Added per-batch genre selection and connected genres into generation jobs, CLI commands, curation metadata, and LLM prompt context.
- Added local brand template saving plus an instant 9:16 browser preview for caption and watermark styling without a long video render.
- Added dashboard controls for custom min/max clip length, multi-select genres, and clearer caption save versus per-item re-render flow.
- Added persisted `rerender_jobs` tracking so clip-level re-render progress survives dashboard refresh and continues polling while jobs are running.
- Added `/api/rerender-jobs` and changed `/api/rerender` to queue asynchronous jobs with status/progress metadata.
- Refactored review preview into a dedicated component module to reduce `MediaStudioApp` surface area.
- Simplified preview UX by keeping seek only inside the 9:16 video player's native control bar.
- Updated generic dashboard copy in shared areas from brand-specific wording to workspace-level wording.
- Added local API endpoints for genre options and saving reusable brand style templates.
- Hardened dashboard API proxy JSON parsing so malformed upstream responses return actionable errors.
- Simplified clip duration choices to user-facing buckets: `Auto (0-3 min)`, `Under 30s`, `30s - 60s`, `1 - 3 min`, and `3+ min`, while preserving legacy duration aliases.
- Added canonical clip length strategies for short generation: `quick_hit`, `standard_short`, `deep_context`, and `platform_max`.
- Connected duration strategies through dashboard, local API, generation jobs, CLI curation, LLM prompts, scoring, and candidate metadata.
- Added adaptive duration metadata including selected duration, boundary confidence, and duration reason.
- Replaced legacy generation job default `45-120s` with canonical `deep_context` while keeping legacy aliases readable for older commands.
- Added local API metadata for duration presets so the dashboard no longer owns static preset copy.
- Refined Review Studio filters into human workflow groups.
- Hardened dashboard media API error handling so offline/empty engine responses show actionable messages instead of raw JSON parse errors.
- Replaced the clip length dropdown with a niche-neutral strategy selector that keeps range and pacing guidance visible.
- Hardened dashboard generation jobs to require a Python runtime with transcript and Whisper dependencies instead of falling back to an empty system interpreter.
- Fixed Review Studio clip list trailing layout so score, QA, cost, and actions no longer collide.
- Added assisted autonomous review gates with review deadlines, pending auto-schedule status, hold/reject controls, and autonomy mode settings.
- Added post-Whisper glossary/fuzzy caption correction metadata for Arabic-Indonesian Nourbit terms.
