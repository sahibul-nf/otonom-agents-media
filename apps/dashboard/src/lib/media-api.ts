export type ClipStatus = "draft" | "rendered" | "approved" | "scheduled" | "ready_to_publish" | "published" | "failed" | "archived" | string;

export type CaptionWord = {
  text: string;
  startMs?: number;
  endMs?: number;
  confidence?: number | null;
};

export type CaptionSegment = {
  text: string;
  startMs: number;
  endMs: number;
  timestampMs?: number;
  confidence?: number | null;
  words?: CaptionWord[];
};

export type CaptionPolishResult = {
  candidate_id: string;
  status: string;
  captions: CaptionSegment[];
  caption_corrections?: ClipCandidate["caption_corrections"];
  pipeline?: Record<string, unknown>;
};

export type ClipCandidate = {
  id: string;
  profile_id?: string;
  source_id?: string;
  source?: {
    id: string;
    url?: string;
    title?: string;
    channel?: string;
    thumbnail_url?: string;
    groupable?: boolean;
  };
  status: ClipStatus;
  title_hook: string;
  hook_subtitle?: string;
  viral_reason: string;
  transcript_span: string;
  start_ms: number;
  end_ms: number;
  caption_source?: string;
  output_path?: string;
  post_caption?: string;
  score?: {
    overall_score?: number;
    performance_score?: number;
    viral_score?: number;
    hook_score?: number;
    pacing_score?: number;
    resonance_score?: number;
    context_score?: number;
    caption_confidence?: number;
    retention_score?: number;
    asr_confidence?: number;
    hygiene_gate?: "pass" | "needs_attention" | "hold";
    hygiene_flags?: string[];
  };
  quality_gate?: {
    passed?: boolean;
    auto_qualified?: boolean;
    review_deadline_at?: string;
    hold_reason?: string;
    hygiene_gate?: "pass" | "needs_attention" | "hold";
    hygiene_flags?: string[];
    checks?: Record<string, boolean>;
    scores?: Record<string, number>;
    thresholds?: Record<string, number>;
    settings?: {
      autonomy_mode?: string;
      review_grace_hours?: number;
      auto_schedule_enabled?: boolean | number;
      overall_threshold?: number;
      hook_threshold?: number;
      caption_threshold?: number;
      boundary_threshold?: number;
    };
  };
  review_deadline_at?: string;
  caption_corrections?: {
    correction_count?: number;
    low_confidence_word_count?: number;
    manual_edit?: boolean;
    edited_caption_count?: number;
    edited_captions?: CaptionSegment[];
    caption_source?: string;
    detected_language?: string;
    speech_language?: string;
    ai_polish?: boolean;
    llm?: {
      llm_reconstructed?: boolean;
      llm_error?: boolean;
      llm_skipped?: boolean;
      llm_rejected_ungrounded?: boolean;
      llm_output_preview?: string;
    };
    ai_polish_pipeline?: {llm?: Record<string, unknown>};
    youtube?: {used?: boolean; youtube_replaced?: number; youtube_skipped?: number};
  };
  asr_metadata?: {
    engine?: string;
    model?: string;
    language?: string;
    detected_language?: string;
    caption_pipeline?: {llm?: Record<string, unknown>};
  };
  captions?: CaptionSegment[];
  render_metadata?: {
    sourceUrl?: string;
    sourceAttribution?: string;
    captions?: CaptionSegment[];
  };
  render_quality?: {
    quality_score?: number;
    duration_ms?: number;
    caption_coverage?: number;
    caption_overlap_count?: number;
    output_path?: string;
    renderer?: string;
    source_height?: number;
  };
  cost?: {
    estimated_total?: number;
    llm_provider?: string;
    llm_cost?: number;
    renderer?: string;
    caption_source?: string;
  };
  curation_metadata?: Record<string, unknown>;
  delivery_orientation?: "landscape" | "portrait";
  rerender_job?: {
    id: string;
    status: string;
    progress?: number;
    message?: string;
    error?: string;
  };
  created_at?: string;
  updated_at?: string;
};

export type EditorCapability = "scene" | "short" | "imported_longform";

export type ExplainerSceneType = "avatar" | "text" | "broll";

export type ExplainerScene = {
  id: string;
  type: ExplainerSceneType;
  duration_target: number;
  script?: string;
  headline?: string;
  narration?: string;
  template?: string;
  clip_file?: string;
  audio_file?: string;
};

export type ExplainerScenePlan = {
  title: string;
  scenes: ExplainerScene[];
};

export type EditorJob = {
  job_id: string;
  status: string;
  error?: string;
  progress?: number;
  message?: string;
  hyperframes_template?: string;
};

export type EditorRender = {
  status: string;
  error?: string;
};

export type EditorLook = {
  hyperframes_template: string;
  brand_system_template_id: string;
  brand_template_path: string;
  label: string;
};

export type EditorContext = {
  candidate_id: string;
  capability: EditorCapability;
  can_edit_scenes: boolean;
  can_trim: boolean;
  can_rerender: boolean;
  render?: EditorRender;
  look?: EditorLook;
  plan?: ExplainerScenePlan;
  job?: EditorJob;
};

export type SaveScenePlanResponse = EditorContext & {
  rerender_started?: boolean;
};

/** Long-form 16:9 candidates (Explainer stitch or Path A HeyGen/MP4 ingest). */
export function isExplainerClip(clip?: ClipCandidate | null): boolean {
  if (!clip) return false;
  if (clip.caption_source === "explainer" || clip.caption_source === "ingest_longform") return true;
  const kind = clip.curation_metadata?.kind;
  if (kind === "explainer" || kind === "longform_ingest") return true;
  if (typeof clip.curation_metadata?.job_id === "string" && String(clip.id || "").startsWith("cand_expl_")) return true;
  return String(clip.render_quality?.renderer || "") === "explainer_stitch" || String(clip.render_quality?.renderer || "") === "ingest_longform";
}

export type PublishTarget = {
  id: number;
  profile_id: string;
  platform: string;
  account_label: string;
  mode: string;
  require_approval: number | boolean;
  ai_disclosure_required: number | boolean;
  daily_cap: number;
  enabled?: number | boolean;
};

export type MediaProfile = {
  id: string;
  name: string;
  niche?: string;
  languages?: string[];
  default_render_preset?: string;
  cta_text?: string;
  watermark_text?: string;
  created_at?: string;
  protected?: boolean;
};

export type WatchChannel = {
  id: string;
  profile_id: string;
  channel_url: string;
  label: string;
  permission_status: string;
  enabled: boolean;
  poll_interval_minutes: number;
  last_polled_at?: string;
  last_seen_video_id?: string;
  last_new_video_id?: string;
  last_new_video_at?: string;
  last_clip_job_id?: string;
  last_error?: string;
  generation_defaults?: Record<string, unknown>;
};

export type CredentialStatus = {
  platforms: Record<
    string,
    {
      ready: boolean;
      unavailable?: boolean;
      unavailable_reason?: string;
      required_keys: string[];
      missing_keys: string[];
      backend?: string;
      postiz_integration_id?: string;
      postiz_integration_name?: string;
    }
  >;
  postiz?: {
    connected: boolean;
    api_url: string;
    api_origin?: string;
    channels?: Record<string, {id: string; name?: string; identifier?: string}>;
  };
  llm?: Record<string, {ready?: boolean; key_env?: string}>;
  vault?: {has_secrets?: boolean; secret_keys?: string[]};
  settings: {
    nourbit_daily_content_cap: string;
    nourbit_default_publish_mode: string;
    comment_automation_enabled: string;
    comment_automation_mode: string;
  };
};

export type PostizIntegration = {
  id: string;
  name: string;
  identifier?: string;
  disabled?: boolean;
};

export type StyleProfile = {
  id?: string;
  label?: string;
  layout?: Record<string, string>;
  caption?: Record<string, string | number | boolean | Record<string, string | number | boolean>>;
  brand?: Record<string, string | number | boolean>;
  ai?: Record<string, string | number | boolean>;
  overlay?: Record<string, string | number | boolean>;
  brand_system?: {
    starter_template?: string;
    caption_style?: string;
    intro_layout?: string;
    intro_block?: string;
    cta_overlay?: string;
    texture_effect?: string;
    texture_effects?: string[];
    extra_blocks?: string[];
    transition_family?: string;
    motion_intensity?: string;
  };
};

export type BrandTemplate = {
  id: string;
  label: string;
  path: string;
  has_brand_system?: string;
  brand_system_template_id?: string;
};

/** Saved brand kits for UI — canonical list from `brand-templates`, enriched from hyperframes when available. */
export function savedBrandKitsForUi(
  hyperframes: HyperframesTemplate[],
  brandLibrary: BrandTemplate[],
): HyperframesTemplate[] {
  const byId = new Map(hyperframes.filter((item) => item.source === "brand_system").map((item) => [item.id, item]));
  const kits: HyperframesTemplate[] = [];
  for (const brand of brandLibrary) {
    if (brand.has_brand_system !== "1") continue;
    const id = (brand.brand_system_template_id || "").trim();
    if (!id) continue;
    const existing = byId.get(id);
    if (existing) {
      kits.push(existing);
      continue;
    }
    kits.push({
      id,
      label: brand.label,
      category: "Brand",
      best_for: "Saved brand system template for reusable HyperFrames production.",
      effects: [],
      caption_style: "Brand captions",
      default_genres: [],
      status: "ready",
      tone: "Brand",
      source: "brand_system",
      formats: ["short_9_16", "long_16_9"],
      brand_template_path: brand.path,
    });
  }
  return kits;
}

/** Fill gaps when the media engine has not been restarted after brand saves. */
export function mergeBrandTemplatesIntoHyperframes(
  templates: HyperframesTemplate[],
  brands: BrandTemplate[],
): HyperframesTemplate[] {
  const byId = new Map(templates.map((item) => [item.id, item]));
  for (const brand of brands) {
    if (brand.has_brand_system !== "1") continue;
    const id = (brand.brand_system_template_id || "").trim();
    if (!id || byId.has(id)) continue;
    byId.set(id, {
      id,
      label: brand.label,
      category: "Brand",
      best_for: "Saved brand system template for reusable HyperFrames production.",
      effects: [],
      caption_style: "Brand captions",
      default_genres: [],
      status: "ready",
      tone: "Brand",
      source: "brand_system",
      formats: ["short_9_16", "long_16_9"],
      brand_template_path: brand.path,
    });
  }
  return [...byId.values()];
}

export type ShellComponents = {
  hook: boolean;
  watermark: boolean;
  source: boolean;
  cta: boolean;
};

export const DEFAULT_SHELL_COMPONENTS: ShellComponents = {
  hook: false,
  watermark: true,
  source: false,
  cta: true,
};

export const TEMPLATE_ONLY_BRAND = "auto";

export function isTemplateOnlyBrand(
  path: string,
  legacyDefaultPath = "profiles/default_workspace_style.json",
): boolean {
  const normalized = String(path || "").trim().toLowerCase();
  return (
    !normalized ||
    normalized === TEMPLATE_ONLY_BRAND ||
    normalized === "template" ||
    normalized === "none" ||
    path === legacyDefaultPath
  );
}

export function templateSupportsFormat(template: HyperframesTemplate, hyperframesFormat: string): boolean {
  const resolved = hyperframesFormat === "long_16_9" ? "long_16_9" : "short_9_16";
  const formats = template.formats?.length ? template.formats : ["short_9_16", "long_16_9"];
  return formats.includes(resolved);
}

export type HyperframesTemplate = {
  id: string;
  label: string;
  category: string;
  best_for: string;
  effects: string[];
  caption_style: string;
  default_genres: string[];
  status: string;
  tone: string;
  source?: string;
  formats?: string[];
  components_used?: string[];
  blocks_used?: string[];
  brand_template_path?: string;
  starter_template?: string;
  preview_seconds?: number;
  preview_status?: string;
  preview_cache_ready?: Record<string, boolean>;
  preview_urls?: Record<string, string>;
  preview_video_urls?: Record<string, string>;
  production_checks?: Record<string, string>;
  recipe_module?: string;
  preview_source_video?: string;
  preview_source_url?: string;
  font_family?: string;
  motion_preset?: string;
  color_grade?: string;
  shell_components?: ShellComponents;
};

export type HyperframesCatalogItem = {
  id: string;
  label: string;
  kind: "example" | "block" | "component" | string;
  category: string;
  oss_section?: string;
  status: "production-ready" | "beta" | "experimental" | string;
  best_for: string;
  lifecycle?: string;
  slot?: string;
  installed?: boolean;
};

export type HyperframesCatalog = {
  version: string;
  items: HyperframesCatalogItem[];
  installed_items?: string[];
  groups: Record<string, HyperframesCatalogItem[]>;
  oss_groups?: Record<string, HyperframesCatalogItem[]>;
  oss_sections?: string[];
  status_policy: Record<string, string>;
};

export type DurationPreset = {
  id: string;
  label: string;
  min_ms: number;
  target_ms: number;
  max_ms: number;
  range_label: string;
  detail: string;
  intent: string;
  best_for: string;
};

export type GenreOption = {
  id: string;
  label: string;
  description: string;
};

export type GenreCatalog = {
  pack: string;
  pack_label: string;
  defaults: string[];
  options: GenreOption[];
};

export function parseGenreCatalog(payload: GenreCatalog | GenreOption[] | null | undefined): GenreCatalog {
  if (Array.isArray(payload)) {
    const options = payload.filter((item) => item && item.id);
    return {
      pack: "general",
      pack_label: "General",
      defaults: options.slice(0, 3).map((item) => item.id),
      options,
    };
  }
  if (payload && Array.isArray(payload.options)) {
    return {
      pack: payload.pack || "general",
      pack_label: payload.pack_label || "General",
      defaults: payload.defaults?.length ? payload.defaults : payload.options.slice(0, 3).map((item) => item.id),
      options: payload.options,
    };
  }
  return {
    pack: "general",
    pack_label: "General",
    defaults: ["story", "advice", "social_commentary"],
    options: [],
  };
}

export type TranscriptProbeResult = {
  status: "available" | "missing" | "disabled" | "restricted" | "unknown";
  message: string;
  languages?: string[];
  requested_languages?: string[];
};

export type SourceResolveResult = {
  ok: boolean;
  provider?: string;
  video_id?: string;
  title?: string;
  channel?: string;
  duration_seconds?: number | null;
  thumbnail_url?: string;
  canonical_url?: string;
  source_url?: string;
  warnings?: string[];
  transcript?: TranscriptProbeResult;
  error?: string;
};

export type GenerationJob = {
  id: string;
  profile_id: string;
  source_url: string;
  source_id?: string;
  count: number;
  clip_length_preset: string;
  clip_min_seconds?: number;
  clip_max_seconds?: number;
  genres?: string[];
  brand_template: string;
  hyperframes_template?: string;
  brand_system_template_id?: string;
  hyperframes_format?: string;
  renderer: string;
  quality: string;
  caption_source: string;
  asr_model: string;
  speech_language?: string;
  transcript_languages?: string;
  llm_provider: string;
  status: string;
  progress: number;
  command: string;
  log_text: string;
  error: string;
  created_at: string;
  updated_at: string;
  result?: {
    count?: number;
    considered?: number;
    passed?: number;
    floor?: number;
    stage?: string;
    candidates?: ShortlistCandidate[];
    renders?: unknown[];
    source_metadata?: SourceResolveResult;
  };
};

export type ShortlistCandidate = {
  id: string;
  title_hook?: string;
  hook_subtitle?: string;
  viral_reason?: string;
  transcript_excerpt?: string;
  start_ms?: number;
  end_ms?: number;
  content_angle?: string;
  editorial_score?: number;
  editorial_source?: string;
};

export type AngleRecommendation = {
  id: string;
  label: string;
  reason: string;
};

export type RerenderJob = {
  id: string;
  candidate_id: string;
  renderer: string;
  quality: string;
  style_path: string;
  status: string;
  progress: number;
  message: string;
  error: string;
  result?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type EngineHealth = {
  hyperframes: {
    enabled: boolean;
    ready: boolean;
    reason?: string;
    package?: string;
    node?: {ok: boolean; version: string; minimum: string};
    ffmpeg?: {ok: boolean; path: string};
    hyperframes?: {ok: boolean; version: string; doctor_ok?: boolean | null; doctor_output?: string};
  };
};

export type ScheduledPost = {
  id: string;
  candidate_id: string;
  profile_id: string;
  scheduled_at: string;
  status: string;
  publish_mode: string;
  platforms: string[];
  platform_results?: Record<string, {status?: string; error?: string; remote_id?: string; remote_url?: string; reason?: string}>;
  published_at?: string;
  last_error?: string;
  title_hook: string;
  viral_reason: string;
  candidate_status: string;
  output_path?: string;
};

export type PublishAttempt = {
  id: string;
  candidate_id: string;
  platform: string;
  mode: string;
  status: string;
  error: string;
  payload?: Record<string, unknown>;
  created_at: string;
};

export type AutonomySettings = {
  profile_id: string;
  autonomy_mode: "off" | "assisted" | "full" | string;
  review_grace_hours: number;
  auto_schedule_enabled: number;
  overall_threshold: number;
  hook_threshold: number;
  caption_threshold: number;
  boundary_threshold: number;
};

export type ExplainerJob = {
  job_id: string;
  profile_id?: string;
  topic?: string;
  status: string;
  plan_path?: string;
  fixtures_dir?: string;
  hyperframes_template?: string;
  candidate_id?: string | null;
  output_path?: string | null;
  error?: string;
  scene_count?: number;
  avatar_scene_count?: number;
  duration_seconds?: number;
};

export type PathAJob = {
  job_id: string;
  profile_id?: string;
  topic?: string;
  title?: string;
  status: string;
  error?: string;
  agent_id?: string;
  run_id?: string;
  agent_url?: string;
  video_url?: string;
  candidate_ids?: string[];
  ingest_job_id?: string;
  telegram_notified?: boolean;
  cursor_run_status?: string;
  trigger_mode?: string;
};

export function apiPath(path: string) {
  return `/api/media/${path.replace(/^\//, "")}`;
}

async function readJsonResponse(response: Response) {
  const text = await response.text();
  if (!text.trim()) {
    throw new Error(`Empty response from media API (${response.status})`);
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`Invalid JSON from media API (${response.status})`);
  }
}

export async function fetchHyperframesTemplatesWithBrands(): Promise<{
  templates: HyperframesTemplate[];
  brandLibrary: BrandTemplate[];
}> {
  const [templates, brands] = await Promise.all([
    apiGet<HyperframesTemplate[]>("hyperframes-templates"),
    apiGet<BrandTemplate[]>("brand-templates"),
  ]);
  return {templates: mergeBrandTemplatesIntoHyperframes(templates, brands), brandLibrary: brands};
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(apiPath(path), {cache: "no-store"});
  const json = await readJsonResponse(response);
  if (!response.ok) throw new Error(json.error || "Request failed");
  return json as T;
}

export async function apiPost<T>(path: string, payload: Record<string, unknown>): Promise<T> {
  const response = await fetch(apiPath(path), {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  const json = await readJsonResponse(response);
  if (!response.ok) throw new Error(json.error || "Request failed");
  return json as T;
}

export type HyperframesPreviewStatus = {
  template: string;
  format: string;
  ready: boolean;
  renderer_ready?: boolean;
  unavailable_reason?: string;
  path?: string;
  size?: number;
};

export async function fetchHyperframesPreviewStatus(templateId: string, format: string): Promise<HyperframesPreviewStatus> {
  const safeId = encodeURIComponent(templateId.replace(":", "__"));
  return apiGet<HyperframesPreviewStatus>(`hyperframes-template-preview-status?template=${safeId}&format=${encodeURIComponent(format)}`);
}

export async function prewarmHyperframesTemplatePreview(templateId: string, includeBrand = false): Promise<void> {
  await apiPost("hyperframes-template-preview-prewarm", {
    template_id: templateId,
    include_brand: includeBrand,
  });
}

export type BrandStudioPreviewStatus = {
  cache_key: string;
  format: string;
  ready: boolean;
  renderer_ready?: boolean;
  unavailable_reason?: string;
  preview_url?: string;
  path?: string;
  size?: number;
  cached?: boolean;
};

export function hyperframesTemplateStockUrl(
  template: Pick<HyperframesTemplate, "id" | "preview_source_url">,
  hyperframesFormat: "short_9_16" | "long_16_9" = "short_9_16",
): string | null {
  if (template.preview_source_url) {
    if (template.preview_source_url.includes("format=")) return template.preview_source_url;
    return `${template.preview_source_url}&format=${encodeURIComponent(hyperframesFormat)}`;
  }
  if (!template.id) return null;
  const safeId = encodeURIComponent(template.id.replace(":", "__"));
  return apiPath(`hyperframes-template-stock?template=${safeId}&format=${encodeURIComponent(hyperframesFormat)}`);
}

export function brandAssetUrl(assetPath: string): string {
  return apiPath(`brand-asset?path=${encodeURIComponent(assetPath)}`);
}

export async function requestBrandStudioPreviewRender(payload: {
  starter_template: string;
  hyperframes_format: string;
  sample_phrase: string;
  style: Record<string, unknown>;
  brand_system: Record<string, unknown>;
}): Promise<BrandStudioPreviewStatus> {
  return apiPost<BrandStudioPreviewStatus>("brand-studio-preview-render", payload);
}

export function formatDuration(ms?: number) {
  if (!ms) return "-";
  const seconds = Math.round(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

export function formatTimestamp(ms: number) {
  const total = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  return [hours, minutes, seconds].map((part) => String(part).padStart(2, "0")).join(":");
}

export function scoreValue(value?: number) {
  return typeof value === "number" ? value : "-";
}

export function platformLabel(platform: string) {
  const labels: Record<string, string> = {
    facebook_reels: "Facebook Reels",
    youtube_shorts: "YouTube Shorts",
    youtube_video: "YouTube Video",
    tiktok: "TikTok",
    telegram_channel: "Telegram Channel",
  };
  return labels[platform] || platform;
}

export function platformShortLabel(platform: string) {
  const labels: Record<string, string> = {
    facebook_reels: "Reels",
    youtube_shorts: "Shorts",
    youtube_video: "YouTube",
    tiktok: "TikTok",
    telegram_channel: "Telegram",
  };
  return labels[platform] || platformLabel(platform);
}

export function humanizePublishError(raw?: string) {
  const text = String(raw || "").trim();
  if (!text) return "";
  const lowered = text.toLowerCase();
  if (
    lowered.includes("invalid credentials")
    || lowered.includes("invalid_token")
    || lowered.includes("autherror")
    || (lowered.includes("youtube") && lowered.includes("reconnect"))
  ) {
    return "YouTube credentials expired. Reconnect YouTube in Postiz (Google OAuth), then retry.";
  }
  const jsonMatch = text.match(/\{[\s\S]*\}$/);
  if (jsonMatch) {
    try {
      const parsed = JSON.parse(jsonMatch[0]) as {message?: unknown};
      const message = parsed.message;
      if (Array.isArray(message) && message.length) {
        return String(message[0]);
      }
      if (typeof message === "string" && message.trim()) {
        return message.trim();
      }
    } catch {
      // keep original
    }
  }
  return text.replace(/^tiktok:\s*/i, "").replace(/^Postiz POST \S+ failed:\s*/i, "");
}

export function cleanPublishStatus(status?: string) {
  if (!status) return "Not run";
  const labels: Record<string, string> = {
    ready: "Ready",
    published: "Posted",
    live: "Live",
    accepted: "Sent to Postiz",
    failed: "Postiz error",
    blocked: "Needs action",
    legacy_blocked: "Outdated",
    skipped: "Already posted (verified)",
    publishing: "Publishing",
    pending: "Waiting",
    queued: "On Postiz calendar",
    cooldown: "Cooling down",
  };
  return labels[status] || status.replaceAll("_", " ");
}

export function publishStatusHint(
  status?: string,
  result?: {error?: string; reason?: string},
): string | undefined {
  switch (status) {
    case "cooldown":
      return "Paused ~12 min after a failed send. Wait, then Publish now again.";
    case "queued":
      return "On Postiz calendar — will post at the scheduled slot unless you Publish now.";
    case "skipped":
      return result?.reason || "Already verified live on this platform.";
    case "failed":
    case "blocked":
      return result?.error || result?.reason || undefined;
    default:
      return result?.error || result?.reason || undefined;
  }
}

const PORTRAIT_ONLY_PLATFORMS = new Set(["youtube_shorts", "facebook_reels", "tiktok"]);
const LANDSCAPE_ONLY_PLATFORMS = new Set(["youtube_video"]);

export function clipDeliveryOrientation(clip?: ClipCandidate | null): "landscape" | "portrait" {
  if (clip?.delivery_orientation === "landscape" || clip?.delivery_orientation === "portrait") {
    return clip.delivery_orientation;
  }
  if (isExplainerClip(clip)) return "landscape";
  return "portrait";
}

export function platformMatchesClipOrientation(platform: string, clip?: ClipCandidate | null): boolean {
  const orientation = clipDeliveryOrientation(clip);
  if (orientation === "landscape") return !PORTRAIT_ONLY_PLATFORMS.has(platform);
  return !LANDSCAPE_ONLY_PLATFORMS.has(platform);
}

export function filterPlatformsForClip(platforms: string[], clip?: ClipCandidate | null): string[] {
  return platforms.filter((platform) => platformMatchesClipOrientation(platform, clip));
}

/** Landscape long-form clips that can enqueue shorts without pasting a URL again. */
export function canMakeShortsFromClip(clip?: ClipCandidate | null): boolean {
  return isExplainerClip(clip);
}

export type MakeShortsFromLongformResult = {
  ok: boolean;
  route: "generation_job" | "clip_batch";
  parent_candidate_id: string;
  generation_job_id?: string;
  candidate_ids?: string[];
  source_url?: string;
  source_id?: string;
  message: string;
};

export type DeleteCandidatesResult = {
  deleted_ids: string[];
  failed: {id: string; error: string}[];
  artifacts_removed?: string[];
};

export type BatchRerenderResult = {
  queued: {candidate_id: string; job_id: string; status: string}[];
  skipped: {id: string; error: string}[];
  failed: {id: string; error: string}[];
};

export type BatchApproveResult = {
  approved_ids: string[];
  skipped: {id: string; error: string}[];
  failed: {id: string; error: string}[];
};

const QUICK_APPROVE_STATUSES = new Set(["rendered", "pending_auto_schedule"]);

export function canQuickApproveClip(clip: ClipCandidate): boolean {
  if (isClipRerendering(clip)) return false;
  return QUICK_APPROVE_STATUSES.has(clip.status);
}

export function canBatchRerenderClip(clip: ClipCandidate): boolean {
  if (clip.status === "published") return false;
  if (clip.caption_source === "ingest_longform") return false;
  const kind = clip.curation_metadata?.kind;
  if (kind === "explainer" || kind === "longform_ingest") return false;
  return true;
}

export function isClipRerendering(clip: ClipCandidate): boolean {
  const status = clip.rerender_job?.status;
  return status === "queued" || status === "running";
}

export function clipOverallScore(clip: ClipCandidate): number | null {
  const score =
    clip.score?.performance_score ??
    clip.score?.overall_score ??
    clip.quality_gate?.scores?.performance ??
    clip.quality_gate?.scores?.overall;
  return typeof score === "number" ? score : null;
}

export function clipHygieneGate(clip: ClipCandidate): "pass" | "needs_attention" | "hold" | null {
  const gate = clip.quality_gate?.hygiene_gate ?? clip.score?.hygiene_gate;
  if (gate === "pass" || gate === "needs_attention" || gate === "hold") return gate;
  return null;
}

export function clipHygieneFlags(clip: ClipCandidate): string[] {
  const flags = clip.quality_gate?.hygiene_flags ?? clip.score?.hygiene_flags;
  return Array.isArray(flags) ? flags.map(String) : [];
}

export function clipHygieneLabel(gate: "pass" | "needs_attention" | "hold" | null): string {
  if (gate === "pass") return "Hygiene pass";
  if (gate === "needs_attention") return "Needs attention";
  if (gate === "hold") return "Hygiene hold";
  return "Hygiene unknown";
}

export function clipHygieneTone(gate: "pass" | "needs_attention" | "hold" | null): string {
  if (gate === "pass") return "border-teal/[0.35] bg-teal/[0.12] text-teal";
  if (gate === "needs_attention") return "border-amber-400/30 bg-amber-500/10 text-amber-100";
  if (gate === "hold") return "border-danger/35 bg-danger/[0.12] text-danger";
  return "border-white/[0.10] bg-white/[0.04] text-zinc-300";
}

export function clipAutonomyThreshold(clip: ClipCandidate, fallback = 80): number {
  return clip.quality_gate?.thresholds?.overall ?? clip.quality_gate?.settings?.overall_threshold ?? fallback;
}

export function clipMeetsAutonomyThreshold(clip: ClipCandidate, fallbackThreshold = 80): boolean {
  const overall = clipOverallScore(clip);
  if (overall == null) return false;
  if (clip.quality_gate?.auto_qualified) return true;
  if (clip.quality_gate?.passed) return true;
  return overall >= clipAutonomyThreshold(clip, fallbackThreshold);
}
