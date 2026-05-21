"use client";

import {Pause, Play, SkipBack, SkipForward, Volume2, VolumeX} from "lucide-react";
import {useRef, useState} from "react";
import {apiPath, ClipCandidate} from "@/lib/media-api";

type PreviewPanelProps = {
  clip?: ClipCandidate;
  statusTone: (status: string) => string;
  embedded?: boolean;
};

export function PreviewPanel({clip, statusTone, embedded = false}: PreviewPanelProps) {
  const output = clip?.output_path || clip?.render_quality?.output_path;
  return (
    <div className={embedded ? "" : "rounded-[28px] border border-white/[0.08] bg-surface p-5"}>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">9:16 Preview</h3>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusTone(clip?.status || "empty")}`}>{clip?.status || "No clip"}</span>
      </div>
      <div className="relative mx-auto grid aspect-[9/16] max-h-[620px] w-full max-w-[350px] place-items-center overflow-hidden rounded-[26px] border border-white/[0.10] bg-black">
        {output ? <VideoPreviewPlayer key={output} output={output} /> : (
          <div className="grid place-items-center gap-3 px-8 text-center text-sm text-zinc-500">
            <Play className="h-10 w-10 text-zinc-700" />
            No rendered clip selected.
          </div>
        )}
      </div>
    </div>
  );
}

function VideoPreviewPlayer({output}: {output: string}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);

  function formatClock(totalSeconds: number) {
    if (!Number.isFinite(totalSeconds) || totalSeconds <= 0) return "0:00";
    const rounded = Math.floor(totalSeconds);
    const hours = Math.floor(rounded / 3600);
    const minutes = Math.floor((rounded % 3600) / 60);
    const seconds = rounded % 60;
    if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    return `${minutes}:${String(seconds).padStart(2, "0")}`;
  }

  async function togglePlayback() {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      await video.play();
      setIsPlaying(true);
      return;
    }
    video.pause();
    setIsPlaying(false);
  }

  function seekTo(nextTime: number) {
    const video = videoRef.current;
    if (!video || !Number.isFinite(video.duration) || video.duration <= 0) return;
    const clamped = Math.min(video.duration, Math.max(0, nextTime));
    video.currentTime = clamped;
    setCurrentTime(clamped);
  }

  function skipBy(deltaSeconds: number) {
    const video = videoRef.current;
    if (!video) return;
    seekTo(video.currentTime + deltaSeconds);
  }

  function toggleMuted() {
    const video = videoRef.current;
    if (!video) return;
    const next = !video.muted;
    video.muted = next;
    setIsMuted(next);
  }

  return (
    <>
      <video
        ref={videoRef}
        playsInline
        preload="metadata"
        className="h-full w-full object-contain"
        src={apiPath(`artifact?path=${encodeURIComponent(output)}`)}
        onLoadedMetadata={(event) => {
          setDuration(event.currentTarget.duration || 0);
          setCurrentTime(event.currentTarget.currentTime || 0);
          setIsReady(true);
          setIsMuted(event.currentTarget.muted);
        }}
        onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime || 0)}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
        onClick={() => void togglePlayback()}
      />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 via-black/30 to-transparent px-4 pb-4 pt-14">
        <div className="pointer-events-auto rounded-[20px] border border-white/10 bg-black/48 px-3 py-3 backdrop-blur-md">
          <input
            type="range"
            min={0}
            max={Math.max(duration, 0)}
            step={0.1}
            value={Math.min(currentTime, duration || 0)}
            onInput={(event) => seekTo(Number(event.currentTarget.value))}
            onChange={(event) => seekTo(Number(event.target.value))}
            className="h-2 w-full cursor-pointer accent-[#6ce2ee]"
            aria-label="Seek preview video"
            disabled={!isReady}
          />
          <div className="mt-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => skipBy(-5)}
                className="grid h-9 w-9 place-items-center rounded-full border border-white/10 bg-white/6 text-zinc-100 transition hover:bg-white/12 disabled:cursor-not-allowed disabled:opacity-40"
                disabled={!isReady}
                aria-label="Seek backward 5 seconds"
              >
                <SkipBack className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => void togglePlayback()}
                className="grid h-10 w-10 place-items-center rounded-full bg-cyan text-ink transition hover:bg-cyan/90 disabled:cursor-not-allowed disabled:opacity-40"
                disabled={!isReady}
                aria-label={isPlaying ? "Pause preview" : "Play preview"}
              >
                {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="ml-0.5 h-4 w-4" />}
              </button>
              <button
                type="button"
                onClick={() => skipBy(5)}
                className="grid h-9 w-9 place-items-center rounded-full border border-white/10 bg-white/6 text-zinc-100 transition hover:bg-white/12 disabled:cursor-not-allowed disabled:opacity-40"
                disabled={!isReady}
                aria-label="Seek forward 5 seconds"
              >
                <SkipForward className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={toggleMuted}
                className="grid h-9 w-9 place-items-center rounded-full border border-white/10 bg-white/6 text-zinc-100 transition hover:bg-white/12 disabled:cursor-not-allowed disabled:opacity-40"
                disabled={!isReady}
                aria-label={isMuted ? "Unmute preview" : "Mute preview"}
              >
                {isMuted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
              </button>
            </div>
            <div className="text-xs font-medium tabular-nums text-zinc-200">
              {formatClock(currentTime)} / {formatClock(duration)}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
