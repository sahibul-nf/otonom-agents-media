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

/** Group legacy clips that share a YouTube video but have generic `*_source` ids. */
export function youtubeVideoGroupKey(clip: ClipCandidate): string | null {
  const url = (clip.source?.url || "").trim();
  if (!url) return null;
  const match = url.match(/(?:[?&]v=|youtu\.be\/|\/shorts\/|\/embed\/)([\w-]{11})/i);
  return match ? `yt:${match[1]}` : null;
}

export function reviewGroupKey(clip: ClipCandidate): string {
  const ytKey = youtubeVideoGroupKey(clip);
  if (ytKey) return ytKey;
  if (isGroupableSource(clip)) {
    return (clip.source_id || clip.source?.id || `clip:${clip.id}`).trim();
  }
  return `clip:${clip.id}`;
}

function isGenericBatchTitle(title: string): boolean {
  const normalized = title.trim().toLowerCase();
  if (!normalized || normalized === "clip batch") return true;
  return normalized.includes("youtube.com/watch") || normalized === "youtube.com";
}

/** Title, thumb, and URL when generation job metadata is missing on the lead clip. */
export function resolveGroupCosmetics(members: ClipCandidate[], _groupKey: string) {
  const lead = members[0];
  const source = lead?.source;
  let title = (source?.title || "").trim() || lead?.title_hook || "Clip batch";
  let channel = (source?.channel || "").trim();
  let thumbnailUrl = (source?.thumbnail_url || "").trim();
  let sourceUrl = (source?.url || "").trim();

  for (const clip of members) {
    const clipSource = clip.source;
    if (!channel && clipSource?.channel) channel = clipSource.channel.trim();
    if (!thumbnailUrl && clipSource?.thumbnail_url) thumbnailUrl = clipSource.thumbnail_url.trim();
    if (!sourceUrl && clipSource?.url) sourceUrl = clipSource.url.trim();
    const clipTitle = (clipSource?.title || "").trim();
    if (isGenericBatchTitle(title) && clipTitle && !isGenericBatchTitle(clipTitle)) {
      title = clipTitle;
    }
  }

  if (isGenericBatchTitle(title)) {
    const hook = members.find((clip) => (clip.title_hook || "").trim())?.title_hook;
    if (hook) title = hook.trim();
  }

  return {title, channel, thumbnailUrl, sourceUrl};
}

export function reviewBatchHref(sourceId: string) {
  return `/review/batch/${encodeURIComponent(sourceId)}`;
}

export function clipMatchesReviewGroupKey(clip: ClipCandidate, groupKey: string): boolean {
  const key = groupKey.trim();
  if (!key) return false;
  if (key.startsWith("yt:")) return youtubeVideoGroupKey(clip) === key;
  if (key.startsWith("clip:")) return `clip:${clip.id}` === key;
  return (clip.source_id || clip.source?.id || "").trim() === key;
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
  return clips.filter((clip) => clipMatchesReviewGroupKey(clip, target));
}

export function groupFromClips(clips: ClipCandidate[], sourceId: string): ReviewClipGroup | null {
  const members = clipsForSourceId(clips, sourceId);
  if (!members.length) return null;
  const cosmetics = resolveGroupCosmetics(members, sourceId);
  const clearedCount = members.filter((clip) => CLEARED_STATUSES.has(clip.status)).length;
  return {
    key: sourceId,
    sourceId,
    title: cosmetics.title,
    channel: cosmetics.channel,
    thumbnailUrl: cosmetics.thumbnailUrl,
    sourceUrl: cosmetics.sourceUrl,
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
    const cosmetics = resolveGroupCosmetics(members, key);
    const clearedCount = members.filter((clip) => CLEARED_STATUSES.has(clip.status)).length;
    const sourceId = key.startsWith("yt:") ? key : (lead?.source_id || source?.id || key).trim();
    return {
      key,
      sourceId,
      title: cosmetics.title,
      channel: cosmetics.channel,
      thumbnailUrl: cosmetics.thumbnailUrl,
      sourceUrl: cosmetics.sourceUrl,
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
