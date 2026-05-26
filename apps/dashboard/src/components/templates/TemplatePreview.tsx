"use client";

import {useRef, useState} from "react";
import {HyperframesTemplate} from "@/lib/media-api";

export type TemplatePreviewFrame = "short" | "long";
const TEMPLATE_PREVIEW_SECONDS = 15;

const templatePreviewThemes: Record<string, {accent: string; secondary: string; caption: string; caption2: string; hook: string; body: string; cta: string}> = {
  spiritual_reflective: {accent: "#d8b45f", secondary: "#8ee6c8", caption: "Allah selalu bersama", caption2: "bahkan saat hati merasa jauh", hook: "A reflective reminder for today", body: "Source: spiritual reflective clip", cta: "Simpan pengingat ini"},
  warm_grain_editorial: {accent: "#e8c77d", secondary: "#9fe7c4", caption: "cerita terasa dekat", caption2: "dengan tekstur yang hangat", hook: "Warm editorial story", body: "Lifestyle · human story", cta: "Save this perspective"},
  play_mode_social: {accent: "#ffdf57", secondary: "#67e8f9", caption: "hook harus langsung terasa", caption2: "baru CTA masuk natural", hook: "Fast social launch clip", body: "Creator · launch moment", cta: "Share the update"},
  swiss_grid_explainer: {accent: "#f4f4f5", secondary: "#22d3ee", caption: "struktur bikin jelas", caption2: "setiap poin punya tempat", hook: "Explain it with structure", body: "Technical · business explainer", cta: "Use the framework"},
  vignelli_portrait_headline: {accent: "#ef4444", secondary: "#f8fafc", caption: "headline harus tegas", caption2: "tanpa visual yang ramai", hook: "Breaking the main point", body: "Portrait announcement", cta: "Read the context"},
  decision_tree_tutorial: {accent: "#8bff9f", secondary: "#f8d35c", caption: "pilih jalur yang tepat", caption2: "lalu jelaskan alasannya", hook: "A decision in three steps", body: "Tutorial · decision flow", cta: "Try this path"},
  kinetic_type_promo: {accent: "#facc15", secondary: "#f472b6", caption: "buat momen terasa besar", caption2: "dengan type yang bergerak", hook: "Launch with kinetic type", body: "Promo · title card", cta: "Start the campaign"},
  product_promo_showcase: {accent: "#a7f36b", secondary: "#67e8f9", caption: "produk terlihat nyata", caption2: "fitur muncul bertahap", hook: "Show the product flow", body: "SaaS · product showcase", cta: "Try the demo"},
  nyt_graph_data_story: {accent: "#74f2ce", secondary: "#f8d35c", caption: "angka punya cerita", caption2: "kalau konteksnya jelas", hook: "Data story in 60s", body: "Report · chart narrative", cta: "Check the trend"},
  podcast_talking_head: {accent: "#6ee7f5", secondary: "#f7a8d8", caption: "ini momen penting", caption2: "yang biasanya orang lewatkan", hook: "Founder explains the shift", body: "Guest highlight · personal brand", cta: "Follow for part two"},
  data_market_explainer: {accent: "#74f2ce", secondary: "#f8d35c", caption: "signal mulai berubah", caption2: "lihat struktur datanya", hook: "Market structure in 60s", body: "BTC/crypto explainer", cta: "Watch the confirmation level"},
  news_geo_brief: {accent: "#7dd3fc", secondary: "#f97373", caption: "konteksnya di sini", caption2: "bukan cuma headline", hook: "Regional brief update", body: "News source · region context", cta: "Check the source trail"},
  product_brand_promo: {accent: "#a7f36b", secondary: "#67e8f9", caption: "buat workflow lebih cepat", caption2: "tanpa pindah tools", hook: "Launch the new workflow", body: "SaaS/product promo", cta: "Try the workflow today"},
};

const templatePreviewVideoFallbacks: Record<string, {short_9_16?: string; long_16_9?: string}> = {
  warm_grain_editorial: {short_9_16: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4", long_16_9: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/warm-grain.mp4"},
  play_mode_social: {short_9_16: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4", long_16_9: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/play-mode.mp4"},
  swiss_grid_explainer: {short_9_16: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4", long_16_9: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/swiss-grid.mp4"},
  vignelli_portrait_headline: {short_9_16: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4", long_16_9: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/kinetic-type.mp4"},
  decision_tree_tutorial: {short_9_16: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4", long_16_9: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/decision-tree.mp4"},
  kinetic_type_promo: {short_9_16: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4", long_16_9: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/kinetic-type.mp4"},
  product_promo_showcase: {short_9_16: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4", long_16_9: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/product-promo.mp4"},
  nyt_graph_data_story: {short_9_16: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4", long_16_9: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/nyt-graph.mp4"},
  spiritual_reflective: {short_9_16: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4", long_16_9: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/warm-grain.mp4"},
  podcast_talking_head: {short_9_16: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4", long_16_9: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/play-mode.mp4"},
  data_market_explainer: {short_9_16: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4", long_16_9: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/nyt-graph.mp4"},
  news_geo_brief: {short_9_16: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4", long_16_9: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/swiss-grid.mp4"},
  product_brand_promo: {short_9_16: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/vignelli.mp4", long_16_9: "https://static.heygen.ai/hyperframes-oss/docs/images/templates/product-promo.mp4"},
};

export function TemplatePreview({
  template,
  compact = false,
  durationSeconds = TEMPLATE_PREVIEW_SECONDS,
  frame = "short",
  hoverToPlay = false,
}: {
  template: HyperframesTemplate;
  compact?: boolean;
  durationSeconds?: number;
  frame?: TemplatePreviewFrame;
  hoverToPlay?: boolean;
}) {
  const theme = templatePreviewThemes[template.id] || templatePreviewThemes.spiritual_reflective;
  const isLong = frame === "long";
  const previewKey = isLong ? "long_16_9" : "short_9_16";
  const previewUrl = template.preview_video_urls?.[previewKey] || template.preview_urls?.[previewKey] || templatePreviewVideoFallbacks[template.id]?.[previewKey];
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [shouldLoadPreview, setShouldLoadPreview] = useState(!hoverToPlay);
  const [videoLoaded, setVideoLoaded] = useState(false);
  const [videoError, setVideoError] = useState(false);
  const previewSize = compact ? (isLong ? "aspect-video" : "aspect-[9/16]") : (isLong ? "aspect-video max-h-[360px]" : "aspect-[9/16] max-h-[560px] max-w-[315px]");
  const frameLabel = compact ? (isLong ? "15s · 16:9" : "15s · 9:16") : `${durationSeconds}s · ${isLong ? "Long 16:9" : "Short/Reels 9:16"}`;
  const renderLabel = compact ? "HF render" : "HyperFrames render";
  const hoverLabel = compact && !isLong ? "Hover preview" : "Hover to play real preview";
  const previewStyle = {
    "--preview-accent": theme.accent,
    "--preview-secondary": theme.secondary,
    "--preview-duration": `${durationSeconds}s`,
    "--preview-word-duration": `${Math.max(2.4, durationSeconds / 3)}s`,
  } as React.CSSProperties;
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

  return (
    <div
      className={`template-card-preview relative mx-auto mb-4 w-full overflow-hidden rounded-[22px] border border-white/[0.08] bg-black shadow-inner ${previewSize}`}
      style={previewStyle}
      onMouseEnter={playPreview}
      onMouseLeave={pausePreview}
      onFocus={playPreview}
      onBlur={pausePreview}
      aria-label={`${template.label} ${durationSeconds}s HyperFrames preview`}
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_45%_28%,rgba(255,255,255,0.16),transparent_25%),linear-gradient(160deg,rgba(18,22,26,1),rgba(4,5,7,1)_58%,rgba(0,0,0,1))]" />
      {previewUrl && shouldLoadPreview && !videoError ? (
        <video
          key={`${template.id}:${previewKey}:${previewUrl}`}
          ref={videoRef}
          className="absolute inset-0 h-full w-full object-cover"
          src={previewUrl}
          muted
          loop
          playsInline
          preload={hoverToPlay ? "none" : "metadata"}
          onLoadedData={() => setVideoLoaded(true)}
          onError={() => setVideoError(true)}
        />
      ) : null}
      {(!previewUrl || videoError || (!shouldLoadPreview && !hoverToPlay)) ? (
        <div className="absolute inset-0 grid place-items-center bg-black/35">
          <div className="whitespace-nowrap rounded-full border border-white/[0.14] bg-black/65 px-4 py-2 text-xs font-semibold leading-4 text-zinc-100">
            {!previewUrl ? "Preview unavailable" : videoError ? "Preview failed to load" : "Hover to load preview"}
          </div>
        </div>
      ) : null}
      {previewUrl && shouldLoadPreview && !videoError && !videoLoaded ? (
        <div className="absolute inset-0 grid place-items-center bg-black/28">
          <div className="rounded-full border border-white/[0.14] bg-black/65 px-4 py-2 text-xs font-semibold text-zinc-100">Loading preview...</div>
        </div>
      ) : null}
      <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-black/70 via-black/20 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-black/82 via-black/24 to-transparent" />
      <div className="absolute left-3 right-3 top-3 z-10 flex items-center justify-between gap-2">
        <div className="rounded-full border border-white/[0.12] bg-black/62 px-2.5 py-1 text-[10px] font-bold text-zinc-200">{frameLabel}</div>
        <div className="rounded-full border border-[var(--preview-accent)]/30 bg-black/62 px-2.5 py-1 text-[10px] font-bold text-[var(--preview-accent)]">{renderLabel}</div>
      </div>
      <div className="absolute bottom-3 left-3 right-3 z-10 min-w-0">
        <p className="truncate text-sm font-black text-white drop-shadow-[0_3px_12px_rgba(0,0,0,.9)]">{template.label}</p>
        {!compact ? <p className="mt-1 line-clamp-2 text-xs leading-4 text-zinc-300">{template.best_for}</p> : null}
      </div>
      {hoverToPlay && previewUrl && !shouldLoadPreview ? (
        <div className="template-preview-play-hint absolute inset-0 z-20 grid place-items-center bg-black/20 transition duration-200">
          <span className="whitespace-nowrap rounded-full border border-white/[0.16] bg-black/72 px-4 py-2 text-xs font-black leading-4 text-white shadow-2xl">{hoverLabel}</span>
        </div>
      ) : null}
    </div>
  );
}
