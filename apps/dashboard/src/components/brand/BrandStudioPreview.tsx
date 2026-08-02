"use client";

import {useEffect, useState} from "react";
import {getRecipeTheme} from "@/components/templates/recipes";

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

export type BrandStudioEffects = {
  starterId: string;
  captionStyle: string;
  textureEffect: string;
  ctaOverlay: string;
  introLayout: string;
};

type BrandStudioPreviewProps = {
  look: BrandStudioLook;
  effects: BrandStudioEffects;
};

type CaptionPlate = "pill" | "box" | "underline";

function captionPlateFromStyle(captionStyle: string): CaptionPlate {
  if (/pill|karaoke|neon/i.test(captionStyle)) return "pill";
  if (/wipe|clip|minimal|box/i.test(captionStyle)) return "underline";
  return "box";
}

function grainOpacity(textureEffect: string) {
  if (/grain/i.test(textureEffect)) return 0.14;
  if (/shimmer/i.test(textureEffect)) return 0.08;
  if (/vignette/i.test(textureEffect)) return 0.05;
  return 0.06;
}

function vignetteStrength(textureEffect: string) {
  if (/vignette/i.test(textureEffect)) return 0.72;
  if (/grain/i.test(textureEffect)) return 0.55;
  return 0.58;
}

/**
 * Brand look preview only — never mounts HyperFrames recipe demos.
 * Effects subtly change plate shape / atmosphere so controls feel honest.
 */
export function BrandStudioPreview({look, effects}: BrandStudioPreviewProps) {
  const [activeWord, setActiveWord] = useState(0);
  const pace = look.motionIntensity === "energetic" ? 420 : look.motionIntensity === "calm" ? 900 : 620;
  const captionPx = Math.min(Math.max(look.fontSize * 0.44, 22), 38);
  const recipeTheme = getRecipeTheme(effects.starterId);
  const plate = captionPlateFromStyle(effects.captionStyle);
  const grain = grainOpacity(effects.textureEffect);
  const vignette = vignetteStrength(effects.textureEffect);
  const showSocialBar = Boolean(effects.ctaOverlay);
  const showIntroAccent = Boolean(effects.introLayout);

  useEffect(() => {
    const id = window.setInterval(() => {
      setActiveWord((current) => (current + 1) % SAMPLE_WORDS.length);
    }, pace);
    return () => window.clearInterval(id);
  }, [pace]);

  const plateClass =
    plate === "pill"
      ? "rounded-full px-5 py-3"
      : plate === "underline"
        ? "rounded-none border-b-2 bg-transparent px-2 py-2 shadow-none"
        : "rounded-[18px] px-4 py-3.5";

  return (
    <div className="relative mx-auto flex h-[min(100%,calc(100dvh-7rem))] max-h-[36rem] w-auto max-w-full items-center justify-center lg:max-h-[min(100%,calc(100dvh-5.5rem))]">
      {/* Device bezel */}
      <div className="relative aspect-[9/16] h-full max-h-full w-auto rounded-[34px] border border-white/[0.14] bg-[#0c0d10] p-[7px] shadow-[0_40px_100px_rgba(0,0,0,.55)]">
        <div className="pointer-events-none absolute left-1/2 top-2.5 z-20 h-1 w-16 -translate-x-1/2 rounded-full bg-white/15" aria-hidden />
        <div className="brand-studio-stage relative h-full w-full overflow-hidden rounded-[28px] bg-[#050507]">
          <div
            className="absolute inset-0 transition-[background] duration-300"
            style={{
              background: `
                radial-gradient(ellipse 90% 55% at 50% 28%, ${look.highlightColor}44, transparent 58%),
                radial-gradient(ellipse 55% 40% at 78% 72%, ${recipeTheme.accent}28, transparent 52%),
                linear-gradient(165deg, #22252c 0%, #0c0d10 52%, #050507 100%)
              `,
            }}
          />

          {/* Neutral subject stand-in */}
          <div
            className="pointer-events-none absolute left-1/2 top-[18%] h-[46%] w-[62%] -translate-x-1/2 rounded-[48%_48%_42%_42%] opacity-95"
            style={{
              background: `
                radial-gradient(circle at 50% 28%, rgba(255,255,255,.28), transparent 40%),
                radial-gradient(circle at 50% 68%, ${look.highlightColor}28, transparent 52%),
                linear-gradient(180deg, #4a4e58 0%, #1a1c22 72%, #0e1014 100%)
              `,
              boxShadow: `0 0 48px ${recipeTheme.accent}22`,
            }}
            aria-hidden
          />

          <div
            className="pointer-events-none absolute inset-0"
            style={{
              background: `radial-gradient(circle at 50% 38%, transparent 20%, rgba(0,0,0,${vignette}) 100%)`,
            }}
          />

          <div
            className="pointer-events-none absolute inset-0 mix-blend-overlay transition-opacity duration-300"
            style={{
              opacity: grain,
              backgroundImage:
                "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
            }}
          />

          {showIntroAccent ? (
            <div
              className="pointer-events-none absolute left-4 top-5 h-0.5 w-12 rounded-full transition-colors duration-300"
              style={{background: recipeTheme.accent}}
              aria-hidden
            />
          ) : null}

          <div className="absolute inset-x-0 bottom-0 flex flex-col items-center px-5 pb-8 pt-20">
            <div
              className={`w-full max-w-[94%] text-center transition-[background,color,border-radius,padding] duration-300 ${plateClass}`}
              style={{
                background: plate === "underline" ? "transparent" : look.backgroundColor,
                color: look.textColor,
                fontFamily: look.fontFamily,
                fontSize: `${captionPx}px`,
                fontWeight: 800,
                letterSpacing: "-0.02em",
                lineHeight: 1.25,
                borderBottomColor: plate === "underline" ? look.highlightColor : undefined,
                boxShadow: plate === "underline" ? "none" : "0 18px 50px rgba(0,0,0,.55)",
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
              <p className="mt-3 max-w-full truncate text-center text-[10px] font-medium tracking-wide text-white/40">
                {look.watermarkText}
              </p>
            ) : null}

            {showSocialBar ? (
              <div
                className="mt-3 h-1 w-24 rounded-full opacity-70 transition-colors duration-300"
                style={{background: `linear-gradient(90deg, ${recipeTheme.accent}, ${look.highlightColor})`}}
                aria-hidden
              />
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
