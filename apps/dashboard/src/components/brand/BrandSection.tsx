"use client";

import {useRouter} from "next/navigation";
import {ArrowUpRight, CheckCircle2, Layers3, Loader2, Palette, Settings2, Sparkles, Trash2} from "lucide-react";
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
  onDeleteTemplate?: (template: BrandTemplate) => void;
};

const STARTER_STORAGE_KEY = "otonom.brandBuilderStarterTemplate";

type AutonomyModeId = "off" | "assisted" | "full";

const AUTONOMY_MODES: Array<{id: AutonomyModeId; label: string; summary: string; detail: string}> = [
  {
    id: "off",
    label: "Off",
    summary: "Manual only",
    detail: "You schedule every approved clip yourself.",
  },
  {
    id: "assisted",
    label: "Assisted",
    summary: "Confirm first",
    detail: "Waits for a review window, then can auto-queue.",
  },
  {
    id: "full",
    label: "Full auto",
    summary: "Hands-off",
    detail: "Approved clips can schedule without waiting on you.",
  },
];

function autonomyModeMeta(mode?: string | null) {
  const id = (mode || "off") as AutonomyModeId;
  return AUTONOMY_MODES.find((item) => item.id === id) || AUTONOMY_MODES[0];
}

function presetIcon(presetId: string) {
  if (presetId === "editorial" || presetId === "ember_sunset" || presetId === "align_minimal") {
    return <Sparkles className="h-5 w-5" />;
  }
  if (presetId === "social" || presetId === "eva_cyber" || presetId === "volt_kinetic") {
    return <Palette className="h-5 w-5" />;
  }
  return <Layers3 className="h-5 w-5" />;
}

export function BrandSection({
  style,
  templates,
  hyperframesTemplates,
  hyperframesCatalog,
  autonomy,
  actionStates,
  defaultTemplate: _defaultTemplate,
  onAutonomyMode,
  onTemplateSaved,
  onDeleteTemplate,
}: Props) {
  const router = useRouter();
  const autonomyBusy = Object.entries(actionStates).find(([key, state]) => key.startsWith("autonomy:") && state.status === "running")?.[1];
  const currentAutonomy = autonomyModeMeta(autonomy?.autonomy_mode);
  const graceHours = autonomy?.review_grace_hours || 12;
  const currentFont = String(style?.caption?.font_family || "Sora");
  const savedStyles = templates.filter((template) => /custom_/i.test(template.path));
  const catalogReady = hyperframesCatalog?.items.filter((item) => item.status === "production-ready").length || 0;

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

  function openBlankBuilder() {
    router.push("/brand/builder?starter=spiritual_reflective");
  }

  return (
    <section className="grid min-w-0 gap-9">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-white/[0.06] pb-5">
        <div className="min-w-0 max-w-xl">
          <p className="text-[10px] font-bold uppercase tracking-widest text-cyan">Brand system</p>
          <p className="mt-1.5 text-sm leading-relaxed text-zinc-400">
            Start from a preset, reopen a saved style, then refine live in Brand Builder.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-white/[0.08] bg-black/20 px-3 py-1 text-[11px] font-semibold text-zinc-400">
            Font · {currentFont}
          </span>
          <button
            type="button"
            onClick={openBlankBuilder}
            className="inline-flex h-9 items-center gap-1.5 rounded-full border border-white/[0.1] bg-white/[0.03] px-3.5 text-[11px] font-semibold text-zinc-200 transition hover:border-cyan/35 hover:text-white"
          >
            Open builder
            <ArrowUpRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div>
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h4 className="text-base font-semibold tracking-tight text-white">Starter presets</h4>
            <p className="mt-1 text-xs text-zinc-500">Each preset opens as an editable starting point.</p>
          </div>
          <p className="text-[11px] font-medium tabular-nums text-zinc-600">
            {brandPresets.length} directions · {hyperframesTemplates.length} templates · {catalogReady} components
          </p>
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
                  {presetIcon(preset.id)}
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

      <div>
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h4 className="text-base font-semibold tracking-tight text-white">Saved styles</h4>
            <p className="mt-1 text-xs text-zinc-500">Reopen to fine-tune in place, then Use in Create.</p>
          </div>
          <div className="flex items-center gap-3">
            <button type="button" onClick={onTemplateSaved} className="text-[11px] font-semibold text-zinc-500 transition hover:text-cyan">
              Refresh
            </button>
            <span className="rounded-full border border-white/[0.08] bg-black/20 px-3 py-1 text-[11px] font-semibold tabular-nums text-zinc-400">
              {savedStyles.length} saved
            </span>
          </div>
        </div>

        {savedStyles.length ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {savedStyles.map((template) => (
              <div
                key={template.id}
                className="group flex min-w-0 items-center gap-2 rounded-[22px] border border-white/[0.06] bg-black/15 p-2 text-left transition hover:border-cyan/[0.22] hover:bg-black/25"
              >
                <button
                  type="button"
                  onClick={() => openSavedTemplate(template)}
                  className="flex min-w-0 flex-1 items-center gap-4 rounded-[18px] p-2 text-left"
                >
                  <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border border-white/[0.06] bg-black/30 text-cyan">
                    <Sparkles className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-white transition-colors group-hover:text-cyan">
                      {template.label}
                    </span>
                    <span className="mt-1 block truncate text-[11px] text-zinc-500">Brand system · edit in Builder</span>
                  </span>
                  <ArrowUpRight className="h-4 w-4 shrink-0 text-zinc-600 transition-colors group-hover:text-cyan" />
                </button>
                {onDeleteTemplate ? (
                  <button
                    type="button"
                    onClick={() => onDeleteTemplate(template)}
                    className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-white/[0.08] text-zinc-500 transition hover:border-danger/35 hover:bg-danger/[0.08] hover:text-danger"
                    aria-label={`Delete ${template.label}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <div className="grid min-h-[7.5rem] place-items-center rounded-[22px] border border-dashed border-white/[0.08] bg-black/10 px-6 py-8 text-center">
            <div>
              <p className="text-sm font-medium text-zinc-400">No saved brand styles yet</p>
              <p className="mt-1 text-xs text-zinc-600">Open a preset, tweak it, then Save in Brand Builder.</p>
            </div>
          </div>
        )}
      </div>

      <details className="group border-t border-white/[0.06] pt-5">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-white/[0.06] bg-black/20 text-zinc-600">
              <Settings2 className="h-3.5 w-3.5" />
            </span>
            <span>
              <span className="block text-[13px] font-semibold text-zinc-400 group-open:text-zinc-200">Advanced · publishing autonomy</span>
              <span className="mt-0.5 block text-[11px] text-zinc-600">
                {currentAutonomy.label} · {currentAutonomy.summary}
              </span>
            </span>
          </div>
          <span className="text-[11px] font-semibold text-zinc-600 transition-colors group-open:text-cyan">Configure</span>
        </summary>
        <div className="mt-4 max-w-lg pl-11">
          <p className="text-xs leading-relaxed text-zinc-500">
            Choose how automation schedules approved clips. Assisted waits {graceHours}h for confirmation before queueing.
          </p>
          <div className="mt-3 grid grid-cols-3 gap-1 rounded-[18px] border border-white/[0.08] bg-black/30 p-1">
            {AUTONOMY_MODES.map((mode) => {
              const active = (autonomy?.autonomy_mode || "off") === mode.id;
              return (
                <button
                  key={mode.id}
                  type="button"
                  disabled={Boolean(autonomyBusy)}
                  onClick={() => onAutonomyMode(mode.id)}
                  title={mode.detail}
                  className={`relative rounded-[14px] px-2 py-2.5 text-center transition ${
                    active ? "bg-cyan text-ink" : "text-zinc-500 hover:text-zinc-200"
                  }`}
                >
                  {actionStates[`autonomy:${mode.id}`]?.status === "running" ? (
                    <span className="absolute inset-0 grid place-items-center rounded-[14px] bg-cyan">
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-ink" />
                    </span>
                  ) : null}
                  <span className="block text-[11px] font-bold">{mode.label}</span>
                </button>
              );
            })}
          </div>
          <p className="mt-3 text-[11px] leading-relaxed text-zinc-500">{currentAutonomy.detail}</p>
          <p className="mt-2 inline-flex items-center gap-1.5 text-[11px] text-zinc-600">
            <CheckCircle2 className="h-3.5 w-3.5 text-cyan/70" />
            Autonomy is separate from brand look tokens.
          </p>
        </div>
      </details>
    </section>
  );
}
