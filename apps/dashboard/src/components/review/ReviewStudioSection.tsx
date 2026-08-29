"use client";

import {AlertTriangle} from "lucide-react";
import {useEffect, useMemo, useState} from "react";
import {ReviewSelectionChrome} from "@/components/review/ReviewSelectionChrome";
import {ReviewSourceGroup} from "@/components/review/ReviewSourceGroup";
import type {ClipCandidate} from "@/lib/media-api";
import {groupReviewClips} from "@/lib/review-groups";
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
  onDeleteSelected: (candidateIds: string[]) => void;
  onMakeShorts?: (clip: ClipCandidate) => void;
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
  onDeleteSelected,
  onMakeShorts,
  statusTone,
}: ReviewStudioSectionProps) {
  const clearState = actionStates["queue:clear"];
  const batchDeleteState = actionStates["review:batch-delete"];
  const [selectionMode, setSelectionMode] = useState(false);
  const groups = useMemo(() => groupReviewClips(clips), [clips]);
  const batchCount = groups.filter((group) => group.showHeader).length;
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
    <section className="mx-auto grid w-full max-w-[1180px] gap-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
          <p className="text-sm leading-6 text-zinc-400">Open a batch to review siblings from one source, or edit a single clip.</p>
          <p className="mt-1 text-xs font-medium text-zinc-600">
            {clips.length} result{clips.length === 1 ? "" : "s"} in this view
            {batchCount ? ` · ${batchCount} source batch${batchCount === 1 ? "" : "es"}` : ""}
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
          onEnter={() => setSelectionMode(true)}
          onExit={exitSelectionMode}
          onToggleAll={() => (selection.allSelected ? selection.clearSelection() : selection.selectAll())}
          onDeleteSelected={() => onDeleteSelected(Array.from(selection.selectedIds))}
        />
      ) : null}
      {clips.length ? (
        <div className="columns-1 gap-4 sm:columns-2 xl:columns-3">
          {groups.map((group) => (
            <div key={group.key} className="mb-4 break-inside-avoid">
              <ReviewSourceGroup
                group={group}
          statusTone={statusTone}
                actionStates={actionStates}
                onDelete={onDeleteClip}
                onMakeShorts={onMakeShorts}
                selectableIds={selectableSet}
                selectedIds={selection.selectedIds}
                selectionMode={selectionMode}
                onToggleSelect={selection.toggle}
              />
                </div>
          ))}
        </div>
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
