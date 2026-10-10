"use client";

import {ArrowDownUp, Zap} from "lucide-react";
import {useEffect, useMemo, useState} from "react";
import {QuickTriageModal} from "@/components/review/QuickTriageModal";
import {ReviewMasonry} from "@/components/review/ReviewMasonry";
import {ReviewSelectionChrome} from "@/components/review/ReviewSelectionChrome";
import {ReviewSourceGroup} from "@/components/review/ReviewSourceGroup";
import {EmptyState} from "@/components/shared/StudioPrimitives";
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
  onOpenCreate?: () => void;
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
  onOpenCreate,
}: ReviewStudioSectionProps) {
  const clearState = actionStates["queue:clear"];
  const batchDeleteState = actionStates["review:batch-delete"];
  const batchRerenderState = actionStates["review:batch-rerender"];
  const batchApproveState = actionStates["review:batch-approve"];
  const [selectionMode, setSelectionMode] = useState(false);
  const [quickTriageOpen, setQuickTriageOpen] = useState(false);
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
    <section className="grid w-full gap-5" aria-labelledby="review-clips-lane">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-teal/30 bg-teal/10 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-teal">
          Clips
        </span>
        <h3 id="review-clips-lane" className="text-sm font-semibold text-zinc-200">
          Video clip candidates
        </h3>
      </div>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
          <p className="text-sm leading-6 text-text-secondary">Open a batch to review siblings from one source, or edit a single clip.</p>
          <p className="mt-1 text-xs font-medium text-text-tertiary">
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
          <button
            type="button"
            onClick={() => setQuickTriageOpen(true)}
            disabled={!clips.length}
            title="Fast keyboard triage cockpit (Space, A, D, J, K)"
            className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full border border-teal/40 bg-teal/10 px-3.5 text-xs font-semibold text-teal transition hover:bg-teal/20 hover:border-teal/60 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal"
          >
            <Zap className="h-3.5 w-3.5 fill-current" />
            <span>Quick Triage</span>
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
        <EmptyState
          tone="idle"
          title="Nothing in this view"
          text="Create a clip batch, or pick another filter to see approved and scheduled items."
          actionLabel={onOpenCreate ? "Go to Create" : undefined}
          onAction={onOpenCreate}
        />
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
      <QuickTriageModal
        isOpen={quickTriageOpen}
        onClose={() => setQuickTriageOpen(false)}
        clips={clips}
        onApproveClip={onApproveClip}
        onDeleteClip={onDeleteClip}
      />
    </section>
  );
}
