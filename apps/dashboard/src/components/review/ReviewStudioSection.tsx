"use client";

import {AlertTriangle, ArrowDownUp} from "lucide-react";
import {useEffect, useMemo, useState} from "react";
import {ReviewMasonry} from "@/components/review/ReviewMasonry";
import {ReviewSelectionChrome} from "@/components/review/ReviewSelectionChrome";
import {ReviewSourceGroup} from "@/components/review/ReviewSourceGroup";
import type {ClipCandidate} from "@/lib/media-api";
import {groupReviewClips, sortReviewGroups, type ReviewSortOrder} from "@/lib/review-groups";
import {useReviewSelection} from "@/lib/use-review-selection";

type ReviewFilter = {
  id: string;
  label: string;
  hint: string;
  statuses: readonly string[];
};

type ActionUiState = {status: "running" | "done" | "failed"; message: string};

export type ReviewStudioSectionProps = {
  clips: ClipCandidate[];
  filter: string;
  showPublished: boolean;
  selectionResetKey: string;
  reviewFilters: readonly ReviewFilter[];
  actionStates: Record<string, ActionUiState>;
  setFilter: (value: string) => void;
  setShowPublished: (value: boolean) => void;
  statusTone: (status: string) => string;
  onClear: () => void;
  onDeleteClip: (clip: ClipCandidate) => void;
  onApproveClip?: (clip: ClipCandidate) => void;
  onDeleteSelected: (candidateIds: string[]) => void;
  onApproveSelected?: (candidateIds: string[]) => void;
  onRerenderSelected?: (candidateIds: string[]) => void;
  onMakeShorts?: (clip: ClipCandidate) => void;
  onScheduleClip?: (clip: ClipCandidate, scheduledAt: string, platforms: string[]) => void;
  onPublishClipNow?: (clip: ClipCandidate, platforms: string[], options?: {republish?: boolean}) => void;
  publishTargets?: string[];
  defaultPublishPlatforms?: (clip: ClipCandidate) => string[];
};

export function ReviewStudioSection({
  clips,
  filter,
  showPublished,
  selectionResetKey,
  reviewFilters,
  actionStates,
  setFilter,
  setShowPublished,
  onClear,
  onDeleteClip,
  onApproveClip,
  onDeleteSelected,
  onApproveSelected,
  onRerenderSelected,
  onMakeShorts,
  onScheduleClip,
  onPublishClipNow,
  publishTargets,
  defaultPublishPlatforms,
  statusTone,
}: ReviewStudioSectionProps) {
  const clearState = actionStates["queue:clear"];
  const batchDeleteState = actionStates["review:batch-delete"];
  const batchRerenderState = actionStates["review:batch-rerender"];
  const batchApproveState = actionStates["review:batch-approve"];
  const [selectionMode, setSelectionMode] = useState(false);
  const [sortOrder, setSortOrder] = useState<ReviewSortOrder>("newest");
  const flattenGroups = filter === "published" || filter === "scheduled";
  const groups = useMemo(
    () => sortReviewGroups(groupReviewClips(clips, {flatten: flattenGroups}), sortOrder),
    [clips, flattenGroups, sortOrder],
  );
  const batchCount = useMemo(() => groups.filter((group) => group.showHeader).length, [groups]);
  const selectableIds = useMemo(
    () => groups.filter((group) => !group.showHeader).flatMap((group) => group.clips.map((clip) => clip.id)),
    [groups],
  );
  const selection = useReviewSelection(selectableIds, selectionResetKey);
  const selectableSet = useMemo(() => new Set(selectableIds), [selectableIds]);

  useEffect(() => {
    setSelectionMode(false);
  }, [selectionResetKey]);

  function exitSelectionMode() {
    setSelectionMode(false);
    selection.clearSelection();
  }

  return (
    <section className="grid w-full gap-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
          <p className="text-sm leading-6 text-zinc-400">Open a batch to review siblings from one source, or edit a single clip.</p>
          <p className="mt-1 text-xs font-medium text-zinc-600">
            {clips.length} result{clips.length === 1 ? "" : "s"} in this view
            {!flattenGroups && batchCount ? ` · ${batchCount} source batch${batchCount === 1 ? "" : "es"}` : ""}
          </p>
          </div>
        <div className="flex max-w-full items-center gap-2 overflow-x-auto pb-1">
          {reviewFilters.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setFilter(item.id)}
              aria-pressed={filter === item.id}
              title={item.hint}
              className={`h-9 shrink-0 rounded-full px-3.5 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan ${filter === item.id ? "bg-cyan text-ink" : "border border-white/[0.08] bg-surface text-zinc-400 hover:text-white"}`}
            >
              {item.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setSortOrder((order) => (order === "newest" ? "oldest" : "newest"))}
            title={sortOrder === "newest" ? "Showing newest first — click for oldest first" : "Showing oldest first — click for newest first"}
            className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full border border-white/[0.08] bg-surface px-3 text-xs font-semibold text-zinc-400 transition hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan"
          >
            <ArrowDownUp className="h-3.5 w-3.5" />
            {sortOrder === "newest" ? "Newest" : "Oldest"}
          </button>
          {!selectionMode ? (
            <ReviewSelectionChrome
              active={false}
              selectedCount={0}
              totalSelectable={selectableIds.length}
              allSelected={false}
              onEnter={() => setSelectionMode(true)}
              onExit={exitSelectionMode}
              onToggleAll={() => undefined}
              onDeleteSelected={() => undefined}
            />
          ) : null}
        </div>
      </div>
      {selectionMode ? (
        <ReviewSelectionChrome
          active
          selectedCount={selection.selectedCount}
          totalSelectable={selectableIds.length}
          allSelected={selection.allSelected}
          deleting={batchDeleteState?.status === "running"}
          rerendering={batchRerenderState?.status === "running"}
          approving={batchApproveState?.status === "running"}
          onEnter={() => setSelectionMode(true)}
          onExit={exitSelectionMode}
          onToggleAll={() => (selection.allSelected ? selection.clearSelection() : selection.selectAll())}
          onDeleteSelected={() => onDeleteSelected(Array.from(selection.selectedIds))}
          onApproveSelected={onApproveSelected ? () => onApproveSelected(Array.from(selection.selectedIds)) : undefined}
          onRerenderSelected={
            onRerenderSelected ? () => onRerenderSelected(Array.from(selection.selectedIds)) : undefined
          }
        />
      ) : null}
      {clips.length ? (
        <ReviewMasonry>
          {groups.map((group) => (
            <ReviewSourceGroup
              key={group.key}
              group={group}
              statusTone={statusTone}
              actionStates={actionStates}
              onDelete={onDeleteClip}
              onApprove={onApproveClip}
              onMakeShorts={onMakeShorts}
              onSchedule={onScheduleClip}
              onPublishNow={onPublishClipNow}
              publishTargets={publishTargets}
              defaultPublishPlatforms={defaultPublishPlatforms}
              selectableIds={selectableSet}
              selectedIds={selection.selectedIds}
              selectionMode={selectionMode}
              onToggleSelect={selection.toggle}
            />
          ))}
        </ReviewMasonry>
      ) : (
        <div className="grid min-h-[140px] place-items-center rounded-[22px] border border-dashed border-white/[0.10] bg-canvas-deep p-6 text-center text-sm text-zinc-500">
      <div>
        <AlertTriangle className="mx-auto mb-3 h-6 w-6 text-zinc-600" />
            No results in this view. Generate a batch or choose another filter.
          </div>
        </div>
      )}
      <details className="justify-self-end text-xs text-zinc-500">
        <summary className="cursor-pointer list-none rounded-full px-3 py-2 hover:text-zinc-300">Queue options</summary>
        <div className="mt-2 flex items-center gap-4 rounded-2xl border border-white/[0.08] bg-surface p-3">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={showPublished} onChange={(event) => setShowPublished(event.target.checked)} className="accent-cyan" />
            Show published
          </label>
          <button type="button" disabled={clearState?.status === "running"} onClick={onClear} className="font-semibold text-danger disabled:opacity-40">
            {clearState?.status === "running" ? "Clearing…" : "Clear queue"}
          </button>
        </div>
      </details>
    </section>
  );
}
