"use client";

import Link from "next/link";
import {ArrowUpRight, Calendar, CheckCircle2, Loader2, MoreHorizontal, Pause, Play, RefreshCw, Scissors, Trash2, Volume2, VolumeX, Zap} from "lucide-react";
import {useCallback, useEffect, useId, useRef, useState, type MouseEvent as ReactMouseEvent} from "react";
import {MediaPreviewFrame} from "@/components/shared/MediaPreviewFrame";
import {ReviewCardSelectToggle} from "@/components/review/ReviewCardSelectToggle";
import {ReviewDistributeDialog, type ReviewDistributeIntent} from "@/components/review/ReviewDistributeDialog";
import {apiPath, canMakeShortsFromClip, canQuickApproveClip, clipAutonomyThreshold, clipHygieneFlags, clipHygieneGate, clipHygieneLabel, clipHygieneTone, clipMeetsAutonomyThreshold, clipOverallScore, type ClipCandidate, formatDuration, isClipRerendering, isExplainerClip} from "@/lib/media-api";
import {claimReviewPreviewPlayback, releaseReviewPreviewPlayback} from "@/lib/review-preview-audio";
import {formatReviewActivityAt} from "@/lib/review-groups";

function readinessLabel(clip: ClipCandidate) {
  if (clip.status === "held") return "Captions unusable";
  if (clip.status === "approved") return "Approved";
  if (clip.status === "scheduled" || clip.status === "ready_to_publish") return "Scheduled";
  if (clip.status === "published") return "Published";
  return "Ready to review";
}

function needsMetadataRefresh(clip: ClipCandidate) {
  const titleSource = String(clip.curation_metadata?.title_source || "");
  const subtitleSource = String(clip.curation_metadata?.subtitle_source || "");
  return titleSource === "heuristic_span" || subtitleSource === "heuristic_span";
}

export function ReviewQueueCard({
  clip,
  statusTone,
  deleting = false,
  editHref,
  onDelete,
  onMakeShorts,
  onApprove,
  onSchedule,
  onPublishNow,
  publishTargets = [],
  defaultPublishPlatforms = [],
  selectable = false,
  selectionMode = false,
  selected = false,
  onToggleSelect,
  approving = false,
  scheduling = false,
  publishing = false,
}: {
  clip: ClipCandidate;
  statusTone: (status: string) => string;
  deleting?: boolean;
  approving?: boolean;
  scheduling?: boolean;
  publishing?: boolean;
  publishTargets?: string[];
  defaultPublishPlatforms?: string[];
  editHref?: string;
  onDelete?: (clip: ClipCandidate) => void;
  onMakeShorts?: (clip: ClipCandidate) => void;
  onApprove?: (clip: ClipCandidate) => void;
  onSchedule?: (clip: ClipCandidate, scheduledAt: string, platforms: string[]) => void;
  onPublishNow?: (clip: ClipCandidate, platforms: string[], options?: {republish?: boolean}) => void;
  selectable?: boolean;
  selectionMode?: boolean;
  selected?: boolean;
  onToggleSelect?: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const menuId = useId();
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [distributeIntent, setDistributeIntent] = useState<ReviewDistributeIntent | null>(null);
  const output = clip.output_path || clip.render_quality?.output_path;
  const source = output ? apiPath(`artifact?path=${encodeURIComponent(output)}`) : null;
  const duration = clip.render_quality?.duration_ms || clip.end_ms - clip.start_ms;
  const editorHref = editHref || `/review/${encodeURIComponent(clip.id)}`;
  const rerendering = isClipRerendering(clip);
  const rerenderProgress = clip.rerender_job?.progress ?? 0;
  const rerenderMessage = clip.rerender_job?.message?.trim() || "";
  const overallScore = clipOverallScore(clip);
  const autoQualified = clipMeetsAutonomyThreshold(clip);
  const scoreThreshold = clipAutonomyThreshold(clip);
  const hygieneGate = clipHygieneGate(clip);
  const hygieneFlags = clipHygieneFlags(clip);
  const canApprove = Boolean(onApprove && canQuickApproveClip(clip));
  const isPublished = clip.status === "published";
  const isScheduled = clip.status === "scheduled" || clip.status === "ready_to_publish";
  const canSchedule = Boolean(onSchedule && clip.status === "approved" && !rerendering);
  const canReschedule = Boolean(onSchedule && (isScheduled || isPublished) && !rerendering);
  const canPublish = Boolean(onPublishNow && (clip.status === "approved" || isScheduled) && !rerendering);
  const canRepublish = Boolean(onPublishNow && isPublished && !rerendering);
  const hasCardMenu = Boolean(onDelete || canApprove || onSchedule || onPublishNow || (canMakeShortsFromClip(clip) && onMakeShorts));
  const menuBusy = deleting || approving || scheduling || publishing;
  const activityLabel = formatReviewActivityAt(clip.updated_at || clip.created_at);

  const pauseThisPreview = useCallback(() => {
    const video = videoRef.current;
    if (!video || video.paused) return;
    video.pause();
  }, []);

  useEffect(() => {
    return () => releaseReviewPreviewPlayback(pauseThisPreview);
  }, [pauseThisPreview]);

  function openDistribute(intent: ReviewDistributeIntent) {
    setMenuOpen(false);
    setDistributeIntent(intent);
  }

  useEffect(() => {
    if (!menuOpen) return;
    function onPointerDown(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [menuOpen]);

  async function togglePreview() {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      claimReviewPreviewPlayback(pauseThisPreview);
      video.muted = muted;
      try {
        await video.play();
      } catch {
        video.muted = true;
        setMuted(true);
        await video.play().catch(() => undefined);
      }
      return;
    }
    video.pause();
  }

  function toggleMuted(event: ReactMouseEvent<HTMLButtonElement>) {
    event.stopPropagation();
    const video = videoRef.current;
    const next = !muted;
    setMuted(next);
    if (video) video.muted = next;
  }

  const showSelectToggle = Boolean(selectionMode && selectable && onToggleSelect);

  return (
    <article
      onClick={
        showSelectToggle
          ? (event) => {
              if ((event.target as HTMLElement).closest("button, a")) return;
              onToggleSelect?.();
            }
          : undefined
      }
      className={`group w-full min-w-0 rounded-[24px] border bg-surface p-3 transition duration-200 hover:-translate-y-0.5 hover:shadow-glow motion-reduce:transform-none motion-reduce:transition-none ${
        showSelectToggle ? "cursor-pointer" : ""
      } ${
        selected
          ? "border-cyan/[0.35] ring-2 ring-cyan/25 ring-offset-2 ring-offset-canvas-deep"
          : "border-white/[0.08] hover:border-cyan/[0.20]"
      }`}
    >
      <div className="relative">
        <MediaPreviewFrame
          aspect={isExplainerClip(clip) ? "landscape" : "portrait"}
          src={source}
          videoRef={videoRef}
          muted={muted}
          loop
          preload="metadata"
          posterSeekSeconds={0.5}
          onMouseEnter={() => {
            const video = videoRef.current;
            if (video && video.paused && !playing) {
              video.muted = true;
              video.play().catch(() => undefined);
            }
          }}
          onMouseLeave={() => {
            const video = videoRef.current;
            if (video && !playing) {
              video.pause();
            }
          }}
          spacing="none"
          rounded="panel"
          showPlayHint={false}
          showVignette
          onPlay={() => {
            claimReviewPreviewPlayback(pauseThisPreview);
            setPlaying(true);
          }}
          onPause={() => {
            setPlaying(false);
            releaseReviewPreviewPlayback(pauseThisPreview);
          }}
          onEnded={() => {
            setPlaying(false);
            releaseReviewPreviewPlayback(pauseThisPreview);
          }}
          ariaLabel={`Preview ${clip.title_hook}`}
          emptyState={<div className="absolute inset-0 grid place-items-center text-sm text-zinc-600">Preview unavailable</div>}
        />
        {source && !selectionMode && !rerendering ? (
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
        {rerendering ? (
          <div className="absolute inset-0 z-[7] grid place-items-center rounded-[16px] bg-black/70 backdrop-blur-[2px]">
            <div className="flex max-w-[14rem] flex-col items-center gap-2 px-4 text-center">
              <Loader2 className="h-8 w-8 animate-spin text-cyan" aria-hidden />
              <p className="text-xs font-semibold text-white">Re-rendering…</p>
              {rerenderProgress > 0 ? (
                <p className="text-[11px] font-semibold tabular-nums text-cyan">{rerenderProgress}%</p>
              ) : null}
              {rerenderMessage ? (
                <p className="line-clamp-2 text-[10px] leading-4 text-zinc-400">{rerenderMessage}</p>
              ) : null}
            </div>
          </div>
        ) : null}
        {showSelectToggle ? (
          <div className="absolute left-2.5 top-2.5 z-[6]">
            <ReviewCardSelectToggle selected={selected} onToggle={onToggleSelect!} label={clip.title_hook} />
          </div>
        ) : null}
        {hasCardMenu && !selectionMode ? (
          <div className="absolute right-2.5 top-2.5 z-[5]" ref={menuRef}>
            <button
              type="button"
              disabled={menuBusy}
              onClick={(event) => {
                event.stopPropagation();
                setMenuOpen((open) => !open);
              }}
              className="grid h-8 w-8 place-items-center rounded-full border border-white/10 bg-black/55 text-white/80 shadow-md backdrop-blur-md transition hover:bg-black/70 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan disabled:opacity-40"
              aria-label={`More actions for ${clip.title_hook}`}
              aria-expanded={menuOpen}
              aria-controls={menuId}
            >
              {menuBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <MoreHorizontal className="h-3.5 w-3.5" />}
            </button>
            {menuOpen ? (
              <div
                id={menuId}
                role="menu"
                className="absolute right-0 top-10 z-50 w-56 overflow-hidden rounded-2xl border border-white/[0.08] bg-canvas-deep/95 p-1 shadow-2xl backdrop-blur-xl"
              >
                {canApprove ? (
                  <button
                    type="button"
                    role="menuitem"
                    disabled={menuBusy || rerendering}
                    onClick={() => {
                      setMenuOpen(false);
                      onApprove?.(clip);
                    }}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm text-teal transition hover:bg-teal/[0.08] disabled:opacity-40"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Approve
                  </button>
                ) : null}
                {canMakeShortsFromClip(clip) && onMakeShorts ? (
                  <button
                    type="button"
                    role="menuitem"
                    disabled={menuBusy}
                    onClick={() => {
                      setMenuOpen(false);
                      onMakeShorts(clip);
                    }}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm text-cyan transition hover:bg-cyan/[0.08] disabled:opacity-40"
                  >
                    <Scissors className="h-3.5 w-3.5" />
                    Make shorts
                  </button>
                ) : null}
                {canSchedule ? (
                  <button
                    type="button"
                    role="menuitem"
                    disabled={menuBusy}
                    onClick={() => openDistribute("schedule")}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm text-zinc-200 transition hover:bg-white/[0.06] disabled:opacity-40"
                  >
                    <Calendar className="h-3.5 w-3.5 text-cyan" />
                    Schedule
                  </button>
                ) : null}
                {canReschedule ? (
                  <button
                    type="button"
                    role="menuitem"
                    disabled={menuBusy}
                    onClick={() => openDistribute("reschedule")}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm text-zinc-200 transition hover:bg-white/[0.06] disabled:opacity-40"
                  >
                    <Calendar className="h-3.5 w-3.5 text-cyan" />
                    Reschedule
                  </button>
                ) : null}
                {canPublish ? (
                  <button
                    type="button"
                    role="menuitem"
                    disabled={menuBusy}
                    onClick={() => openDistribute("publish")}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm text-zinc-200 transition hover:bg-white/[0.06] disabled:opacity-40"
                  >
                    <Zap className="h-3.5 w-3.5 text-cyan" />
                    Publish now
                  </button>
                ) : null}
                {canRepublish ? (
                  <button
                    type="button"
                    role="menuitem"
                    disabled={menuBusy}
                    onClick={() => openDistribute("republish")}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm text-zinc-200 transition hover:bg-white/[0.06] disabled:opacity-40"
                  >
                    <RefreshCw className="h-3.5 w-3.5 text-cyan" />
                    Republish
                  </button>
                ) : null}
                {onDelete ? (
                  <button
                    type="button"
                    role="menuitem"
                    disabled={menuBusy}
                    onClick={() => {
                      setMenuOpen(false);
                      onDelete(clip);
                    }}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm text-danger transition hover:bg-danger/[0.08] disabled:opacity-40"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Delete clip
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}
        <span className="pointer-events-none absolute bottom-3 left-3 z-[4] flex items-center gap-1.5">
          <span className="rounded-full bg-black/65 px-2.5 py-1 text-[11px] font-semibold tabular-nums text-white backdrop-blur-md">
            {formatDuration(duration)}
          </span>
          {typeof clip.render_quality?.source_height === "number" && clip.render_quality.source_height < 720 ? (
            <span className="rounded-full border border-amber-400/40 bg-amber-500/20 px-2 py-1 text-[10px] font-semibold text-amber-100 backdrop-blur-md">
              {clip.render_quality.source_height}p source
            </span>
          ) : null}
        </span>
        {source && !rerendering ? (
          <button
            type="button"
            onClick={toggleMuted}
            className="absolute bottom-3 right-3 z-[6] grid h-8 w-8 place-items-center rounded-full border border-white/10 bg-black/55 text-white/90 shadow-md backdrop-blur-md transition hover:bg-black/70 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan"
            aria-label={muted ? `Unmute ${clip.title_hook}` : `Mute ${clip.title_hook}`}
          >
            {muted ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
          </button>
        ) : null}
      </div>

      <div className="px-1 pb-1 pt-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="line-clamp-2 text-sm font-semibold leading-5 text-white">{clip.title_hook}</h3>
            {activityLabel ? <p className="mt-1 text-[11px] text-zinc-500">{activityLabel}</p> : null}
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {rerendering ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-cyan/[0.35] bg-cyan/[0.12] px-2.5 py-1 text-[10px] font-semibold text-cyan">
                  <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
                  Re-rendering{rerenderProgress > 0 ? ` ${rerenderProgress}%` : ""}
                </span>
              ) : (
                <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold ${statusTone(clip.status)}`}>
                  {readinessLabel(clip)}
                </span>
              )}
              {needsMetadataRefresh(clip) ? (
                <span
                  className="inline-flex rounded-full border border-amber-400/35 bg-amber-500/15 px-2.5 py-1 text-[10px] font-semibold text-amber-100"
                  title="Hook title was auto-generated from transcript — open Edit → Metadata to refresh and re-render"
                >
                  Auto hook
                </span>
              ) : null}
              {overallScore != null ? (
                <span
                  className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[10px] font-semibold tabular-nums ${
                    autoQualified
                      ? "border-teal/[0.35] bg-teal/[0.12] text-teal"
                      : "border-amber-400/30 bg-amber-500/10 text-amber-100"
                  }`}
                  title={
                    autoQualified
                      ? `Performance score ${overallScore} meets autonomy threshold (${scoreThreshold})`
                      : `Performance score ${overallScore} is below autonomy threshold (${scoreThreshold})`
                  }
                >
                  {autoQualified ? <CheckCircle2 className="h-3 w-3" aria-hidden /> : null}
                  Performance {overallScore}
                  {autoQualified ? " · Auto-qualified" : ""}
                </span>
              ) : null}
              {hygieneGate ? (
                <span
                  className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold ${clipHygieneTone(hygieneGate)}`}
                  title={hygieneFlags.length ? hygieneFlags.join(", ") : clipHygieneLabel(hygieneGate)}
                >
                  {clipHygieneLabel(hygieneGate)}
                </span>
              ) : null}
            </div>
          </div>
          <Link
              href={editorHref}
              onClick={(event) => {
                if (selectionMode || rerendering) event.preventDefault();
              }}
              aria-disabled={selectionMode || rerendering}
              tabIndex={selectionMode || rerendering ? -1 : undefined}
              className={`inline-flex h-10 shrink-0 items-center gap-1.5 rounded-full border border-white/[0.10] bg-white/[0.04] px-3 text-xs font-semibold text-zinc-200 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan ${
                selectionMode || rerendering ? "pointer-events-none opacity-35" : "hover:border-cyan/[0.30] hover:text-cyan"
              }`}
            >
              Edit <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
        </div>
      </div>
      {distributeIntent ? (
        <ReviewDistributeDialog
          clip={clip}
          intent={distributeIntent}
          publishTargets={publishTargets}
          defaultPlatforms={defaultPublishPlatforms}
          busy={scheduling || publishing}
          onClose={() => setDistributeIntent(null)}
          onSchedule={(scheduledAt, platforms) => {
            setDistributeIntent(null);
            onSchedule?.(clip, scheduledAt, platforms);
          }}
          onPublish={(platforms) => {
            setDistributeIntent(null);
            onPublishNow?.(clip, platforms, {republish: distributeIntent === "republish" || isPublished});
          }}
        />
      ) : null}
    </article>
  );
}
