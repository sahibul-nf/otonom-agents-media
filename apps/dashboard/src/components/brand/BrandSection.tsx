"use client";

import {useRouter} from "next/navigation";
import {CheckCircle2, Layers3, Loader2, Palette, Settings2, Sparkles} from "lucide-react";
import {useEffect} from "react";
import {brandPresets} from "@/components/brand/BrandBuilderWorkspace";
import type {AutonomySettings, BrandTemplate, HyperframesCatalog, HyperframesTemplate, StyleProfile} from "@/lib/media-api";

type ActionUiState = {status: "running" | "done" | "failed"; message: string};

type Props = {
  style: StyleProfile | null;
  templates: BrandTemplate[];
  hyperframesTemplates: HyperframesTemplate[];
  hyperframesCatalog: HyperframesCatalog | null;
  autonomy: AutonomySettings | null;
  actionStates: Record<string, ActionUiState>;
  defaultTemplate: string;
  onAutonomyMode: (mode: string) => void;
  onTemplateSaved: () => void;
};

const STARTER_STORAGE_KEY = "otonom.brandBuilderStarterTemplate";

export function BrandSection({
  style,
  templates,
  hyperframesTemplates,
  hyperframesCatalog,
  autonomy,
  actionStates,
  defaultTemplate,
  onAutonomyMode,
  onTemplateSaved,
}: Props) {
  const router = useRouter();
  const autonomyBusy = Object.entries(actionStates).find(([key, state]) => key.startsWith("autonomy:") && state.status === "running")?.[1];
  const productionReadyCount = hyperframesCatalog?.items.filter((item) => item.status === "production-ready").length || 0;
  const currentFont = String(style?.caption?.font_family || "Sora");

  useEffect(() => {
    const starterTemplate = window.localStorage.getItem(STARTER_STORAGE_KEY);
    if (!starterTemplate) return;
    router.push(`/brand/builder?starter=${encodeURIComponent(starterTemplate)}`);
  }, [router]);

  function openPreset(preset: (typeof brandPresets)[number]) {
    window.localStorage.setItem(STARTER_STORAGE_KEY, preset.starterTemplate);
    router.push(`/brand/builder?preset=${encodeURIComponent(preset.id)}&starter=${encodeURIComponent(preset.starterTemplate)}`);
  }

  function openSavedTemplate(template: BrandTemplate) {
    router.push(`/brand/builder?base=${encodeURIComponent(template.path)}`);
  }

  return (
    <section className="grid min-w-0 gap-6">
      <div className="min-w-0 overflow-hidden rounded-[32px] border border-white/[0.08] bg-surface/30 backdrop-blur-md">
        <div className="border-b border-white/[0.08] bg-gradient-to-b from-cyan/[0.03] to-transparent p-6 sm:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-widest text-cyan">HyperFrames Brand System</p>
              <h3 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-white">
                Choose a <span className="font-editorial font-normal italic text-cyan">brand direction</span>
              </h3>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-zinc-400">
                Start from a production preset or reopen a saved style. Detailed controls live in the dedicated Brand Builder workspace.
              </p>
            </div>
            <div className="grid gap-1 text-right text-xs text-zinc-500">
              <span>{hyperframesTemplates.length} starter templates</span>
              <span>{productionReadyCount} production-ready components</span>
            </div>
          </div>
        </div>

        <div className="grid gap-7 p-6 sm:p-8">
          <div>
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h4 className="font-semibold text-white">Starter presets</h4>
                <p className="mt-1 text-xs text-zinc-500">Each preset opens as an editable starting point.</p>
              </div>
              <span className="rounded-full border border-white/[0.08] bg-black/20 px-3 py-1 text-xs font-semibold text-zinc-400">Current font · {currentFont}</span>
            </div>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {brandPresets.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => openPreset(preset)}
                  className="group relative flex min-h-[210px] flex-col justify-between rounded-[28px] border border-white/[0.06] bg-black/15 p-5 text-left transition-all duration-300 hover:-translate-y-0.5 hover:border-cyan/[0.25] hover:bg-black/25"
                >
                  <div>
                    <span className="grid h-10 w-10 place-items-center rounded-2xl border border-white/[0.05] bg-black/30 text-cyan transition-transform group-hover:scale-105">
                      {preset.id === "editorial" ? <Sparkles className="h-5 w-5" /> : preset.id === "social" ? <Palette className="h-5 w-5" /> : <Layers3 className="h-5 w-5" />}
                    </span>
                    <p className="mt-5 text-base font-bold tracking-tight text-white">{preset.label}</p>
                    <p className="mt-1.5 text-xs leading-relaxed text-zinc-500 transition-colors group-hover:text-zinc-400">{preset.note}</p>
                  </div>
                  <div className="mt-4 flex items-center justify-between border-t border-white/[0.04] pt-4">
                    <div className="flex items-center gap-1.5">
                      <span className="h-4 w-4 rounded-full border border-white/10" style={{backgroundColor: preset.backgroundColor}} />
                      <span className="h-4 w-4 rounded-full border border-white/10" style={{backgroundColor: preset.highlightColor}} />
                      <span className="font-mono text-[10px] font-semibold text-zinc-500">{preset.fontFamily}</span>
                    </div>
                    <span className="text-[9px] font-bold uppercase tracking-wider text-cyan">Open builder →</span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-[28px] border border-white/[0.06] bg-black/15 p-5">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h4 className="font-semibold tracking-tight text-white">Saved brand styles</h4>
                <p className="mt-0.5 text-xs text-zinc-500">Reopen a saved system in the builder to fine-tune or create a copy.</p>
              </div>
              <span className="self-start rounded-full border border-cyan/[0.22] bg-teal/[0.08] px-3.5 py-1 text-xs font-bold uppercase tracking-wider text-cyan">{templates.length} saved</span>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {templates.length ? templates.map((template) => (
                <button key={template.id} type="button" onClick={() => openSavedTemplate(template)} className="group flex min-w-0 items-center justify-between gap-4 rounded-2xl border border-white/[0.05] bg-surface/30 p-4 text-left text-zinc-200 transition hover:-translate-y-0.5 hover:border-cyan/[0.20] hover:bg-surface/50">
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold text-white transition-colors group-hover:text-cyan">{template.label}</span>
                    <span className="mt-1 block truncate text-[11px] font-bold uppercase tracking-wider text-zinc-500">Saved workspace style</span>
                  </span>
                  <Sparkles className="h-4 w-4 shrink-0 text-zinc-500 transition-colors group-hover:text-cyan" />
                </button>
              )) : (
                <div className="col-span-2 grid min-h-[140px] place-items-center rounded-[24px] border border-dashed border-white/[0.08] bg-black/15 p-6 text-center text-sm leading-relaxed text-zinc-500">
                  No customized style files stored yet.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <details className="group rounded-[28px] border border-white/[0.07] bg-surface/20 p-5">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-2xl border border-white/[0.07] bg-black/20 text-zinc-500"><Settings2 className="h-4 w-4" /></span>
            <span>
              <span className="block text-sm font-semibold text-zinc-200">Advanced publishing autonomy</span>
              <span className="mt-0.5 block text-xs text-zinc-600">Current mode: {autonomy?.autonomy_mode || "off"}</span>
            </span>
          </div>
          <span className="text-xs font-semibold text-zinc-500 transition-colors group-open:text-cyan">Configure</span>
        </summary>
        <div className="mt-5 border-t border-white/[0.06] pt-5">
          <p className="max-w-2xl text-xs leading-relaxed text-zinc-500">Control how aggressively automation schedules approved content. Assisted mode waits {autonomy?.review_grace_hours || 12} hours for manual confirmation.</p>
          <div className="mt-4 grid max-w-lg grid-cols-3 rounded-full border border-white/[0.08] bg-black/30 p-1">
            {["off", "assisted", "full"].map((mode) => {
              const active = autonomy?.autonomy_mode === mode;
              return (
                <button key={mode} type="button" disabled={Boolean(autonomyBusy)} onClick={() => onAutonomyMode(mode)} className={`relative rounded-full py-2.5 text-xs font-bold uppercase tracking-wider transition ${active ? "bg-cyan text-ink" : "text-zinc-500 hover:text-zinc-200"}`}>
                  {actionStates[`autonomy:${mode}`]?.status === "running" ? <span className="absolute inset-0 grid place-items-center rounded-full bg-cyan"><Loader2 className="h-3.5 w-3.5 animate-spin text-ink" /></span> : null}
                  {mode}
                </button>
              );
            })}
          </div>
          <div className="mt-4 flex flex-wrap gap-3 text-xs text-zinc-500">
            <span className="inline-flex items-center gap-1.5"><CheckCircle2 className="h-3.5 w-3.5 text-cyan" /> Base: {defaultTemplate}</span>
            <button type="button" onClick={onTemplateSaved} className="font-semibold text-cyan hover:text-white">Refresh saved styles</button>
          </div>
        </div>
      </details>
    </section>
  );
}
