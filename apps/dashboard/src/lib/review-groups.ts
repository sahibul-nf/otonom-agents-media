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
