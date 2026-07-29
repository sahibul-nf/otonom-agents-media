"use client";

import Link from "next/link";
import {ArrowUpRight, Pause, Play} from "lucide-react";
import {useRef, useState} from "react";
import {MediaPreviewFrame} from "@/components/shared/MediaPreviewFrame";
import {apiPath, type ClipCandidate, formatDuration, isExplainerClip} from "@/lib/media-api";

function readinessLabel(clip: ClipCandidate) {
  if (clip.status === "held") return "Needs a fix";
  if (clip.status === "approved") return "Approved";
  if (clip.status === "scheduled" || clip.status === "ready_to_publish") return "Scheduled";
  if (clip.status === "published") return "Published";
  return "Ready to review";
}

export function ReviewQueueCard({
  clip,
  statusTone,
}: {
  clip: ClipCandidate;
  statusTone: (status: string) => string;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const output = clip.output_path || clip.render_quality?.output_path;
  const source = output ? apiPath(`artifact?path=${encodeURIComponent(output)}`) : null;
  const duration = clip.render_quality?.duration_ms || clip.end_ms - clip.start_ms;

  async function togglePreview() {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      await video.play();
      return;
    }
    video.pause();
  }

  return (
    <article className="group min-w-0 rounded-[24px] border border-white/[0.08] bg-surface p-3 transition duration-200 hover:-translate-y-0.5 hover:border-cyan/[0.20] hover:shadow-glow motion-reduce:transform-none motion-reduce:transition-none">
      <div className="relative">
        <MediaPreviewFrame
          aspect={isExplainerClip(clip) ? "landscape" : "portrait"}
          src={source}
          videoRef={videoRef}
          muted
          loop
          preload="metadata"
          spacing="none"
          rounded="panel"
          showPlayHint={false}
          showVignette
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => setPlaying(false)}
          ariaLabel={`Preview ${clip.title_hook}`}
          emptyState={<div className="absolute inset-0 grid place-items-center text-sm text-zinc-600">Preview unavailable</div>}
        />
        {source ? (
          <button
            type="button"
            onClick={() => void togglePreview()}
            className="absolute inset-0 z-[3] grid place-items-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-cyan"
            aria-label={playing ? `Pause ${clip.title_hook}` : `Play ${clip.title_hook}`}
          >
            <span className={`grid h-12 w-12 place-items-center rounded-full border border-white/15 bg-black/55 text-white shadow-lg backdrop-blur-md transition ${playing ? "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100" : "opacity-100"}`}>
              {playing ? <Pause className="h-5 w-5 fill-white" /> : <Play className="ml-0.5 h-5 w-5 fill-white" />}
            </span>
          </button>
        ) : null}
        <span className="pointer-events-none absolute bottom-3 left-3 z-[4] rounded-full bg-black/65 px-2.5 py-1 text-[11px] font-semibold tabular-nums text-white backdrop-blur-md">
          {formatDuration(duration)}
        </span>
      </div>

      <div className="px-1 pb-1 pt-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="line-clamp-2 text-sm font-semibold leading-5 text-white">{clip.title_hook}</h3>
            <span className={`mt-2 inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold ${statusTone(clip.status === "held" ? "failed" : clip.status)}`}>
              {readinessLabel(clip)}
            </span>
          </div>
          <Link
            href={`/review/${encodeURIComponent(clip.id)}`}
            className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded-full border border-white/[0.10] bg-white/[0.04] px-3 text-xs font-semibold text-zinc-200 transition hover:border-cyan/[0.30] hover:text-cyan focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan"
          >
            Edit <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>
    </article>
  );
}
