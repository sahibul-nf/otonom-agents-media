"use client";

import {AlertTriangle, Loader2} from "lucide-react";

export type ActionUiState = {status: "running" | "done" | "failed"; message: string};

export function InlineActionStatus({state}: {state?: ActionUiState}) {
  if (!state) return null;
  const tone =
    state.status === "failed"
      ? "border-danger/[0.26] bg-danger/[0.10] text-danger"
      : state.status === "done"
        ? "border-teal/[0.26] bg-teal/[0.10] text-teal"
        : "border-cyan/[0.26] bg-teal/[0.10] text-cyan";
  return (
    <div className={`rounded-2xl border px-3 py-2 text-xs font-medium ${tone}`}>
      <div className="flex items-center gap-2">
        {state.status === "running" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
        <span>{state.message}</span>
      </div>
      {state.status === "running" ? (
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.08]">
          <div className="h-full w-2/3 animate-pulse rounded-full bg-cyan" />
        </div>
      ) : null}
    </div>
  );
}

export function SettingTile({label, value}: {label: string; value: string | number}) {
  return (
    <div className="rounded-[18px] border border-white/[0.08] bg-canvas-deep p-4">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-white">{value}</p>
    </div>
  );
}

export function EmptyState({title = "Nothing here yet", text, actionLabel, onAction}: {title?: string; text: string; actionLabel?: string; onAction?: () => void}) {
  return (
    <div className="grid min-h-[140px] place-items-center rounded-[22px] border border-dashed border-white/[0.10] bg-canvas-deep p-6 text-center">
      <div>
        <AlertTriangle className="mx-auto mb-3 h-6 w-6 text-zinc-600" />
        <p className="text-sm font-semibold text-zinc-300">{title}</p>
        <p className="mt-1 max-w-sm text-sm leading-6 text-zinc-500">{text}</p>
        {actionLabel && onAction ? (
          <button type="button" onClick={onAction} className="mt-4 rounded-full border border-cyan/[0.28] bg-teal/[0.10] px-4 py-2 text-xs font-semibold text-cyan">
            {actionLabel}
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function LoadingState({text = "Loading…"}: {text?: string}) {
  return (
    <div role="status" aria-live="polite" className="grid min-h-[140px] place-items-center rounded-[22px] border border-white/[0.06] bg-canvas-deep p-6 text-center">
      <div className="w-full max-w-xs">
        <Loader2 className="mx-auto mb-3 h-5 w-5 animate-spin text-cyan" />
        <p className="text-sm font-medium text-zinc-400">{text}</p>
        <div className="mt-4 grid gap-2" aria-hidden>
          <div className="h-2 animate-pulse rounded-full bg-white/[0.06]" />
          <div className="h-2 w-2/3 animate-pulse rounded-full bg-white/[0.06]" />
        </div>
      </div>
    </div>
  );
}

const recoveryClass =
  "inline-flex min-h-[32px] items-center rounded-full border border-danger/[0.30] bg-danger/[0.08] px-3 text-[11px] font-bold text-danger transition hover:bg-danger/[0.16] disabled:cursor-not-allowed disabled:opacity-50";

/** One-click fix for an error. Pass `href` for navigation or `onClick` for an in-page action. */
export function RecoveryAction({label, href, onClick, disabled}: {label: string; href?: string; onClick?: () => void; disabled?: boolean}) {
  if (href) {
    return (
      <a href={href} className={recoveryClass}>
        {label}
      </a>
    );
  }
  return (
    <button type="button" onClick={onClick} disabled={disabled} className={recoveryClass}>
      {label}
    </button>
  );
}
