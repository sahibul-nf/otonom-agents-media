"use client";

import {useEffect, useRef, useState, type CSSProperties} from "react";

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
  transitionFamily: string;
};

type BrandStudioPreviewProps = {
  look: BrandStudioLook;
  effects?: BrandStudioEffects;
};

type CaptionChrome = {
  plateRadius: string;
  platePadding: string;
  plateBackground: string;
  plateShadow?: string;
  wordGap: string;
};

/**
 * Caption-first brand preview with lightweight effect stubs.
 * Approximate intent signal — not HyperFrames render fidelity.
 */
export function BrandStudioPreview({look, effects}: BrandStudioPreviewProps) {
  const [activeWord, setActiveWord] = useState(0);
  const [introVisible, setIntroVisible] = useState(false);
  const [transitionKey, setTransitionKey] = useState(0);
  const [transitionClass, setTransitionClass] = useState("");
  const introReady = useRef(false);
  const transitionReady = useRef(false);

  const pace = look.motionIntensity === "energetic" ? 420 : look.motionIntensity === "calm" ? 900 : 620;
  const captionPx = Math.min(Math.max(look.fontSize * 0.46, 24), 40);
  const captionStyle = effects?.captionStyle || "caption-editorial-emphasis";
  const textureEffect = effects?.textureEffect || "vignette";
  const ctaOverlay = effects?.ctaOverlay || "";
  const introLayout = effects?.introLayout || "editorial-hook";
  const transitionFamily = effects?.transitionFamily || "dissolve";
  const chrome = captionChrome(captionStyle, look);

  useEffect(() => {
    const id = window.setInterval(() => {
      setActiveWord((current) => (current + 1) % SAMPLE_WORDS.length);
    }, pace);
    return () => window.clearInterval(id);
  }, [pace]);

  useEffect(() => {
    if (!introReady.current) {
      introReady.current = true;
      return;
    }
    setIntroVisible(true);
    const id = window.setTimeout(() => setIntroVisible(false), 1500);
    return () => window.clearTimeout(id);
  }, [introLayout]);

  useEffect(() => {
    if (!transitionReady.current) {
      transitionReady.current = true;
      return;
    }
    setTransitionClass(transitionFamily);
    setTransitionKey((key) => key + 1);
    const id = window.setTimeout(() => setTransitionClass(""), 520);
    return () => window.clearTimeout(id);
  }, [transitionFamily]);

  // Short-form stage: 9:16 (Shorts / Reels / TikTok).
  // ~82dvh matches the intended studio height (clear margin under header, not edge-flush).
  const frameWidth = "min(27rem, 100%, calc(82dvh * 9 / 16))";

  return (
    <div className="flex h-full max-h-full w-full flex-col items-center justify-center gap-2.5 py-1">
      <div
        className="relative shrink-0 overflow-hidden rounded-[24px] border border-white/[0.1] shadow-[0_28px_80px_rgba(0,0,0,.4)]"
        style={{
          aspectRatio: "9 / 16",
          width: frameWidth,
          height: "auto",
          maxHeight: "82dvh",
          background: `
            radial-gradient(ellipse 80% 50% at 50% 30%, ${look.highlightColor}28, transparent 55%),
            linear-gradient(180deg, #1a1c22 0%, #0a0b0e 100%)
          `,
        }}
      >
        <TextureLayer effect={textureEffect} accent={look.highlightColor} />

        {introVisible ? <IntroStub layout={introLayout} accent={look.highlightColor} /> : null}

        {transitionClass ? (
          <div
            key={transitionKey}
            className="pointer-events-none absolute inset-0 z-30"
            aria-hidden
            style={transitionOverlayStyle(transitionClass, look.highlightColor)}
          />
        ) : null}

        <div className="absolute inset-x-0 bottom-0 z-10 flex flex-col items-center px-5 pb-9 pt-16">
          {ctaOverlay ? <CtaStub overlay={ctaOverlay} accent={look.highlightColor} /> : null}

          <div
            className={`w-full max-w-[94%] text-center transition-[background,color,box-shadow,border-radius,padding] duration-300 ${chrome.plateRadius} ${chrome.platePadding}`}
            style={{
              background: chrome.plateBackground,
              color: look.textColor,
              fontFamily: look.fontFamily,
              fontSize: `${captionPx}px`,
              fontWeight: 800,
              letterSpacing: "-0.02em",
              lineHeight: 1.25,
              boxShadow: chrome.plateShadow,
              WebkitTextStroke:
                look.strokeWidth > 0 && !captionStyle.includes("neon")
                  ? `${Math.min(look.strokeWidth / 4, 2)}px rgba(0,0,0,.45)`
                  : undefined,
            }}
          >
            <p className={`flex flex-wrap items-center justify-center ${chrome.wordGap}`}>
              {SAMPLE_WORDS.map((word, index) => {
                const isActive = index === activeWord;
                const isHighlightWord = word === "Sharp";
                return (
                  <span
                    key={word}
                    className="inline-block transition-[color,transform,background,text-shadow,filter] duration-200"
                    style={wordStyle({
                      captionStyle,
                      look,
                      isActive,
                      isHighlightWord,
                    })}
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

      {effects ? (
        <p className="text-center text-[10px] font-medium tracking-wide text-zinc-600">
          9:16 short-form · approximate preview · final look on render
        </p>
      ) : null}
    </div>
  );
}

function captionChrome(captionStyle: string, look: BrandStudioLook): CaptionChrome {
  if (captionStyle.includes("pill")) {
    return {
      plateRadius: "rounded-full",
      platePadding: "px-5 py-2.5",
      plateBackground: look.backgroundColor,
      wordGap: "gap-x-1.5 gap-y-1",
    };
  }
  if (captionStyle.includes("neon")) {
    return {
      plateRadius: "rounded-2xl",
      platePadding: "px-4 py-3",
      plateBackground: "transparent",
      plateShadow: `0 0 28px ${look.highlightColor}33`,
      wordGap: "gap-x-1.5 gap-y-1",
    };
  }
  if (captionStyle.includes("kinetic")) {
    return {
      plateRadius: "rounded-xl",
      platePadding: "px-4 py-3.5",
      plateBackground: look.backgroundColor,
      wordGap: "gap-x-2 gap-y-1",
    };
  }
  if (captionStyle.includes("clip") || captionStyle.includes("wipe")) {
    return {
      plateRadius: "rounded-lg",
      platePadding: "px-3.5 py-3",
      plateBackground: look.backgroundColor,
      wordGap: "gap-x-1 gap-y-1",
    };
  }
  if (captionStyle.includes("gradient")) {
    return {
      plateRadius: "rounded-2xl",
      platePadding: "px-4 py-3.5",
      plateBackground: `${look.backgroundColor}cc`,
      wordGap: "gap-x-1.5 gap-y-1",
    };
  }
  return {
    plateRadius: "rounded-2xl",
    platePadding: "px-4 py-3.5",
    plateBackground: look.backgroundColor,
    wordGap: "gap-x-1.5 gap-y-1",
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

function TextureLayer({effect, accent}: {effect: string; accent: string}) {
  const id = effect.toLowerCase();
  const showVignette = id.includes("vignette") || (!id.includes("grain") && !id.includes("shimmer"));
  return (
    <>
      {showVignette ? (
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
      {id.includes("shimmer") ? (
        <div className="pointer-events-none absolute inset-0 z-[5] overflow-hidden" aria-hidden>
          <div
            className="brand-studio-shimmer absolute inset-y-0 w-1/3 opacity-40"
            style={{
              background: `linear-gradient(105deg, transparent 20%, ${accent}55 48%, transparent 72%)`,
            }}
          />
        </div>
      ) : null}
    </>
  );
}

function IntroStub({layout, accent}: {layout: string; accent: string}) {
  const id = layout.toLowerCase();
  if (id.includes("headline")) {
    return (
      <div className="pointer-events-none absolute inset-x-4 top-[18%] z-20 text-center" aria-hidden>
        <p
          className="brand-studio-intro-in text-2xl font-black tracking-tight text-white"
          style={{textShadow: `0 0 24px ${accent}66`}}
        >
          Hook moment
        </p>
      </div>
    );
  }
  if (id.includes("data")) {
    return (
      <div
        className="brand-studio-intro-in pointer-events-none absolute left-4 top-8 z-20 max-w-[58%] rounded-xl border border-white/15 bg-black/55 px-3 py-2"
        aria-hidden
      >
        <p className="text-[9px] font-bold uppercase tracking-widest" style={{color: accent}}>
          Callout
        </p>
        <p className="mt-0.5 text-xs font-semibold text-white">Key insight</p>
      </div>
    );
  }
  if (id.includes("lower")) {
    return (
      <div
        className="brand-studio-intro-in pointer-events-none absolute bottom-[38%] left-4 z-20 rounded-lg border-l-2 bg-black/60 px-3 py-2"
        style={{borderColor: accent}}
        aria-hidden
      >
        <p className="text-[10px] font-bold text-white">Lower-third hook</p>
      </div>
    );
  }
  return (
    <div
      className="brand-studio-intro-in pointer-events-none absolute inset-x-5 top-8 z-20 rounded-full border border-white/10 bg-black/50 px-4 py-2 text-center"
      aria-hidden
    >
      <p className="text-[11px] font-semibold text-white/90">
        Editorial hook <span style={{color: accent}}>·</span> soft open
      </p>
    </div>
  );
}

function CtaStub({overlay, accent}: {overlay: string; accent: string}) {
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
      className="mb-3 flex items-center gap-2 rounded-full border border-white/15 bg-black/55 px-3 py-1.5 shadow-lg backdrop-blur-sm"
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

function transitionOverlayStyle(family: string, accent: string): CSSProperties {
  const id = family.toLowerCase();
  if (id.includes("push")) {
    return {
      background: `linear-gradient(90deg, ${accent}33, rgba(0,0,0,.55))`,
      animation: "brand-studio-push 520ms ease-out both",
    };
  }
  if (id.includes("zoom")) {
    return {
      background: "rgba(0,0,0,.35)",
      animation: "brand-studio-zoom 520ms ease-out both",
    };
  }
  if (id.includes("whip")) {
    return {
      background: `linear-gradient(105deg, transparent, ${accent}44, rgba(0,0,0,.5), transparent)`,
      animation: "brand-studio-whip 480ms ease-out both",
    };
  }
  return {
    background: "rgba(0,0,0,.55)",
    animation: "brand-studio-dissolve 520ms ease-out both",
  };
}
