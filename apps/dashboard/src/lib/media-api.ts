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
  status: ClipStatus;
  title_hook: string;
  viral_reason: string;
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
  };
  cost?: {
    estimated_total?: number;
    llm_provider?: string;
    renderer?: string;
    caption_source?: string;
  };
  curation_metadata?: Record<string, unknown>;
};

export type PublishTarget = {
  id: number;
  profile_id: string;
  platform: string;
  account_label: string;
  mode: string;
  require_approval: number;
  ai_disclosure_required: number;
  daily_cap: number;
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
  layout?: Record<string, string>;
  caption?: Record<string, string | number | boolean | Record<string, string | number | boolean>>;
  brand?: Record<string, string | number | boolean>;
  ai?: Record<string, string | number | boolean>;
  overlay?: Record<string, string | number | boolean>;
};

export type BrandTemplate = {
  id: string;
  label: string;
  path: string;
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

export type GenerationJob = {
  id: string;
  profile_id: string;
  source_url: string;
  count: number;
  clip_length_preset: string;
  clip_min_seconds?: number;
  clip_max_seconds?: number;
  genres?: string[];
  brand_template: string;
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
  result?: {count?: number; renders?: unknown[]};
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
