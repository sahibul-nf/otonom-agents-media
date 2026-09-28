"use client";

import {Check, Loader2, Play, RefreshCcw, Save, Sparkles} from "lucide-react";
import type {ClipCandidate, EditorContext} from "@/lib/media-api";
import type {EditorActionStates} from "@/components/review/editor/types";

export function EditorHeaderActions({
  clip,
  context,
  dirty,
  lookChanged = false,
  rendering,
  actionStates,
  onSave,
  onRender,
  onRerender,
  onPolishCaptions,
  onApprove,
  onSchedule,
}: {
  clip: ClipCandidate;
  context: EditorContext;
  dirty: boolean;
  lookChanged?: boolean;
  rendering: boolean;
  actionStates: EditorActionStates;
  onSave: () => void;
  onRender: () => void;
  onRerender?: () => void;
  onPolishCaptions?: () => void;
  onApprove: () => void;
  onSchedule: () => void;
}) {
  const saving = actionStates.plan?.status === "running";
  const rerendering = actionStates[`clip:${clip.id}:rerender`]?.status === "running";
  const polishing = actionStates[`clip:${clip.id}:caption-polish`]?.status === "running";
  const approving = actionStates[`clip:${clip.id}:approve`]?.status === "running";
  const scheduling = actionStates[`clip:${clip.id}:schedule`]?.status === "running";
  const scheduleMode = clip.status === "approved";
  const canDecide = ["draft", "rendered", "held", "pending_auto_schedule"].includes(clip.status);
  const decideDisabled = dirty || lookChanged || rendering || saving || (scheduleMode ? scheduling : !canDecide || approving);
  const renderError = context.job?.error || context.render?.error;
  const statusLabel = renderError || (rendering ? "Rendering…" : lookChanged ? "Look changed" : dirty ? "Unsaved" : "Saved");
  const showRender = context.capability === "scene" && context.can_rerender && !dirty && context.job?.status === "planned";
  const showShortRerender = context.capability === "short" && context.can_rerender && !dirty && Boolean(onRerender);
  const showCaptionPolish = context.capability === "short" && Boolean(clip.captions?.length) && Boolean(onPolishCaptions);

  return (
    <div className="flex min-w-0 items-center gap-1.5 rounded-full border border-white/[0.06] bg-black/25 p-1 backdrop-blur-md sm:gap-2 sm:px-1.5">
      <span className={`hidden px-2 text-[11px] font-medium sm:inline ${renderError ? "text-danger" : dirty || lookChanged ? "text-warning" : "text-zinc-500"}`}>
        {statusLabel}
      </span>
      <button type="button" onClick={onSave} disabled={!dirty || saving || rendering} className={ghostChip}>
        {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
        <span className="hidden sm:inline">{saving ? "Saving…" : "Save"}</span>
      </button>
      {showRender ? (
        <button type="button" onClick={onRender} disabled={rendering || saving} className={ghostChip}>
          {rendering ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
          <span className="hidden md:inline">Render</span>
        </button>
      ) : null}
      {showShortRerender ? (
        <button type="button" onClick={onRerender} disabled={rendering || rerendering || saving} className={ghostChip} title="Re-render video with current hook title and captions">
          {rendering || rerendering ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCcw className="h-3.5 w-3.5" />}
          <span className="hidden md:inline">{rendering || rerendering ? "Rendering…" : "Re-render"}</span>
        </button>
      ) : null}
      {showCaptionPolish ? (
        <button
          type="button"
          onClick={onPolishCaptions}
          disabled={dirty || rendering || saving || polishing}
          className={ghostChip}
          title="Fix spelling, remove stutters, and add punctuation with AI"
        >
          {polishing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
          <span className="hidden md:inline">{polishing ? "Polishing…" : "AI Polish"}</span>
        </button>
      ) : null}
      <button type="button" onClick={scheduleMode ? onSchedule : onApprove} disabled={decideDisabled} className={primaryChip}>
        {approving || scheduling ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
        {scheduleMode ? "Schedule" : "Approve"}
      </button>
    </div>
  );
}

const ghostChip = "inline-flex h-8 items-center justify-center gap-1.5 rounded-full px-3 text-xs font-semibold text-zinc-300 transition hover:bg-white/[0.06] hover:text-white disabled:cursor-not-allowed disabled:opacity-40";
const primaryChip = "inline-flex h-8 items-center justify-center gap-1.5 rounded-full bg-cyan px-3.5 text-xs font-bold text-ink transition hover:bg-cyan/90 disabled:cursor-not-allowed disabled:opacity-40";
