# Changelog

## [Unreleased]

### Added
- **Content factory:** six-format packages with YouTube/chat/topic sources, vault-stored LLM keys or local agent CLI (`docs/LLM_CONNECTORS.md`), Review approve + Postiz text publish, explainer job hook for short/long packages.
- **TikTok (#113):** native OAuth marked unsupported (dev app removed); updated Publish copy, vault disconnect for all `TIKTOK_*` keys, docs, and legacy-gated `scripts/tiktok_oauth_helper.py`.
- **Create (#108):** content package form (six formats, source kinds, brand preset, writing model including agent) on the Generate tab.
- **Still/carousel (#109):** content packages render TechTalk-style PNGs (1080² or 1080×1920 personal) via explainer card layers, not 1×1 placeholders.
- **Explainer sync (#110):** when an explainer job finishes, linked short/long packages get `video_path` from `final.mp4`, explainer status in Review, and publish refreshes before Postiz video upload.
- Create finds a **text shortlist** before rendering. Slide to find clips, set a minimum editorial score (default 80), then render only the ideas you keep. Suggested content angles appear after a YouTube link resolves.
- Optional **Jev** decisions (`TYPESAFE_API_KEY` or `JEV_API_KEY`) can score keep/drop and pick a content angle. Copy is still written by the existing LLM.
- `docs/saas-readiness.md` — local-first → multi-user checklist (DB, auth seam, credentials, artifacts, workers); no cloud implementation.
- HyperFrames: **8** new built-in caption recipes (`swiss_grid_explainer`, `vignelli_portrait_headline`, `decision_tree_tutorial`, `kinetic_type_promo`, `nyt_graph_data_story`, `eva_neon_cyber`, `volt_lime_kinetic`, `ember_sunset_gradient`) with catalog metadata, dashboard preview overlays, and stock preview mapping.

- Dashboard **light theme**: OS light mode no longer leaves near-white `zinc` text on pale canvas. Shell uses semantic tokens; video preview overlays stay light-on-dark.

### Changed
- Dashboard **Main Flow UX (#105)**:
  - Synchronized active section state with URL (`?section=`), supporting browser back/forward and deep linking while preserving extra query params.
  - Main loop stepper in sidebar and home rail streamlined to **Create → Review → Schedule → Publish**, relocating Brand, Templates, and Long video into the dedicated **Setup & tools** section.
  - `getNextAction` upgraded to handle in-flight generation jobs, failed generation jobs, failed clip renders, and partially published clips, with account connection prompts prioritized before scheduling.
  - Mobile bottom navigation updated with direct Home access and visual status dot indicators matching touch target requirements.
  - Unified `LoadingState` and `RecoveryAction` components across Dashboard sections; failed publish items now surface immediate recovery actions (Reconnect account, Re-render in Review, Retry now).
  - Added unit test suites for `studio-flow` and `publish-recovery` (24 passing unit tests).
- Post captions drop generic `Sumber:` / `Source:` lines that are not the real channel, and no longer end a short caption with `...`.
- Hook prompts reject transcript slices. `viral_reason` stays a reason to post, not a copy of the subtitle.
- Upgraded **solo-dev-ai-kit** to **kit_version=12** (bootstrap merge; `GH_PROJECT_NUM=7` preserved). New kit: `gh-set-issue-status.sh`, `/update` + `/verify` Cursor commands, orchestrator Status columns (`gh-ensure-project-status.sh`). Otonom-only: `gh-sync-project-status.sh` (thin wrapper).
- TikTok on **Publish** stays visible but **Unavailable** (no OAuth, schedule, or Postiz map) while TikTok rejects personal/internal developer apps for production API access.
- Heuristic and LLM metadata skip family-blessing litanies and ASR junk (`hadratu qutblah`); titles should state the teaching, not “Berkahi keluarga…”.
- Review inbox masonry keeps **3 column slots** on wide screens when a tab has only 1–2 clips (e.g. Published) so card width matches All/Review instead of stretching two-up.
- Review Editor **Metadata** tab: title and description are editable; **Save changes** persists hook copy (`hook-metadata` API).
- Refresh metadata accepts Indonesian paraphrase from the LLM (same as Generate post with AI) and falls back to local copy instead of failing on word-overlap.
- Review Editor inspector (QA and other tools) can scroll inside the right rail so content is not clipped by the Timeline.
- Review Editor **QA** tab: **AI & captions** panel shows writing model, curation/reconstruct LLM status, ASR, and a note that job `llm_cost` is only an estimate.
- Review Editor **Look** tab: re-render can switch **preset HyperFrames templates** (built-in recipes) as well as saved brand templates; captions and trim are unchanged.
- Review Editor **Look**: preset and saved-brand pickers use the same template browser modal as Create; saved brand list matches Brand page (`brand-templates` and hyperframes share the same `custom_*.json` + `brand_system` catalog).

- Post copy Generate with AI uses the YouTube channel name; `Source: Channel clip` is stripped and no longer prompted.
- Heuristic clip titles skip opening Arabic/liturgical clauses so Metadata is not “Warfal hujub” / first-dua fragments.
- HyperFrames captions sit above grain/vignette texture (`z-index: 220`).
- Review card sizing restored to original layout: inbox uses `sm:2` / `xl:3` grid (full column width); batch page uses `22rem` columns; review content width back to `1180px`.
- Review Editor Look tab: template preview uses the HyperFrames video preview player (API returns MP4, not a static image); preview only when a new preset/brand is selected; clearer preset vs brand copy and link to Templates.
- Create clip: source overlay on rendered shorts now uses the resolved YouTube channel name (`Source: …`) instead of the placeholder `Source: Channel clip` when Shell → Source is enabled.
- Brand Builder: saved watermark and Identity fields persist when reopening a template (removed legacy filter that reset “Nourbit” watermarks to “Brand Clips”; Update merges into the existing `custom_*.json`).
- Brand Builder render: intro and subscribe (CTA) beats no longer overlap — recipe intro overlay exits before the social card enters; CTA hold is clamped to ~2s on short and long clips.
- Brand Builder: live preview now sequences intro, caption, and subscribe windows (approximate); Rendered tab is labeled exact timing.
- Brand Builder: empty social logo uses channel initials instead of the default HeyGen avatar on render.
- Brand Builder: X Post Card CTA deferred (hidden from Subscribe picker; saved `x-post` values normalize to None; vendored composition kept as experimental).
- Brand Builder render: portrait social CTAs (`tiktok-follow`, `instagram-follow`) now composite at full native canvas (1080×1920) instead of a shrunk bottom strip, so the follow card is visible on 9:16 renders.
- Brand Builder render: OSS composition files (`compositions/tiktok-follow.html`, etc.) are now copied into the preview project before HyperFrames render — previously the HTML referenced blocks that 404'd during capture.
- Brand Builder render: social CTA blocks use inspect-safe slide offsets and hide inactive button labels so HyperFrames layout check no longer fails on `clipped_text` / `text_box_overflow`.
- Brand Builder Identity: optional **Social CTA** fields — username/handle, follower count, and profile logo — customize TikTok/Instagram/YouTube subscribe widgets on render.
- Create/Generate: `curation_source` is now persisted on `generation_jobs` for post-run auditing; CLI copy includes `--profile`, `--source-id`, and `--niche`.
- Post copy: captions auto-enrich during curation when an LLM key exists, with workspace-aware prompts, per-platform length limits at publish, and heuristic fallback when the model fails.
- TikTok via Postiz: send `autoAddMusic` as `yes`/`no` (not boolean) so `/public/v1/posts` no longer returns HTTP 400.
- Schedule queue cards: denser layout — slot + title + compact destination chips; time editor and extra destinations stay collapsed; cooling-down is a short chip (`wait 12m`); Postiz errors are humanized instead of raw JSON.
- Schedule queue polls Postiz every 45s while the Schedule tab is open; Unschedule is blocked once any destination is live so a Facebook timeout cannot cancel a live YouTube post.
- Schedule/Postiz: reconcile treats Postiz posts with a `releaseURL` as live even when workflow `state` is still `ERROR` (common for Facebook Reels after Meta accepts the upload but Postiz times out).
- Schedule/Postiz: reconcile now calls `GET /posts` with required `startDate`/`endDate` (was empty without them), polls live state, and marks parent `published` when Postiz-backed destinations are live even if native Telegram/TikTok are still `pending`.
- Schedule/Postiz: loading Calendar polls Postiz post list and only marks a platform `live` (parent `published` when every routed dest is live) when Postiz says published; QUEUE still held in Otonom; false greens roll back.
- Postiz sync keeps an existing calendar post when the slot is unchanged (on/off other accounts); stores Postiz post ids (cuid) instead of upload UUIDs so time edits can DELETE the old post instead of leaving a duplicate.

### Changed
- Brand Builder: Intro control is now **None** | **Template hook** | **YouTube lower-third (open)**; Brand Studio preview render bumped to 8s (contract v10).
- HyperFrames OSS catalog: official blocks and components (`yt-lower-third`, `tiktok-follow`, captions, grain/vignette/shimmer) are vendored under `media-engine/render/hyperframes/compositions/` and wired into renders via `data-composition-src` — no more `brand-social-pill` placeholder CTAs.
- Brand Builder: Finishing pickers list **installed** OSS catalog items; texture effects support multi-select; optional extra overlay blocks (up to 3); transition no-op dropdown removed.
- HyperFrames catalog API is derived from the vendored `oss-manifest.json` (only installed items are selectable).
- HyperFrames templates: template overlays now enter, drift, and exit on a GSAP lifecycle instead of staying frozen; Brand Studio uses short hook overlays (not duplicate caption text).
- Brand Builder: one-line captions with a hugging plate; Recipe Sample removed from the stage; product-facing copy.
- Brand Builder: inspector reorganized into Presets, Identity, Captions, and Finishing tabs; stage toolbar split into canvas controls and playback tiers; outro CTA decoupled from captions with explicit None option; shimmer sweep removed from live preview.

### Added
- Create: selecting a saved brand with Visual **Auto** uses that brand’s Builder preset recipe (`brand_system.starter_template`) and sets `brand_system_template_id` for Review re-renders (including workspace brands not listed in the public template gallery).
- Review Editor (short clips): **Look** inspector tab to pick a saved brand template and **Re-render** with new overlays/CTA while keeping captions and trim.
- Brand Builder: live compositor on sample stock footage with Identity overlay; optional Recipe sample (gallery MP4) and **Render 5s look** brand-aware HyperFrames draft with cache.
- Brand Builder: Recipe vs Brand overlay stage modes so Identity captions no longer stack on baked-in recipe video; HUD and render chips stay off the phone.
- Create: **Auto** default for Content Angles (per-clip LLM angle selection); genre pack label shown in Advanced.
- Create: visual template picker moved above Advanced (template-first); Templates gallery adds text search; browse modal shows template status badges.
- Review card ⋯ menu: compact actions below the preview; Schedule / Publish / Reschedule / Republish open a destination dialog instead of overlaying the video.
- Published clips can **Reschedule** (new slot) or **Republish** (new Postiz delivery; live posts stay up).
- Review grid: each batch/single card shows Jakarta activity datetime; default sort is newest first with a Newest/Oldest toggle.
- Waiting pool and Review card ⋯ menu: pick a custom datetime (or Next 09:00 / Next 19:30) before the first schedule.
- Schedule queue cards: edit slot time (09:00 / 19:30 shortcuts), per-item **Publish now**, optional destination chips, and Postiz `type: schedule` calendar mirror so mapped channels appear before air time. Due-worker skips platforms already on Postiz (#93).
- Create clips: YouTube transcript **pre-flight** on source resolve (CC available / missing / disabled badge), humanized errors when captions are absent, and **Transcribe from audio** curation fallback via Whisper when YouTube has no subtitles (#90).
- Contextual Caption AI Polish: multi-word niche phrase glossary, LLM semantic reconstruction with timestamp re-alignment, and one-click **AI Polish** in the Review Editor for short clips.
- `POST /api/caption-polish` endpoint to run glossary + LLM caption cleanup on existing clip captions.

### Changed
- Review: removed redundant **Repair** filter tab (`held` clips stay in **Review** with a Captions unusable badge); header and grid re-centered with a stable 3-column layout.
- Review **Published** / **Scheduled** tabs no longer group clips into source-batch tiles — each clip gets its own card with the correct status badge and preview.
- Production caption pipeline now runs phrase glossary correction and full LLM reconstruction (when `llm_provider` is set) before caption grouping.
- ASR initial prompt includes domain vocabulary hints per niche pack (devotional, tech & finance).

### Added
- Review **Quick Approve** on queue cards (no Editor) plus **batch Approve** via selection or **Approve all** on source batch pages.
- Niche-aware clip scoring (Devotional, Tech & Finance, General) with viral/hook/retention/ASR breakdown; Brand → Advanced autonomy panel exposes **minimum score** slider and **grace period**; Review cards and Inspector show score badges and auto-qualification status against your threshold.
- Review **batch actions**: multi-select clips via **Select** mode in Review (ungrouped cards) and source batch headers, then **Delete** via `POST /api/delete-candidates` (#86) or **Re-render** via `POST /api/batch-rerender`; cards show a re-rendering overlay with progress while jobs are queued or running.
- Clip hook titles: auto metadata enrichment before render/insert when an LLM key is available; improved heuristic fallbacks from transcript clauses; Review **Auto hook** badge when title/subtitle came from span heuristics; manual **Re-render** in Review editor (header + Metadata tab) and **Refresh & re-render** after metadata update (#87).
- **Make shorts** from approved long-form in Review: one-click handoff to `clip_batch` (local file) or Create `generation_jobs` (published YouTube URL) without re-pasting links (#85).
- YouTube long-form publish target (**YouTube Video**) for landscape 16:9 clips: Review → Schedule → Publish via `videos.insert` with the same YouTube OAuth as Shorts; vertical-only targets are hidden/blocked for long-form (#84).
- Clip recipe overlays now fill named slots (`kicker`, `headline`, `subhead`, `stamp`, `line_a`, `line_b`) from the clip hook (and LLM overlay JSON when ranking is on) instead of gallery dummy copy (#82). Template gallery preview cache bumped to `PREVIEW_CONTRACT_VERSION=3`.

### Changed
- Clip scoring now uses a **two-layer model**: **Performance score** (hook, pacing, niche resonance, context payoff) ranks social potential; **Hygiene gate** (pass / needs attention / hold) tracks caption, boundary, and rights readiness separately. Review cards show both badges; full autonomy requires hygiene pass.
- `npm run dev` from `apps/dashboard` starts media engine + dashboard (same as repo root); use `npm run dev:next` for Next.js only.

### Fixed
- Karaoke captions no longer slide onto the next sentence after silence-trim when Whisper skips the opening; hybrid YouTube text maps through the trim timeline (or is skipped); low-confidence ASR cannot be replaced with an unrelated CC token; LLM reconstruct keeps spoken wording instead of title synonyms; `caption_sync_score` now reflects first-word gap (#91).
- Clip batch generation no longer aborts the whole job when one HyperFrames render fails; successful clips still land in Review and failed clips are marked `failed` with readable layout errors.
- `story_handwritten` template overlay text is constrained and auto-fit to the canvas so long hooks no longer fail HyperFrames inspect.
- Generation job errors now surface human-readable HyperFrames layout messages instead of truncated JSON (`hyperframes inspect failed: {`).
- Review manual re-render reuses timed captions from the last render contract (or regenerates from audio when missing) instead of failing with a caption-source CLI hint.
- Review re-render preserves the original HyperFrames template/format from the last render contract instead of re-resolving `auto` (which could switch recipes).
- Hook overlay on re-render now follows refreshed `title_hook` instead of stale `overlay_slots` from the first curation pass; caption karaoke timing is pulled earlier when the first word starts noticeably after t=0.
- Caption burn-in no longer lags minutes into the clip when stored captions use absolute source timestamps: render/re-render rebases to clip-zero (same rule as Review preview) and auto-regenerates captions when the timeline no longer matches the trimmed source file.
- HyperFrames re-render no longer trips the default 10-minute FFmpeg streaming timeout on slow local encodes; batch re-renders are serialized so clips do not compete for CPU/Chrome.
- Template-only karaoke captions use a 48px size (40–50 band) with stroke plus a caption card so they stay readable on talking-head footage and in the Review 9:16 preview (#83).
- Clip render sharpness (#81): YouTube section download prefers ≥720p and retries if the file is below 720p **or unscored**; HD format strings no longer fall through to 360p progressive in the same `-f`; Review cards show a `{n}p source` badge when the mezzanine is below 720p. Restart the engine and generate a new batch — old 360p artifacts stay blurry.
- YouTube clip generate no longer stops on `Requested format is not available` after the first HD client fails; it falls through to the `android` progressive client (works when YouTube SABR blocks `android_vr` CDN URLs).
- YouTube source clips prefer default yt-dlp clients (visionos/tv DASH) for ≥720p instead of `android_vr`/`android`, which YouTube now gates behind a GVS PO token and otherwise only serve 360p. Deno/Node are put on PATH so n-challenge solving can run.
- Intel Brief (`techtalk_intel_brief`) is **long-form only** (`long_16_9`): hidden from short template gallery/picker and excluded from Auto-by-niche on short clip generate; Explainer/long-form paths unchanged.

- Multi-tenant template catalog: builtin `techtalk_intel_brief` label neutralized to **Intel Brief** (id + aliases unchanged); workspace default stays in `profiles/techtalk_style.json`.
- Template gallery previews: background prewarm on server start/template list; status API exposes `renderer_ready`; UI falls back to recipe overlay with "Recipe preview" instead of infinite loading when HyperFrames is off or prewarm fails.
- Intel Brief (`techtalk_intel_brief`) preview render: move recipe `motion_extra` CSS into the style block (fixes HyperFrames lint `invalid_inline_script_syntax`).
- Create UX: clarify visual template vs captions/watermark — rename default style to **Platform default**, collapse single-option brand picker, link to Brand tab; align Advanced card radii with clip-length tiles (`rounded-2xl`).
- Delete saved brand styles (#79): remove `profiles/custom_*.json` and matching `brand:custom_*` catalog entries from Brand and Templates with confirm; Create config resets when the active style is deleted.
- Optional shell layers (#78): each recipe defines default hook/watermark/source/CTA toggles; renderer omits disabled nodes; Create Advanced exposes per-batch overrides; generation jobs pass `shell_components` through CLI → style → contract.
- Template gallery previews: drop shared shell hook/brand/CTA/source chrome and generic fixture copy; recipe overlay + niche captions only; stale preview cache auto-regenerates (`PREVIEW_CONTRACT_VERSION=2`).
- Templates UX: remove internal “HF render” badge from style previews; detail modal copy uses “sample clip” instead of HyperFrames jargon; grid cards show compact `9:16` format badge; fix nested-button hydration on template cards.
- Per-template distinct visuals (#77): renderer shell hook/CTA/watermark styling delegated to recipe modules; dashboard preview loading uses a subtle bottom bar so recipe mocks stay readable; all 20 template overlays have distinct caption mocks; preview dummy copy varies by niche category.
- Auto speech-language detection (#75): Whisper defaults to **auto** (detect from audio); workspace niche only shapes YouTube transcript fallback order. Create Advanced still lets operators pin `id` / `en` / `ar` / `ms`.
- Hybrid caption quality (#76): glossary and LLM polish follow workspace genre pack (devotional vs tech/finance vs general); YouTube token replacement uses anchor/length guards so high-confidence Whisper words are not overwritten by misaligned cues.
- Template catalog QA (#3): built-in previews expose cache-ready status; uncached/brand styles show a generating state instead of a frozen modal; recipe overlays/themes polished for TechTalk + spot-check templates. Sanity: `python3 -m unittest tests.test_hyperframes_templates tests.test_hyperframes_previews`.
- Create content angles are a **universal industry set** (#74): story / advice / opinion / explainer / commentary / history / tutorial. Niche and brand voice come from the workspace profile in the curation prompt — no custom chips, no kajian-only catalog.
- Create clip count is a **maximum** (#73): curation no longer fails when the LLM finds fewer than N valid windows; remaining slots fill from the heuristic scorer. Create copy says “fewer clips still succeed”; timestamps like `1:23` parse.
- Create double-submit guard (#72): Slide to Generate locks synchronously on confirm and stays disabled while a batch is queued/running, so one slide cannot spawn twin jobs.
- YouTube clip download: retry alternate player clients/formats on HTTP 403; optional `MEDIA_ENGINE_YTDLP_COOKIES`; Create failure message names YouTube block instead of bare `ffmpeg exited with code 8`.
- Production captions (#71): generate default is **YouTube + Whisper** (`hybrid` is real — YT text on Whisper timings, glossary, then LLM polish on uncertain tokens only). Review stays Approve/skip; no per-word editor loop.
- Caption gate (#70): typical Whisper doubt no longer holds every clip (old ≤4 uncertain-word cap). Review is Approve/skip; `held` only for unusable captions. Existing false holds reconcile on the next Review load.

- Review gallery preview audio (#68): Play on Review/batch cards starts with sound; mute toggle on the thumbnail; starting another card pauses the previous one.
- Local dashboard default port is `3100` (#67) so it can run next to Postiz on `:3000` / `:4200`; override with `DASHBOARD_PORT`. Media engine stays on `8765`.
- Review source batch page (#65): multi-clip sources open `/review/batch/[sourceId]`; inbox uses a staggered (masonry) grid so 9:16 clips and 16:9 batch/long-form cards pack without gaps; Editor back returns to the batch; singles stay flat.
- Review queue Delete + Editor back (#62): quiet ⋯ on gallery card media (top-right) for delete (confirm → `delete-candidate`); Editor back always returns to `/?section=review` (dirty leave still confirms).
- Review groups multi-clip batches by source (#58): shared `source_id` shows a collapsible header (title/thumb/count/progress); single-clip results stay flat cards; Create per-video ids from #59 enable grouping.
- Create YouTube validate + metadata (#59): debounced `/api/resolve-source` via yt-dlp shows title/channel/duration/thumbnail before generate; invalid links block Slide to Generate; soft duration warnings; metadata stored on the generation job for Review groups (#58).
- Brand Advanced autonomy labels (#54): Off / Assisted / Full auto with short help text; Advanced summary drops `.json` path basename.
- Templates copy/CTA (#53): “Styles ready” language (no Template engine); **Use in Create** is the only primary CTA; Inspect demoted to View details / Details; card badges use friendly status labels.
- SaaS UX finish (#22): Home reframed as weekly Create→Review→Schedule→Publish loop (no Command Center / Continue Pipeline); Create Advanced keeps product controls and buries CLI/model under Developer options; Schedule recovery tools demoted; Explainer hybrid plan under Labs; sidebar Loop/More groups + mobile 4+More nav; quieter workspace manage copy.
- Workspace switcher placement (#50): move switch + Manage into the desktop sidebar under the product mark; mobile keeps a compact header control; remove the cramped Guided Studio OS breadcrumb above section titles.
- Brand library page polish (#48): drop competing HyperFrames hero panel; quieter Brand kit header; keep Starter preset cards; clearer Saved styles + demoted autonomy.
- Brand Studio closed loop (#48): reopen restores `brand_system` Effects; Update overwrites the same custom file; post-save **Use in Create** handoff; saved brand templates expose `brand_template_path` + starter recipe for HyperFrames; Create auto-wires style path; render uses style watermark/font/stroke/plate plus texture/CTA stubs.
- Brand Studio SaaS polish (#48): Identity / Style / Effects IA; tokenized chrome with editable template name; Effects as quiet inspector rows; baseline under Advanced.
- Brand Studio Effects live stubs (#48): caption style / texture / CTA / intro flash / transition micro-anim update the stage as approximate previews; starter recipe stays a small panel reference (not stacked on canvas).
- Create clips polish (#44): Generate batch is primary; Watch sources quieter and lower in the same `max-w-4xl` column; workspace display name (no “Workspace workspace”); `1 clip` pluralization; human failed-run copy; CLI moved under Advanced.
- Publish connect-first UX (#42): OAuth platforms show **Connect account** as the primary CTA; Telegram opens a connect dialog for bot token + channel; quieter cards; Auto publish only after connect; sidebar is logs-only.
- Publish destinations UI: fixed workspace hydrate race that left Publish empty (0/0) while the sidebar showed 0/4; sync now waits for the stored workspace and Load destinations re-fetches/seeds rows.
- Channels empty fix (#39): new workspaces and empty `workspace` profiles auto-seed Telegram / YouTube Shorts / Facebook Reels / TikTok publish destinations; Create says “Watch YouTube sources”, sidebar/publish says “Publish accounts”.
- Workspace CRUD in dashboard (#36): **Manage** next to the workspace switcher creates / renames / deletes workspaces via API (`POST /api/profiles`, `/api/profile-update`, `/api/profile-delete`). Built-in `nourbit` and `workspace` cannot be deleted; custom workspaces need slide-confirm and `force` when clips/schedule/channels remain. Create initializes an empty credential vault for that profile.
- Workspace-scoped publish credentials (#34): Facebook/YouTube/TikTok/Telegram account tokens live in a per-profile vault under `media-engine/data/credentials/` (gitignored); OAuth connect/disconnect and live publish resolve the active workspace. Existing `.env.local` account keys migrate once into `nourbit`.
- Watch channel → auto-clip → autonomy schedule (#32): add a YouTube channel once, poll for new uploads, enqueue clip jobs, apply `off`/`assisted`/`full` autonomy, and enforce per-account posts/day delivery caps with a workspace switcher (`nourbit` / `workspace`).
- Channel watcher worker: `python -m media_engine.cli watch-poll` and `scripts/run_watch_poll_worker.sh` for background polling.
- Batch Remove Pauses (#31): short-form right rail **Silence** tool sets a gap threshold in seconds, previews match count, then batch-compresses those pauses (caption remap + keep plan + re-render) without replacing per-chip Remove Pause.
- Remove Pause A/V cut fix (#29): keep plans use the current source/caption timeline (not the original YouTube span), clamp to source duration, and HyperFrames `durationMs` follows the trimmed media so exports no longer pad leftover silence.
- Remove Pause preview refresh (#29): short-form editor-context now surfaces async re-render jobs so the stage shows Rendering…, polls to completion, refreshes clip data, and reloads the preview video (cache-busted).
- Remove Pause UX fix (#29): Pause chip menu no longer vanishes on rail scroll; menu uses fixed positioning with Seek / Remove, and Remove status shows in the Captions rail.
- Remove Pause (#29): Pause chips open Seek / Remove actions; Remove compresses that silence window, retimes captions/words, and queues a short-form re-render with the pending keep plan (burn-in cue bridges stay intact).
- Karaoke word highlight (#30): Captions rail follows the spoken word during preview playback with an Opus-style cyan chip (solid pill behind the active word); falls back to cue highlight when word timings are missing or copy is dirty.
- Auto-trim silence on short-form render (#28): source clips drop leading/trailing dead-air and compress long internal pauses before captions/render; diagnostics land on `render_quality.silence_trim`.
- Interactive Captions document (#27): short-form Captions rail keeps continuous copy, adds playhead-synced cue highlight, floating selection toolbar (Play/Pause + Seek), and Pause chips from **word-level** gaps (cue windows stay bridged for burn-in).
- SaaS dashboard UX (#22): Create and Long Video now center one primary task with contextual progress and secondary history/operator controls; Review is a one-interaction preview gallery with a dedicated `/review/[clipId]` editing workspace.
- Studio workspace polish (#22): Review Editor now uses a preview-first inspector/timeline layout; Templates, Channels, Schedule, Brand Builder, mobile navigation, and contextual activity surfaces follow a focused SaaS hierarchy.
- AI Scene Editor reconstruction (#22): Review now opens a full-width three-pane production workspace with real Explainer scene-plan add/edit/reorder/delete APIs, atomic save and full-render handoff, capability-aware short/imported-long-form finishing tools, dirty-leave and approval gates, responsive scene/transcript navigation, a contextual inspector, and an explicit Save → Render → Approve command flow.
- Editor visual polish (#22): Script/Captions rail is now a HeyGen-style numbered text list without bordered cards; editor chrome uses the dashboard canvas tokens and quieter inspector/timeline surfaces.
- Inline script editing (#22): Scene and caption text can be typed directly in the Script/Captions rail, with type/duration and add/duplicate/reorder/delete actions on each block.
- Editor save & script flow (#22): one command-bar Save covers script/captions/post copy; confirmations kept only for discard-dirty and delete; Script/Captions reads as continuous numbered paragraphs.
- Continuous captions (#22): short-form Captions rail is one paragraph document; timed cues keep their windows and words redistribute on Save.
- OpusClip-familiar editor chrome (#26): header Save changes + Approve, center stage, right icon tool rail with collapsible detail panel, and always-visible bottom timeline synced to script/captions.
- Editor visual system (#26): Review Editor chrome now uses the same surface cards, cyan CTAs, rounded-full actions, and eyebrow labels as Brand Builder / dashboard sections.
- Editor canvas vibe (#26): bordered panel cards removed; workspace reads as one continuous canvas with quiet hairline dividers and a floating preview stage.
- Canvas tool docks (#26): top/left/right/bottom chrome are floating glass docks (gradient fades + soft chips) instead of bordered dashboard toolbars.
- Long-form canvas polish (#26): Explainer/imported long-form uses quieter script document selection, wider 16:9 floating stage, and a softer scene timeline strip.
- Resizable script rail (#26): left Captions/Script dock defaults wider and can be dragged (300–560px); width persists in localStorage.
- Verified Create → Generate queues HTTP 202 without FK/lock; failed jobs now surface actionable CLI errors (not bare exit codes); Next proxy only says “offline” on true connection failures (#2).
- Path A control loop (#21): dashboard **Generate via Cursor** → Automation webhook / Cloud Agents API → poll until `FINISHED` → local `ingest_longform` → Telegram status (no public URL).
- Path A: ingest HeyGen/long-form MP4 into Review via `POST /api/ingest-longform`, Otonom MCP `ingest_longform`, and Explainer dashboard form (`review_only` + optional `clip_batch`).
- Path B scaffold: `heygen_client.py` Video Agent Direct API helpers + MCP tools (API wallet; dry-run supported). Docs: `docs/heygen-paths.md`.
- Explainer non-avatar visuals v2: multi-layer TechTalk motion cards (staggered reveals, distinct text vs broll data stage) as the FFmpeg happy path.
- Explainer non-avatar narration: mux Sahibul NF VO onto text/broll via `import_narration_audio` (Creator avatar-proxy extract; `create_speech` needs API credits).
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
