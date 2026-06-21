"use client";

import {useRef, useState, useEffect} from "react";
import {Play, Pause, Volume2, VolumeX} from "lucide-react";
import {MediaPreviewFrame} from "@/components/shared/MediaPreviewFrame";
import {HyperframesTemplate} from "@/lib/media-api";
import {getRecipeTheme, TemplateRecipeOverlay} from "@/components/templates/recipes";
import {recipeThemes} from "@/components/templates/recipes/recipeThemes";

export type TemplatePreviewFrame = "short" | "long";
const TEMPLATE_PREVIEW_SECONDS = 15;

/** @deprecated Use getRecipeTheme — kept for imports that expect legacy shape */
export const templatePreviewThemes = Object.fromEntries(
  Object.entries(recipeThemes).map(([id, theme]) => [
    id,
    {
      accent: theme.accent,
      secondary: theme.secondary,
      caption: theme.caption,
      caption2: theme.caption2,
      hook: theme.hook,
      body: theme.body,
      cta: theme.cta,
    },
  ]),
);

export function TemplatePreview({
  template,
  compact = false,
  gridCard = false,
  hideFooterLabel = false,
  flush = false,
  durationSeconds = TEMPLATE_PREVIEW_SECONDS,
  frame = "short",
  hoverToPlay = false,
  spacing,
}: {
  template: HyperframesTemplate;
  compact?: boolean;
  gridCard?: boolean;
  hideFooterLabel?: boolean;
  flush?: boolean;
  durationSeconds?: number;
  frame?: TemplatePreviewFrame;
  hoverToPlay?: boolean;
  spacing?: "card" | "compact" | "none";
}) {
  const theme = getRecipeTheme(template.id);
  const isLong = frame === "long";
  const previewKey = isLong ? "long_16_9" : "short_9_16";
  const previewUrl = template.preview_video_urls?.[previewKey] || template.preview_urls?.[previewKey];
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [shouldLoadPreview, setShouldLoadPreview] = useState(!hoverToPlay);
  const [videoLoaded, setVideoLoaded] = useState(false);
  const [videoError, setVideoError] = useState(false);

  const [isPlaying, setIsPlaying] = useState(true);
  const [isMuted, setIsMuted] = useState(true);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [controlsVisible, setControlsVisible] = useState(true);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    if (!compact && shouldLoadPreview) {
      const video = videoRef.current;
      if (video) {
        video.muted = isMuted;
        video.play().catch(() => {});
      }
    }
  }, [compact, shouldLoadPreview, isMuted]);

  const previewSize = compact
    ? isLong
      ? gridCard
        ? "aspect-video max-h-[14rem] w-full"
        : "aspect-video"
      : gridCard
        ? "aspect-[9/16] w-full max-w-full"
        : "aspect-[9/16]"
    : isLong
      ? "w-full max-w-[730px] aspect-video h-auto max-h-full"
      : "h-full aspect-[9/16] w-auto max-w-full";
  const badgeInset = gridCard ? "left-2 right-2 top-2" : "left-3 right-3 top-3";
  const footerInset = gridCard ? "bottom-2 left-2 right-2" : "bottom-3 left-3 right-3";
  const frameLabel = compact ? (isLong ? "15s · 16:9" : "15s · 9:16") : `${durationSeconds}s · ${isLong ? "Long 16:9" : "Short/Reels 9:16"}`;
  const renderLabel = compact ? "HF render" : "HyperFrames render";
  const hoverLabel = gridCard ? "Hover" : compact && !isLong ? "Hover preview" : "Hover to play real preview";
  const previewStyle = {
    "--preview-accent": theme.accent,
    "--preview-secondary": theme.secondary,
    "--preview-duration": `${durationSeconds}s`,
    "--preview-word-duration": `${Math.max(2.4, durationSeconds / 3)}s`,
  } as React.CSSProperties;
  const formatClock = (totalSeconds: number) => {
    if (!Number.isFinite(totalSeconds) || totalSeconds <= 0) return "0:00";
    const rounded = Math.floor(totalSeconds);
    const minutes = Math.floor(rounded / 60);
    const seconds = rounded % 60;
    return `${minutes}:${String(seconds).padStart(2, "0")}`;
  };

  const togglePlayback = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      video.play().catch(() => {});
      setIsPlaying(true);
    } else {
      video.pause();
      setIsPlaying(false);
    }
  };

  const seekTo = (nextTime: number) => {
    const video = videoRef.current;
    if (!video || !Number.isFinite(video.duration) || video.duration <= 0) return;
    const clamped = Math.min(video.duration, Math.max(0, nextTime));
    video.currentTime = clamped;
    setCurrentTime(clamped);
  };

  const toggleMuted = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const video = videoRef.current;
    if (!video) return;
    const next = !video.muted;
    video.muted = next;
    setIsMuted(next);
  };

  const playPreview = () => {
    if (!hoverToPlay) return;
    setShouldLoadPreview(true);
    setVideoLoaded(false);
    setVideoError(false);
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = 0;
    window.setTimeout(() => void video.play().catch(() => undefined), 0);
  };
  const pausePreview = () => {
    if (!hoverToPlay) return;
    const video = videoRef.current;
    if (!video) return;
    video.pause();
    video.currentTime = 0;
  };

  const showVideo = Boolean(previewUrl && shouldLoadPreview && !videoError);
  const showRecipeOverlay = !showVideo || (shouldLoadPreview && !videoLoaded && !videoError);
  const rounded = flush ? "none" : gridCard ? "panel" : compact ? "detail" : "detail";

  return (
    <MediaPreviewFrame
      aspect={isLong ? "landscape" : "portrait"}
      src={showVideo ? previewUrl : null}
      videoRef={videoRef}
      videoKey={`${template.id}:${previewKey}:${previewUrl}`}
      className={flush ? "template-card-preview" : `template-card-preview mx-auto ${previewSize}`}
      shellClassName={flush ? "!mb-0 !rounded-none !border-0 !shadow-none" : ""}
      rounded={rounded}
      spacing={spacing ?? (flush ? "none" : gridCard ? "card" : compact ? "compact" : "compact")}
      fillParent={flush}
      preload={hoverToPlay ? "none" : "metadata"}
      muted={compact ? true : isMuted}
      showPlayHint={hoverToPlay && Boolean(previewUrl)}
      showVignette={!flush}
      onMouseEnter={playPreview}
      onMouseLeave={pausePreview}
      onFocus={playPreview}
      onBlur={pausePreview}
      onLoadedData={() => {
        setVideoLoaded(true);
        setIsReady(true);
        const video = videoRef.current;
        if (video) {
          setDuration(video.duration || 0);
          setCurrentTime(video.currentTime || 0);
        }
      }}
      onError={() => setVideoError(true)}
      onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime || 0)}
      onPlay={() => setIsPlaying(true)}
      onPause={() => setIsPlaying(false)}
      onEnded={() => setIsPlaying(false)}
      ariaLabel={`${template.label} ${durationSeconds}s HyperFrames preview`}
      emptyState={
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_45%_28%,rgba(255,255,255,0.16),transparent_25%),linear-gradient(160deg,rgba(18,22,26,1),rgba(4,5,7,1)_58%,rgba(0,0,0,1))]" style={previewStyle} />
      }
    >
      {showRecipeOverlay ? <TemplateRecipeOverlay templateId={template.id} theme={theme} compact={compact || gridCard} /> : null}
      {showVideo ? (
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_45%_28%,rgba(255,255,255,0.08),transparent_30%)]" style={previewStyle} />
      ) : null}
      {videoError ? (
        <div className="absolute inset-0 z-[3] grid place-items-center bg-black/35">
          <div className="whitespace-nowrap rounded-full border border-white/[0.14] bg-black/65 px-4 py-2 text-xs font-semibold leading-4 text-zinc-100">
            Preview failed — showing recipe
          </div>
        </div>
      ) : null}
      {previewUrl && shouldLoadPreview && !videoError && !videoLoaded ? (
        <div className="absolute inset-0 z-[3] grid place-items-center bg-black/28">
          <div className="rounded-full border border-white/[0.14] bg-black/65 px-4 py-2 text-xs font-semibold text-zinc-100">Loading preview...</div>
        </div>
      ) : null}
      {!flush ? (
        <>
          <div className="absolute inset-x-0 top-0 z-[4] h-24 bg-gradient-to-b from-black/70 via-black/20 to-transparent" />
          <div className="absolute inset-x-0 bottom-0 z-[4] h-28 bg-gradient-to-t from-black/82 via-black/24 to-transparent" />
        </>
      ) : null}
      {!flush ? (
        <div className={`absolute ${badgeInset} z-[5] flex items-center justify-between gap-1.5`}>
          <div className={`rounded-full border border-white/[0.12] bg-black/62 font-bold text-zinc-200 ${gridCard ? "px-2 py-0.5 text-[9px]" : "px-2.5 py-1 text-[10px]"}`}>{frameLabel}</div>
          <div className={`rounded-full border border-[var(--preview-accent)]/30 bg-black/62 font-bold text-[var(--preview-accent)] ${gridCard ? "px-2 py-0.5 text-[9px]" : "px-2.5 py-1 text-[10px]"}`} style={previewStyle}>
            {renderLabel}
          </div>
        </div>
      ) : null}
      {!hideFooterLabel && !flush ? (
        <div className={`absolute ${footerInset} z-[5] min-w-0 transition-opacity duration-200 ${!compact && controlsVisible && isPlaying ? "opacity-35" : "opacity-100"}`}>
          <p className={`truncate font-black text-white drop-shadow-[0_3px_12px_rgba(0,0,0,.9)] ${gridCard ? "text-xs" : "text-sm"}`}>{template.label}</p>
          {!compact ? <p className="mt-1 line-clamp-2 text-xs leading-4 text-zinc-300">{template.best_for}</p> : null}
        </div>
      ) : null}
      {hoverToPlay && previewUrl && !shouldLoadPreview ? (
        <div className="template-preview-play-hint absolute inset-0 z-20 grid place-items-center bg-black/20 transition duration-200">
          <span className="whitespace-nowrap rounded-full border border-white/[0.16] bg-black/72 px-4 py-2 text-xs font-black leading-4 text-white shadow-2xl">{hoverLabel}</span>
        </div>
      ) : null}

      {!compact && showVideo ? (
        <>
          <div
            className="absolute inset-0 z-[2] cursor-pointer"
            onClick={togglePlayback}
            onMouseMove={() => {
              setControlsVisible(true);
              const win = window as Window & {_templateControlsTimeout?: number};
              window.clearTimeout(win._templateControlsTimeout);
              if (isPlaying) {
                win._templateControlsTimeout = window.setTimeout(() => {
                  setControlsVisible(false);
                }, 2200);
              }
            }}
            onMouseLeave={() => {
              if (isPlaying) setControlsVisible(false);
            }}
          />
          <div
            className={`pointer-events-none absolute inset-x-0 bottom-0 z-[6] bg-gradient-to-t from-black/85 via-black/10 to-transparent px-3 pb-3 pt-6 transition-opacity duration-200 ${controlsVisible || !isPlaying ? "opacity-100" : "opacity-0"}`}
            onMouseEnter={() => setControlsVisible(true)}
          >
            <div className="pointer-events-auto rounded-[14px] border border-white/[0.08] bg-[#0c0d10]/42 px-3 py-2 shadow-2xl backdrop-blur-md">
              <input
                type="range"
                min={0}
                max={Math.max(duration, 0)}
                step={0.1}
                value={Math.min(currentTime, duration || 0)}
                onInput={(event) => seekTo(Number(event.currentTarget.value))}
                onChange={(event) => seekTo(Number(event.target.value))}
                className="h-1.5 w-full cursor-pointer accent-cyan bg-white/18 rounded-lg appearance-none transition hover:bg-white/25"
                aria-label="Seek preview video"
                disabled={!isReady}
              />
              <div className="mt-1.5 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={togglePlayback}
                    className="grid h-7 w-7 place-items-center rounded-full bg-cyan text-ink transition hover:bg-cyan/90 disabled:opacity-45"
                    disabled={!isReady}
                    aria-label={isPlaying ? "Pause video" : "Play video"}
                  >
                    {isPlaying ? <Pause className="h-3.5 w-3.5 fill-current" /> : <Play className="ml-0.5 h-3.5 w-3.5 fill-current" />}
                  </button>
                  <button
                    type="button"
                    onClick={toggleMuted}
                    className="grid h-7 w-7 place-items-center rounded-full border border-white/10 bg-white/8 text-zinc-200 transition hover:bg-white/15"
                    disabled={!isReady}
                    aria-label={isMuted ? "Unmute video" : "Mute video"}
                  >
                    {isMuted ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
                  </button>
                </div>
                <div className="text-[10px] font-semibold tabular-nums text-zinc-300">
                  {formatClock(currentTime)} / {formatClock(duration)}
                </div>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </MediaPreviewFrame>
  );
}
