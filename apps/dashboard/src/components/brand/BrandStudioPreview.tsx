"use client";

import {HelpCircle, Pause, Play, RotateCcw} from "lucide-react";
import {useEffect, useMemo, useRef, useState, type CSSProperties, type RefObject} from "react";
import {MediaPreviewFrame} from "@/components/shared/MediaPreviewFrame";
import {hyperframesTemplateStockUrl, type HyperframesTemplate} from "@/lib/media-api";
import type {RecipePreviewFormat} from "@/components/brand/useRecipePreviewVideo";

export type CaptionPosition = "bottom" | "center" | "top";
export type PreviewAspectRatio = "9:16" | "16:9";
export type PreviewBackground = "dark" | "light" | "vignette";
export type PreviewStageView = "live" | "baked";

const CAPTION_LINE_WORDS = 5;
const BRAND_STUDIO_PREVIEW_SECONDS = 8;
const CTA_HOLD_MIN_S = 1.6;
const CTA_HOLD_MAX_S = 2.2;
const LIVE_INTRO_OVERLAY_MAX_S = 1.5;
const OVERLAY_CTA_GAP_S = 0.25;

export const SAMPLE_PHRASE_PRESETS = [
  {id: "devotional", label: "Bahasa", text: "Ketenangan hati hadir saat bersyukur."},
  {id: "tech", label: "Tech", text: "AI agents will change how software is built."},
  {id: "english", label: "English", text: "This is the most important lesson."},
] as const;

export type BrandStudioLook = {
  fontFamily: string;
  fontSize: number;
  textColor: string;
  highlightColor: string;
  backgroundColor: string;
  strokeWidth: number;
  watermarkText: string;
  motionIntensity: string;
  position?: CaptionPosition;
  uppercase?: boolean;
  aspectRatio?: PreviewAspectRatio;
};

export type BrandStudioEffects = {
  starterId: string;
  captionStyle: string;
  textureEffects?: string[];
  ctaOverlay: string;
  introLayout: string;
  extraBlocks?: string[];
};

type BrandStudioPreviewProps = {
  look: BrandStudioLook;
  effects?: BrandStudioEffects;
  recipeTemplate?: HyperframesTemplate | null;
  sampleText?: string;
  onSampleTextChange?: (text: string) => void;
  showToolbar?: boolean;
  bakedPreviewUrl?: string | null;
  bakeBusy?: boolean;
  bakeError?: string | null;
  onRenderFiveSecondLook?: (format: RecipePreviewFormat) => void;
  dirty?: boolean;
};

type CaptionChrome = {
  plateRadius: string;
  platePadding: string;
  plateBackground: string;
  plateShadow?: string;
  wordGap: string;
};

/** Live preview on sample footage, plus an optional rendered clip. */
export function BrandStudioPreview({
  look,
  effects,
  recipeTemplate,
  sampleText: controlledSampleText,
  onSampleTextChange,
  showToolbar = true,
  bakedPreviewUrl,
  bakeBusy = false,
  bakeError,
  onRenderFiveSecondLook,
  dirty = false,
}: BrandStudioPreviewProps) {
  const [activeWord, setActiveWord] = useState(0);
  const [aspectRatio, setAspectRatio] = useState<PreviewAspectRatio>(look.aspectRatio || "9:16");
  const [background, setBackground] = useState<PreviewBackground>("dark");
  const [safeZones, setSafeZones] = useState(false);
  const [playing, setPlaying] = useState(true);
  const [phrasePreset, setPhrasePreset] = useState<string>("devotional");
  const [customPhrase, setCustomPhrase] = useState("");
  const [stageView, setStageView] = useState<PreviewStageView>("live");
  const [phaseTime, setPhaseTime] = useState(0);
  const stockVideoRef = useRef<HTMLVideoElement | null>(null);
  const bakedVideoRef = useRef<HTMLVideoElement | null>(null);

  const previewFormat = aspectRatio === "16:9" ? "long_16_9" : "short_9_16";
  const stockUrl = useMemo(
    () => (recipeTemplate ? hyperframesTemplateStockUrl(recipeTemplate, previewFormat) : null),
    [recipeTemplate, previewFormat],
  );

  const liveMode = stageView === "live";
  const bakedMode = stageView === "baked" && Boolean(bakedPreviewUrl);
  const activeVideoRef = bakedMode ? bakedVideoRef : stockVideoRef;
  const activeVideoUrl = bakedMode ? bakedPreviewUrl : stockUrl;
  const showActiveVideo = bakedMode ? Boolean(bakedPreviewUrl) : Boolean(stockUrl);

  const sampleText = controlledSampleText
    ?? (phrasePreset === "custom"
      ? customPhrase
      : SAMPLE_PHRASE_PRESETS.find((item) => item.id === phrasePreset)?.text
        || SAMPLE_PHRASE_PRESETS[0].text);

  const words = useMemo(() => {
    const raw = sampleText.trim() || SAMPLE_PHRASE_PRESETS[0].text;
    return raw.split(/\s+/).filter(Boolean);
  }, [sampleText]);

  const highlightIndex = Math.max(0, Math.min(words.length - 1, Math.floor(words.length * 0.45)));
  const lineStart = Math.max(0, Math.min(activeWord, Math.max(0, words.length - CAPTION_LINE_WORDS)));
  const lineWords = words.slice(lineStart, lineStart + CAPTION_LINE_WORDS);

  const pace = look.motionIntensity === "energetic" ? 420 : look.motionIntensity === "calm" ? 900 : 620;
  const captionPx = Math.min(
    Math.max(look.fontSize * (aspectRatio === "16:9" ? 0.28 : 0.32), 16),
    aspectRatio === "16:9" ? 28 : 22,
  );
  const captionStyle = effects?.captionStyle || "caption-editorial-emphasis";
  const textureEffects = effects?.textureEffects?.length ? effects.textureEffects : [];
  const ctaOverlay = effects?.ctaOverlay || "none";
  const introLayout = effects?.introLayout || "template-hook";
  const placement = useMemo(
    () => placementBeats(BRAND_STUDIO_PREVIEW_SECONDS, introLayout, ctaOverlay),
    [introLayout, ctaOverlay],
  );
  const showIntroOverlay = liveMode && placement.showRecipeOverlay && phaseTime < placement.overlayExit;
  const showIntroBlock = liveMode && placement.showIntroBlock && phaseTime < placement.introBlockEnd;
  const captionStart = placement.showIntroBlock
    ? placement.introBlockEnd
    : placement.showRecipeOverlay
      ? placement.overlayExit
      : 0;
  const showLiveCaption = liveMode && phaseTime >= captionStart && phaseTime < placement.ctaStart;
  const showOutroCallout = liveMode && Boolean(ctaOverlay && ctaOverlay !== "none") && phaseTime >= placement.ctaStart;
  const position = look.position || "bottom";
  const chrome = captionChrome(captionStyle, look);

  useEffect(() => {
    setActiveWord(0);
  }, [sampleText]);

  useEffect(() => {
    if (bakedPreviewUrl) setStageView("baked");
  }, [bakedPreviewUrl]);

  useEffect(() => {
    if (dirty) setStageView("live");
  }, [dirty]);

  useEffect(() => {
    if (!liveMode || !playing || words.length < 2) return;
    const id = window.setInterval(() => {
      setActiveWord((current) => (current + 1) % words.length);
    }, pace);
    return () => window.clearInterval(id);
  }, [liveMode, pace, playing, words.length]);

  useEffect(() => {
    const video = activeVideoRef.current;
    if (!video || !showActiveVideo) return;
    if (playing) {
      void video.play().catch(() => undefined);
    } else {
      video.pause();
    }
  }, [playing, showActiveVideo, activeVideoUrl, activeVideoRef]);

  useEffect(() => {
    const video = stockVideoRef.current;
    if (!liveMode || !video || !stockUrl) return;
    const onTimeUpdate = () => {
      setPhaseTime(video.currentTime % BRAND_STUDIO_PREVIEW_SECONDS);
    };
    video.addEventListener("timeupdate", onTimeUpdate);
    return () => video.removeEventListener("timeupdate", onTimeUpdate);
  }, [liveMode, stockUrl]);

  useEffect(() => {
    if (!liveMode || !playing || stockUrl) return;
    const started = performance.now();
    const id = window.setInterval(() => {
      const elapsed = (performance.now() - started) / 1000;
      setPhaseTime(elapsed % BRAND_STUDIO_PREVIEW_SECONDS);
    }, 50);
    return () => window.clearInterval(id);
  }, [liveMode, playing, stockUrl]);

  const frameStyle: CSSProperties = aspectRatio === "16:9"
    ? {aspectRatio: "16 / 9", width: "min(62rem, 100%, calc(78dvh * 16 / 9))"}
    : {aspectRatio: "9 / 16", width: "min(27rem, 100%, calc(80dvh * 9 / 16))"};
  const stageToolbarWidth = aspectRatio === "16:9" ? "max-w-5xl" : "max-w-2xl";

  const stageBackground = stageBackgroundStyle(background, look.highlightColor);

  function togglePlayback() {
    setPlaying((current) => !current);
  }

  function replayPreview() {
    setActiveWord(0);
    setPhaseTime(0);
    const video = activeVideoRef.current;
    if (video && showActiveVideo) {
      video.currentTime = 0;
      void video.play().catch(() => undefined);
    }
    setPlaying(true);
  }

  return (
    <div className="flex h-full max-h-full w-full flex-col items-center justify-center gap-2.5 py-1">
      {showToolbar ? (
        <div className={`flex w-full ${stageToolbarWidth} items-center justify-between gap-2 px-1`}>
          <div className="flex flex-wrap items-center gap-1">
            <ToolbarToggle
              label="Live (approx.)"
              active={stageView === "live"}
              onClick={() => setStageView("live")}
              title="Approximate intro, caption, and subscribe timing on sample footage. Updates as you edit."
            />
            {bakedPreviewUrl ? (
              <ToolbarToggle
                label="Rendered (exact)"
                active={stageView === "baked"}
                onClick={() => setStageView("baked")}
                title="Exact HyperFrames render with real intro/outro beats."
              />
            ) : null}
          </div>
          <div className="flex items-center gap-1">
            <ToolbarToggle label="9:16" active={aspectRatio === "9:16"} onClick={() => setAspectRatio("9:16")} title="Portrait — Shorts, Reels, and TikTok." />
            <ToolbarToggle label="16:9" active={aspectRatio === "16:9"} onClick={() => setAspectRatio("16:9")} title="Landscape — YouTube and long-form." />
          </div>
          {onRenderFiveSecondLook ? (
            <span className="inline-flex shrink-0 items-center gap-1">
              <button
                type="button"
                disabled={bakeBusy}
                onClick={() => onRenderFiveSecondLook(previewFormat)}
                title="Renders a short preview with this look. Takes a few seconds; run again after you change colors or captions."
                className="inline-flex h-8 items-center rounded-full border border-cyan/30 bg-cyan/[0.12] px-3 text-xs font-semibold text-cyan transition hover:bg-cyan/[0.2] disabled:opacity-50"
              >
                {bakeBusy ? "Rendering…" : "Render preview"}
              </button>
              <StageTooltip text="Renders an 8s clip with exact intro/outro timing. Takes a few seconds. Edit anything and it goes back to live preview." />
            </span>
          ) : (
            <span className="w-px shrink-0" aria-hidden />
          )}
        </div>
      ) : null}

      {bakeError ? (
        <p className="rounded-full border border-rose-500/30 bg-rose-500/10 px-3 py-1 text-[11px] font-medium text-rose-200">
          {bakeError}
        </p>
      ) : null}

      <div
        className="relative shrink-0 overflow-hidden rounded-[24px] border border-white/[0.1] shadow-[0_28px_80px_rgba(0,0,0,.4)]"
        style={{...frameStyle, background: liveMode && !stockUrl ? stageBackground : "#050507"}}
      >
        {liveMode && stockUrl ? (
          <StageVideoLayer
            previewUrl={stockUrl}
            videoRef={stockVideoRef}
            ariaLabel="Sample footage"
          />
        ) : null}

        {bakedMode && bakedPreviewUrl ? (
          <StageVideoLayer
            previewUrl={bakedPreviewUrl}
            videoRef={bakedVideoRef}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            ariaLabel="Rendered brand preview"
          />
        ) : null}

        {liveMode ? textureEffects.map((effect) => <TextureLayer key={effect} effect={effect} />) : null}

        {safeZones ? <SafeZoneOverlay aspectRatio={aspectRatio} /> : null}

        {liveMode ? (
          <>
            {look.watermarkText ? (
              <div className="absolute left-3.5 top-3.5 z-20 flex items-center gap-1.5 rounded-full border border-white/10 bg-black/40 px-2.5 py-1 text-[10px] font-medium tracking-wide text-white/70 backdrop-blur-md">
                {look.watermarkText}
              </div>
            ) : null}
            {showIntroOverlay ? (
              <div className="absolute inset-x-0 top-[20%] z-20 flex justify-center px-6">
                <p
                  className="max-w-[88%] text-center text-lg font-semibold leading-snug tracking-tight text-white/95 drop-shadow-[0_2px_12px_rgba(0,0,0,.55)]"
                  style={{fontFamily: look.fontFamily}}
                >
                  {sampleText}
                </p>
              </div>
            ) : null}
            {showIntroBlock ? (
              <div className="absolute inset-x-0 bottom-[14%] z-20 flex flex-col items-center px-5">
                <p className="mb-1.5 text-[8px] font-semibold uppercase tracking-widest text-zinc-500/90">Intro card</p>
                <OutroCalloutCard overlay="yt-lower-third" accent={look.highlightColor} />
              </div>
            ) : null}
            {showLiveCaption ? (
              <div className={`absolute inset-x-0 z-30 flex flex-col items-center px-5 ${captionPositionClass(position)}`}>
                <CaptionPlate
                  chrome={chrome}
                  look={look}
                  captionPx={captionPx}
                  captionStyle={captionStyle}
                  words={lineWords}
                  activeWord={Math.max(0, activeWord - lineStart)}
                  highlightIndex={Math.max(-1, highlightIndex - lineStart)}
                />
              </div>
            ) : null}
            {showOutroCallout ? (
              <div className="absolute inset-x-0 bottom-[14%] z-20 flex flex-col items-center px-5">
                <p className="mb-1.5 text-[8px] font-semibold uppercase tracking-widest text-zinc-500/90">Subscribe prompt (approx.)</p>
                <OutroCalloutCard overlay={ctaOverlay} accent={look.highlightColor} />
              </div>
            ) : null}
          </>
        ) : null}
      </div>

      {showToolbar ? (
        <div className={`flex w-full ${stageToolbarWidth} flex-wrap items-center justify-between gap-2 px-1`}>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={togglePlayback}
              className="inline-flex h-8 items-center gap-1 rounded-full border border-white/[0.10] bg-black/30 px-3 text-xs font-semibold text-zinc-300 hover:border-cyan/30 hover:text-white"
              aria-label={playing ? "Pause preview" : "Play preview"}
            >
              {playing ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
              {playing ? "Pause" : "Play"}
            </button>
            <button
              type="button"
              onClick={replayPreview}
              className="inline-flex h-8 items-center gap-1 rounded-full border border-white/[0.10] bg-black/30 px-3 text-xs font-semibold text-zinc-300 hover:border-cyan/30 hover:text-white"
              aria-label="Replay preview"
            >
              <RotateCcw className="h-3 w-3" />
              Replay
            </button>
          </div>
          {liveMode ? (
            <div className="flex flex-wrap items-center justify-center gap-1">
              {SAMPLE_PHRASE_PRESETS.map((preset) => (
                <ToolbarToggle
                  key={preset.id}
                  label={preset.label}
                  active={phrasePreset === preset.id}
                  onClick={() => {
                    setPhrasePreset(preset.id);
                    onSampleTextChange?.(preset.text);
                  }}
                />
              ))}
              <ToolbarToggle
                label="Custom"
                active={phrasePreset === "custom"}
                onClick={() => setPhrasePreset("custom")}
              />
            </div>
          ) : (
            <span className="flex-1" />
          )}
          <ToolbarToggle label="Safe zones" active={safeZones} onClick={() => setSafeZones((current) => !current)} />
        </div>
      ) : null}

      {phrasePreset === "custom" && showToolbar && liveMode ? (
        <input
          type="text"
          value={customPhrase}
          onChange={(event) => {
            setCustomPhrase(event.target.value);
            onSampleTextChange?.(event.target.value);
          }}
          placeholder="Type a one-line caption…"
          className="h-9 w-full max-w-2xl rounded-full border border-white/[0.08] bg-black/25 px-4 text-xs text-zinc-200 outline-none focus:border-cyan/30"
        />
      ) : null}

      <p className={`max-w-md text-center text-xs font-medium leading-relaxed tracking-wide text-zinc-500 ${stageToolbarWidth}`}>
        {aspectRatio}
        {recipeTemplate ? ` · ${recipeTemplate.label}` : ""}
        {liveMode ? " · Live timing is approximate" : ""}
        {bakedMode ? " · Rendered preview (exact)" : ""}
        {bakeBusy ? " · Rendering preview…" : ""}
      </p>
    </div>
  );
}

function CaptionPlate({
  chrome,
  look,
  captionPx,
  captionStyle,
  words,
  activeWord,
  highlightIndex,
}: {
  chrome: CaptionChrome;
  look: BrandStudioLook;
  captionPx: number;
  captionStyle: string;
  words: string[];
  activeWord: number;
  highlightIndex: number;
}) {
  return (
    <div
      className={`inline-flex max-w-[88%] items-center overflow-hidden whitespace-nowrap text-center transition-[background,color,box-shadow,border-radius,padding] duration-300 ${chrome.plateRadius} ${chrome.platePadding}`}
      style={{
        background: chrome.plateBackground === "transparent" ? undefined : chrome.plateBackground,
        width: "fit-content",
        maxWidth: "92%",
        color: look.textColor,
        fontFamily: look.fontFamily,
        fontSize: `${captionPx}px`,
        fontWeight: 800,
        letterSpacing: "-0.02em",
        lineHeight: 1.15,
        boxShadow: chrome.plateShadow,
        textTransform: look.uppercase ? "uppercase" : "none",
        WebkitTextStroke:
          look.strokeWidth > 0 && !captionStyle.includes("neon")
            ? `${Math.min(look.strokeWidth / 4, 2)}px rgba(0,0,0,.45)`
            : undefined,
      }}
    >
      <p className={`flex flex-nowrap items-center justify-center ${chrome.wordGap}`}>
        {words.map((word, index) => {
          const isActive = index === activeWord;
          const isHighlightWord = index === highlightIndex;
          const displayWord = look.uppercase ? word.toUpperCase() : word;
          return (
            <span
              key={`${word}-${index}`}
              className="inline-block whitespace-nowrap transition-[color,transform,background,text-shadow,filter] duration-200"
              style={wordStyle({
                captionStyle,
                look,
                isActive,
                isHighlightWord,
              })}
            >
              {displayWord}
            </span>
          );
        })}
      </p>
    </div>
  );
}

function StageVideoLayer({
  previewUrl,
  videoRef,
  ariaLabel,
  onLoaded,
  onError,
  onPlay,
  onPause,
}: {
  previewUrl: string;
  videoRef: RefObject<HTMLVideoElement | null>;
  ariaLabel: string;
  onLoaded?: () => void;
  onError?: () => void;
  onPlay?: () => void;
  onPause?: () => void;
}) {
  return (
    <MediaPreviewFrame
      fillParent
      src={previewUrl}
      videoRef={videoRef}
      videoKey={previewUrl}
      rounded="none"
      spacing="none"
      muted
      loop
      preload="metadata"
      showVignette={false}
      videoClassName="object-cover"
      className="!absolute inset-0 !aspect-auto h-full w-full !rounded-none border-0"
      shellClassName="!absolute inset-0 !mb-0 !aspect-auto h-full w-full !rounded-none !border-0 !shadow-none"
      onLoadedData={onLoaded}
      onError={onError}
      onPlay={onPlay}
      onPause={onPause}
      ariaLabel={ariaLabel}
    />
  );
}

function ToolbarToggle({label, active, onClick, title}: {label: string; active: boolean; onClick: () => void; title?: string}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={`inline-flex h-8 items-center rounded-full border px-3 text-xs font-semibold transition ${
        active ? "border-cyan/40 bg-cyan/[0.12] text-white" : "border-white/[0.08] bg-black/25 text-zinc-400 hover:text-zinc-200"
      }`}
    >
      {label}
    </button>
  );
}

function StageTooltip({text}: {text: string}) {
  return (
    <span className="group relative inline-flex shrink-0">
      <HelpCircle className="h-3.5 w-3.5 text-zinc-500 transition hover:text-zinc-300" aria-hidden />
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-[calc(100%+6px)] right-0 z-50 hidden w-52 rounded-lg border border-white/10 bg-zinc-900 px-2.5 py-2 text-xs leading-relaxed text-zinc-300 shadow-xl group-hover:block"
      >
        {text}
      </span>
    </span>
  );
}

function captionPositionClass(position: CaptionPosition) {
  if (position === "top") return "top-[18%] pb-9 pt-16";
  if (position === "center") return "top-1/2 -translate-y-1/2 py-8";
  return "bottom-0 pb-9 pt-16";
}

function stageBackgroundStyle(background: PreviewBackground, accent: string) {
  if (background === "light") {
    return `linear-gradient(180deg, #f4f4f5 0%, #e4e4e7 100%)`;
  }
  if (background === "vignette") {
    return `
      radial-gradient(ellipse 90% 70% at 50% 40%, ${accent}22, transparent 60%),
      linear-gradient(180deg, #2a2d35 0%, #0a0b0e 100%)
    `;
  }
  return `
    radial-gradient(ellipse 80% 50% at 50% 30%, ${accent}28, transparent 55%),
    linear-gradient(180deg, #1a1c22 0%, #0a0b0e 100%)
  `;
}

function SafeZoneOverlay({aspectRatio}: {aspectRatio: PreviewAspectRatio}) {
  const bottomInset = aspectRatio === "16:9" ? "12%" : "18%";
  const topInset = aspectRatio === "16:9" ? "8%" : "14%";
  return (
    <div className="pointer-events-none absolute inset-0 z-[15]" aria-hidden>
      <div
        className="absolute inset-x-[6%] rounded-xl border border-dashed border-warning/40"
        style={{top: topInset, bottom: bottomInset}}
      />
      <p className="absolute bottom-2 left-1/2 -translate-x-1/2 text-[9px] font-semibold uppercase tracking-widest text-warning/70">
        Safe zone
      </p>
    </div>
  );
}

function captionChrome(captionStyle: string, look: BrandStudioLook): CaptionChrome {
  if (captionStyle.includes("pill")) {
    return {
      plateRadius: "rounded-full",
      platePadding: "px-4 py-1.5",
      plateBackground: look.backgroundColor,
      wordGap: "gap-x-1.5 gap-y-0.5",
    };
  }
  if (captionStyle.includes("neon")) {
    return {
      plateRadius: "rounded-2xl",
      platePadding: "px-2 py-1",
      plateBackground: "transparent",
      plateShadow: `0 0 28px ${look.highlightColor}33`,
      wordGap: "gap-x-1.5 gap-y-0.5",
    };
  }
  if (captionStyle.includes("kinetic")) {
    return {
      plateRadius: "rounded-xl",
      platePadding: "px-3 py-2",
      plateBackground: look.backgroundColor,
      wordGap: "gap-x-2 gap-y-0.5",
    };
  }
  if (captionStyle.includes("clip") || captionStyle.includes("wipe")) {
    return {
      plateRadius: "rounded-lg",
      platePadding: "px-2.5 py-1.5",
      plateBackground: look.backgroundColor,
      wordGap: "gap-x-1 gap-y-0.5",
    };
  }
  if (captionStyle.includes("gradient")) {
    return {
      plateRadius: "rounded-2xl",
      platePadding: "px-3 py-2",
      plateBackground: `${look.backgroundColor}cc`,
      wordGap: "gap-x-1.5 gap-y-0.5",
    };
  }
  return {
    plateRadius: "rounded-xl",
    platePadding: "px-3 py-2",
    plateBackground: look.backgroundColor,
    wordGap: "gap-x-1.5 gap-y-0.5",
  };
}

function wordStyle({
  captionStyle,
  look,
  isActive,
  isHighlightWord,
}: {
  captionStyle: string;
  look: BrandStudioLook;
  isActive: boolean;
  isHighlightWord: boolean;
}): CSSProperties {
  const accent = isActive || isHighlightWord;
  const color = accent ? look.highlightColor : look.textColor;

  if (captionStyle.includes("neon")) {
    return {
      color,
      textShadow: accent ? `0 0 10px ${look.highlightColor}, 0 0 22px ${look.highlightColor}88` : "none",
      transform: isActive ? "translateY(-1px)" : "none",
    };
  }
  if (captionStyle.includes("kinetic")) {
    return {
      color,
      transform: isActive ? "translateY(-3px) scale(1.12)" : "none",
      filter: isActive ? "brightness(1.15)" : "none",
    };
  }
  if (captionStyle.includes("clip") || captionStyle.includes("wipe") || captionStyle.includes("minimal")) {
    return {
      color: isActive ? look.backgroundColor || "#09090b" : look.textColor,
      background: isActive ? look.highlightColor : isHighlightWord ? `${look.highlightColor}33` : "transparent",
      borderRadius: 4,
      padding: isActive || isHighlightWord ? "0 0.2em" : undefined,
      transform: isActive ? "translateY(-1px)" : "none",
    };
  }
  if (captionStyle.includes("gradient")) {
    if (!accent) return {color: look.textColor};
    return {
      backgroundImage: `linear-gradient(110deg, ${look.highlightColor}, ${look.textColor})`,
      WebkitBackgroundClip: "text",
      backgroundClip: "text",
      color: "transparent",
      transform: isActive ? "translateY(-1px)" : "none",
    };
  }
  if (captionStyle.includes("highlight") && !captionStyle.includes("editorial")) {
    return {
      color: look.textColor,
      background: accent ? `${look.highlightColor}55` : "transparent",
      borderRadius: 4,
      padding: accent ? "0 0.15em" : undefined,
      transform: isActive ? "translateY(-1px)" : "none",
    };
  }
  return {
    color,
    transform: isActive ? "translateY(-1px)" : "none",
  };
}

function TextureLayer({effect}: {effect: string}) {
  const id = effect.toLowerCase();
  if (id === "none" || !id) return null;
  return (
    <>
      {id.includes("vignette") ? (
        <div
          className="pointer-events-none absolute inset-0 z-[5]"
          aria-hidden
          style={{
            background: "radial-gradient(ellipse 70% 65% at 50% 45%, transparent 42%, rgba(0,0,0,.55) 100%)",
          }}
        />
      ) : null}
      {id.includes("grain") ? (
        <div
          className="pointer-events-none absolute inset-0 z-[5] opacity-[0.28] mix-blend-overlay"
          aria-hidden
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.55'/%3E%3C/svg%3E")`,
            backgroundSize: "160px 160px",
          }}
        />
      ) : null}
    </>
  );
}

function normalizeIntroLayout(value: string): string {
  const layout = value.trim().toLowerCase();
  if (!layout || layout === "none") return "none";
  if (layout === "lower-third-hook") return "lower-third-hook";
  if (
    layout === "template-hook"
    || layout === "editorial-hook"
    || layout === "headline-slam"
    || layout === "data-callout"
  ) {
    return "template-hook";
  }
  return "template-hook";
}

type PlacementBeats = {
  ctaStart: number;
  overlayExit: number;
  introBlockEnd: number;
  showRecipeOverlay: boolean;
  showIntroBlock: boolean;
};

function placementBeats(totalS: number, introLayout: string, ctaOverlay: string): PlacementBeats {
  const intro = normalizeIntroLayout(introLayout);
  const ctaId = ctaOverlay && ctaOverlay !== "none" ? ctaOverlay : "";
  const ratioHold = totalS * (totalS <= 10 ? 0.35 : 0.22);
  const ctaHold = ctaId ? Math.min(CTA_HOLD_MAX_S, Math.max(CTA_HOLD_MIN_S, ratioHold)) : 0;
  const ctaStart = ctaId ? totalS - ctaHold : totalS;
  const showIntroBlock = intro === "lower-third-hook";
  const showRecipeOverlay = intro === "template-hook";
  let overlayExit = 0;
  if (showRecipeOverlay) {
    const introCap = Math.min(LIVE_INTRO_OVERLAY_MAX_S, totalS * 0.35);
    overlayExit = ctaId
      ? Math.min(introCap, ctaStart - OVERLAY_CTA_GAP_S)
      : introCap;
    overlayExit = Math.max(0.9, Math.min(overlayExit, totalS - 0.35));
  }
  let introBlockEnd = 0;
  if (showIntroBlock) {
    const maxIntro = ctaId ? ctaStart - OVERLAY_CTA_GAP_S : Math.min(CTA_HOLD_MAX_S, totalS * 0.4);
    introBlockEnd = Math.min(CTA_HOLD_MAX_S, Math.max(CTA_HOLD_MIN_S, maxIntro));
  }
  return {ctaStart, overlayExit, introBlockEnd, showRecipeOverlay, showIntroBlock};
}

function OutroCalloutCard({overlay, accent}: {overlay: string; accent: string}) {
  const id = overlay.toLowerCase();
  let label = "Follow";
  let mark = "●";
  if (id.includes("yt") || id.includes("youtube")) {
    label = "Subscribe";
    mark = "▶";
  } else if (id.includes("instagram") || id.includes("ig")) {
    label = "Follow";
    mark = "◎";
  } else if (id.includes("tiktok")) {
    label = "Follow";
    mark = "♪";
  } else if (id.includes("x-") || id.includes("twitter")) {
    label = "Post";
    mark = "𝕏";
  }

  return (
    <div
      className="flex items-center gap-2 rounded-full border border-white/15 bg-black/55 px-3 py-1.5 shadow-lg backdrop-blur-sm"
      aria-hidden
    >
      <span
        className="grid h-5 w-5 place-items-center rounded-full text-[9px] font-bold text-ink"
        style={{background: accent}}
      >
        {mark}
      </span>
      <span className="text-[10px] font-semibold tracking-wide text-white/90">{label}</span>
    </div>
  );
}

