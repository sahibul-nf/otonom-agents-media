"use client";

import {CheckCircle2, Loader2, RefreshCcw, Trash2} from "lucide-react";

export function ReviewSelectionChrome({
  active,
  selectedCount,
  totalSelectable,
  allSelected,
  deleting = false,
  rerendering = false,
  approving = false,
  onEnter,
  onExit,
  onToggleAll,
  onDeleteSelected,
  onRerenderSelected,
  onApproveSelected,
}: {
  active: boolean;
  selectedCount: number;
  totalSelectable: number;
  allSelected: boolean;
  deleting?: boolean;
  rerendering?: boolean;
  approving?: boolean;
  onEnter: () => void;
  onExit: () => void;
  onToggleAll: () => void;
  onDeleteSelected: () => void;
  onRerenderSelected?: () => void;
  onApproveSelected?: () => void;
}) {
  if (!totalSelectable) return null;

  const busy = deleting || rerendering || approving;
  const chipClass =
    "inline-flex h-9 shrink-0 items-center rounded-full border border-white/[0.10] bg-white/[0.04] px-3.5 text-xs font-semibold text-zinc-200 transition hover:border-cyan/[0.28] hover:text-white disabled:opacity-40";

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
        <button type="button" onClick={onToggleAll} disabled={busy} className={chipClass}>
          {allSelected ? "Clear all" : "Select all"}
        </button>
        <button type="button" onClick={onExit} disabled={busy} className={chipClass}>
          Done
        </button>
        {selectedCount > 0 ? (
          <>
            {onApproveSelected ? (
              <button
                type="button"
                onClick={onApproveSelected}
                disabled={busy}
                className="inline-flex h-8 items-center gap-1.5 rounded-full border border-teal/[0.35] bg-teal/[0.12] px-3.5 text-[11px] font-semibold text-teal transition hover:bg-teal/[0.18] disabled:opacity-40"
              >
                {approving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                Approve {selectedCount}
              </button>
            ) : null}
            {onRerenderSelected ? (
              <button
                type="button"
                onClick={onRerenderSelected}
                disabled={busy}
                className="inline-flex h-8 items-center gap-1.5 rounded-full border border-cyan/[0.28] bg-cyan/[0.12] px-3.5 text-[11px] font-semibold text-cyan transition hover:bg-cyan/[0.18] disabled:opacity-40"
              >
                {rerendering ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCcw className="h-3.5 w-3.5" />}
                Re-render {selectedCount}
              </button>
            ) : null}
            <button
              type="button"
              onClick={onDeleteSelected}
              disabled={busy}
              className="inline-flex h-8 items-center gap-1.5 rounded-full bg-danger px-3.5 text-[11px] font-semibold text-white transition hover:bg-danger/90 disabled:opacity-40"
            >
              {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
              Delete {selectedCount}
            </button>
          </>
        ) : null}
      </div>
    </div>
  );
}
