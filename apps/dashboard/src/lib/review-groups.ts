import type {ClipCandidate} from "@/lib/media-api";

const CLEARED_STATUSES = new Set(["approved", "scheduled", "ready_to_publish", "published"]);

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
};

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
  };
}

export function groupReviewClips(clips: ClipCandidate[]): ReviewClipGroup[] {
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
