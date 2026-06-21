"use client";

import {useEffect, useMemo, useState} from "react";
import {BadgeCheck, CheckCircle2, ChevronDown, Layers3, Loader2, Palette, Sparkles, Sliders, Settings2, Info} from "lucide-react";
import {apiGet, apiPost, AutonomySettings, BrandTemplate, HyperframesCatalog, HyperframesTemplate, StyleProfile} from "@/lib/media-api";
import {FocusModal} from "@/components/FocusModal";
import {TemplatePreview} from "@/components/templates/TemplatePreview";

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

const fontOptions = [
  {value: "Sora", label: "Sora", note: "Brand default"},
  {value: "Inter", label: "Inter", note: "Clean UI sans"},
  {value: "Montserrat", label: "Montserrat", note: "Bold editorial"},
  {value: "Poppins", label: "Poppins", note: "Rounded social captions"},
  {value: "Roboto", label: "Roboto", note: "Android/system friendly"},
  {value: "Arial", label: "Arial", note: "Universal fallback"},
  {value: "system-ui", label: "System UI", note: "Device native"},
  {value: "__custom", label: "Custom font", note: "Advanced"},
];

const brandPresets = [
  {
    id: "editorial",
    label: "Editorial Calm",
    note: "Best for reflective, education, and story-led clips.",
    starterTemplate: "spiritual_reflective",
    fontFamily: "Sora",
    fontSize: 54,
    highlightColor: "#d8b45f",
    backgroundColor: "#111214",
    strokeWidth: 6,
    captionStyle: "caption-editorial-emphasis",
    introLayout: "editorial-hook",
    ctaOverlay: "yt-lower-third",
    textureEffect: "grain-overlay",
    transitionFamily: "dissolve",
    motionIntensity: "calm",
  },
  {
    id: "social",
    label: "Social Punch",
    note: "Best for creator clips, podcast highlights, and short hooks.",
    starterTemplate: "play_mode_social",
    fontFamily: "Poppins",
    fontSize: 56,
    highlightColor: "#67e8f9",
    backgroundColor: "#05070a",
    strokeWidth: 8,
    captionStyle: "caption-pill-karaoke",
    introLayout: "lower-third-hook",
    ctaOverlay: "instagram-follow",
    textureEffect: "shimmer-sweep",
    transitionFamily: "push",
    motionIntensity: "energetic",
  },
  {
    id: "analyst",
    label: "Analyst Clean",
    note: "Best for data, market, business, and technical explainers.",
    starterTemplate: "spiritual_reflective",
    fontFamily: "Inter",
    fontSize: 48,
    highlightColor: "#74f2ce",
    backgroundColor: "#07100f",
    strokeWidth: 4,
    captionStyle: "caption-clip-wipe",
    introLayout: "data-callout",
    ctaOverlay: "yt-lower-third",
    textureEffect: "vignette",
    transitionFamily: "zoom",
    motionIntensity: "balanced",
  },
  {
    id: "eva_cyber",
    label: "Eva Neon Cyber",
    note: "Vibrant neon overlays, glowing captions, and futuristic accents.",
    starterTemplate: "eva_neon_cyber",
    fontFamily: "Poppins",
    fontSize: 54,
    highlightColor: "#ff2a85",
    backgroundColor: "#030305",
    strokeWidth: 8,
    captionStyle: "caption-neon-glow",
    introLayout: "headline-slam",
    ctaOverlay: "instagram-follow",
    textureEffect: "shimmer-sweep",
    transitionFamily: "whip-pan",
    motionIntensity: "energetic",
  },
  {
    id: "volt_kinetic",
    label: "Volt Lime Kinetic",
    note: "High-contrast bold bounce, electric lime highlights, and title drops.",
    starterTemplate: "volt_lime_kinetic",
    fontFamily: "Montserrat",
    fontSize: 58,
    highlightColor: "#a7f36b",
    backgroundColor: "#040507",
    strokeWidth: 10,
    captionStyle: "caption-kinetic-slam",
    introLayout: "headline-slam",
    ctaOverlay: "tiktok-follow",
    textureEffect: "shimmer-sweep",
    transitionFamily: "zoom",
    motionIntensity: "energetic",
  },
  {
    id: "ember_sunset",
    label: "Ember Sunset",
    note: "High-aesthetic sunset gradient text with soft warm ambient glows.",
    starterTemplate: "ember_sunset_gradient",
    fontFamily: "Sora",
    fontSize: 52,
    highlightColor: "#ff5e36",
    backgroundColor: "#120a06",
    strokeWidth: 6,
    captionStyle: "caption-gradient-fill",
    introLayout: "editorial-hook",
    ctaOverlay: "yt-lower-third",
    textureEffect: "vignette",
    transitionFamily: "dissolve",
    motionIntensity: "calm",
  },
  {
    id: "align_minimal",
    label: "Align Minimal Box",
    note: "Sleek monochrome active word bounding boxes and clean snap reveals.",
    starterTemplate: "align_minimal_box",
    fontFamily: "Inter",
    fontSize: 48,
    highlightColor: "#f8fafc",
    backgroundColor: "#09090b",
    strokeWidth: 4,
    captionStyle: "caption-clip-wipe",
    introLayout: "lower-third-hook",
    ctaOverlay: "x-post",
    textureEffect: "vignette",
    transitionFamily: "dissolve",
    motionIntensity: "balanced",
  },
] as const;

function hexFromColor(value: unknown, fallback = "#000000") {
  const text = String(value || "").trim();
  if (/^#[0-9a-f]{6}$/i.test(text)) return text.toLowerCase();
  if (/^#[0-9a-f]{3}$/i.test(text)) {
    return `#${text.slice(1).split("").map((char) => `${char}${char}`).join("")}`.toLowerCase();
  }
  const rgba = text.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
  if (rgba) {
    return `#${rgba.slice(1, 4).map((part) => Number(part).toString(16).padStart(2, "0")).join("")}`.toLowerCase();
  }
  return fallback;
}

function publicBrandText(value: unknown, fallback: string) {
  const text = String(value || "").trim();
  return text && !/nourbit|nouraniyyah/i.test(text) ? text : fallback;
}

export function BrandSection({
  style,
  templates,
  autonomy,
  actionStates,
  defaultTemplate,
  onAutonomyMode,
  onTemplateSaved,
  hyperframesTemplates,
  hyperframesCatalog,
}: Props) {
  const editorFromStyle = (source?: StyleProfile | null) => {
    const caption = source?.caption || {};
    const brand = source?.brand || {};
    const starterTemplateRequest = typeof window !== "undefined" ? window.localStorage.getItem("otonom.brandBuilderStarterTemplate") : null;
    const starterTemplate = starterTemplateRequest || "spiritual_reflective";
    if (typeof window !== "undefined") {
      window.localStorage.removeItem("otonom.brandBuilderStarterTemplate");
    }
    return {
      fontFamily: String(caption.font_family || "Sora"),
      fontSize: Number(caption.font_size || 54),
      textColor: hexFromColor(caption.text_color, "#ffffff"),
      highlightColor: hexFromColor(caption.highlight_word_color, "#00ff36"),
      backgroundColor: hexFromColor(caption.background_color, "#000000"),
      strokeWidth: Number(caption.stroke_width || 10),
      watermarkText: publicBrandText(brand.watermark_text, "Brand Clips"),
      starterTemplate,
      captionStyle: "caption-editorial-emphasis",
      introLayout: "editorial-hook",
      ctaOverlay: "yt-lower-third",
      textureEffect: "vignette",
      transitionFamily: "dissolve",
      motionIntensity: "balanced",
      openBuilder: Boolean(starterTemplateRequest),
    };
  };
  const [selectedTemplate, setSelectedTemplate] = useState(defaultTemplate);
  const [editor, setEditor] = useState(editorFromStyle(style));
  const initialStarter = hyperframesTemplates.find((template) => template.id === editor.starterTemplate);
  const [label, setLabel] = useState(initialStarter ? `${initialStarter.label} Brand Template` : "Custom Workspace Template");
  const [saveState, setSaveState] = useState("Ready");
  const [templateBusy, setTemplateBusy] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const [builderOpen, setBuilderOpen] = useState(Boolean(editor.openBuilder));
  const [fontAvailability, setFontAvailability] = useState<"checking" | "available" | "fallback" >("checking");
  const selectedFontOption = useMemo(() => fontOptions.some((font) => font.value === editor.fontFamily) ? editor.fontFamily : "__custom", [editor.fontFamily]);
  const selectedStarter = hyperframesTemplates.find((template) => template.id === editor.starterTemplate);
  const productionReadyCount = hyperframesCatalog?.items.filter((item) => item.status === "production-ready").length || 0;

  useEffect(() => {
    let cancelled = false;
    async function checkFont() {
      setFontAvailability("checking");
      if (editor.fontFamily === "system-ui") {
        setFontAvailability("available");
        return;
      }
      const fonts = document.fonts;
      if (!fonts?.check) {
        setFontAvailability("fallback");
        return;
      }
      try {
        await fonts.ready;
        if (!cancelled) setFontAvailability(fonts.check(`16px "${editor.fontFamily}"`) ? "available" : "fallback");
      } catch {
        if (!cancelled) setFontAvailability("fallback");
      }
    }
    void checkFont();
    return () => {
      cancelled = true;
    };
  }, [editor.fontFamily]);

  const updateEditor = (patch: Partial<typeof editor>) => setEditor((current) => ({...current, ...patch}));
  const applyPreset = (preset: (typeof brandPresets)[number]) => {
    setEditor((current) => ({
      ...current,
      starterTemplate: preset.starterTemplate,
      fontFamily: preset.fontFamily,
      fontSize: preset.fontSize,
      highlightColor: preset.highlightColor,
      backgroundColor: preset.backgroundColor,
      strokeWidth: preset.strokeWidth,
      captionStyle: preset.captionStyle,
      introLayout: preset.introLayout,
      ctaOverlay: preset.ctaOverlay,
      textureEffect: preset.textureEffect,
      transitionFamily: preset.transitionFamily,
      motionIntensity: preset.motionIntensity,
    }));
    setLabel(`${preset.label} Brand Template`);
    setSaveState("Preset applied");
    setBuilderOpen(true);
  };
  const stylePayload: StyleProfile = {
    caption: {
      font_family: editor.fontFamily,
      font_size: editor.fontSize,
      text_color: editor.textColor,
      highlight_word_color: editor.highlightColor,
      background_color: editor.backgroundColor,
      stroke_width: editor.strokeWidth,
    },
    brand: {
      watermark_text: editor.watermarkText,
    },
  };
  const brandSystemPayload = {
    starter_template: editor.starterTemplate,
    caption_style: editor.captionStyle,
    intro_layout: editor.introLayout,
    cta_overlay: editor.ctaOverlay,
    texture_effect: editor.textureEffect,
    transition_family: editor.transitionFamily,
    motion_intensity: editor.motionIntensity,
  };

  async function saveTemplate() {
    setSaveBusy(true);
    setSaveState("Saving...");
    try {
      await apiPost("brand-system-templates", {label, style: stylePayload, brand_system: brandSystemPayload, base_template: selectedTemplate});
      setSaveState("Template saved");
      await onTemplateSaved();
    } catch (error) {
      setSaveState(error instanceof Error ? error.message : "Save failed");
    } finally {
      setSaveBusy(false);
    }
  }

  async function loadTemplate(path: string) {
    setSelectedTemplate(path);
    setTemplateBusy(true);
    setSaveState("Loading template...");
    try {
      const loaded = await apiGet<StyleProfile>(`style?path=${encodeURIComponent(path)}`);
      const template = templates.find((item) => item.path === path);
      setEditor(editorFromStyle(loaded));
      setLabel(template?.label ? `${template.label} Copy` : "Custom Workspace Template");
      setSaveState("Template loaded");
    } catch (error) {
      setSaveState(error instanceof Error ? error.message : "Template load failed");
    } finally {
      setTemplateBusy(false);
    }
  }
  const autonomyBusy = Object.entries(actionStates).find(([key, state]) => key.startsWith("autonomy:") && state.status === "running")?.[1];

  return (
    <>
    <section className="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
      {/* Brand Main Panel */}
      <div className="min-w-0 overflow-hidden rounded-[32px] border border-white/[0.08] bg-surface/30 backdrop-blur-md">
        <div className="border-b border-white/[0.08] bg-gradient-to-b from-cyan/[0.03] to-transparent p-6 sm:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-widest text-cyan">HyperFrames Brand System</p>
              <h3 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-white">
                Brand <span className="font-editorial italic font-normal text-cyan">customizer</span>
              </h3>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-zinc-400">
                Choose a production style direction. Tap any direction to apply its presets and load the visual brand builder workspace.
              </p>
            </div>
            <span className={`rounded-full border px-3.5 py-1.5 text-xs font-bold uppercase tracking-wider ${saveState.toLowerCase().includes("failed") ? "border-danger/30 bg-danger/10 text-danger" : "border-cyan/[0.25] bg-teal/[0.08] text-cyan"}`}>
              {saveState}
            </span>
          </div>
        </div>

        <div className="grid gap-6 p-6 sm:p-8">
          {/* Custom Paint-Swatch Preset Selection */}
          <div className="grid gap-4 md:grid-cols-3">
            {brandPresets.map((preset) => {
              const active = editor.starterTemplate === preset.starterTemplate && editor.motionIntensity === preset.motionIntensity;
              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => applyPreset(preset)}
                  className={`group relative flex flex-col justify-between min-h-[220px] rounded-[28px] border p-5 text-left transition-all duration-300 ${
                    active 
                      ? "border-cyan bg-cyan/[0.03] shadow-[0_12px_24px_rgba(98,238,248,0.06)]" 
                      : "border-white/[0.06] bg-black/15 hover:border-white/[0.14] hover:bg-black/24"
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between gap-3">
                      <span className="grid h-10 w-10 place-items-center rounded-2xl bg-black/30 border border-white/5 text-cyan group-hover:scale-110 transition-transform">
                        {preset.id === "editorial" ? <Sparkles className="h-5 w-5" /> : preset.id === "social" ? <Palette className="h-5 w-5" /> : <Layers3 className="h-5 w-5" />}
                      </span>
                      {active && (
                        <span className="inline-flex h-2.5 w-2.5 rounded-full bg-cyan shadow-[0_0_8px_rgba(98,238,248,0.5)]" />
                      )}
                    </div>
                    <p className="mt-5 text-base font-bold text-white tracking-tight">{preset.label}</p>
                    <p className="mt-1.5 text-xs leading-relaxed text-zinc-500 group-hover:text-zinc-400 transition-colors line-clamp-2">{preset.note}</p>
                  </div>

                  {/* Brand Swatch/Paint-chip block */}
                  <div className="mt-4 flex items-center justify-between pt-4 border-t border-white/[0.04]">
                    <div className="flex items-center gap-1.5">
                      <span className="h-4 w-4 rounded-full border border-white/10" style={{backgroundColor: preset.backgroundColor}} title="Background color" />
                      <span className="h-4 w-4 rounded-full border border-white/10" style={{backgroundColor: preset.highlightColor}} title="Highlight color" />
                      <span className="text-[10px] font-semibold text-zinc-500 font-mono tracking-tight">{preset.fontFamily}</span>
                    </div>
                    <span className="text-[9px] uppercase font-bold tracking-wider text-cyan group-hover:translate-x-0.5 transition-transform">Customize →</span>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Saved Brand Templates */}
          <div className="rounded-[28px] border border-white/[0.06] bg-black/15 p-5">
            <div className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <h4 className="font-semibold text-white tracking-tight">Saved Brand System Templates</h4>
                <p className="text-xs text-zinc-500 mt-0.5">Deploy or fine-tune historical customized layouts stored inside your local workspace.</p>
              </div>
              <span className="rounded-full border border-cyan/[0.22] bg-teal/[0.08] px-3.5 py-1 text-xs font-bold uppercase tracking-wider text-cyan self-start">
                {templates.length} Saved Templates
              </span>
            </div>
            
            <div className="grid gap-3 md:grid-cols-2">
              {templates.length ? templates.map((template) => (
                <button
                  key={template.id}
                  type="button"
                  onClick={() => {
                    void loadTemplate(template.path);
                    setBuilderOpen(true);
                  }}
                  className="group flex min-w-0 items-center justify-between gap-4 rounded-2xl border border-white/[0.05] bg-surface/30 p-4 text-left text-zinc-200 transition-all duration-200 hover:border-cyan/[0.20] hover:bg-surface/50 hover:-translate-y-0.5"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold text-white group-hover:text-cyan transition-colors">{template.label}</span>
                    <span className="mt-1 block truncate text-[11px] text-zinc-500 uppercase tracking-wider font-bold">Workspace Style</span>
                  </span>
                  <span className="grid h-8 w-8 place-items-center rounded-full bg-black/20 text-zinc-500 group-hover:text-cyan group-hover:bg-cyan/10 transition-colors">
                    <Sparkles className="h-4 w-4" />
                  </span>
                </button>
              )) : <div className="col-span-2"><EmptyState text="No customized style files stored in library yet." /></div>}
            </div>
          </div>
        </div>
      </div>

      {/* Sidebar Automation Panel */}
      <aside className="min-w-0 rounded-[32px] border border-white/[0.08] bg-surface/30 p-6 backdrop-blur-md xl:self-start">
        <div className="flex flex-col gap-3 pb-5 border-b border-white/[0.06]">
          <div className="flex items-center gap-2">
            <Settings2 className="h-4 w-4 text-cyan" />
            <p className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">Automation Guardrails</p>
          </div>
          <h4 className="text-lg font-semibold text-white tracking-[-0.02em]">
            Publishing <span className="font-editorial italic font-normal text-cyan">autonomy</span>
          </h4>
          <p className="text-xs text-zinc-400 leading-relaxed">
            Configure how aggressively autonomy routines schedule your content pipeline. Assisted mode waits {autonomy?.review_grace_hours || 12}h for manual confirmation before publishing.
          </p>
        </div>

        {/* Satisfying capsule pills choice */}
        <div className="mt-5 p-1 rounded-full border border-white/[0.08] bg-black/32 grid grid-cols-3">
          {["off", "assisted", "full"].map((mode) => {
            const active = autonomy?.autonomy_mode === mode;
            return (
              <button
                key={mode}
                type="button"
                disabled={Boolean(autonomyBusy)}
                onClick={() => onAutonomyMode(mode)}
                className={`relative py-2.5 text-xs font-bold uppercase tracking-wider rounded-full transition-all ${
                  active 
                    ? "bg-cyan text-ink shadow-[0_4px_12px_rgba(102,232,249,0.2)]" 
                    : "text-zinc-500 hover:text-zinc-200"
                }`}
              >
                {actionStates[`autonomy:${mode}`]?.status === "running" && (
                  <span className="absolute inset-0 flex items-center justify-center bg-cyan rounded-full">
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-ink" />
                  </span>
                )}
                {mode}
              </button>
            );
          })}
        </div>
        
        {autonomyBusy && (
          <p className="mt-3.5 text-xs font-medium text-cyan flex items-center gap-1.5 justify-center">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span>{autonomyBusy.message}</span>
          </p>
        )}

        <div className="mt-5 grid gap-2">
          <ReadinessMini ready={Boolean(selectedStarter)} label="Starter Template" value={selectedStarter?.label || editor.starterTemplate} />
          <ReadinessMini ready={productionReadyCount > 0} label="Catalog Assets" value={`${productionReadyCount} active slots`} />
          <ReadinessMini ready={fontAvailability === "available"} label="Device Font Status" value={fontAvailability === "available" ? "Font fully loaded" : "Fallback active"} />
          <ReadinessMini ready={Boolean(autonomy?.auto_schedule_enabled)} label="Scheduled Pipelines" value={autonomy?.auto_schedule_enabled ? "Auto Schedule On" : "Auto Schedule Off"} />
        </div>
      </aside>
    </section>

    {/* Custom Brand Builder Modal Redesign with physical mockup */}
    <FocusModal
      open={builderOpen}
      title="Brand Builder"
      subtitle="Refine aesthetic typography, custom colors, watermarks, and components in real time."
      width="max"
      onClose={() => setBuilderOpen(false)}
    >
    <section className="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
      <div className="min-w-0 overflow-hidden rounded-[32px] border border-white/[0.08] bg-surface/30 backdrop-blur-md">
        <div className="border-b border-white/[0.08] bg-gradient-to-b from-cyan/[0.03] to-transparent p-5 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-cyan">Interactive Sandbox</p>
              <h3 className="mt-1.5 text-2xl font-semibold text-white tracking-tight">Style Customizer</h3>
            </div>
            <span className="rounded-full border border-cyan/[0.22] bg-teal/[0.08] px-3.5 py-1 text-xs font-bold uppercase tracking-wider text-cyan">
              {saveState}
            </span>
          </div>
        </div>

        <div className="grid gap-5 p-5 sm:p-6">
          <div className="rounded-[26px] border border-cyan/[0.14] bg-cyan/[0.02] p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-cyan">Direction settings</p>
                <h4 className="mt-1 text-lg font-semibold text-white">Preset Reference</h4>
                <p className="text-xs text-zinc-500 mt-1 leading-relaxed">Customize starting point vectors. Your specific overrides take priority on template save.</p>
              </div>
              {templateBusy ? <Loader2 className="h-4 w-4 shrink-0 animate-spin text-cyan" /> : <BadgeCheck className="h-5 w-5 shrink-0 text-cyan" />}
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              {brandPresets.map((preset) => {
                const active = editor.starterTemplate === preset.starterTemplate && editor.motionIntensity === preset.motionIntensity;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => applyPreset(preset)}
                    className={`min-w-0 rounded-[22px] border p-4 text-left transition ${active ? "border-cyan/[0.45] bg-cyan/[0.10]" : "border-white/[0.06] bg-black/15 hover:border-white/[0.12]"}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="grid h-8 w-8 place-items-center rounded-xl bg-black/20 text-cyan">
                        {preset.id === "editorial" ? <Sparkles className="h-3.5 w-3.5" /> : preset.id === "social" ? <Palette className="h-3.5 w-3.5" /> : <Layers3 className="h-3.5 w-3.5" />}
                      </span>
                      {active ? <CheckCircle2 className="h-3.5 w-3.5 text-cyan" /> : null}
                    </div>
                    <p className="mt-4 text-sm font-bold text-white truncate">{preset.label}</p>
                  </button>
                );
              })}
            </div>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="grid min-w-0 gap-2 text-xs font-bold uppercase tracking-wider text-zinc-500">
                Template Label
                <input value={label} onChange={(event) => setLabel(event.target.value)} className="h-11 min-w-0 rounded-2xl border border-white/[0.08] bg-black/20 px-3.5 text-sm text-zinc-200 outline-none focus:border-cyan/[0.35]" />
              </label>
              <label className="grid min-w-0 gap-2 text-xs font-bold uppercase tracking-wider text-zinc-500">
                Baseline Style File
                <div className="relative flex items-center">
                  <select
                    value={selectedTemplate}
                    disabled={templateBusy}
                    onChange={(event) => void loadTemplate(event.target.value)}
                    className="h-11 w-full appearance-none cursor-pointer rounded-2xl border border-white/[0.08] bg-black/20 pl-3.5 pr-10 text-sm font-semibold text-white outline-none focus:border-cyan/[0.35] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {(templates.length ? templates : [{id: defaultTemplate, label: "Default style baseline", path: defaultTemplate}]).map((template) => (
                      <option key={template.id} value={template.path} className="bg-[#17171a] text-white">{template.label}</option>
                    ))}
                  </select>
                  <span className="absolute right-3.5 pointer-events-none text-zinc-500">
                    <ChevronDown className="h-4 w-4" />
                  </span>
                </div>
              </label>
            </div>
          </div>

          <details className="group rounded-[26px] border border-white/[0.06] bg-black/15 p-5">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
              <span>
                <span className="block font-semibold text-white">Fine-tune individual slots</span>
                <span className="mt-1 block text-xs text-zinc-500">Control typography, Karaoke overlays, transitions, and lower thirds directly.</span>
              </span>
              <span className="rounded-full border border-white/[0.08] bg-surface px-3 py-1.5 text-xs font-semibold text-zinc-400">{editor.fontSize}px · {editor.motionIntensity}</span>
            </summary>
            <div className="mt-5 grid gap-6">
              <div>
                <div className="mb-3">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-cyan">Aesthetic specs</p>
                  <h4 className="font-semibold text-white mt-1">Watermark & Caption overlay</h4>
                </div>
                <div className="grid min-w-0 gap-4 lg:grid-cols-2">
                  <FontField
                    value={editor.fontFamily}
                    selectedOption={selectedFontOption}
                    availability={fontAvailability}
                    onSelect={(value) => updateEditor({fontFamily: value === "__custom" ? editor.fontFamily : value})}
                    onCustom={(value) => updateEditor({fontFamily: value})}
                  />
                  <NumberField label="Font size" value={editor.fontSize} min={28} max={76} onChange={(value) => updateEditor({fontSize: value})} />
                  <ColorField label="Text color" value={editor.textColor} onChange={(value) => updateEditor({textColor: value})} />
                  <ColorField label="Highlight" value={editor.highlightColor} onChange={(value) => updateEditor({highlightColor: value})} />
                  <ColorField label="Caption background" value={editor.backgroundColor} onChange={(value) => updateEditor({backgroundColor: value})} />
                  <NumberField label="Stroke width" value={editor.strokeWidth} min={0} max={16} onChange={(value) => updateEditor({strokeWidth: value})} />
                </div>
                <div className="mt-4 rounded-[20px] border border-white/[0.04] bg-black/20 p-3.5">
                  <TextField label="Watermark Text" value={editor.watermarkText} onChange={(value) => updateEditor({watermarkText: value})} />
                </div>
              </div>

              <div className="border-t border-white/[0.04] pt-5">
                <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-cyan">Engine instructions</p>
                    <h4 className="font-semibold text-white mt-1">Component Layout Slots</h4>
                  </div>
                  <span className="rounded-full border border-teal/[0.22] bg-teal/[0.08] px-3 py-1 text-xs font-bold uppercase tracking-wider text-teal">{productionReadyCount} slots active</span>
                </div>
                <div className="grid min-w-0 gap-4 lg:grid-cols-2">
                  <SelectField
                    label="Starter template"
                    value={editor.starterTemplate}
                    options={(hyperframesTemplates.length ? hyperframesTemplates : [{id: "spiritual_reflective", label: "Spiritual Reflective"} as HyperframesTemplate]).map((template) => ({value: template.id, label: template.label}))}
                    onChange={(value) => updateEditor({starterTemplate: value})}
                  />
                  <SelectField
                    label="Motion Intensity"
                    value={editor.motionIntensity}
                    options={[
                      {value: "calm", label: "Calm"},
                      {value: "balanced", label: "Balanced"},
                      {value: "energetic", label: "Energetic"},
                    ]}
                    onChange={(value) => updateEditor({motionIntensity: value})}
                  />
                  <SelectField label="Caption Overlays" value={editor.captionStyle} options={catalogOptions(hyperframesCatalog, "Captions", ["caption-editorial-emphasis", "caption-pill-karaoke", "caption-highlight"])} onChange={(value) => updateEditor({captionStyle: value})} />
                  <SelectField label="Texture overlays" value={editor.textureEffect} options={catalogOptions(hyperframesCatalog, "Texture/effects", ["vignette", "grain-overlay", "shimmer-sweep"])} onChange={(value) => updateEditor({textureEffect: value})} />
                  <SelectField label="Social callouts" value={editor.ctaOverlay} options={catalogOptions(hyperframesCatalog, "Social overlays", ["yt-lower-third", "instagram-follow", "tiktok-follow"])} onChange={(value) => updateEditor({ctaOverlay: value})} />
                  <SelectField label="Transitions" value={editor.transitionFamily} options={[{value: "dissolve", label: "Dissolve"}, {value: "push", label: "Push"}, {value: "zoom", label: "Zoom"}, {value: "whip-pan", label: "Whip Pan"}]} onChange={(value) => updateEditor({transitionFamily: value})} />
                  <SelectField label="Hooks & intro" value={editor.introLayout} options={[{value: "editorial-hook", label: "Editorial hook"}, {value: "lower-third-hook", label: "Lower-third hook"}, {value: "data-callout", label: "Data callout"}, {value: "headline-slam", label: "Headline slam"}]} onChange={(value) => updateEditor({introLayout: value})} />
                </div>
              </div>
            </div>
          </details>

          <div className="rounded-[26px] border border-cyan/[0.18] bg-teal/[0.08] p-5">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-cyan">Aesthetic Release</p>
                <h4 className="font-semibold text-white mt-1">Deploy changes</h4>
                <p className="text-xs text-zinc-500 mt-1 max-w-sm leading-relaxed">Save customized variables as a workspace template, making them immediately available in Creation.</p>
              </div>
              <div className="flex flex-wrap items-center gap-2.5 self-start sm:self-center">
                <button data-autofocus type="button" disabled={saveBusy || templateBusy} onClick={saveTemplate} className="inline-flex h-11 items-center gap-1.5 rounded-full bg-cyan px-5 text-xs font-bold uppercase tracking-wider text-ink disabled:cursor-not-allowed disabled:opacity-50 shadow-[0_8px_16px_rgba(102,232,249,0.15)]">
                  {saveBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  {saveBusy ? "Saving..." : "Save Template"}
                </button>
                <button type="button" disabled={saveBusy || templateBusy} onClick={() => void loadTemplate(selectedTemplate)} className="inline-flex h-11 items-center gap-1.5 rounded-full border border-white/[0.10] px-5 text-xs font-bold uppercase tracking-wider text-zinc-300 disabled:cursor-not-allowed disabled:opacity-50">
                  {templateBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  {templateBusy ? "Reset" : "Reset Base"}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Live Preview Modal aside with high-fidelity physical phone mockup */}
      <aside className="min-w-0 rounded-[32px] border border-white/[0.08] bg-surface/30 p-5 sm:p-6 xl:sticky xl:top-0 xl:self-start">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-5">
          <div className="min-w-0">
            <h3 className="text-lg font-semibold text-white tracking-tight">Interactive sandbox</h3>
            <p className="text-xs text-zinc-500 mt-0.5">Template preview with live brand overlay · hover to play</p>
          </div>
          <span className="rounded-full border border-cyan/[0.18] bg-teal/[0.08] px-3 py-1 text-xs font-semibold text-cyan">9:16</span>
        </div>

        {/* Clean 9:16 Sandbox preview container matching the grid cards precisely */}
        <div className="relative mx-auto w-full max-w-[17.5rem] aspect-[9/16] overflow-hidden rounded-[16px] border border-white/[0.08] bg-[#050507] shadow-inner transition-[border-color,box-shadow] duration-200">
          {selectedStarter ? (
            <TemplatePreview template={selectedStarter} compact gridCard hideFooterLabel hoverToPlay flush />
          ) : (
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_20%,rgba(108,226,238,.18),transparent_34%),linear-gradient(180deg,#24262c,#0a0a0c_68%)]" />
          )}

          <div className="pointer-events-none absolute inset-0 z-10 bg-gradient-to-b from-black/55 via-black/20 to-black/70" />

          <div className="pointer-events-none absolute inset-0 z-10 flex flex-col justify-between p-5">
            <div>
              <p
                className="text-center text-xl font-black leading-tight tracking-tight text-white drop-shadow-lg sm:text-2xl"
                style={{fontFamily: editor.fontFamily}}
              >
                Your strongest hook goes here
              </p>
              <p className="mx-auto mt-2 max-w-[200px] text-center text-[10px] font-semibold leading-relaxed text-zinc-300">
                {selectedStarter?.best_for || "A reusable brand system for clips, explainers, and socials."}
              </p>
            </div>
            <div className="grid gap-3">
              <div
                className="mx-auto max-w-full rounded-xl px-4 py-2.5 text-center font-black leading-none shadow-lg"
                style={{
                  background: editor.backgroundColor,
                  color: editor.textColor,
                  fontFamily: editor.fontFamily,
                  fontSize: `${Math.min(editor.fontSize - 12, 36)}px`,
                  WebkitTextStroke: `${editor.strokeWidth / 2.5}px #000`,
                }}
              >
                <span style={{color: editor.highlightColor}}>Sharp</span> key moment
              </div>
              <div className="flex items-center justify-between text-[10px] font-semibold text-zinc-400">
                <span>{editor.watermarkText}</span>
                <span style={{color: editor.highlightColor}}>{selectedStarter?.label || "Brand preset"}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-5 grid gap-2 rounded-[22px] border border-white/[0.06] bg-black/20 p-3.5 text-xs">
          <PreviewSpec label="Font Family" value={editor.fontFamily} />
          <PreviewSpec label="Caption Preset" value={`${editor.fontSize}px / stroke ${editor.strokeWidth}px`} />
          <PreviewSpec label="Channel Label" value={editor.watermarkText || "None"} />
        </div>
      </aside>
    </section>
    </FocusModal>
    </>
  );
}

function PreviewSpec({label, value}: {label: string; value: string}) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-3 rounded-xl bg-surface/50 px-3 py-2">
      <span className="text-zinc-500">{label}</span>
      <span className="min-w-0 truncate font-semibold text-zinc-200">{value}</span>
    </div>
  );
}

function catalogOptions(catalog: HyperframesCatalog | null, category: string, fallback: string[]) {
  const items = (catalog?.items || []).filter((item) => item.category === category && item.status !== "experimental");
  const options = items.length ? items.map((item) => ({value: item.id, label: `${item.label} · ${item.status}`})) : fallback.map((value) => ({value, label: value}));
  return options;
}

function SelectField({label, value, options, onChange}: {label: string; value: string; options: {value: string; label: string}[]; onChange: (value: string) => void}) {
  return (
    <label className="grid gap-2 text-xs font-bold uppercase tracking-wider text-zinc-500">
      {label}
      <div className="relative flex items-center">
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="h-11 w-full appearance-none cursor-pointer rounded-2xl border border-white/[0.08] bg-black/20 pl-3 pr-10 text-sm font-semibold normal-case tracking-normal text-white outline-none focus:border-cyan/[0.35]"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value} className="bg-[#17171a] text-white">{option.label}</option>
          ))}
        </select>
        <span className="absolute right-3.5 pointer-events-none text-zinc-500">
          <ChevronDown className="h-4 w-4" />
        </span>
      </div>
    </label>
  );
}

function ReadinessMini({ready, label, value}: {ready: boolean; label: string; value: string | number}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[20px] border border-white/[0.06] bg-black/15 p-3.5">
      <div className="min-w-0">
        <p className="text-[10px] uppercase font-bold tracking-wider text-zinc-500">{label}</p>
        <p className="mt-1 truncate text-xs font-semibold text-white">{value}</p>
      </div>
      <CheckCircle2 className={ready ? "h-4 w-4 shrink-0 text-cyan" : "h-4 w-4 shrink-0 text-zinc-700"} />
    </div>
  );
}

function TextField({label, value, onChange}: {label: string; value: string; onChange: (value: string) => void}) {
  return (
    <label className="grid gap-2 text-xs font-bold uppercase tracking-wider text-zinc-500">
      {label}
      <input value={value} onChange={(event) => onChange(event.target.value)} className="h-11 rounded-2xl border border-white/[0.08] bg-black/20 px-3 text-sm font-semibold normal-case tracking-normal text-white outline-none focus:border-cyan/[0.35]" />
    </label>
  );
}

function FontField({
  value,
  selectedOption,
  availability,
  onSelect,
  onCustom,
}: {
  value: string;
  selectedOption: string;
  availability: "checking" | "available" | "fallback";
  onSelect: (value: string) => void;
  onCustom: (value: string) => void;
}) {
  const availabilityLabel =
    availability === "checking" ? "Checking..." : availability === "available" ? "Fully loaded" : "Fallback active";
  return (
    <div className="grid gap-2 text-xs font-bold uppercase tracking-wider text-zinc-500">
      Font Family
      <div className="relative flex items-center">
        <select
          value={selectedOption}
          onChange={(event) => onSelect(event.target.value)}
          className="h-11 w-full appearance-none cursor-pointer rounded-2xl border border-white/[0.08] bg-black/20 pl-3 pr-10 text-sm font-semibold normal-case tracking-normal text-white outline-none focus:border-cyan/[0.35]"
        >
          {fontOptions.map((font) => (
            <option key={font.value} value={font.value} className="bg-[#17171a] text-white">{font.label} - {font.note}</option>
          ))}
        </select>
        <span className="absolute right-3.5 pointer-events-none text-zinc-500">
          <ChevronDown className="h-4 w-4" />
        </span>
      </div>
      {selectedOption === "__custom" ? (
        <input
          value={value}
          onChange={(event) => onCustom(event.target.value)}
          placeholder="Exact installed font name"
          className="h-11 rounded-2xl border border-white/[0.08] bg-black/20 px-3 text-sm font-semibold normal-case tracking-normal text-white outline-none focus:border-cyan/[0.35]"
        />
      ) : null}
      <span className={`text-[10px] font-bold uppercase mt-1 ${availability === "available" ? "text-cyan" : availability === "checking" ? "text-zinc-500" : "text-warning"}`}>
        {availabilityLabel}
      </span>
    </div>
  );
}

function NumberField({label, value, min, max, onChange}: {label: string; value: number; min: number; max: number; onChange: (value: number) => void}) {
  return (
    <label className="grid gap-2 text-xs font-bold uppercase tracking-wider text-zinc-500">
      {label}
      <input type="number" min={min} max={max} value={value} onChange={(event) => onChange(Number(event.target.value))} className="h-11 rounded-2xl border border-white/[0.08] bg-black/20 px-3 text-sm font-semibold normal-case tracking-normal text-white outline-none focus:border-cyan/[0.35]" />
    </label>
  );
}

function ColorField({label, value, onChange}: {label: string; value: string; onChange: (value: string) => void}) {
  return (
    <label className="grid gap-2 text-xs font-bold uppercase tracking-wider text-zinc-500">
      {label}
      <div className="flex h-11 items-center gap-2.5 rounded-2xl border border-white/[0.08] bg-black/20 px-3 focus-within:border-cyan/[0.35] transition-colors">
        <input type="color" value={value} onChange={(event) => onChange(event.target.value)} className="h-6 w-8 rounded border-0 bg-transparent p-0 cursor-pointer" />
        <input value={value} onChange={(event) => onChange(event.target.value)} className="min-w-0 flex-1 bg-transparent text-sm font-semibold normal-case tracking-normal text-white outline-none" />
      </div>
    </label>
  );
}

function EmptyState({text}: {text: string}) {
  return (
    <div className="grid min-h-[140px] place-items-center rounded-[24px] border border-dashed border-white/[0.08] bg-black/15 p-6 text-center text-sm text-zinc-500 leading-relaxed">
      {text}
    </div>
  );
}
