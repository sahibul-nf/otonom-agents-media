"use client";

import {Loader2, Trash2} from "lucide-react";

export function ReviewSelectionChrome({
  active,
  selectedCount,
  totalSelectable,
  allSelected,
  deleting = false,
  onEnter,
  onExit,
  onToggleAll,
  onDeleteSelected,
}: {
  active: boolean;
  selectedCount: number;
  totalSelectable: number;
  allSelected: boolean;
  deleting?: boolean;
  onEnter: () => void;
  onExit: () => void;
  onToggleAll: () => void;
  onDeleteSelected: () => void;
}) {
  if (!totalSelectable) return null;

  const chipClass =
    "inline-flex h-8 shrink-0 items-center rounded-full border border-white/[0.10] bg-white/[0.04] px-3 text-[11px] font-semibold text-zinc-200 transition hover:border-cyan/[0.28] hover:text-white disabled:opacity-40";

  if (!active) {
    return (
      <button type="button" onClick={onEnter} className={`${chipClass} gap-1.5`}>
        Select
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-[22px] border border-cyan/[0.18] bg-cyan/[0.05] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="text-xs font-semibold text-white">Selection mode</p>
        <p className="mt-0.5 text-[11px] text-zinc-500">
          {selectedCount
            ? `${selectedCount} of ${totalSelectable} selected`
            : `Choose up to ${totalSelectable} clip${totalSelectable === 1 ? "" : "s"} in this view`}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={onToggleAll} disabled={deleting} className={chipClass}>
          {allSelected ? "Clear all" : "Select all"}
        </button>
        <button type="button" onClick={onExit} disabled={deleting} className={chipClass}>
          Done
        </button>
        {selectedCount > 0 ? (
          <button
            type="button"
            onClick={onDeleteSelected}
            disabled={deleting}
            className="inline-flex h-8 items-center gap-1.5 rounded-full bg-danger px-3.5 text-[11px] font-semibold text-white transition hover:bg-danger/90 disabled:opacity-40"
          >
            {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
            Delete {selectedCount}
          </button>
        ) : null}
      </div>
    </div>
  );
}
