export type ClipStatus = "draft" | "rendered" | "approved" | "scheduled" | "ready_to_publish" | "published" | "failed" | "archived" | string;

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
  caption?: Record<string, string | number | boolean>;
  overlay?: Record<string, string | number | boolean>;
};

export type BrandTemplate = {
  id: string;
  label: string;
  path: string;
};

export type GenerationJob = {
  id: string;
  profile_id: string;
  source_url: string;
  count: number;
  clip_length_preset: string;
  brand_template: string;
  renderer: string;
  quality: string;
  caption_source: string;
  asr_model: string;
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

export type ScheduledPost = {
  id: string;
  candidate_id: string;
  profile_id: string;
  scheduled_at: string;
  status: string;
  publish_mode: string;
  platforms: string[];
  title_hook: string;
  viral_reason: string;
  candidate_status: string;
  output_path?: string;
};

export function apiPath(path: string) {
  return `/api/media/${path.replace(/^\//, "")}`;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(apiPath(path), {cache: "no-store"});
  const json = await response.json();
  if (!response.ok) throw new Error(json.error || "Request failed");
  return json as T;
}

export async function apiPost<T>(path: string, payload: Record<string, unknown>): Promise<T> {
  const response = await fetch(apiPath(path), {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  const json = await response.json();
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
