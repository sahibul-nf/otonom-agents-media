"use client";

import {ChevronDown} from "lucide-react";
import {ReviewQueueCard} from "@/components/review/ReviewQueueCard";
import type {ReviewClipGroup} from "@/lib/review-groups";

export function ReviewSourceGroup({
  group,
  statusTone,
  actionStates,
  onDelete,
}: {
  group: ReviewClipGroup;
  statusTone: (status: string) => string;
  actionStates?: Record<string, {status: "running" | "done" | "failed"; message: string}>;
  onDelete?: (clip: ReviewClipGroup["clips"][number]) => void;
}) {
  if (!group.showHeader) {
    const clip = group.clips[0];
    if (!clip) return null;
    return (
      <ReviewQueueCard
        clip={clip}
        statusTone={statusTone}
        deleting={actionStates?.[`clip:${clip.id}:delete`]?.status === "running"}
        onDelete={onDelete}
      />
    );
  }

  const total = group.clips.length;
  const progressLabel = `${group.clearedCount}/${total} cleared`;

  return (
    <details open className="group/batch col-span-full rounded-[28px] border border-white/[0.08] bg-black/20 p-3 sm:p-4">
      <summary className="flex cursor-pointer list-none items-start gap-3 rounded-[20px] px-1 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan [&::-webkit-details-marker]:hidden">
        <div className="relative h-14 w-14 shrink-0 overflow-hidden rounded-2xl border border-white/[0.08] bg-canvas-deep sm:h-16 sm:w-16">
          {group.thumbnailUrl ? (
            // External YouTube thumbs; next/image remote allowlist not required for this cosmetic.
            // eslint-disable-next-line @next/next/no-img-element
            <img src={group.thumbnailUrl} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="grid h-full w-full place-items-center text-[10px] font-semibold uppercase tracking-wider text-zinc-600">Src</div>
          )}
        </div>
        <div className="min-w-0 flex-1 pt-0.5">
          <p className="truncate text-sm font-semibold text-white sm:text-[15px]">{group.title}</p>
          <p className="mt-1 truncate text-xs text-zinc-500">
            {group.channel ? `${group.channel} · ` : ""}
            {total} clip{total === 1 ? "" : "s"} · {progressLabel}
          </p>
        </div>
        <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-zinc-500 transition-transform group-open/batch:rotate-180" aria-hidden />
      </summary>
      <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {group.clips.map((clip) => (
          <ReviewQueueCard
            key={clip.id}
            clip={clip}
            statusTone={statusTone}
            deleting={actionStates?.[`clip:${clip.id}:delete`]?.status === "running"}
            onDelete={onDelete}
          />
        ))}
      </div>
    </details>
  );
}
