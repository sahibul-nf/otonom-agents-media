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
};

/**
 * Brand look preview only — never mounts HyperFrames recipe demos.
 * Those MP4s already burn in hooks/callouts; stacking a caption on them
 * recreates the cluttered double-chrome frame.
 */
export function BrandStudioPreview({look}: BrandStudioPreviewProps) {
  const [activeWord, setActiveWord] = useState(0);
  const pace = look.motionIntensity === "energetic" ? 420 : look.motionIntensity === "calm" ? 900 : 620;
  const captionPx = Math.min(Math.max(look.fontSize * 0.44, 22), 38);

  useEffect(() => {
    const id = window.setInterval(() => {
      setActiveWord((current) => (current + 1) % SAMPLE_WORDS.length);
    }, pace);
    return () => window.clearInterval(id);
  }, [pace]);

  return (
    <div className="brand-studio-stage relative mx-auto aspect-[9/16] w-full max-w-[min(100%,24rem)] overflow-hidden rounded-[28px] border border-white/[0.12] bg-[#050507] shadow-[0_40px_100px_rgba(0,0,0,.55)]">
      {/* Clean plate — brand atmosphere only */}
      <div
        className="absolute inset-0 transition-[background] duration-500"
        style={{
          background: `
            radial-gradient(ellipse 90% 55% at 50% 28%, ${look.highlightColor}55, transparent 58%),
            radial-gradient(ellipse 60% 40% at 20% 70%, ${look.highlightColor}18, transparent 50%),
            linear-gradient(165deg, #22252c 0%, #0c0d10 52%, #050507 100%)
          `,
        }}
      />

      {/* Soft subject stand-in (no recipe chrome) */}
      <div
        className="pointer-events-none absolute left-1/2 top-[22%] h-[42%] w-[58%] -translate-x-1/2 rounded-[40%] opacity-90 blur-[1px]"
        style={{
          background: `
            radial-gradient(circle at 50% 35%, rgba(255,255,255,.22), transparent 42%),
            radial-gradient(circle at 50% 70%, ${look.highlightColor}33, transparent 55%),
            linear-gradient(180deg, #3a3d46 0%, #15171c 100%)
          `,
          boxShadow: `0 0 60px ${look.highlightColor}33`,
        }}
        aria-hidden
      />

      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_38%,transparent_22%,rgba(0,0,0,.62)_100%)]" />

      <div
        className="pointer-events-none absolute inset-0 opacity-[0.08] mix-blend-overlay"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
        }}
      />

      {/* Single caption — owns the lower third */}
      <div className="absolute inset-x-0 bottom-0 flex flex-col items-center px-5 pb-9 pt-24">
        <div
          className="w-full max-w-[94%] rounded-[18px] px-4 py-3.5 text-center shadow-[0_18px_50px_rgba(0,0,0,.55)] transition-[background,color] duration-300"
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

        {look.watermarkText ? (
          <p className="mt-3.5 max-w-full truncate text-center text-[10px] font-medium tracking-wide text-white/40">
            {look.watermarkText}
          </p>
        ) : null}
      </div>
    </div>
  );
}
