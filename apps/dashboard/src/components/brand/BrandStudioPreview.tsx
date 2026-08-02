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

/** Kept for call-site compat; preview stays caption-first and simple. */
export type BrandStudioEffects = {
  starterId: string;
  captionStyle: string;
  textureEffect: string;
  ctaOverlay: string;
  introLayout: string;
};

type BrandStudioPreviewProps = {
  look: BrandStudioLook;
  effects?: BrandStudioEffects;
};

/**
 * Simple brand caption preview — gradient plate + karaoke sample only.
 * No device chrome, recipe video, or effect ornamentation.
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
    <div
      className="relative mx-auto aspect-[9/16] h-[min(100%,calc(100dvh-7rem))] max-h-[34rem] w-auto max-w-full overflow-hidden rounded-[22px] border border-white/[0.1] shadow-[0_28px_80px_rgba(0,0,0,.4)] lg:max-h-[min(100%,calc(100dvh-5.5rem))]"
      style={{
        background: `
          radial-gradient(ellipse 80% 50% at 50% 30%, ${look.highlightColor}28, transparent 55%),
          linear-gradient(180deg, #1a1c22 0%, #0a0b0e 100%)
        `,
      }}
    >
      <div className="absolute inset-x-0 bottom-0 flex flex-col items-center px-6 pb-10 pt-16">
        <div
          className="w-full max-w-[94%] rounded-2xl px-4 py-3.5 text-center transition-[background,color] duration-300"
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
                  className="inline-block transition-[color,transform] duration-200"
                  style={{
                    color: isActive || isHighlightWord ? look.highlightColor : look.textColor,
                    transform: isActive ? "translateY(-1px)" : "none",
                  }}
                >
                  {word}
                </span>
              );
            })}
          </p>
        </div>
        {look.watermarkText ? (
          <p className="mt-3 text-[10px] font-medium tracking-wide text-white/35">{look.watermarkText}</p>
        ) : null}
      </div>
    </div>
  );
}
