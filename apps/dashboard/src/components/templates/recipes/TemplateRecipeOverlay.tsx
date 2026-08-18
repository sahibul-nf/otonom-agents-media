"use client";

import type {RecipeOverlayProps} from "./types";

type CaptionVariant =
  | "pill"
  | "serif"
  | "sticky"
  | "banner"
  | "mono"
  | "chalk"
  | "neon"
  | "stamp"
  | "quote"
  | "pricing"
  | "pink"
  | "magazine"
  | "botanical"
  | "glitch";

function CaptionMock({
  theme,
  compact,
  variant = "pill",
}: {
  theme: RecipeOverlayProps["theme"];
  compact?: boolean;
  variant?: CaptionVariant;
}) {
  const bottom = compact ? "bottom-[28%]" : "bottom-[32%]";
  const base = `absolute inset-x-0 z-[4] flex justify-center px-4 ${bottom}`;
  const font = {fontFamily: theme.fontFamily};

  switch (variant) {
    case "serif":
      return (
        <div className={base}>
          <div className="max-w-[92%] border-b-2 border-dotted px-2 py-2 text-center" style={{...font, borderColor: `${theme.accent}88`}}>
            <p className="text-sm font-semibold italic text-white">{theme.caption}</p>
            <p className="mt-1 text-xs text-zinc-300">{theme.caption2}</p>
          </div>
        </div>
      );
    case "sticky":
      return (
        <div className={base}>
          <div className="max-w-[88%] rotate-[-2deg] rounded-lg bg-[#ffe566] px-4 py-3 text-center shadow-xl" style={font}>
            <p className="text-sm font-bold text-black">{theme.caption}</p>
            <p className="mt-1 text-xs font-semibold text-amber-950/80">{theme.caption2}</p>
          </div>
        </div>
      );
    case "banner":
      return (
        <div className={`absolute inset-x-0 z-[4] ${compact ? "bottom-[24%]" : "bottom-[28%]"}`}>
          <div className="bg-red-600 py-2 text-center text-xs font-bold tracking-wide text-white">{theme.caption}</div>
          <p className="mt-2 text-center text-[11px] font-semibold text-zinc-200">{theme.caption2}</p>
        </div>
      );
    case "mono":
      return (
        <div className={base}>
          <div className="max-w-[92%] border border-sky-300/35 bg-slate-950/75 px-3 py-2 text-center font-mono" style={font}>
            <p className="text-xs font-semibold text-sky-200">{theme.caption}</p>
            <p className="mt-1 text-[11px] text-sky-100/80">{theme.caption2}</p>
          </div>
        </div>
      );
    case "chalk":
      return (
        <div className={base}>
          <div className="max-w-[92%] rounded-md border border-dashed border-slate-400/40 bg-slate-950/85 px-4 py-3 text-center" style={font}>
            <p className="text-sm text-slate-100">{theme.caption}</p>
            <p className="mt-1 text-xs text-slate-300">{theme.caption2}</p>
          </div>
        </div>
      );
    case "neon":
      return (
        <div className={base}>
          <div className="max-w-[92%] rounded-xl border border-cyan-400/40 bg-black/70 px-4 py-3 text-center shadow-[0_0_24px_rgba(0,243,255,.25)]" style={font}>
            <p className="text-sm font-black uppercase tracking-wide text-white">{theme.caption}</p>
            <p className="mt-1 text-xs font-semibold text-cyan-200">{theme.caption2}</p>
          </div>
        </div>
      );
    case "stamp":
      return (
        <div className={base}>
          <div className="max-w-[88%] border-4 border-lime-500 px-3 py-2 text-center" style={font}>
            <p className="text-xs font-black tracking-widest text-lime-500">{theme.caption}</p>
            <p className="mt-1 text-[11px] font-bold text-zinc-200">{theme.caption2}</p>
          </div>
        </div>
      );
    case "quote":
      return (
        <div className={base}>
          <div className="max-w-[92%] border-y border-white/20 py-3 text-center" style={font}>
            <p className="text-sm font-semibold italic text-white">“{theme.caption}”</p>
            <p className="mt-1 text-xs text-zinc-300">{theme.caption2}</p>
          </div>
        </div>
      );
    case "pricing":
      return (
        <div className={base}>
          <div className="rounded-2xl border-2 px-4 py-3 text-center" style={{...font, borderColor: theme.accent, background: "rgba(0,0,0,.75)"}}>
            <p className="text-[10px] uppercase tracking-wider text-zinc-400">Plan</p>
            <p className="text-lg font-black" style={{color: theme.accent}}>{theme.caption}</p>
            <p className="mt-1 text-xs text-zinc-300">{theme.caption2}</p>
          </div>
        </div>
      );
    case "pink":
      return (
        <div className={base}>
          <div className="max-w-[88%] rounded-3xl bg-[#ff7ad1] px-4 py-3 text-center text-[#1a1020]" style={font}>
            <p className="text-sm font-black">{theme.caption}</p>
            <p className="mt-1 text-xs font-semibold">{theme.caption2}</p>
          </div>
        </div>
      );
    case "magazine":
      return (
        <div className={base}>
          <div className="max-w-[92%] border-2 border-white/25 px-4 py-3 text-center" style={font}>
            <p className="text-[10px] tracking-[0.28em] text-zinc-300">ARCHIVE</p>
            <p className="mt-1 text-sm font-semibold text-white">{theme.caption}</p>
          </div>
        </div>
      );
    case "botanical":
      return (
        <div className={base}>
          <div className="max-w-[88%] rounded-full border border-emerald-300/35 bg-emerald-950/45 px-4 py-3 text-center" style={font}>
            <p className="text-sm font-semibold text-emerald-100">{theme.caption}</p>
            <p className="mt-1 text-xs text-emerald-200/80">{theme.caption2}</p>
          </div>
        </div>
      );
    case "glitch":
      return (
        <div className={base}>
          <div className="max-w-[92%] text-center" style={font}>
            <p className="text-sm font-black uppercase text-white" style={{textShadow: "3px 0 #f0f, -3px 0 #0ff"}}>{theme.caption}</p>
            <p className="mt-1 text-xs font-semibold text-fuchsia-200">{theme.caption2}</p>
          </div>
        </div>
      );
    default:
      return (
        <div className={base}>
          <div
            className="max-w-[92%] rounded-2xl border border-white/15 bg-black/70 px-4 py-3 text-center shadow-2xl"
            style={{...font, borderColor: `${theme.accent}55`}}
          >
            <p className="text-sm font-black text-white" style={{color: theme.accent === "#f8fafc" ? "#f8fafc" : theme.accent}}>
              {theme.caption}
            </p>
            <p className="mt-1 text-xs font-semibold text-zinc-300">{theme.caption2}</p>
          </div>
        </div>
      );
  }
}

export function TemplateRecipeOverlay({templateId, theme, compact}: RecipeOverlayProps) {
  const small = compact ? "text-[10px] px-2 py-1" : "text-xs px-3 py-1.5";

  switch (templateId) {
    case "spiritual_reflective":
      return (
        <>
          <div className="absolute left-3 top-3 z-[4] max-w-[70%] border-l-4 border-amber-300/80 bg-black/50 px-3 py-2" style={{fontFamily: theme.fontFamily}}>
            <p className="text-[10px] font-bold uppercase text-amber-200">Reflect</p>
          </div>
          <CaptionMock theme={theme} compact={compact} variant="serif" />
        </>
      );
    case "energy_warm_question":
      return <CaptionMock theme={theme} compact={compact} variant="sticky" />;
    case "arion_pink_callout":
      return <CaptionMock theme={theme} compact={compact} variant="pink" />;
    case "quintessence_serif":
      return <CaptionMock theme={theme} compact={compact} variant="serif" />;
    case "archive_magazine":
      return (
        <>
          <div className="absolute left-4 right-4 top-14 z-[4] border-2 border-white/25 px-4 py-3 text-center" style={{fontFamily: theme.fontFamily}}>
            <p className="text-[10px] tracking-[0.28em] text-zinc-300">ARCHIVE</p>
          </div>
          <CaptionMock theme={theme} compact={compact} variant="magazine" />
        </>
      );
    case "story_handwritten":
      return (
        <>
          <div className="absolute right-4 top-24 z-[4] h-16 w-16 rotate-[-8deg] rounded-full border-2 border-dashed border-orange-300/50" />
          <CaptionMock theme={theme} compact={compact} variant="sticky" />
        </>
      );
    case "kai_mustard_uppercase":
      return (
        <>
          <div className="absolute left-3 top-16 z-[4] h-12 w-28 border-4 border-[#d4a017] bg-[#d4a017]/15" />
          <CaptionMock theme={theme} compact={compact} variant="stamp" />
        </>
      );
    case "byline_trust_quote":
      return (
        <>
          <div className="absolute inset-x-6 top-[34%] z-[4] border-y border-white/20 py-4" />
          <CaptionMock theme={theme} compact={compact} variant="quote" />
        </>
      );
    case "sonnet_botanical":
      return (
        <>
          <div className="absolute right-4 top-16 z-[3] h-20 w-20 rounded-full bg-emerald-300/25 blur-sm" />
          <CaptionMock theme={theme} compact={compact} variant="botanical" />
        </>
      );
    case "rocket_glitch":
      return (
        <>
          <div className="absolute left-4 top-20 z-[4] h-10 w-40 bg-fuchsia-500/20 blur-md" />
          <CaptionMock theme={theme} compact={compact} variant="glitch" />
        </>
      );
    case "grit_training_stamp":
      return (
        <>
          <div className="absolute left-3 top-16 z-[4] rotate-[-8deg] border-4 border-lime-500 px-3 py-2" style={{fontFamily: theme.fontFamily}}>
            <span className="sr-only">Training stamp</span>
          </div>
          <CaptionMock theme={theme} compact={compact} variant="stamp" />
        </>
      );
    case "cove_callout_pill":
      return (
        <>
          <div className="absolute left-1/2 top-[36%] z-[4] flex -translate-x-1/2 flex-col gap-2">
            <span className="h-9 w-28 rounded-full bg-[#ff7ad1]/90" />
            <span className="h-9 w-24 rounded-full bg-[#67e8f9]/90" />
          </div>
          <CaptionMock theme={theme} compact={compact} variant="pink" />
        </>
      );
    case "pulse_remember_overlay":
      return (
        <>
          <div className="absolute inset-x-0 top-[38%] z-[4] h-8 bg-red-600/90" />
          <CaptionMock theme={theme} compact={compact} variant="banner" />
        </>
      );
    case "blueprint_grid_paper":
      return (
        <>
          <div className="absolute inset-6 z-[3] border border-sky-300/30 bg-[linear-gradient(rgba(125,211,252,.12)_1px,transparent_1px),linear-gradient(90deg,rgba(125,211,252,.12)_1px,transparent_1px)] bg-[size:20px_20px]" />
          <CaptionMock theme={theme} compact={compact} variant="mono" />
        </>
      );
    case "sketch_post_it":
      return (
        <>
          <div className="absolute left-3 top-20 z-[4] h-10 w-16 rotate-[-6deg] bg-[#fef08a]" />
          <div className="absolute right-3 top-28 z-[4] h-10 w-14 rotate-[5deg] bg-pink-200" />
          <CaptionMock theme={theme} compact={compact} variant="sticky" />
        </>
      );
    case "neon_seize_future":
      return (
        <>
          <div className="pointer-events-none absolute left-1/2 top-[35%] z-[3] h-20 w-20 -translate-x-1/2 -translate-y-1/2 bg-[conic-gradient(from_0deg,#ff2a85,#00f3ff,#facc15,#a7f36b,#ff2a85)] opacity-80" style={{clipPath: "polygon(50% 0%,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%)"}} />
          <CaptionMock theme={theme} compact={compact} variant="neon" />
        </>
      );
    case "velocity_business_promo":
      return (
        <>
          <div className="absolute left-4 top-20 z-[4] space-y-2">
            <div className="h-3 w-20 rounded bg-yellow-300/80" />
            <div className="h-4 w-28 rounded bg-white/30" />
          </div>
          <CaptionMock theme={theme} compact={compact} variant="pill" />
        </>
      );
    case "prism_pro_pricing":
      return (
        <>
          <div className="absolute right-4 top-20 z-[4] rounded-2xl border-2 px-4 py-2 text-center" style={{borderColor: theme.accent, background: "rgba(0,0,0,.75)"}}>
            <p className="text-[10px] text-zinc-400">Pro</p>
            <p className="text-2xl font-black" style={{color: theme.accent}}>$29</p>
          </div>
          <CaptionMock theme={theme} compact={compact} variant="pricing" />
        </>
      );
    case "chalk_word_emphasis":
      return (
        <>
          <div className="absolute inset-x-6 bottom-[44%] z-[4] rounded-md border border-dashed border-slate-500/40 bg-slate-950/80 px-4 py-3" />
          <CaptionMock theme={theme} compact={compact} variant="chalk" />
        </>
      );
    case "techtalk_intel_brief":
      return (
        <>
          <div className="absolute inset-x-4 bottom-[38%] z-[4] rounded-xl border border-teal-400/40 bg-black/55 px-3 py-2" style={{fontFamily: theme.fontFamily}}>
            <p className="text-[10px] font-bold uppercase tracking-wider text-teal-300">Intel brief</p>
          </div>
          <CaptionMock theme={theme} compact={compact} variant="mono" />
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
