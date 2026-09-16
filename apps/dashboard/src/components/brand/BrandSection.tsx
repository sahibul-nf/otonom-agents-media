"use client";

import {useRouter} from "next/navigation";
import {ArrowUpRight, CheckCircle2, Copy, Layers3, Loader2, Palette, Pencil, Search, Settings2, Sparkles, Trash2, Wand2} from "lucide-react";
import {useEffect, useMemo, useState} from "react";
import {brandPresets} from "@/components/brand/BrandBuilderWorkspace";
import {apiGet} from "@/lib/media-api";
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
  onAutonomySettingsChange: (patch: Partial<AutonomySettings>) => void;
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

type SavedStyleMeta = {
  highlightColor: string;
  backgroundColor: string;
  textColor: string;
  fontFamily: string;
  fontSize: number;
  starterTemplate: string;
};

function hexFromColor(value: unknown, fallback: string) {
  const text = String(value || "").trim();
  if (/^#[0-9a-f]{6}$/i.test(text)) return text.toLowerCase();
  const rgba = text.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
  return rgba ? `#${rgba.slice(1, 4).map((part) => Number(part).toString(16).padStart(2, "0")).join("")}`.toLowerCase() : fallback;
}

function metaFromStyle(source: StyleProfile): SavedStyleMeta {
  const caption = source.caption || {};
  const brandSystem = source.brand_system || {};
  return {
    highlightColor: hexFromColor(caption.highlight_word_color, "#00ff36"),
    backgroundColor: hexFromColor(caption.background_color, "#111214"),
    textColor: hexFromColor(caption.text_color, "#ffffff"),
    fontFamily: String(caption.font_family || "Sora"),
    fontSize: Number(caption.font_size || 54),
    starterTemplate: String(brandSystem.starter_template || "spiritual_reflective"),
  };
}

function brandIdFromPath(path: string) {
  const slug = path.split("/").pop()?.replace(/\.json$/, "") || "";
  return `brand:${slug}`;
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
  onAutonomySettingsChange,
  onTemplateSaved,
  onDeleteTemplate,
}: Props) {
  const router = useRouter();
  const autonomyBusy = Object.entries(actionStates).find(([key, state]) => key.startsWith("autonomy:") && state.status === "running")?.[1];
  const currentAutonomy = autonomyModeMeta(autonomy?.autonomy_mode);
  const graceHours = autonomy?.review_grace_hours || 12;
  const minScore = autonomy?.overall_threshold ?? 80;
  const [draftMinScore, setDraftMinScore] = useState(minScore);
  const [draftGraceHours, setDraftGraceHours] = useState(graceHours);
  const currentFont = String(style?.caption?.font_family || "Sora");

  useEffect(() => {
    setDraftMinScore(minScore);
  }, [minScore]);

  useEffect(() => {
    setDraftGraceHours(graceHours);
  }, [graceHours]);
  const savedStyles = useMemo(
    () => templates.filter((template) => /custom_/i.test(template.path)),
    [templates],
  );
  const savedStylePathsKey = useMemo(
    () => savedStyles.map((template) => template.path).sort().join("|"),
    [savedStyles],
  );
  const catalogReady = hyperframesCatalog?.items.filter((item) => item.status === "production-ready").length || 0;
  const [savedSearch, setSavedSearch] = useState("");
  const [styleMeta, setStyleMeta] = useState<Record<string, SavedStyleMeta>>({});

  useEffect(() => {
    if (!savedStylePathsKey) {
      setStyleMeta({});
      return;
    }
    const paths = savedStylePathsKey.split("|");
    let cancelled = false;
    async function loadMeta() {
      const entries = await Promise.all(
        paths.map(async (path) => {
          try {
            const loaded = await apiGet<StyleProfile>(`style?path=${encodeURIComponent(path)}`);
            return [path, metaFromStyle(loaded)] as const;
          } catch {
            return [path, metaFromStyle({caption: {}, brand_system: {}})] as const;
          }
        }),
      );
      if (cancelled) return;
      setStyleMeta(Object.fromEntries(entries));
    }
    void loadMeta();
    return () => {
      cancelled = true;
    };
  }, [savedStylePathsKey]);

  const filteredSavedStyles = useMemo(() => {
    const query = savedSearch.trim().toLowerCase();
    if (!query) return savedStyles;
    return savedStyles.filter((template) => {
      const meta = styleMeta[template.path];
      const haystack = [template.label, meta?.fontFamily, meta?.starterTemplate].filter(Boolean).join(" ").toLowerCase();
      return haystack.includes(query);
    });
  }, [savedSearch, savedStyles, styleMeta]);

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

  function duplicateSavedTemplate(template: BrandTemplate) {
    router.push(`/brand/builder?base=${encodeURIComponent(template.path)}&duplicate=1`);
  }

  function useSavedTemplateInCreate(template: BrandTemplate) {
    const brandId = brandIdFromPath(template.path);
    window.localStorage.setItem(
      "otonom.generateBrandHandoff",
      JSON.stringify({
        brandTemplate: template.path,
        hyperframesTemplate: brandId,
        brandSystemTemplateId: brandId,
        renderer: "hyperframes",
      }),
    );
    router.push("/?section=generate");
  }

  return (
    <section className="grid min-w-0 gap-9">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-white/[0.06] pb-5">
        <div className="min-w-0 max-w-xl">
          <p className="text-[10px] font-bold uppercase tracking-widest text-cyan">Brand kit</p>
          <p className="mt-1.5 text-sm leading-relaxed text-zinc-400">
            Save custom caption & watermark styles here. Create already uses the platform default until you save one.
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
            <p className="mt-1 text-xs text-zinc-500">Saved styles appear as options in Create → Advanced → Captions & watermark.</p>
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

        {savedStyles.length > 3 ? (
          <label className="mb-4 flex items-center gap-2 rounded-full border border-white/[0.08] bg-black/20 px-3 py-2">
            <Search className="h-3.5 w-3.5 text-zinc-500" />
            <input
              type="search"
              value={savedSearch}
              onChange={(event) => setSavedSearch(event.target.value)}
              placeholder="Search saved styles"
              className="min-w-0 flex-1 bg-transparent text-sm text-zinc-200 outline-none placeholder:text-zinc-600"
            />
          </label>
        ) : null}

        {savedStyles.length ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {filteredSavedStyles.map((template) => {
              const meta = styleMeta[template.path];
              const starterLabel =
                hyperframesTemplates.find((item) => item.id === meta?.starterTemplate)?.label || meta?.starterTemplate || "Brand system";
              return (
                <article
                  key={template.id}
                  className="group rounded-[22px] border border-white/[0.06] bg-black/15 p-4 text-left transition hover:border-cyan/[0.22] hover:bg-black/25"
                >
                  <div className="flex items-start gap-3">
                    <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border border-white/[0.06] bg-black/30 text-cyan">
                      <Sparkles className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-white transition-colors group-hover:text-cyan">{template.label}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <span className="inline-flex items-center gap-1.5">
                          <span className="h-3.5 w-3.5 rounded-full border border-white/10" style={{background: meta?.highlightColor || "#00ff36"}} title="Highlight" />
                          <span className="h-3.5 w-3.5 rounded-full border border-white/10" style={{background: meta?.backgroundColor || "#111214"}} title="Plate" />
                          <span className="h-3.5 w-3.5 rounded-full border border-white/10" style={{background: meta?.textColor || "#ffffff"}} title="Text" />
                        </span>
                        <span className="rounded-full border border-white/[0.08] px-2 py-0.5 text-[10px] font-semibold text-zinc-400">
                          {meta?.fontFamily || "Sora"} · {meta?.fontSize || 54}px
                        </span>
                        <span className="rounded-full border border-cyan/20 bg-cyan/[0.08] px-2 py-0.5 text-[10px] font-semibold text-cyan">
                          {starterLabel}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2 border-t border-white/[0.05] pt-3">
                    <button
                      type="button"
                      onClick={() => openSavedTemplate(template)}
                      className="inline-flex h-8 items-center gap-1.5 rounded-full border border-white/[0.08] px-3 text-[11px] font-semibold text-zinc-300 transition hover:border-cyan/30 hover:text-white"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => duplicateSavedTemplate(template)}
                      className="inline-flex h-8 items-center gap-1.5 rounded-full border border-white/[0.08] px-3 text-[11px] font-semibold text-zinc-300 transition hover:border-cyan/30 hover:text-white"
                    >
                      <Copy className="h-3.5 w-3.5" />
                      Duplicate
                    </button>
                    <button
                      type="button"
                      onClick={() => useSavedTemplateInCreate(template)}
                      className="inline-flex h-8 items-center gap-1.5 rounded-full border border-cyan/25 bg-cyan/[0.08] px-3 text-[11px] font-semibold text-cyan transition hover:bg-cyan/[0.14]"
                    >
                      <Wand2 className="h-3.5 w-3.5" />
                      Use in Create
                    </button>
                    {onDeleteTemplate ? (
                      <button
                        type="button"
                        onClick={() => onDeleteTemplate(template)}
                        className="inline-flex h-8 items-center gap-1.5 rounded-full border border-white/[0.08] px-3 text-[11px] font-semibold text-zinc-500 transition hover:border-danger/35 hover:bg-danger/[0.08] hover:text-danger"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Delete
                      </button>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        ) : filteredSavedStyles.length === 0 && savedStyles.length ? (
          <div className="grid min-h-[7.5rem] place-items-center rounded-[22px] border border-dashed border-white/[0.08] bg-black/10 px-6 py-8 text-center">
            <p className="text-sm font-medium text-zinc-400">No saved styles match “{savedSearch.trim()}”</p>
          </div>
        ) : (
          <div className="grid min-h-[7.5rem] place-items-center rounded-[22px] border border-dashed border-white/[0.08] bg-black/10 px-6 py-8 text-center">
            <div>
              <p className="text-sm font-medium text-zinc-400">No saved caption styles yet</p>
              <p className="mt-1 text-xs text-zinc-600">
                Create uses the built-in platform default. Open a preset, tweak it, then Save in Brand Builder to unlock it in Create.
              </p>
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
          <div className="mt-4 grid gap-4">
            <label className="grid gap-2">
              <span className="flex items-center justify-between text-[11px] font-semibold text-zinc-400">
                Minimum score
                <span className="tabular-nums text-cyan">{draftMinScore}</span>
              </span>
              <input
                type="range"
                min={0}
                max={100}
                step={1}
                value={draftMinScore}
                disabled={Boolean(autonomyBusy)}
                onChange={(event) => setDraftMinScore(Number(event.target.value))}
                onMouseUp={(event) => onAutonomySettingsChange({overall_threshold: Number((event.target as HTMLInputElement).value)})}
                onTouchEnd={(event) => onAutonomySettingsChange({overall_threshold: Number((event.target as HTMLInputElement).value)})}
                className="w-full accent-cyan"
              />
              <span className="text-[10px] leading-relaxed text-zinc-600">
                Clips at or above this overall score can auto-qualify when autonomy is Assisted or Full.
              </span>
            </label>
            <label className="grid gap-2">
              <span className="text-[11px] font-semibold text-zinc-400">Grace period (hours)</span>
              <input
                type="number"
                min={1}
                max={168}
                value={draftGraceHours}
                disabled={Boolean(autonomyBusy) || (autonomy?.autonomy_mode || "off") === "off"}
                onChange={(event) => setDraftGraceHours(Number(event.target.value))}
                onBlur={() => onAutonomySettingsChange({review_grace_hours: draftGraceHours})}
                className="h-10 rounded-2xl border border-white/[0.08] bg-black/30 px-3 text-sm text-zinc-100 outline-none focus:border-cyan/[0.28]"
              />
              <span className="text-[10px] leading-relaxed text-zinc-600">
                Assisted mode waits this long before auto-queueing qualified clips.
              </span>
            </label>
          </div>
          <p className="mt-2 inline-flex items-center gap-1.5 text-[11px] text-zinc-600">
            <CheckCircle2 className="h-3.5 w-3.5 text-cyan/70" />
            Autonomy is separate from brand look tokens.
          </p>
        </div>
      </details>
    </section>
  );
}
