"use client";

import {Captions, Film, Lock, Minus, Plus} from "lucide-react";
import {useState, type MouseEvent} from "react";
import {type ClipCandidate, formatTimestamp} from "@/lib/media-api";

export function ReviewTimeStrip({
  clip,
  currentSeconds,
  onSeek,
  selectedCaptionIndex,
  onSelectCaption,
}: {
  clip: ClipCandidate;
  currentSeconds: number;
  onSeek: (seconds: number) => void;
  selectedCaptionIndex?: number;
  onSelectCaption?: (index: number) => void;
}) {
  const durationMs = Math.max(1, clip.end_ms - clip.start_ms);
  const captions = clip.captions || [];
  const captionOffsetMs = (captions[0]?.startMs || 0) >= Math.max(0, clip.start_ms - 1_000) ? clip.start_ms : 0;
  const progress = Math.max(0, Math.min(100, ((currentSeconds * 1000) / durationMs) * 100));
  const durationSeconds = durationMs / 1000;
  const [pixelsPerSecond, setPixelsPerSecond] = useState(12);
  const timelineWidth = Math.max(960, Math.round(durationSeconds * pixelsPerSecond));
  const labelWidth = 104;
  const rulerStep = durationSeconds > 600 ? 60 : durationSeconds > 180 ? 30 : durationSeconds > 60 ? 10 : 5;
  const rulerMarks = Array.from({length: Math.floor(durationSeconds / rulerStep) + 1}, (_, index) => index * rulerStep);

  function seekFromTrack(event: MouseEvent<HTMLButtonElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    onSeek(ratio * durationSeconds);
  }

  return (
    <section className="min-w-0 overflow-hidden">
      <div className="flex h-10 items-center justify-end gap-1.5 px-4">
        <button
          type="button"
          onClick={() => setPixelsPerSecond((value) => Math.max(6, value - 2))}
          className="grid h-8 w-8 place-items-center rounded-full text-zinc-500 transition hover:bg-white/[0.06] hover:text-white"
          aria-label="Zoom timeline out"
        >
          <Minus className="h-3.5 w-3.5" />
        </button>
        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-white/[0.08]">
          <div className="h-full bg-cyan/70" style={{width: `${((pixelsPerSecond - 6) / 18) * 100}%`}} />
        </div>
        <button
          type="button"
          onClick={() => setPixelsPerSecond((value) => Math.min(24, value + 2))}
          className="grid h-8 w-8 place-items-center rounded-full text-zinc-500 transition hover:bg-white/[0.06] hover:text-white"
          aria-label="Zoom timeline in"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="overflow-x-auto pb-4">
        <div className="relative" style={{width: labelWidth + timelineWidth}}>
          <div className="relative h-6" style={{marginLeft: labelWidth}}>
            {rulerMarks.map((second) => (
              <div key={second} className="absolute bottom-0 top-0 border-l border-white/[0.08]" style={{left: `${(second / durationSeconds) * 100}%`}}>
                <span className="absolute left-1.5 top-0.5 font-mono text-[10px] text-zinc-500">
                  {formatTimestamp(second * 1000).replace(/^00:/, "")}
                </span>
              </div>
            ))}
          </div>

          <div className="flex h-12">
            <div
              className="sticky left-0 z-20 flex shrink-0 items-center gap-2 bg-canvas/90 px-3 text-[11px] font-medium text-zinc-500 backdrop-blur-sm"
              style={{width: labelWidth}}
            >
              <Film className="h-3.5 w-3.5" /> Video
            </div>
            <button type="button" onClick={seekFromTrack} className="relative h-full text-left" style={{width: timelineWidth}} aria-label="Seek video track">
              <span className="absolute inset-x-1 inset-y-2 rounded-xl bg-gradient-to-r from-cyan/[0.16] to-teal/[0.06] px-3 text-[11px] font-medium leading-8 text-cyan/85">
                Source · {formatTimestamp(durationMs)}
              </span>
            </button>
          </div>

          <div className="mt-1 flex h-14">
            <div
              className="sticky left-0 z-20 flex shrink-0 items-center justify-between bg-canvas/90 px-3 text-[11px] font-medium text-zinc-500 backdrop-blur-sm"
              style={{width: labelWidth}}
            >
              <span className="inline-flex items-center gap-2">
                <Captions className="h-3.5 w-3.5" /> Captions
              </span>
              <Lock className="h-3 w-3 text-zinc-700" />
            </div>
            <div className="relative h-full" style={{width: timelineWidth}}>
              {captions.length ? (
                captions.map((caption, index) => {
                  const relativeStartMs = Math.max(0, caption.startMs - captionOffsetMs);
                  const segmentDuration = Math.max(500, caption.endMs - caption.startMs);
                  const left = (relativeStartMs / durationMs) * 100;
                  const width = Math.max(0.6, (segmentDuration / durationMs) * 100);
                  const selected = selectedCaptionIndex === index;
                  return (
                    <button
                      key={`${caption.startMs}-${index}`}
                      type="button"
                      onClick={() => {
                        onSeek(relativeStartMs / 1000);
                        onSelectCaption?.(index);
                      }}
                      aria-pressed={selected}
                      className={`absolute bottom-2 top-2 truncate rounded-lg px-2 text-left text-[11px] leading-5 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan ${
                        selected ? "bg-cyan/20 text-white" : "bg-white/[0.07] text-zinc-300 hover:bg-white/[0.12] hover:text-zinc-100"
                      }`}
                      style={{left: `${left}%`, width: `${width}%`}}
                      title={`${formatTimestamp(relativeStartMs)} — ${caption.text}`}
                    >
                      {caption.text}
                    </button>
                  );
                })
              ) : (
                <div className="grid h-full place-items-center text-[11px] text-zinc-600">No timed captions</div>
              )}
            </div>
          </div>

          <div
            className="pointer-events-none absolute bottom-0 top-0 z-30 w-px bg-cyan"
            style={{left: labelWidth + (progress / 100) * timelineWidth}}
          >
            <span className="absolute -left-[4px] top-0 h-2.5 w-2.5 rounded-full bg-cyan" />
          </div>
        </div>
      </div>
    </section>
  );
}
