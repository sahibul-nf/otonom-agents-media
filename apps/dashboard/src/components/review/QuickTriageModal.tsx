"use client";

import {useCallback, useEffect, useRef, useState} from "react";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Edit3,
  ExternalLink,
  Flame,
  Info,
  Pause,
  Play,
  Sparkles,
  Trash2,
  Volume2,
  VolumeX,
  X,
  Zap,
} from "lucide-react";
import Link from "next/link";
import {
  apiPath,
  canQuickApproveClip,
  clipOverallScore,
  type ClipCandidate,
  formatDuration,
} from "@/lib/media-api";

export type QuickTriageModalProps = {
  isOpen: boolean;
  onClose: () => void;
  clips: ClipCandidate[];
  onApproveClip?: (clip: ClipCandidate) => void;
  onDeleteClip?: (clip: ClipCandidate) => void;
  initialIndex?: number;
};

export function QuickTriageModal({
  isOpen,
  onClose,
  clips,
  onApproveClip,
  onDeleteClip,
  initialIndex = 0,
}: QuickTriageModalProps) {
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const [isPlaying, setIsPlaying] = useState(true);
  const [isMuted, setIsMuted] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<"approve" | "delete" | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      setCurrentIndex(Math.min(initialIndex, Math.max(0, clips.length - 1)));
      setIsPlaying(true);
    }
  }, [isOpen, initialIndex, clips.length]);

  const currentClip = clips[currentIndex];

  const goNext = useCallback(() => {
    if (currentIndex < clips.length - 1) {
      setCurrentIndex((prev) => prev + 1);
      setIsPlaying(true);
    }
  }, [currentIndex, clips.length]);

  const goPrev = useCallback(() => {
    if (currentIndex > 0) {
      setCurrentIndex((prev) => prev - 1);
      setIsPlaying(true);
    }
  }, [currentIndex]);

  const handleApprove = useCallback(() => {
    if (!currentClip || !onApproveClip) return;
    setActionFeedback("approve");
    onApproveClip(currentClip);
    setTimeout(() => {
      setActionFeedback(null);
      goNext();
    }, 280);
  }, [currentClip, onApproveClip, goNext]);

  const handleDelete = useCallback(() => {
    if (!currentClip || !onDeleteClip) return;
    setActionFeedback("delete");
    onDeleteClip(currentClip);
    setTimeout(() => {
      setActionFeedback(null);
      if (currentIndex >= clips.length - 1 && currentIndex > 0) {
        setCurrentIndex((prev) => prev - 1);
      }
    }, 280);
  }, [currentClip, onDeleteClip, currentIndex, clips.length]);

  const togglePlay = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      video.play().catch(() => undefined);
      setIsPlaying(true);
    } else {
      video.pause();
      setIsPlaying(false);
    }
  }, []);

  // Keyboard navigation shortcuts
  useEffect(() => {
    if (!isOpen) return;

    function handleKeyDown(e: KeyboardEvent) {
      // Don't intercept if user is typing in an input
      if (
        document.activeElement?.tagName === "INPUT" ||
        document.activeElement?.tagName === "TEXTAREA"
      ) {
        return;
      }

      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.code === "Space") {
        e.preventDefault();
        togglePlay();
      } else if (e.key.toLowerCase() === "a" || e.key === "Enter") {
        e.preventDefault();
        handleApprove();
      } else if (e.key.toLowerCase() === "d" || e.key === "Backspace") {
        e.preventDefault();
        handleDelete();
      } else if (e.key === "ArrowRight" || e.key.toLowerCase() === "k") {
        e.preventDefault();
        goNext();
      } else if (e.key === "ArrowLeft" || e.key.toLowerCase() === "j") {
        e.preventDefault();
        goPrev();
      } else if (e.key.toLowerCase() === "m") {
        e.preventDefault();
        setIsMuted((prev) => !prev);
      } else if (e.key.toLowerCase() === "e") {
        e.preventDefault();
        if (currentClip) {
          window.location.assign(`/review/${encodeURIComponent(currentClip.id)}`);
        }
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose, togglePlay, handleApprove, handleDelete, goNext, goPrev, currentClip]);

  if (!isOpen) return null;

  if (!currentClip || clips.length === 0) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-200">
        <div className="max-w-md w-full rounded-3xl border border-white/10 bg-surface p-8 text-center shadow-2xl">
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-teal/10 border border-teal/20 text-teal mb-4">
            <Sparkles className="h-8 w-8" />
          </div>
          <h3 className="text-xl font-bold text-text-primary">Queue Zero!</h3>
          <p className="mt-2 text-sm text-zinc-400">
            All candidate clips in this view have been triaged or approved. Your pipeline is ready.
          </p>
          <button
            type="button"
            onClick={onClose}
            className="mt-6 inline-flex h-10 w-full items-center justify-center rounded-full bg-cyan px-6 font-semibold text-ink transition hover:bg-cyan/90"
          >
            Back to Studio
          </button>
        </div>
      </div>
    );
  }

  const output = currentClip.output_path || currentClip.render_quality?.output_path;
  const videoSrc = output ? apiPath(`artifact?path=${encodeURIComponent(output)}`) : null;
  const duration = currentClip.render_quality?.duration_ms || currentClip.end_ms - currentClip.start_ms;
  const score = clipOverallScore(currentClip);
  const canApprove = Boolean(onApproveClip && canQuickApproveClip(currentClip));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-3 sm:p-6 animate-in fade-in duration-200">
      {/* Backdrop click to close */}
      <div className="absolute inset-0 -z-10" onClick={onClose} />

      <div className="relative flex h-full max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-3xl border border-white/[0.12] bg-surface shadow-2xl lg:flex-row">
        {/* Top Header Mobile / Close Button */}
        <div className="absolute right-4 top-4 z-20 flex items-center gap-2">
          <button
            type="button"
            onClick={onClose}
            className="grid h-9 w-9 place-items-center rounded-full bg-black/60 text-zinc-300 backdrop-blur transition hover:bg-black/90 hover:text-white"
            title="Close triage (Esc)"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Left Side: Video Preview Frame */}
        <div className="relative flex flex-1 items-center justify-center bg-black/95 p-4 sm:p-6">
          <div
            className={`relative flex aspect-[9/16] h-full max-h-[76vh] max-w-full items-center justify-center overflow-hidden rounded-2xl border border-white/10 bg-black shadow-2xl transition-transform duration-300 ${
              actionFeedback === "approve"
                ? "scale-[1.02] ring-4 ring-teal"
                : actionFeedback === "delete"
                  ? "scale-[0.98] ring-4 ring-danger opacity-70"
                  : ""
            }`}
          >
            {videoSrc ? (
              <video
                ref={videoRef}
                src={videoSrc}
                autoPlay
                playsInline
                loop
                muted={isMuted}
                onClick={togglePlay}
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                className="h-full w-full object-cover cursor-pointer"
              />
            ) : (
              <div className="grid place-items-center p-6 text-center text-zinc-500">
                <p className="text-sm">No preview video rendered yet</p>
              </div>
            )}

            {/* Over-video Play/Pause Indicator */}
            {!isPlaying && videoSrc && (
              <button
                type="button"
                onClick={togglePlay}
                className="absolute inset-0 grid place-items-center bg-black/30 backdrop-blur-[2px] transition"
              >
                <div className="grid h-16 w-16 place-items-center rounded-full bg-cyan text-ink shadow-lg">
                  <Play className="h-8 w-8 translate-x-0.5 fill-current" />
                </div>
              </button>
            )}

            {/* Bottom Floating Video Controls */}
            <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between rounded-xl bg-black/60 px-3 py-1.5 backdrop-blur-md text-xs text-white">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={togglePlay}
                  className="hover:text-cyan transition"
                >
                  {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                </button>
                <span className="font-mono text-[11px] text-zinc-300">
                  {formatDuration(duration)}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setIsMuted((prev) => !prev)}
                className="hover:text-cyan transition"
                title="Mute / Unmute (M)"
              >
                {isMuted ? <VolumeX className="h-4 w-4 text-zinc-400" /> : <Volume2 className="h-4 w-4 text-cyan" />}
              </button>
            </div>
          </div>
        </div>

        {/* Right Side: Editorial Metadata, Viral Scoring & Action Cockpit */}
        <div className="flex w-full flex-col justify-between border-t border-white/[0.08] bg-surface-raised p-6 lg:w-[420px] lg:border-l lg:border-t-0">
          <div className="overflow-y-auto pr-1">
            {/* Queue Counter & Navigation */}
            <div className="mb-4 flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-cyan/20 bg-cyan/10 px-3 py-1 text-xs font-semibold text-cyan">
                <Zap className="h-3.5 w-3.5" />
                Clip {currentIndex + 1} of {clips.length}
              </span>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={goPrev}
                  disabled={currentIndex === 0}
                  className="grid h-8 w-8 place-items-center rounded-full border border-white/10 text-zinc-400 hover:border-white/20 hover:text-white disabled:opacity-30 disabled:hover:border-white/10"
                  title="Previous (J / Left)"
                >
                  <ArrowLeft className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={goNext}
                  disabled={currentIndex === clips.length - 1}
                  className="grid h-8 w-8 place-items-center rounded-full border border-white/10 text-zinc-400 hover:border-white/20 hover:text-white disabled:opacity-30 disabled:hover:border-white/10"
                  title="Next (K / Right)"
                >
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Title & Hook */}
            <h2 className="text-lg font-bold leading-snug text-text-primary">
              {currentClip.title_hook || "Untitled Clip"}
            </h2>
            {currentClip.hook_subtitle && (
              <p className="mt-1 text-xs text-zinc-400 italic">
                &ldquo;{currentClip.hook_subtitle}&rdquo;
              </p>
            )}

            {/* Viral Score Breakdown Card */}
            <div className="mt-4 rounded-2xl border border-white/[0.08] bg-surface-panel p-4">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-xs font-semibold text-zinc-300">
                  <Flame className="h-4 w-4 text-warning" />
                  Performance score
                </span>
                <span className="font-mono text-sm font-bold text-cyan">
                  {score != null ? `${Math.round(score)}` : "Unrated"}
                </span>
              </div>
              {currentClip.viral_reason && (
                <p className="mt-2.5 text-xs leading-relaxed text-zinc-400">
                  {currentClip.viral_reason}
                </p>
              )}
            </div>

            {/* Transcript Hook Snippet */}
            {currentClip.transcript_span && (
              <div className="mt-3 rounded-2xl border border-white/[0.06] bg-surface p-3.5">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
                  Opening Hook Line
                </span>
                <p className="mt-1 text-xs leading-relaxed text-zinc-300 line-clamp-3">
                  {currentClip.transcript_span}
                </p>
              </div>
            )}
          </div>

          {/* Action Cockpit with Keyboard Hints */}
          <div className="mt-6 border-t border-white/[0.08] pt-4">
            <div className="grid grid-cols-2 gap-2.5">
              <button
                type="button"
                onClick={handleApprove}
                disabled={!canApprove}
                className="group relative flex h-11 items-center justify-center gap-2 rounded-2xl border border-teal/40 bg-teal/15 px-4 font-semibold text-teal transition hover:bg-teal/25 hover:border-teal/60 disabled:opacity-40"
              >
                <CheckCircle2 className="h-4 w-4" />
                <span>Approve</span>
                <kbd className="ml-1 rounded border border-teal/30 bg-teal/10 px-1.5 py-0.5 text-[10px] font-mono text-teal">
                  A
                </kbd>
              </button>

              <button
                type="button"
                onClick={handleDelete}
                className="group flex h-11 items-center justify-center gap-2 rounded-2xl border border-danger/30 bg-danger/10 px-4 font-semibold text-danger transition hover:bg-danger/20 hover:border-danger/50"
              >
                <Trash2 className="h-4 w-4" />
                <span>Reject</span>
                <kbd className="ml-1 rounded border border-danger/30 bg-danger/10 px-1.5 py-0.5 text-[10px] font-mono text-danger">
                  D
                </kbd>
              </button>
            </div>

            <div className="mt-2.5 flex items-center justify-between gap-2">
              <Link
                href={`/review/${encodeURIComponent(currentClip.id)}`}
                className="inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-xl border border-border bg-surface px-3 text-xs font-medium text-zinc-300 transition hover:bg-surface-strong hover:text-white"
              >
                <Edit3 className="h-3.5 w-3.5" />
                <span>Edit Captions</span>
                <kbd className="ml-1 rounded border border-border bg-surface-panel px-1 text-[10px] text-zinc-400">
                  E
                </kbd>
              </Link>
            </div>

            {/* Quick Keyboard Reference Legend */}
            <div className="mt-3 flex items-center justify-center gap-3 text-[11px] text-zinc-500">
              <span>
                <kbd className="font-mono text-zinc-400">Space</kbd> Play/Pause
              </span>
              <span>•</span>
              <span>
                <kbd className="font-mono text-zinc-400">J/K</kbd> Nav
              </span>
              <span>•</span>
              <span>
                <kbd className="font-mono text-zinc-400">Esc</kbd> Exit
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
