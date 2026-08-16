"use client";

import type {RecipeOverlayProps} from "./types";

function CaptionMock({theme, compact}: {theme: RecipeOverlayProps["theme"]; compact?: boolean}) {
  return (
    <div className={`absolute inset-x-0 z-[4] flex justify-center px-4 ${compact ? "bottom-[28%]" : "bottom-[32%]"}`}>
      <div
        className="max-w-[92%] rounded-2xl border border-white/15 bg-black/70 px-4 py-3 text-center shadow-2xl"
        style={{fontFamily: theme.fontFamily, borderColor: `${theme.accent}55`}}
      >
        <p className="text-sm font-black text-white" style={{color: theme.accent === "#f8fafc" ? "#111" : undefined}}>
          {theme.caption}
        </p>
        <p className="mt-1 text-xs font-semibold text-zinc-300">{theme.caption2}</p>
      </div>
    </div>
  );
}

export function TemplateRecipeOverlay({templateId, theme, compact}: RecipeOverlayProps) {
  const small = compact ? "text-[10px] px-2 py-1" : "text-xs px-3 py-1.5";

  switch (templateId) {
    case "spiritual_reflective":
      return (
        <>
          <div className="absolute left-3 top-3 z-[4] max-w-[70%] border-l-4 border-amber-300/80 bg-black/50 px-3 py-2" style={{fontFamily: theme.fontFamily}}>
            <p className="text-[10px] font-bold uppercase text-amber-200">Reflect</p>
            <p className="text-sm text-zinc-100">{theme.body}</p>
          </div>
          <CaptionMock theme={theme} compact={compact} />
        </>
      );
    case "energy_warm_question":
      return (
        <>
          <div className="absolute left-3 top-24 z-[4] rotate-[-5deg] rounded-lg rounded-br-2xl bg-[#ffe566] px-4 py-3 text-lg font-bold text-black" style={{fontFamily: theme.fontFamily}}>
            more views?
          </div>
          <CaptionMock theme={theme} compact={compact} />
        </>
      );
    case "pulse_remember_overlay":
      return (
        <>
          <div className="absolute inset-x-0 top-[38%] z-[4] bg-red-600 py-2 text-center text-xs font-bold tracking-wide text-white">
            REMEMBER THE CONSISTENCY
          </div>
          <CaptionMock theme={theme} compact={compact} />
        </>
      );
    case "blueprint_grid_paper":
      return (
        <>
          <div className="absolute inset-6 z-[3] border border-sky-300/30 bg-[linear-gradient(rgba(125,211,252,.12)_1px,transparent_1px),linear-gradient(90deg,rgba(125,211,252,.12)_1px,transparent_1px)] bg-[size:20px_20px]" />
          <p className="absolute left-8 top-10 z-[4] font-mono text-sm text-sky-200">how to build anything</p>
          <CaptionMock theme={theme} compact={compact} />
        </>
      );
    case "sketch_post_it":
      return (
        <>
          <div className="absolute left-3 top-20 z-[4] rotate-[-6deg] bg-[#fef08a] px-3 py-2 text-lg text-amber-950" style={{fontFamily: theme.fontFamily}}>idea</div>
          <div className="absolute right-3 top-28 z-[4] rotate-[5deg] bg-pink-200 px-3 py-2 text-lg text-pink-950" style={{fontFamily: theme.fontFamily}}>ship</div>
          <CaptionMock theme={theme} compact={compact} />
        </>
      );
    case "grit_training_stamp":
      return (
        <>
          <div className="absolute left-3 top-16 z-[4] rotate-[-8deg] border-4 border-lime-500 px-3 py-2 text-sm font-black tracking-widest text-lime-500" style={{fontFamily: theme.fontFamily}}>
            TRAINING
          </div>
          <CaptionMock theme={theme} compact={compact} />
        </>
      );
    case "neon_seize_future":
      return (
        <>
          <div className="pointer-events-none absolute left-1/2 top-[35%] z-[3] h-20 w-20 -translate-x-1/2 -translate-y-1/2 bg-[conic-gradient(from_0deg,#ff2a85,#00f3ff,#facc15,#a7f36b,#ff2a85)] opacity-80" style={{clipPath: "polygon(50% 0%,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%)"}} />
          <CaptionMock theme={theme} compact={compact} />
        </>
      );
    case "byline_trust_quote":
      return (
        <>
          <div className="absolute inset-x-6 top-[34%] z-[4] border-y border-white/20 py-4 text-center" style={{fontFamily: theme.fontFamily}}>
            <p className="text-lg font-semibold italic text-white">“Trust the process”</p>
          </div>
          <CaptionMock theme={theme} compact={compact} />
        </>
      );
    case "quintessence_serif":
      return (
        <>
          <p className="absolute left-6 top-16 z-[4] text-3xl font-semibold text-white" style={{fontFamily: theme.fontFamily}}>
            More clarity
          </p>
          <CaptionMock theme={theme} compact={compact} />
        </>
      );
    case "velocity_business_promo":
      return (
        <>
          <div className="absolute left-4 top-20 z-[4] space-y-1" style={{fontFamily: theme.fontFamily}}>
            <p className="text-2xl font-black text-yellow-300">BOOST</p>
            <p className="text-lg font-bold text-white">YOUR BUSINESS</p>
          </div>
          <CaptionMock theme={theme} compact={compact} />
        </>
      );
    case "techtalk_intel_brief":
      return (
        <>
          <div className="absolute inset-x-4 bottom-[38%] z-[4] rounded-xl border border-teal-400/40 bg-black/55 px-3 py-2" style={{fontFamily: theme.fontFamily}}>
            <p className="text-[10px] font-bold uppercase tracking-wider text-teal-300">Intel brief</p>
            <p className="mt-1 text-sm font-semibold text-white">Key takeaway · edu-finance</p>
          </div>
          <CaptionMock theme={theme} compact={compact} />
        </>
      );
    default:
      return (
        <>
          <div
            className="pointer-events-none absolute inset-0 z-[3] opacity-80"
            style={{background: `radial-gradient(circle at 30% 20%, ${theme.accent}22, transparent 40%), radial-gradient(circle at 80% 70%, ${theme.secondary}18, transparent 35%)`}}
          />
          <div className={`absolute left-3 top-3 z-[4] rounded-full border ${small} font-bold`} style={{borderColor: `${theme.accent}66`, color: theme.accent}}>
            {theme.captionStyle}
          </div>
          <CaptionMock theme={theme} compact={compact} />
        </>
      );
  }
}
