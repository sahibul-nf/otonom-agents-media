"use client";

import {Loader2} from "lucide-react";
import {PreviewPanel, type PreviewPlaybackRequest, type PreviewSeekRequest} from "@/components/review/PreviewPanel";
import {capabilityLabel} from "@/components/review/editor/types";
import {formatTimestamp, type ClipCandidate, type EditorContext} from "@/lib/media-api";

export function EditorStage({
  clip,
  context,
  currentSeconds,
  seekRequest,
  playbackRequest,
  rendering,
  previewEpoch = 0,
  onTimeChange,
  onPlaybackChange,
}: {
  clip: ClipCandidate;
  context: EditorContext;
  currentSeconds: number;
  seekRequest?: PreviewSeekRequest;
  playbackRequest?: PreviewPlaybackRequest;
  rendering: boolean;
  previewEpoch?: number;
  onTimeChange: (seconds: number) => void;
  onPlaybackChange: (playing: boolean) => void;
}) {
  const longform = context.capability === "scene" || context.capability === "imported_longform";

  return (
    <section className="relative flex h-full min-h-[420px] min-w-0 flex-col lg:min-h-0">
      <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex h-10 items-center justify-between gap-3 px-5">
        <div className="flex items-center gap-2">
          <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-zinc-600">Preview</p>
          <span className="text-[11px] text-zinc-700">· {capabilityLabel(context.capability)}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-medium tabular-nums text-zinc-600">
            {context.capability === "short" ? "9:16" : "16:9"}
          </span>
          <span className="font-mono text-[11px] tabular-nums text-zinc-600">{formatTimestamp(currentSeconds * 1000)}</span>
        </div>
      </div>

      {/* Explicit top/bottom canvas gutters so the frame doesn't kiss the chrome */}
      <div className="flex min-h-0 flex-1 flex-col">
        <div className={`shrink-0 ${longform ? "h-11" : "h-12"}`} aria-hidden />
        <div className={`flex min-h-0 flex-1 items-center justify-center overflow-hidden ${longform ? "px-4 sm:px-8" : "px-5 sm:px-8"}`}>
          <div className="relative flex h-full min-h-0 w-full max-w-full items-center justify-center">
            <PreviewPanel
              clip={clip}
              statusTone={() => ""}
              embedded
              hideHeader
              variant="stage"
              previewEpoch={previewEpoch}
              seekRequest={seekRequest}
              playbackRequest={playbackRequest}
              onTimeChange={onTimeChange}
              onPlaybackChange={onPlaybackChange}
            />
            {rendering ? (
              <div className="absolute inset-0 grid place-items-center bg-canvas/70 backdrop-blur-sm">
                <div className="px-5 py-4 text-center">
                  <Loader2 className="mx-auto h-5 w-5 animate-spin text-cyan" />
                  <p className="mt-2 text-sm font-semibold text-white">Rendering full video</p>
                  <p className="mt-1 text-xs text-zinc-500">
                    {context.job?.message || "The editor will refresh when the job finishes."}
                  </p>
                </div>
              </div>
            ) : null}
          </div>
        </div>
        <div className={`shrink-0 ${longform ? "h-4 sm:h-5" : "h-5 sm:h-7"}`} aria-hidden />
      </div>
    </section>
  );
}
