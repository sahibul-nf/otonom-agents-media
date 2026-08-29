"use client";

import Link from "next/link";
import {ArrowUpRight, Layers} from "lucide-react";
import {ReviewQueueCard} from "@/components/review/ReviewQueueCard";
import {reviewBatchHref, type ReviewClipGroup} from "@/lib/review-groups";

export function ReviewSourceGroup({
  group,
  statusTone,
  actionStates,
  onDelete,
  onMakeShorts,
  selectableIds,
  selectedIds,
  selectionMode = false,
  onToggleSelect,
}: {
  group: ReviewClipGroup;
  statusTone: (status: string) => string;
  actionStates?: Record<string, {status: "running" | "done" | "failed"; message: string}>;
  onDelete?: (clip: ReviewClipGroup["clips"][number]) => void;
  onMakeShorts?: (clip: ReviewClipGroup["clips"][number]) => void;
  selectableIds?: Set<string>;
  selectedIds?: Set<string>;
  selectionMode?: boolean;
  onToggleSelect?: (clipId: string) => void;
}) {
  if (!group.showHeader) {
    const clip = group.clips[0];
    if (!clip) return null;
    const selectable = Boolean(selectableIds?.has(clip.id));
    return (
      <ReviewQueueCard
        clip={clip}
        statusTone={statusTone}
        deleting={actionStates?.[`clip:${clip.id}:delete`]?.status === "running"}
        onDelete={onDelete}
        onMakeShorts={onMakeShorts}
        selectable={selectable}
        selectionMode={selectionMode}
        selected={Boolean(selectedIds?.has(clip.id))}
        onToggleSelect={selectable ? () => onToggleSelect?.(clip.id) : undefined}
      />
    );
  }

  const total = group.clips.length;
  const progressLabel = `${group.clearedCount}/${total} cleared`;
  const href = reviewBatchHref(group.sourceId);

  return (
    <Link
      href={href}
      className="group/batch block w-full min-w-0 rounded-[24px] border border-white/[0.08] bg-surface p-3 transition duration-200 hover:-translate-y-0.5 hover:border-cyan/[0.20] hover:shadow-glow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan motion-reduce:transform-none motion-reduce:transition-none"
    >
      <div className="relative aspect-video overflow-hidden rounded-[16px] border border-white/[0.06] bg-canvas-deep">
        {group.thumbnailUrl ? (
          // External YouTube thumbs; next/image remote allowlist not required for this cosmetic.
          // eslint-disable-next-line @next/next/no-img-element
          <img src={group.thumbnailUrl} alt="" className="h-full w-full object-cover" />
        ) : (
          <div className="grid h-full w-full place-items-center text-zinc-600">
            <Layers className="h-8 w-8" />
          </div>
        )}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/70 via-black/15 to-transparent" />
        <span className="pointer-events-none absolute bottom-3 left-3 z-[1] rounded-full bg-black/65 px-2.5 py-1 text-[11px] font-semibold text-white backdrop-blur-md">
          {total} clips
        </span>
        <span className="pointer-events-none absolute right-3 top-3 z-[1] rounded-full border border-white/15 bg-black/45 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-white/90 backdrop-blur-md">
          Batch
        </span>
      </div>

      <div className="px-1 pb-1 pt-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="line-clamp-2 text-sm font-semibold leading-5 text-white transition-colors group-hover/batch:text-cyan">{group.title}</h3>
            <p className="mt-1.5 truncate text-[11px] text-zinc-500">
              {group.channel ? `${group.channel} · ` : ""}
              {progressLabel}
            </p>
            <span className="mt-2 inline-flex rounded-full border border-cyan/[0.25] bg-cyan/[0.08] px-2.5 py-1 text-[10px] font-semibold text-cyan">
              Source batch
            </span>
          </div>
          <span className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded-full border border-white/[0.10] bg-white/[0.04] px-3 text-xs font-semibold text-zinc-200 transition group-hover/batch:border-cyan/[0.30] group-hover/batch:text-cyan">
            Open <ArrowUpRight className="h-3.5 w-3.5" />
          </span>
        </div>
      </div>
    </Link>
  );
}
