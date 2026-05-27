"use client";

import {useEffect, useMemo, useState} from "react";
import {BadgeCheck, CheckCircle2, Layers3, Loader2, Palette, Sparkles} from "lucide-react";
import {apiGet, apiPost, AutonomySettings, BrandTemplate, HyperframesCatalog, HyperframesTemplate, StyleProfile} from "@/lib/media-api";
import {FocusModal} from "@/components/FocusModal";

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
    starterTemplate: "data_market_explainer",
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
    const starterTemplateRequest = window.localStorage.getItem("otonom.brandBuilderStarterTemplate");
    const starterTemplate = starterTemplateRequest || "spiritual_reflective";
    window.localStorage.removeItem("otonom.brandBuilderStarterTemplate");
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
  const [fontAvailability, setFontAvailability] = useState<"checking" | "available" | "fallback">("checking");
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
    <section className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
      <div className="min-w-0 overflow-hidden rounded-[28px] border border-white/[0.08] bg-surface">
        <div className="border-b border-white/[0.08] bg-[radial-gradient(circle_at_10%_0%,rgba(108,226,238,.14),transparent_34%),linear-gradient(180deg,rgba(255,255,255,.035),transparent)] p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-cyan">HyperFrames brand system</p>
              <h3 className="mt-1 text-2xl font-semibold text-white">Brand System</h3>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-zinc-400">Choose a production brand direction. Open the builder only when customization is needed.</p>
            </div>
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${saveState.toLowerCase().includes("failed") ? "border-danger/30 bg-danger/10 text-danger" : "border-cyan/[0.22] bg-teal/[0.08] text-cyan"}`}>
              {saveState}
            </span>
          </div>
        </div>
        <div className="grid gap-4 p-4 sm:p-5">
          <div className="grid gap-3 md:grid-cols-3">
            {brandPresets.map((preset) => {
              const active = editor.starterTemplate === preset.starterTemplate && editor.motionIntensity === preset.motionIntensity;
              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => applyPreset(preset)}
                  className={`min-w-0 rounded-[24px] border p-5 text-left transition ${active ? "border-cyan/[0.45] bg-cyan/[0.10] shadow-glow" : "border-white/[0.08] bg-canvas-deep hover:border-white/[0.16]"}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="grid h-11 w-11 place-items-center rounded-2xl bg-surface text-cyan">
                      {preset.id === "editorial" ? <Sparkles className="h-5 w-5" /> : preset.id === "social" ? <Palette className="h-5 w-5" /> : <Layers3 className="h-5 w-5" />}
                    </span>
                    {active ? <CheckCircle2 className="h-4 w-4 text-cyan" /> : null}
                  </div>
                  <p className="mt-5 text-lg font-semibold text-white">{preset.label}</p>
                  <p className="mt-2 text-sm leading-6 text-zinc-400">{preset.note}</p>
                  <span className="mt-4 inline-flex rounded-full border border-cyan/[0.20] bg-teal/[0.08] px-3 py-1 text-xs font-semibold text-cyan">Open builder</span>
                </button>
              );
            })}
          </div>

          <div className="rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h4 className="font-semibold text-white">Saved brand templates</h4>
                <p className="mt-1 text-sm text-zinc-500">Open a saved template only when you need to inspect or customize it.</p>
              </div>
              <span className="rounded-full border border-cyan/[0.22] bg-teal/[0.08] px-3 py-1 text-xs font-semibold text-cyan">{templates.length} saved</span>
            </div>
            <div className="grid gap-2 md:grid-cols-2">
              {templates.length ? templates.map((template) => (
                <button
                  key={template.id}
                  type="button"
                  onClick={() => {
                    void loadTemplate(template.path);
                    setBuilderOpen(true);
                  }}
                  className="flex min-w-0 items-center justify-between gap-3 rounded-2xl bg-surface px-4 py-3 text-left text-zinc-200 transition hover:bg-surface-raised"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold">{template.label}</span>
                    <span className="mt-1 block truncate text-xs text-zinc-500">Saved Brand System Template</span>
                  </span>
                  <Sparkles className="h-4 w-4 shrink-0 text-cyan" />
                </button>
              )) : <EmptyState text="No style templates found." />}
            </div>
          </div>
        </div>
      </div>

      <aside className="min-w-0 rounded-[28px] border border-white/[0.08] bg-surface p-4 sm:p-5 xl:self-start">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Automation guardrails</p>
            <h4 className="mt-1 text-xl font-semibold text-white">Publishing autonomy</h4>
            <p className="mt-1 text-sm leading-6 text-zinc-400">Assisted mode gives you {autonomy?.review_grace_hours || 12}h to approve before high-score clips enter the schedule queue.</p>
          </div>
          <span className="rounded-full border border-cyan/[0.18] bg-teal/[0.08] px-3 py-1 text-xs font-semibold capitalize text-cyan">{autonomy?.autonomy_mode || "off"}</span>
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-3 xl:grid-cols-1">
          {["off", "assisted", "full"].map((mode) => (
            <button
              key={mode}
              type="button"
              disabled={Boolean(autonomyBusy)}
              onClick={() => onAutonomyMode(mode)}
              className={`inline-flex items-center justify-center gap-2 rounded-full px-3 py-2 text-sm font-semibold capitalize disabled:cursor-not-allowed disabled:opacity-50 ${autonomy?.autonomy_mode === mode ? "bg-cyan text-ink" : "border border-white/[0.10] text-zinc-300"}`}
            >
              {actionStates[`autonomy:${mode}`]?.status === "running" ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
              {actionStates[`autonomy:${mode}`]?.status === "running" ? "Saving..." : mode}
            </button>
          ))}
        </div>
        {autonomyBusy ? <p className="mt-3 text-xs font-medium text-cyan">{autonomyBusy.message}</p> : null}
        <div className="mt-4 grid gap-2">
          <ReadinessMini ready={Boolean(selectedStarter)} label="Starter" value={selectedStarter?.label || editor.starterTemplate} />
          <ReadinessMini ready={productionReadyCount > 0} label="Catalog" value={`${productionReadyCount} production-ready`} />
          <ReadinessMini ready={fontAvailability === "available"} label="Font" value={fontAvailability === "available" ? "Available" : "Fallback ready"} />
          <ReadinessMini ready={Boolean(autonomy?.auto_schedule_enabled)} label="Auto schedule" value={autonomy?.auto_schedule_enabled ? "On" : "Off"} />
        </div>
      </aside>
    </section>

    <FocusModal
      open={builderOpen}
      title="Brand Builder"
      subtitle="Customize the selected brand direction, preview it, then save it as a reusable HyperFrames Brand System Template."
      width="max"
      onClose={() => setBuilderOpen(false)}
    >
    <section className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
      <div className="min-w-0 overflow-hidden rounded-[28px] border border-white/[0.08] bg-surface">
        <div className="border-b border-white/[0.08] bg-[radial-gradient(circle_at_10%_0%,rgba(108,226,238,.14),transparent_34%),linear-gradient(180deg,rgba(255,255,255,.035),transparent)] p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-cyan">HyperFrames brand system</p>
              <h3 className="mt-1 text-2xl font-semibold text-white">Brand System</h3>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-zinc-400">Create reusable brand templates from HyperFrames-ready slots instead of raw renderer configuration.</p>
            </div>
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${saveState.toLowerCase().includes("failed") ? "border-danger/30 bg-danger/10 text-danger" : "border-cyan/[0.22] bg-teal/[0.08] text-cyan"}`}>
              {saveState}
            </span>
          </div>
        </div>

        <div className="grid gap-4 p-4 sm:p-5">
          <div className="rounded-[24px] border border-cyan/[0.18] bg-teal/[0.07] p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-wide text-cyan">Production setup</p>
                <h4 className="mt-1 text-xl font-semibold text-white">Choose the brand direction</h4>
                <p className="mt-1 max-w-2xl text-sm leading-6 text-zinc-400">Pick an intent preset, name it, then save. Detailed HyperFrames slots stay available when the brand needs precision.</p>
              </div>
              {templateBusy ? <Loader2 className="h-4 w-4 shrink-0 animate-spin text-cyan" /> : <BadgeCheck className="h-5 w-5 shrink-0 text-cyan" />}
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              {brandPresets.map((preset) => {
                const active = editor.starterTemplate === preset.starterTemplate && editor.motionIntensity === preset.motionIntensity;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => applyPreset(preset)}
                    className={`min-w-0 rounded-[22px] border p-4 text-left transition ${active ? "border-cyan/[0.45] bg-cyan/[0.10] shadow-glow" : "border-white/[0.08] bg-canvas-deep hover:border-white/[0.16]"}`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="grid h-10 w-10 place-items-center rounded-2xl bg-surface text-cyan">
                        {preset.id === "editorial" ? <Sparkles className="h-5 w-5" /> : preset.id === "social" ? <Palette className="h-5 w-5" /> : <Layers3 className="h-5 w-5" />}
                      </span>
                      {active ? <CheckCircle2 className="h-4 w-4 text-cyan" /> : null}
                    </div>
                    <p className="mt-4 font-semibold text-white">{preset.label}</p>
                    <p className="mt-2 text-xs leading-5 text-zinc-400">{preset.note}</p>
                  </button>
                );
              })}
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <label className="grid min-w-0 gap-2 text-sm font-medium text-zinc-300">
                Template name
                <input value={label} onChange={(event) => setLabel(event.target.value)} className="h-12 min-w-0 rounded-2xl border border-white/[0.08] bg-surface px-4 text-sm text-zinc-200 outline-none focus:border-cyan/[0.35]" />
              </label>
              <label className="grid min-w-0 gap-2 text-sm font-medium text-zinc-300">
                Base style file
                <select
                  value={selectedTemplate}
                  disabled={templateBusy}
                  onChange={(event) => void loadTemplate(event.target.value)}
                  className="h-12 min-w-0 rounded-2xl border border-white/[0.08] bg-surface px-4 text-sm font-semibold text-white outline-none disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {(templates.length ? templates : [{id: defaultTemplate, label: "Default style baseline", path: defaultTemplate}]).map((template) => (
                    <option key={template.id} value={template.path}>{template.label}</option>
                  ))}
                </select>
              </label>
            </div>

            <div className="mt-4 grid gap-2 sm:grid-cols-3">
              <ReadinessMini ready={Boolean(selectedStarter)} label="Starter" value={selectedStarter?.label || editor.starterTemplate} />
              <ReadinessMini ready={productionReadyCount > 0} label="Catalog" value={`${productionReadyCount} production-ready`} />
              <ReadinessMini ready={fontAvailability === "available"} label="Font" value={fontAvailability === "available" ? "Available" : "Fallback ready"} />
            </div>
          </div>

          <details className="group rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
              <span>
                <span className="block font-semibold text-white">Advanced slot customization</span>
                <span className="mt-1 block text-sm text-zinc-500">Use only when the preset needs typography, caption, CTA, or transition changes.</span>
              </span>
              <span className="rounded-full border border-white/[0.08] bg-surface px-3 py-1 text-xs font-semibold text-zinc-400">{editor.fontSize}px · {editor.motionIntensity}</span>
            </summary>
            <div className="mt-4 grid gap-5">
              <div>
                <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-cyan">Visual identity</p>
                    <h4 className="mt-1 font-semibold text-white">Caption and watermark</h4>
                  </div>
                </div>
                <div className="grid min-w-0 gap-3 lg:grid-cols-2">
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
                <div className="mt-3 rounded-[20px] border border-white/[0.08] bg-surface p-3">
                  <TextField label="Watermark text" value={editor.watermarkText} onChange={(value) => updateEditor({watermarkText: value})} />
                </div>
              </div>

              <div>
                <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-cyan">HyperFrames slots</p>
                    <h4 className="mt-1 font-semibold text-white">Components and motion</h4>
                  </div>
                  <span className="rounded-full border border-teal/[0.22] bg-teal/[0.08] px-3 py-1 text-xs font-semibold text-teal">{productionReadyCount} production-ready</span>
                </div>
                <div className="grid min-w-0 gap-3 lg:grid-cols-2">
                  <SelectField
                    label="HyperFrames starter"
                    value={editor.starterTemplate}
                    options={(hyperframesTemplates.length ? hyperframesTemplates : [{id: "spiritual_reflective", label: "Spiritual Reflective"} as HyperframesTemplate]).map((template) => ({value: template.id, label: template.label}))}
                    onChange={(value) => updateEditor({starterTemplate: value})}
                  />
                  <SelectField
                    label="Motion intensity"
                    value={editor.motionIntensity}
                    options={[
                      {value: "calm", label: "Calm"},
                      {value: "balanced", label: "Balanced"},
                      {value: "energetic", label: "Energetic"},
                    ]}
                    onChange={(value) => updateEditor({motionIntensity: value})}
                  />
                  <SelectField label="Caption style" value={editor.captionStyle} options={catalogOptions(hyperframesCatalog, "Captions", ["caption-editorial-emphasis", "caption-pill-karaoke", "caption-highlight"])} onChange={(value) => updateEditor({captionStyle: value})} />
                  <SelectField label="Texture/effect" value={editor.textureEffect} options={catalogOptions(hyperframesCatalog, "Texture/effects", ["vignette", "grain-overlay", "shimmer-sweep"])} onChange={(value) => updateEditor({textureEffect: value})} />
                  <SelectField label="CTA/social overlay" value={editor.ctaOverlay} options={catalogOptions(hyperframesCatalog, "Social overlays", ["yt-lower-third", "instagram-follow", "tiktok-follow"])} onChange={(value) => updateEditor({ctaOverlay: value})} />
                  <SelectField label="Transition family" value={editor.transitionFamily} options={[{value: "dissolve", label: "Dissolve"}, {value: "push", label: "Push"}, {value: "zoom", label: "Zoom"}, {value: "whip-pan", label: "Whip Pan"}]} onChange={(value) => updateEditor({transitionFamily: value})} />
                  <SelectField label="Intro/hook layout" value={editor.introLayout} options={[{value: "editorial-hook", label: "Editorial hook"}, {value: "lower-third-hook", label: "Lower-third hook"}, {value: "data-callout", label: "Data callout"}, {value: "headline-slam", label: "Headline slam"}]} onChange={(value) => updateEditor({introLayout: value})} />
                </div>
              </div>
            </div>
          </details>

          <div className="rounded-[24px] border border-cyan/[0.18] bg-teal/[0.08] p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-cyan">Step 4</p>
                <h4 className="mt-1 font-semibold text-white">Save template for production</h4>
                <p className="mt-1 text-sm text-zinc-400">Saved Brand System Templates appear in Templates and Generate.</p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <button data-autofocus type="button" disabled={saveBusy || templateBusy} onClick={saveTemplate} className="inline-flex items-center gap-2 rounded-full bg-cyan px-5 py-3 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50">
                  {saveBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  {saveBusy ? "Saving..." : "Save template"}
                </button>
                <button type="button" disabled={saveBusy || templateBusy} onClick={() => void loadTemplate(selectedTemplate)} className="inline-flex items-center gap-2 rounded-full border border-white/[0.10] px-5 py-3 text-sm font-semibold text-zinc-300 disabled:cursor-not-allowed disabled:opacity-50">
                  {templateBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  {templateBusy ? "Loading..." : "Reset to base"}
                </button>
              </div>
            </div>
          </div>

          <details className="group rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
              <span>
                <span className="block font-semibold text-white">Saved template library</span>
                <span className="mt-1 block text-sm text-zinc-500">Open only when you need to inspect or switch saved style files.</span>
              </span>
              <span className="rounded-full border border-cyan/[0.22] bg-teal/[0.08] px-3 py-1 text-xs font-semibold text-cyan">{templates.length} saved</span>
            </summary>
            <div className="mt-3 grid gap-2">
              {templates.length ? templates.map((template) => (
                <button
                  key={template.id}
                  type="button"
                  onClick={() => void loadTemplate(template.path)}
                  className={`flex min-w-0 items-center justify-between gap-3 rounded-2xl px-4 py-3 text-left transition ${selectedTemplate === template.path ? "bg-teal/[0.14] text-cyan ring-1 ring-cyan/[0.26]" : "bg-surface text-zinc-200 hover:bg-surface-raised"}`}
                >
                  <span className="min-w-0">
                    <span className="flex min-w-0 flex-wrap items-center gap-2">
                      <span className="truncate text-sm font-semibold">{template.label}</span>
                      {selectedTemplate === template.path ? <span className="rounded-full border border-cyan/[0.22] bg-cyan/[0.08] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-cyan">Active base</span> : null}
                    </span>
                    <span className="mt-1 block truncate text-xs text-zinc-500">Saved Brand System Template</span>
                  </span>
                  {selectedTemplate === template.path ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : null}
                </button>
              )) : <EmptyState text="No style templates found." />}
            </div>
          </details>

          <div className="rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Automation guardrails</p>
                <h4 className="mt-1 font-semibold text-white">Publishing autonomy</h4>
                <p className="mt-1 text-sm leading-6 text-zinc-400">Assisted mode gives you {autonomy?.review_grace_hours || 12}h to approve before high-score clips enter the schedule queue.</p>
              </div>
              <span className="rounded-full border border-cyan/[0.18] bg-teal/[0.08] px-3 py-1 text-xs font-semibold capitalize text-cyan">{autonomy?.autonomy_mode || "off"}</span>
            </div>
            <div className="mt-4 grid gap-2 sm:grid-cols-3">
              {["off", "assisted", "full"].map((mode) => (
                <button
                  key={mode}
                  type="button"
                  disabled={Boolean(autonomyBusy)}
                  onClick={() => onAutonomyMode(mode)}
                  className={`inline-flex items-center justify-center gap-2 rounded-full px-3 py-2 text-sm font-semibold capitalize disabled:cursor-not-allowed disabled:opacity-50 ${autonomy?.autonomy_mode === mode ? "bg-cyan text-ink" : "border border-white/[0.10] text-zinc-300"}`}
                >
                  {actionStates[`autonomy:${mode}`]?.status === "running" ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                  {actionStates[`autonomy:${mode}`]?.status === "running" ? "Saving..." : mode}
                </button>
              ))}
            </div>
            {autonomyBusy ? <p className="mt-3 text-xs font-medium text-cyan">{autonomyBusy.message}</p> : null}
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              <ReadinessMini ready={Boolean(autonomy?.review_grace_hours)} label="Review window" value={`${autonomy?.review_grace_hours || 12}h`} />
              <ReadinessMini ready={Boolean(autonomy?.auto_schedule_enabled)} label="Auto schedule" value={autonomy?.auto_schedule_enabled ? "On" : "Off"} />
              <ReadinessMini ready label="Overall gate" value={autonomy?.overall_threshold || 82} />
              <ReadinessMini ready label="Caption gate" value={autonomy?.caption_threshold || 90} />
            </div>
          </div>
        </div>
      </div>

      <aside className="min-w-0 rounded-[28px] border border-white/[0.08] bg-surface p-4 sm:p-5 xl:sticky xl:top-24 xl:self-start">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-xl font-semibold text-white">Live preview</h3>
            <p className="mt-1 text-sm text-zinc-500">Instant browser preview, no render needed.</p>
          </div>
          <span className="rounded-full border border-cyan/[0.18] bg-teal/[0.08] px-3 py-1 text-xs font-semibold text-cyan">9:16</span>
        </div>
        <div className="mt-4 mx-auto flex aspect-[9/16] max-h-[620px] w-full max-w-[350px] flex-col justify-between overflow-hidden rounded-[28px] border border-white/[0.10] bg-[radial-gradient(circle_at_50%_20%,rgba(108,226,238,.18),transparent_34%),linear-gradient(180deg,#31343a,#111214_68%)] p-7 shadow-glow">
          <div>
            <p className="text-center text-3xl font-black leading-tight text-white drop-shadow-lg">Your strongest hook goes here</p>
            <p className="mx-auto mt-3 max-w-[260px] text-center text-sm font-semibold leading-5 text-zinc-200">A reusable brand system for clips, explainers, promos, and social highlights.</p>
          </div>
          <div className="grid gap-5">
            <div
              className="mx-auto max-w-full rounded-xl px-5 py-3 text-center font-black leading-none shadow-lg"
              style={{
                background: editor.backgroundColor,
                color: editor.textColor,
                fontFamily: editor.fontFamily,
                fontSize: `${Math.min(editor.fontSize, 46)}px`,
                WebkitTextStroke: `${editor.strokeWidth / 2}px #000`,
              }}
            >
              <span style={{color: editor.highlightColor}}>Sharp</span> key moment
            </div>
            <div className="flex items-center justify-between text-xs font-semibold">
              <span className="text-white">{editor.watermarkText}</span>
              <span style={{color: editor.highlightColor}}>Source: Brand channel</span>
            </div>
          </div>
        </div>
        <div className="mt-4 grid gap-2 rounded-[22px] border border-white/[0.08] bg-canvas-deep p-3 text-xs">
          <PreviewSpec label="Font" value={editor.fontFamily} />
          <PreviewSpec label="Caption" value={`${editor.fontSize}px / stroke ${editor.strokeWidth}px`} />
          <PreviewSpec label="Watermark" value={editor.watermarkText || "None"} />
        </div>
      </aside>
    </section>
    </FocusModal>
    </>
  );
}

function PreviewSpec({label, value}: {label: string; value: string}) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-3 rounded-2xl bg-surface px-3 py-2">
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
    <label className="grid gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)} className="h-11 rounded-2xl border border-white/[0.08] bg-canvas-deep px-3 text-sm font-semibold normal-case tracking-normal text-white outline-none focus:border-cyan/[0.35]">
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </label>
  );
}

function ReadinessMini({ready, label, value}: {ready: boolean; label: string; value: string | number}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[18px] border border-white/[0.08] bg-canvas-deep p-4">
      <div className="min-w-0">
        <p className="text-xs text-zinc-500">{label}</p>
        <p className="mt-1 truncate text-sm font-semibold text-white">{value}</p>
      </div>
      <CheckCircle2 className={ready ? "h-4 w-4 shrink-0 text-cyan" : "h-4 w-4 shrink-0 text-zinc-600"} />
    </div>
  );
}

function TextField({label, value, onChange}: {label: string; value: string; onChange: (value: string) => void}) {
  return (
    <label className="grid gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
      {label}
      <input value={value} onChange={(event) => onChange(event.target.value)} className="h-11 rounded-2xl border border-white/[0.08] bg-canvas-deep px-3 text-sm font-semibold normal-case tracking-normal text-white outline-none focus:border-cyan/[0.35]" />
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
    availability === "checking" ? "Checking font..." : availability === "available" ? "Available on this device" : "Will use renderer/browser fallback";
  return (
    <div className="grid gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
      Font family
      <select
        value={selectedOption}
        onChange={(event) => onSelect(event.target.value)}
        className="h-11 rounded-2xl border border-white/[0.08] bg-canvas-deep px-3 text-sm font-semibold normal-case tracking-normal text-white outline-none focus:border-cyan/[0.35]"
      >
        {fontOptions.map((font) => (
          <option key={font.value} value={font.value}>{font.label} - {font.note}</option>
        ))}
      </select>
      {selectedOption === "__custom" ? (
        <input
          value={value}
          onChange={(event) => onCustom(event.target.value)}
          placeholder="Exact installed font name"
          className="h-11 rounded-2xl border border-white/[0.08] bg-canvas-deep px-3 text-sm font-semibold normal-case tracking-normal text-white outline-none focus:border-cyan/[0.35]"
        />
      ) : null}
      <span className={availability === "available" ? "text-cyan" : availability === "checking" ? "text-zinc-500" : "text-warning"}>
        {availabilityLabel}
      </span>
    </div>
  );
}

function NumberField({label, value, min, max, onChange}: {label: string; value: number; min: number; max: number; onChange: (value: number) => void}) {
  return (
    <label className="grid gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
      {label}
      <input type="number" min={min} max={max} value={value} onChange={(event) => onChange(Number(event.target.value))} className="h-11 rounded-2xl border border-white/[0.08] bg-canvas-deep px-3 text-sm font-semibold normal-case tracking-normal text-white outline-none focus:border-cyan/[0.35]" />
    </label>
  );
}

function ColorField({label, value, onChange}: {label: string; value: string; onChange: (value: string) => void}) {
  return (
    <label className="grid gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
      {label}
      <div className="flex h-11 items-center gap-2 rounded-2xl border border-white/[0.08] bg-canvas-deep px-3 focus-within:border-cyan/[0.35]">
        <input type="color" value={value} onChange={(event) => onChange(event.target.value)} className="h-7 w-8 rounded border-0 bg-transparent p-0" />
        <input value={value} onChange={(event) => onChange(event.target.value)} className="min-w-0 flex-1 bg-transparent text-sm font-semibold normal-case tracking-normal text-white outline-none" />
      </div>
    </label>
  );
}

function EmptyState({text}: {text: string}) {
  return (
    <div className="grid min-h-[140px] place-items-center rounded-[22px] border border-dashed border-white/[0.10] bg-canvas-deep p-6 text-center text-sm text-zinc-500">
      {text}
    </div>
  );
}
