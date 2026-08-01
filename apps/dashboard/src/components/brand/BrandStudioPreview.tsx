"use client";

import {useEffect, useState} from "react";

const SAMPLE_WORDS = ["This", "is", "your", "Sharp", "moment"] as const;

export type BrandStudioLook = {
  fontFamily: string;
  fontSize: number;
  textColor: string;
  highlightColor: string;
  backgroundColor: string;
  strokeWidth: number;
  watermarkText: string;
  motionIntensity: string;
};

type BrandStudioPreviewProps = {
  look: BrandStudioLook;
  ambientVideoUrl?: string | null;
  recipeLabel?: string;
};

export function BrandStudioPreview({look, ambientVideoUrl, recipeLabel}: BrandStudioPreviewProps) {
  const [activeWord, setActiveWord] = useState(0);
  const [videoReady, setVideoReady] = useState(false);
  const pace = look.motionIntensity === "energetic" ? 420 : look.motionIntensity === "calm" ? 900 : 620;
  const captionPx = Math.min(Math.max(look.fontSize * 0.42, 20), 36);

  useEffect(() => {
    const id = window.setInterval(() => {
      setActiveWord((current) => (current + 1) % SAMPLE_WORDS.length);
    }, pace);
    return () => window.clearInterval(id);
  }, [pace]);

  useEffect(() => {
    setVideoReady(false);
  }, [ambientVideoUrl]);

  return (
    <div className="brand-studio-stage relative mx-auto aspect-[9/16] w-full max-w-[min(100%,22rem)] overflow-hidden rounded-[28px] border border-white/[0.12] bg-[#050507] shadow-[0_40px_100px_rgba(0,0,0,.55)]">
      {/* Atmosphere */}
      <div
        className="absolute inset-0 transition-[background] duration-500"
        style={{
          background: `
            radial-gradient(ellipse 80% 50% at 50% 18%, ${look.highlightColor}40, transparent 55%),
            radial-gradient(ellipse 70% 45% at 70% 78%, ${look.highlightColor}18, transparent 50%),
            linear-gradient(165deg, #1c1e24 0%, #0a0b0e 48%, #050507 100%)
          `,
        }}
      />

      {ambientVideoUrl ? (
        <video
          key={ambientVideoUrl}
          className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-700 ${videoReady ? "opacity-45" : "opacity-0"}`}
          src={ambientVideoUrl}
          muted
          loop
          playsInline
          autoPlay
          preload="metadata"
          onLoadedData={() => setVideoReady(true)}
          onError={() => setVideoReady(false)}
        />
      ) : null}

      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_40%,transparent_30%,rgba(0,0,0,.55)_100%)]" />

      {/* Soft film grain */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.07] mix-blend-overlay"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
        }}
      />

      {/* Composition: one caption block */}
      <div className="absolute inset-x-0 bottom-0 top-[42%] flex flex-col items-center justify-end px-5 pb-8">
        <div
          className="w-full max-w-[92%] rounded-[18px] px-4 py-3.5 text-center shadow-[0_18px_50px_rgba(0,0,0,.5)] transition-[background,color] duration-300"
          style={{
            background: look.backgroundColor,
            color: look.textColor,
            fontFamily: look.fontFamily,
            fontSize: `${captionPx}px`,
            fontWeight: 800,
            letterSpacing: "-0.02em",
            lineHeight: 1.25,
            WebkitTextStroke:
              look.strokeWidth > 0 ? `${Math.min(look.strokeWidth / 4, 2)}px rgba(0,0,0,.45)` : undefined,
          }}
        >
          <p className="flex flex-wrap items-center justify-center gap-x-1.5 gap-y-1">
            {SAMPLE_WORDS.map((word, index) => {
              const isActive = index === activeWord;
              const isHighlightWord = word === "Sharp";
              return (
                <span
                  key={word}
                  className="inline-block transition-[color,transform,background-color] duration-200"
                  style={{
                    color: isActive || isHighlightWord ? look.highlightColor : look.textColor,
                    transform: isActive ? "translateY(-1px) scale(1.04)" : "none",
                    background:
                      isActive && isHighlightWord
                        ? `${look.highlightColor}22`
                        : isActive
                          ? "rgba(255,255,255,.08)"
                          : "transparent",
                    borderRadius: 8,
                    padding: isActive ? "0 4px" : "0",
                  }}
                >
                  {word}
                </span>
              );
            })}
          </p>
        </div>

        <div className="mt-4 flex w-full items-center justify-between px-1 text-[10px] font-medium tracking-wide text-white/45">
          <span className="truncate">{look.watermarkText || " "}</span>
          <span className="truncate text-right" style={{color: `${look.highlightColor}cc`}}>
            {recipeLabel || "Brand"}
          </span>
        </div>
      </div>

      {/* Quiet top meta — not a chrome badge stack */}
      <div className="absolute left-0 right-0 top-0 flex items-start justify-between p-4">
        <div className="h-1 w-10 rounded-full bg-white/25" aria-hidden />
        <div
          className="h-2 w-2 rounded-full shadow-[0_0_12px_currentColor]"
          style={{background: look.highlightColor, color: look.highlightColor}}
          aria-hidden
        />
      </div>
    </div>
  );
}
