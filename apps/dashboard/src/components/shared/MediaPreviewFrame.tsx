"use client";

import {Play} from "lucide-react";
import {useRef, type ReactNode, type RefObject} from "react";

export type MediaPreviewAspect = "portrait" | "landscape";

/** Matches Review grid card column width (xl: minmax(17.5rem, 1fr)) */
export const MEDIA_PREVIEW_GRID_MAX_W = "17.5rem";
export const mediaPreviewGridPortraitClass = "mx-auto w-full max-w-[17.5rem] aspect-[9/16]";
export const mediaPreviewGridLandscapeClass = "mx-auto w-full max-w-[17.5rem] aspect-video";

const aspectClass: Record<MediaPreviewAspect, string> = {
  portrait: "aspect-[9/16]",
  landscape: "aspect-video",
};

const roundedClass = {
  card: "rounded-[14px]",
  panel: "rounded-[16px]",
  bezel: "rounded-[34px]",
  detail: "rounded-[22px]",
  none: "",
} as const;

export type MediaPreviewFrameProps = {
  aspect?: MediaPreviewAspect;
  src?: string | null;
  videoRef?: RefObject<HTMLVideoElement | null>;
  className?: string;
  shellClassName?: string;
  rounded?: keyof typeof roundedClass;
  /** Bottom margin under frame in card layouts */
  spacing?: "card" | "compact" | "none";
  /** Stretch to fill a positioned parent (Brand Builder phone screen) */
  fillParent?: boolean;
  muted?: boolean;
  loop?: boolean;
  playsInline?: boolean;
  preload?: "none" | "metadata" | "auto";
  showPlayHint?: boolean;
  showVignette?: boolean;
  emptyState?: ReactNode;
  children?: ReactNode;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
  onFocus?: () => void;
  onBlur?: () => void;
  videoKey?: string;
  onLoadedData?: () => void;
  onError?: () => void;
  onTimeUpdate?: (event: React.SyntheticEvent<HTMLVideoElement>) => void;
  onPlay?: () => void;
  onPause?: () => void;
  onEnded?: () => void;
  /** Seek once after metadata so Review posters skip a corrupt first frame. */
  posterSeekSeconds?: number;
  ariaLabel?: string;
  /** Cap width to Review grid card footprint (17.5rem) */
  gridMatch?: boolean;
};

export function MediaPreviewFrame({
  aspect = "portrait",
  src,
  videoRef,
  className = "",
  shellClassName = "",
  rounded = "card",
  spacing = "card",
  fillParent = false,
  muted = true,
  loop = true,
  playsInline = true,
  preload = "metadata",
  showPlayHint = false,
  showVignette = true,
  emptyState,
  children,
  onMouseEnter,
  onMouseLeave,
  onFocus,
  onBlur,
  videoKey,
  onLoadedData,
  onError,
  onTimeUpdate,
  onPlay,
  onPause,
  onEnded,
  ariaLabel,
  posterSeekSeconds = 0,
  gridMatch = false,
}: MediaPreviewFrameProps) {
  const hasVideo = Boolean(src);
  const spacingClass = spacing === "card" ? "mb-2.5" : spacing === "compact" ? "mb-4" : "";
  const gridMatchClass = gridMatch ? "mx-auto w-full max-w-[17.5rem]" : "";
  const posterSeekedKey = useRef("");

  function seekPoster(video: HTMLVideoElement) {
    if (posterSeekSeconds <= 0) return;
    const key = `${src ?? ""}:${posterSeekSeconds}`;
    if (posterSeekedKey.current === key) return;
    if (!Number.isFinite(video.duration) || video.duration < posterSeekSeconds) return;
    if (!video.paused) return;
    posterSeekedKey.current = key;
    video.currentTime = posterSeekSeconds;
  }

  return (
    <div
      className={`media-preview-frame relative w-full overflow-hidden border border-white/[0.08] bg-[#050507] shadow-inner transition-[border-color,box-shadow] duration-200 ${fillParent ? "absolute inset-0 !aspect-auto h-full w-full" : aspectClass[aspect]} ${gridMatchClass} ${roundedClass[rounded]} ${spacingClass} ${shellClassName} ${className}`}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onFocus={onFocus}
      onBlur={onBlur}
      aria-label={ariaLabel}
    >
      {hasVideo ? (
        <video
          key={videoKey ?? src ?? undefined}
          ref={videoRef}
          src={src!}
          className="absolute inset-0 h-full w-full object-contain"
          muted={muted}
          loop={loop}
          playsInline={playsInline}
          preload={preload}
          onLoadedMetadata={(event) => seekPoster(event.currentTarget)}
          onLoadedData={onLoadedData}
          onError={onError}
          onTimeUpdate={onTimeUpdate}
          onPlay={onPlay}
          onPause={onPause}
          onEnded={onEnded}
        />
      ) : (
        emptyState
      )}
      {showVignette ? (
        <div className="pointer-events-none absolute inset-0 z-[1] bg-gradient-to-t from-black/55 via-transparent to-black/30" />
      ) : null}
      {hasVideo && showPlayHint ? (
        <div className="media-preview-frame-play-hint pointer-events-none absolute inset-0 z-[2] flex items-center justify-center">
          <div className="rounded-full border border-white/[0.12] bg-black/45 p-2.5 backdrop-blur-md">
            <Play className="h-5 w-5 fill-white/90 text-white/90" />
          </div>
        </div>
      ) : null}
      {children}
    </div>
  );
}
