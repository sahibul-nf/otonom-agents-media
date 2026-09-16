import type {ClipCandidate} from "@/lib/media-api";

const CLEARED_STATUSES = new Set(["approved", "scheduled", "ready_to_publish", "published"]);

export type ReviewSortOrder = "newest" | "oldest";

export type ReviewClipGroup = {
  key: string;
  sourceId: string;
  title: string;
  channel: string;
  thumbnailUrl: string;
  sourceUrl: string;
  clips: ClipCandidate[];
  /** Multi-clip batches get header chrome; singles stay flat cards. */
  showHeader: boolean;
  clearedCount: number;
  /** Latest clip activity timestamp (created/updated) for sorting and display. */
  activityAt: string | null;
};

export function clipActivityAt(clip: ClipCandidate): number {
  const raw = (clip.updated_at || clip.created_at || "").trim();
  const ms = Date.parse(raw);
  return Number.isNaN(ms) ? 0 : ms;
}

export function groupActivityAt(group: ReviewClipGroup): number {
  if (!group.clips.length) return 0;
  return Math.max(...group.clips.map(clipActivityAt));
}

export function latestClipActivityIso(clips: ClipCandidate[]): string | null {
  let latest = "";
  let latestMs = 0;
  for (const clip of clips) {
    const raw = (clip.updated_at || clip.created_at || "").trim();
    const ms = Date.parse(raw);
    if (!raw || Number.isNaN(ms)) continue;
    if (ms >= latestMs) {
      latestMs = ms;
      latest = raw;
    }
  }
  return latest || null;
}

export function formatReviewActivityAt(value: string | undefined | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("id-ID", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Jakarta",
  }).format(date);
}

export function sortReviewGroups(groups: ReviewClipGroup[], order: ReviewSortOrder): ReviewClipGroup[] {
  const sorted = [...groups];
  sorted.sort((left, right) => {
    const diff = groupActivityAt(right) - groupActivityAt(left);
    return order === "newest" ? diff : -diff;
  });
  return sorted;
}

function isGroupableSource(clip: ClipCandidate): boolean {
  if (clip.source?.groupable === false) return false;
  if (clip.source?.groupable === true) return true;
  const sourceId = (clip.source_id || clip.source?.id || "").trim();
  if (!sourceId) return false;
  if (sourceId === "workspace_source") return false;
  if (sourceId.endsWith("_source")) return false;
  return true;
}

export function reviewGroupKey(clip: ClipCandidate): string {
  if (!isGroupableSource(clip)) return `clip:${clip.id}`;
  return (clip.source_id || clip.source?.id || `clip:${clip.id}`).trim();
}

export function reviewBatchHref(sourceId: string) {
  return `/review/batch/${encodeURIComponent(sourceId)}`;
}

export function reviewEditorHref(clipId: string, sourceId?: string) {
  const base = `/review/${encodeURIComponent(clipId)}`;
  if (!sourceId) return base;
  const params = new URLSearchParams({from: "batch", sourceId});
  return `${base}?${params.toString()}`;
}

export function clipsForSourceId(clips: ClipCandidate[], sourceId: string): ClipCandidate[] {
  const target = sourceId.trim();
  if (!target) return [];
  return clips.filter((clip) => (clip.source_id || clip.source?.id || "").trim() === target);
}

export function groupFromClips(clips: ClipCandidate[], sourceId: string): ReviewClipGroup | null {
  const members = clipsForSourceId(clips, sourceId);
  if (!members.length) return null;
  const lead = members[0];
  const source = lead?.source;
  const title = (source?.title || "").trim() || lead?.title_hook || "Clip batch";
  const channel = (source?.channel || "").trim();
  const thumbnailUrl = (source?.thumbnail_url || "").trim();
  const sourceUrl = (source?.url || "").trim();
  const clearedCount = members.filter((clip) => CLEARED_STATUSES.has(clip.status)).length;
  return {
    key: sourceId,
    sourceId,
    title,
    channel,
    thumbnailUrl,
    sourceUrl,
    clips: members,
    showHeader: members.length > 1,
    clearedCount,
    activityAt: latestClipActivityIso(members),
  };
}

function flatReviewGroups(clips: ClipCandidate[]): ReviewClipGroup[] {
  return clips.map((clip) => {
    const source = clip.source;
    const title = (source?.title || "").trim() || clip.title_hook || "Clip";
    const channel = (source?.channel || "").trim();
    const thumbnailUrl = (source?.thumbnail_url || "").trim();
    const sourceUrl = (source?.url || "").trim();
    return {
      key: `clip:${clip.id}`,
      sourceId: (clip.source_id || source?.id || clip.id).trim(),
      title,
      channel,
      thumbnailUrl,
      sourceUrl,
      clips: [clip],
      showHeader: false,
      clearedCount: CLEARED_STATUSES.has(clip.status) ? 1 : 0,
      activityAt: latestClipActivityIso([clip]),
    };
  });
}

/** Status tabs (Published / Scheduled) show one card per clip so badges and previews stay consistent. */
export function groupReviewClips(clips: ClipCandidate[], options?: {flatten?: boolean}): ReviewClipGroup[] {
  if (options?.flatten) return flatReviewGroups(clips);

  const order: string[] = [];
  const buckets = new Map<string, ClipCandidate[]>();

  for (const clip of clips) {
    const key = reviewGroupKey(clip);
    if (!buckets.has(key)) {
      buckets.set(key, []);
      order.push(key);
    }
    buckets.get(key)!.push(clip);
  }

  return order.map((key) => {
    const members = buckets.get(key) || [];
    const lead = members[0];
    const source = lead?.source;
    const title = (source?.title || "").trim() || lead?.title_hook || "Clip batch";
    const channel = (source?.channel || "").trim();
    const thumbnailUrl = (source?.thumbnail_url || "").trim();
    const sourceUrl = (source?.url || "").trim();
    const clearedCount = members.filter((clip) => CLEARED_STATUSES.has(clip.status)).length;
    return {
      key,
      sourceId: (lead?.source_id || source?.id || key).trim(),
      title,
      channel,
      thumbnailUrl,
      sourceUrl,
      clips: members,
      showHeader: members.length > 1,
      clearedCount,
      activityAt: latestClipActivityIso(members),
    };
  });
}

export function reviewStatusTone(status: string) {
  if (["approved", "published", "ready", "rendered", "scheduled", "ready_to_publish", "completed", "pending_auto_schedule"].includes(status)) {
    return "text-teal border-teal/[0.30] bg-teal/[0.10]";
  }
  if (["running", "queued", "starting", "triggering", "polling", "ingesting", "rendering", "planned"].includes(status)) {
    return "text-cyan border-cyan/[0.30] bg-teal/[0.10]";
  }
  if (["failed", "rejected"].includes(status)) return "text-danger border-danger/[0.30] bg-danger/[0.10]";
  if (["held"].includes(status)) return "text-warning border-warning/[0.30] bg-warning/[0.10]";
  if (["cooldown"].includes(status)) return "text-zinc-300 border-white/[0.14] bg-white/[0.04]";
  return "text-warning border-warning/[0.30] bg-warning/[0.10]";
}
