"use client";

import {useRouter} from "next/navigation";
import {CheckCircle2, Layers3, Loader2, Palette, Plus, Settings2, Sparkles} from "lucide-react";
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
  style: _style,
  templates,
  hyperframesTemplates: _hyperframesTemplates,
  hyperframesCatalog: _hyperframesCatalog,
  autonomy,
  actionStates,
  defaultTemplate: _defaultTemplate,
  onAutonomyMode,
  onTemplateSaved,
}: Props) {
  const router = useRouter();
  const autonomyBusy = Object.entries(actionStates).find(([key, state]) => key.startsWith("autonomy:") && state.status === "running")?.[1];

  useEffect(() => {
    const starterTemplate = window.localStorage.getItem(STARTER_STORAGE_KEY);
    if (!starterTemplate) return;
    router.push(`/brand/builder?starter=${encodeURIComponent(starterTemplate)}`);
  }, [router]);

  function openPreset(preset: (typeof brandPresets)[number]) {
    window.localStorage.setItem(STARTER_STORAGE_KEY, preset.starterTemplate);
    router.push(`/brand/builder?preset=${encodeURIComponent(preset.id)}&starter=${encodeURIComponent(preset.starterTemplate)}`);
  }

  function openBlank() {
    router.push("/brand/builder");
  }

  function openSavedTemplate(template: BrandTemplate) {
    router.push(`/brand/builder?base=${encodeURIComponent(template.path)}`);
  }

  return (
    <section className="mx-auto grid w-full max-w-5xl min-w-0 gap-5">
      <div className="min-w-0 rounded-[28px] border border-white/[0.08] bg-surface/30 p-5 backdrop-blur-md sm:rounded-[32px] sm:p-6">
        <div className="mb-5">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan">Starter presets</p>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-400">
            Pick a direction to open the builder, or reopen a saved style below.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {brandPresets.map((preset) => (
            <button
              key={preset.id}
              type="button"
              onClick={() => openPreset(preset)}
              className="group flex min-h-[180px] flex-col justify-between rounded-[24px] border border-white/[0.06] bg-black/15 p-4 text-left transition hover:-translate-y-0.5 hover:border-cyan/[0.25] hover:bg-black/25"
            >
              <div>
                <span className="grid h-9 w-9 place-items-center rounded-2xl border border-white/[0.05] bg-black/30 text-cyan">
                  {preset.id === "editorial" || preset.id === "ember_sunset" ? (
                    <Sparkles className="h-4 w-4" />
                  ) : preset.id === "social" || preset.id === "volt_kinetic" || preset.id === "eva_cyber" ? (
                    <Palette className="h-4 w-4" />
                  ) : (
                    <Layers3 className="h-4 w-4" />
                  )}
                </span>
                <p className="mt-4 text-sm font-bold tracking-tight text-white">{preset.label}</p>
                <p className="mt-1 text-xs leading-relaxed text-zinc-500 group-hover:text-zinc-400">{preset.note}</p>
              </div>
              <div className="mt-3 flex items-center justify-between border-t border-white/[0.04] pt-3">
                <div className="flex items-center gap-1.5">
                  <span className="h-3.5 w-3.5 rounded-full border border-white/10" style={{backgroundColor: preset.backgroundColor}} />
                  <span className="h-3.5 w-3.5 rounded-full border border-white/10" style={{backgroundColor: preset.highlightColor}} />
                  <span className="font-mono text-[10px] font-semibold text-zinc-500">{preset.fontFamily}</span>
                </div>
                <span className="text-[9px] font-bold uppercase tracking-wider text-cyan">Open →</span>
              </div>
            </button>
          ))}
          <button
            type="button"
            onClick={openBlank}
            className="group flex min-h-[180px] flex-col justify-between rounded-[24px] border border-dashed border-white/[0.10] bg-black/10 p-4 text-left transition hover:-translate-y-0.5 hover:border-cyan/[0.25] hover:bg-black/20"
          >
            <div>
              <span className="grid h-9 w-9 place-items-center rounded-2xl border border-white/[0.05] bg-black/30 text-zinc-400 group-hover:text-cyan">
                <Plus className="h-4 w-4" />
              </span>
              <p className="mt-4 text-sm font-bold tracking-tight text-white">Start blank</p>
              <p className="mt-1 text-xs leading-relaxed text-zinc-500 group-hover:text-zinc-400">Open the builder from your current workspace baseline.</p>
            </div>
            <div className="mt-3 flex items-center justify-end border-t border-white/[0.04] pt-3">
              <span className="text-[9px] font-bold uppercase tracking-wider text-cyan">Open →</span>
            </div>
          </button>
        </div>

        <div className="mt-5 border-t border-white/[0.06] pt-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <h4 className="text-sm font-semibold text-white">Saved styles</h4>
              <p className="mt-0.5 text-xs text-zinc-500">Reopen to fine-tune or duplicate.</p>
            </div>
            {templates.length ? (
              <span className="rounded-full border border-white/[0.08] bg-black/20 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                {templates.length}
              </span>
            ) : null}
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {templates.length ? (
              templates.map((template) => (
                <button
                  key={template.id}
                  type="button"
                  onClick={() => openSavedTemplate(template)}
                  className="group flex min-w-0 items-center justify-between gap-3 rounded-2xl border border-white/[0.06] bg-black/15 px-4 py-3 text-left transition hover:border-cyan/[0.20] hover:bg-black/25"
                >
                  <span className="min-w-0 truncate text-sm font-semibold text-white group-hover:text-cyan">{template.label}</span>
                  <Sparkles className="h-3.5 w-3.5 shrink-0 text-zinc-600 group-hover:text-cyan" />
                </button>
              ))
            ) : (
              <div className="sm:col-span-2 rounded-2xl border border-dashed border-white/[0.08] bg-black/10 px-4 py-8 text-center text-sm text-zinc-600">
                No saved styles yet. Open a preset and save from the builder.
              </div>
            )}
          </div>
        </div>
      </div>

      <details className="group rounded-[24px] border border-white/[0.06] bg-black/10 p-4">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl border border-white/[0.06] bg-black/20 text-zinc-600">
              <Settings2 className="h-3.5 w-3.5" />
            </span>
            <span>
              <span className="block text-xs font-semibold text-zinc-400">Advanced · publishing autonomy</span>
              <span className="mt-0.5 block text-[11px] text-zinc-600">Mode: {autonomy?.autonomy_mode || "off"}</span>
            </span>
          </div>
          <span className="text-[11px] font-semibold text-zinc-600 group-open:text-zinc-400">Configure</span>
        </summary>
        <div className="mt-4 border-t border-white/[0.06] pt-4">
          <p className="max-w-2xl text-xs leading-relaxed text-zinc-500">
            How aggressively approved clips can be scheduled. Assisted waits {autonomy?.review_grace_hours || 12}h for confirmation.
          </p>
          <div className="mt-3 grid max-w-md grid-cols-3 rounded-full border border-white/[0.08] bg-black/30 p-1">
            {["off", "assisted", "full"].map((mode) => {
              const active = autonomy?.autonomy_mode === mode;
              return (
                <button
                  key={mode}
                  type="button"
                  disabled={Boolean(autonomyBusy)}
                  onClick={() => onAutonomyMode(mode)}
                  className={`relative rounded-full py-2 text-[10px] font-bold uppercase tracking-wider transition ${active ? "bg-cyan text-ink" : "text-zinc-500 hover:text-zinc-200"}`}
                >
                  {actionStates[`autonomy:${mode}`]?.status === "running" ? (
                    <span className="absolute inset-0 grid place-items-center rounded-full bg-cyan">
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-ink" />
                    </span>
                  ) : null}
                  {mode}
                </button>
              );
            })}
          </div>
          <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-zinc-600">
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-zinc-500" /> Baseline ready
            </span>
            <button type="button" onClick={onTemplateSaved} className="font-semibold text-zinc-400 hover:text-cyan">
              Refresh saved styles
            </button>
          </div>
        </div>
      </details>
    </section>
  );
}
