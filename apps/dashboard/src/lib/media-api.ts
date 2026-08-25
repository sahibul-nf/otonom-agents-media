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
    viral_score?: number;
    hook_score?: number;
    context_score?: number;
    caption_confidence?: number;
    retention_score?: number;
    asr_confidence?: number;
  };
  quality_gate?: {
    passed?: boolean;
    review_deadline_at?: string;
    checks?: Record<string, boolean>;
    scores?: Record<string, number>;
    settings?: Record<string, unknown>;
  };
  review_deadline_at?: string;
  caption_corrections?: {
    correction_count?: number;
    low_confidence_word_count?: number;
    manual_edit?: boolean;
    edited_caption_count?: number;
    edited_captions?: CaptionSegment[];
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
    renderer?: string;
    caption_source?: string;
  };
  curation_metadata?: Record<string, unknown>;
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

export type EditorContext = {
  candidate_id: string;
  capability: EditorCapability;
  can_edit_scenes: boolean;
  can_trim: boolean;
  can_rerender: boolean;
  render?: EditorRender;
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
  platforms: Record<string, {ready: boolean; required_keys: string[]; missing_keys: string[]}>;
  settings: {
    nourbit_daily_content_cap: string;
    nourbit_default_publish_mode: string;
    comment_automation_enabled: string;
    comment_automation_mode: string;
  };
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
    cta_overlay?: string;
    texture_effect?: string;
    transition_family?: string;
    motion_intensity?: string;
  };
};

export type BrandTemplate = {
  id: string;
  label: string;
  path: string;
  has_brand_system?: string;
};

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
  status: "production-ready" | "beta" | "experimental" | string;
  best_for: string;
};

export type HyperframesCatalog = {
  version: string;
  items: HyperframesCatalogItem[];
  groups: Record<string, HyperframesCatalogItem[]>;
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
    renders?: unknown[];
    source_metadata?: SourceResolveResult;
  };
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
    tiktok: "TikTok",
    telegram_channel: "Telegram Channel",
  };
  return labels[platform] || platform;
}
