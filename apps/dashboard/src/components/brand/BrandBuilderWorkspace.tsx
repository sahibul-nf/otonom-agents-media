"use client";

import Link from "next/link";
import {useRouter} from "next/navigation";
import {ArrowLeft, ChevronDown, Loader2} from "lucide-react";
import {useEffect, useState} from "react";
import {BrandStudioPreview} from "@/components/brand/BrandStudioPreview";
import {getRecipeTheme} from "@/components/templates/recipes";
import {
  apiGet,
  apiPost,
  type BrandTemplate,
  type HyperframesCatalog,
  type HyperframesTemplate,
  type StyleProfile,
} from "@/lib/media-api";

const DEFAULT_TEMPLATE = "profiles/default_workspace_style.json";
const STARTER_STORAGE_KEY = "otonom.brandBuilderStarterTemplate";

export const brandPresets = [
  {id: "editorial", label: "Editorial Calm", note: "Reflective, education, and story-led clips.", starterTemplate: "spiritual_reflective", fontFamily: "Sora", fontSize: 54, highlightColor: "#d8b45f", backgroundColor: "#111214", strokeWidth: 6, captionStyle: "caption-editorial-emphasis", introLayout: "editorial-hook", ctaOverlay: "yt-lower-third", textureEffect: "grain-overlay", transitionFamily: "dissolve", motionIntensity: "calm"},
  {id: "social", label: "Social Punch", note: "Creator clips, podcast highlights, and short hooks.", starterTemplate: "play_mode_social", fontFamily: "Poppins", fontSize: 56, highlightColor: "#67e8f9", backgroundColor: "#05070a", strokeWidth: 8, captionStyle: "caption-pill-karaoke", introLayout: "lower-third-hook", ctaOverlay: "instagram-follow", textureEffect: "shimmer-sweep", transitionFamily: "push", motionIntensity: "energetic"},
  {id: "analyst", label: "Analyst Clean", note: "Data, market, business, and technical explainers.", starterTemplate: "spiritual_reflective", fontFamily: "Inter", fontSize: 48, highlightColor: "#74f2ce", backgroundColor: "#07100f", strokeWidth: 4, captionStyle: "caption-clip-wipe", introLayout: "data-callout", ctaOverlay: "yt-lower-third", textureEffect: "vignette", transitionFamily: "zoom", motionIntensity: "balanced"},
  {id: "eva_cyber", label: "Eva Neon Cyber", note: "Neon overlays, glowing captions, and futuristic accents.", starterTemplate: "eva_neon_cyber", fontFamily: "Poppins", fontSize: 54, highlightColor: "#ff2a85", backgroundColor: "#030305", strokeWidth: 8, captionStyle: "caption-neon-glow", introLayout: "headline-slam", ctaOverlay: "instagram-follow", textureEffect: "shimmer-sweep", transitionFamily: "whip-pan", motionIntensity: "energetic"},
  {id: "volt_kinetic", label: "Volt Lime Kinetic", note: "Bold bounce, electric lime highlights, and title drops.", starterTemplate: "volt_lime_kinetic", fontFamily: "Montserrat", fontSize: 58, highlightColor: "#a7f36b", backgroundColor: "#040507", strokeWidth: 10, captionStyle: "caption-kinetic-slam", introLayout: "headline-slam", ctaOverlay: "tiktok-follow", textureEffect: "shimmer-sweep", transitionFamily: "zoom", motionIntensity: "energetic"},
  {id: "ember_sunset", label: "Ember Sunset", note: "Sunset gradient text with soft warm ambient glows.", starterTemplate: "ember_sunset_gradient", fontFamily: "Sora", fontSize: 52, highlightColor: "#ff5e36", backgroundColor: "#120a06", strokeWidth: 6, captionStyle: "caption-gradient-fill", introLayout: "editorial-hook", ctaOverlay: "yt-lower-third", textureEffect: "vignette", transitionFamily: "dissolve", motionIntensity: "calm"},
  {id: "align_minimal", label: "Align Minimal Box", note: "Monochrome active-word boxes and clean snap reveals.", starterTemplate: "align_minimal_box", fontFamily: "Inter", fontSize: 48, highlightColor: "#f8fafc", backgroundColor: "#09090b", strokeWidth: 4, captionStyle: "caption-clip-wipe", introLayout: "lower-third-hook", ctaOverlay: "x-post", textureEffect: "vignette", transitionFamily: "dissolve", motionIntensity: "balanced"},
] as const;

type EditorState = {
  fontFamily: string;
  fontSize: number;
  textColor: string;
  highlightColor: string;
  backgroundColor: string;
  strokeWidth: number;
  watermarkText: string;
  starterTemplate: string;
  captionStyle: string;
  introLayout: string;
  ctaOverlay: string;
  textureEffect: string;
  transitionFamily: string;
  motionIntensity: string;
};

type WorkspaceProps = {
  style: StyleProfile | null;
  templates: BrandTemplate[];
  hyperframesTemplates: HyperframesTemplate[];
  hyperframesCatalog: HyperframesCatalog | null;
  defaultTemplate?: string;
  initialStarter?: string;
  initialPreset?: string;
  initialBaseTemplate?: string;
  onTemplateSaved: () => void | Promise<void>;
};

const fontOptions = ["Sora", "Inter", "Montserrat", "Poppins", "Roboto", "Arial", "system-ui"] as const;
type DockTab = "identity" | "style" | "effects";
type RecipeLayer = "captions" | "texture" | "social" | "transition" | "intro";

function hexFromColor(value: unknown, fallback: string) {
  const text = String(value || "").trim();
  if (/^#[0-9a-f]{6}$/i.test(text)) return text.toLowerCase();
  if (/^#[0-9a-f]{3}$/i.test(text)) return `#${text.slice(1).split("").map((character) => `${character}${character}`).join("")}`.toLowerCase();
  const rgba = text.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
  return rgba ? `#${rgba.slice(1, 4).map((part) => Number(part).toString(16).padStart(2, "0")).join("")}`.toLowerCase() : fallback;
}

function editorFromStyle(source: StyleProfile | null, starterTemplate = "spiritual_reflective"): EditorState {
  const caption = source?.caption || {};
  const brand = source?.brand || {};
  const watermark = String(brand.watermark_text || "").trim();
  return {
    fontFamily: String(caption.font_family || "Sora"),
    fontSize: Number(caption.font_size || 54),
    textColor: hexFromColor(caption.text_color, "#ffffff"),
    highlightColor: hexFromColor(caption.highlight_word_color, "#00ff36"),
    backgroundColor: hexFromColor(caption.background_color, "#000000"),
    strokeWidth: Number(caption.stroke_width || 10),
    watermarkText: watermark && !/nourbit|nouraniyyah/i.test(watermark) ? watermark : "Brand Clips",
    starterTemplate,
    captionStyle: "caption-editorial-emphasis",
    introLayout: "editorial-hook",
    ctaOverlay: "yt-lower-third",
    textureEffect: "vignette",
    transitionFamily: "dissolve",
    motionIntensity: "balanced",
  };
}

function applyPresetToEditor(editor: EditorState, presetId?: string) {
  const preset = brandPresets.find((item) => item.id === presetId);
  if (!preset) return editor;
  return {
    ...editor,
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
  };
}

function snapshot(label: string, selectedTemplate: string, editor: EditorState) {
  return JSON.stringify({label, selectedTemplate, editor});
}

function catalogOptions(catalog: HyperframesCatalog | null, category: string, fallback: string[]) {
  const items = (catalog?.items || []).filter((item) => item.category === category && item.status !== "experimental");
  return items.length
    ? items.map((item) => ({
        value: item.id,
        label: item.status === "production-ready" ? item.label : `${item.label} · ${item.status}`,
      }))
    : fallback.map((value) => ({value, label: value}));
}

export function BrandBuilderWorkspace({
  style,
  templates,
  hyperframesTemplates,
  hyperframesCatalog,
  defaultTemplate = DEFAULT_TEMPLATE,
  initialStarter,
  initialPreset,
  initialBaseTemplate,
  onTemplateSaved,
}: WorkspaceProps) {
  const router = useRouter();
  const resolvedStarter = initialStarter || "spiritual_reflective";
  const validInitialBase = initialBaseTemplate === defaultTemplate || templates.some((template) => template.path === initialBaseTemplate)
    ? initialBaseTemplate
    : undefined;
  const initialEditor = applyPresetToEditor(editorFromStyle(style, resolvedStarter), initialPreset);
  const initialStarterTemplate = hyperframesTemplates.find((template) => template.id === initialEditor.starterTemplate);
  const [editor, setEditor] = useState(initialEditor);
  const [selectedTemplate, setSelectedTemplate] = useState(validInitialBase || defaultTemplate);
  const [label, setLabel] = useState(() => {
    const preset = brandPresets.find((item) => item.id === initialPreset);
    return preset ? `${preset.label} Brand Template` : initialStarterTemplate ? `${initialStarterTemplate.label} Brand Template` : "Custom Workspace Template";
  });
  const [saveState, setSaveState] = useState("Ready");
  const [templateBusy, setTemplateBusy] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const [dockTab, setDockTab] = useState<DockTab>("identity");
  const [recipeLayer, setRecipeLayer] = useState<RecipeLayer>("captions");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [activePresetId, setActivePresetId] = useState(initialPreset || "");
  const starterTemplates = hyperframesTemplates.length
    ? hyperframesTemplates
    : ([{id: "spiritual_reflective", label: "Spiritual Reflective", best_for: "Reflective clips"}] as HyperframesTemplate[]);
  const captionOptions = catalogOptions(hyperframesCatalog, "Captions", ["caption-editorial-emphasis", "caption-pill-karaoke", "caption-highlight"]);
  const textureOptions = catalogOptions(hyperframesCatalog, "Texture/effects", ["vignette", "grain-overlay", "shimmer-sweep"]);
  const socialOptions = catalogOptions(hyperframesCatalog, "Social overlays", ["yt-lower-third", "instagram-follow", "tiktok-follow"]);
  const transitionOptions = [
    {value: "dissolve", label: "Dissolve"},
    {value: "push", label: "Push"},
    {value: "zoom", label: "Zoom"},
    {value: "whip-pan", label: "Whip Pan"},
  ];
  const introOptions = [
    {value: "editorial-hook", label: "Editorial hook"},
    {value: "lower-third-hook", label: "Lower-third hook"},
    {value: "data-callout", label: "Data callout"},
    {value: "headline-slam", label: "Headline slam"},
  ];
  const baselineOptions = [
    {id: defaultTemplate, label: "Default style baseline", path: defaultTemplate},
    ...templates.filter((template) => template.path !== defaultTemplate),
  ].map((template) => ({value: template.path, label: template.label}));
  const layerRows: {id: RecipeLayer; label: string; value: string; options: {value: string; label: string}[]}[] = [
    {id: "captions", label: "Captions", value: editor.captionStyle, options: captionOptions},
    {id: "texture", label: "Texture", value: editor.textureEffect, options: textureOptions},
    {id: "social", label: "Social", value: editor.ctaOverlay, options: socialOptions},
    {id: "transition", label: "Transition", value: editor.transitionFamily, options: transitionOptions},
    {id: "intro", label: "Intro", value: editor.introLayout, options: introOptions},
  ];
  const [cleanSnapshot, setCleanSnapshot] = useState(() => snapshot(label, selectedTemplate, initialEditor));
  const currentSnapshot = snapshot(label, selectedTemplate, editor);
  const dirty = currentSnapshot !== cleanSnapshot;
  const selectedStarter = hyperframesTemplates.find((template) => template.id === editor.starterTemplate) || starterTemplates.find((template) => template.id === editor.starterTemplate);

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [dirty]);

  const updateEditor = (patch: Partial<EditorState>) => {
    setActivePresetId("");
    setEditor((current) => ({...current, ...patch}));
  };

  function applyPreset(presetId: string) {
    setActivePresetId(presetId);
    setEditor((current) => applyPresetToEditor(current, presetId));
  }

  function leaveBuilder() {
    if (dirty && !window.confirm("Discard your unsaved Brand Builder changes?")) return;
    router.push("/?section=brand");
  }

  async function loadTemplate(path: string, markClean = false) {
    setSelectedTemplate(path);
    setTemplateBusy(true);
    setSaveState("Loading…");
    try {
      const loaded = await apiGet<StyleProfile>(`style?path=${encodeURIComponent(path)}`);
      const nextEditor = editorFromStyle(loaded, editor.starterTemplate);
      const template = templates.find((item) => item.path === path);
      const nextLabel = template?.label ? `${template.label} Copy` : "Custom Workspace Template";
      setEditor(nextEditor);
      setLabel(nextLabel);
      setActivePresetId("");
      if (markClean) setCleanSnapshot(snapshot(nextLabel, path, nextEditor));
      setSaveState("Loaded");
    } catch (error) {
      setSaveState(error instanceof Error ? error.message : "Load failed");
    } finally {
      setTemplateBusy(false);
    }
  }

  useEffect(() => {
    if (!validInitialBase || validInitialBase === defaultTemplate) return;
    const frame = window.requestAnimationFrame(() => void loadTemplate(validInitialBase, true));
    return () => window.cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function saveTemplate() {
    setSaveBusy(true);
    setSaveState("Saving…");
    try {
      await apiPost("brand-system-templates", {
        label,
        style: {
          caption: {
            font_family: editor.fontFamily,
            font_size: editor.fontSize,
            text_color: editor.textColor,
            highlight_word_color: editor.highlightColor,
            background_color: editor.backgroundColor,
            stroke_width: editor.strokeWidth,
          },
          brand: {watermark_text: editor.watermarkText},
        },
        brand_system: {
          starter_template: editor.starterTemplate,
          caption_style: editor.captionStyle,
          intro_layout: editor.introLayout,
          cta_overlay: editor.ctaOverlay,
          texture_effect: editor.textureEffect,
          transition_family: editor.transitionFamily,
          motion_intensity: editor.motionIntensity,
        },
        base_template: selectedTemplate,
      });
      setCleanSnapshot(snapshot(label, selectedTemplate, editor));
      setSaveState("Saved");
      await onTemplateSaved();
    } catch (error) {
      setSaveState(error instanceof Error ? error.message : "Save failed");
    } finally {
      setSaveBusy(false);
    }
  }

  return (
    <main className="flex h-dvh flex-col overflow-hidden bg-canvas-deep text-zinc-100">
      <header className="z-40 flex shrink-0 items-center justify-between gap-3 border-b border-white/[0.08] bg-canvas-deep/95 px-3 py-2.5 backdrop-blur-md sm:px-5">
        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <button
            type="button"
            onClick={leaveBuilder}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-zinc-400 transition hover:bg-white/[0.06] hover:text-white"
            aria-label="Back to Brand"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div className="min-w-0 flex-1">
            <input
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              className="w-full max-w-md truncate bg-transparent text-sm font-semibold text-white outline-none placeholder:text-zinc-600 focus:text-white"
              placeholder="Template name"
              aria-label="Template name"
            />
            <p className="truncate text-[11px] text-zinc-500">{selectedStarter?.label || "Custom style"}</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2.5">
          <span className={`hidden text-[11px] font-medium sm:inline ${dirty ? "text-warning" : "text-zinc-500"}`} title={!dirty ? "No changes to save" : undefined}>
            {dirty ? "Unsaved changes" : saveState}
          </span>
          <button
            type="button"
            disabled={!dirty || saveBusy || templateBusy}
            onClick={() => void saveTemplate()}
            title={!dirty ? "No changes to save" : "Save brand template"}
            className="inline-flex h-9 items-center gap-2 rounded-full bg-cyan px-4 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saveBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            {saveBusy ? "Saving…" : "Save"}
          </button>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(300px,400px)_minmax(0,1fr)]">
        <aside className="order-2 flex min-h-0 flex-col border-t border-white/[0.08] bg-surface/40 lg:order-1 lg:border-r lg:border-t-0">
          <div className="flex shrink-0 gap-0.5 overflow-x-auto border-b border-white/[0.08] px-2 pt-2.5 pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:px-3">
            {(
              [
                {id: "identity" as const, label: "Identity"},
                {id: "style" as const, label: "Style"},
                {id: "effects" as const, label: "Effects"},
              ] as const
            ).map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setDockTab(tab.id)}
                className={`shrink-0 rounded-full px-3.5 py-1.5 text-[11px] font-semibold tracking-wide transition ${
                  dockTab === tab.id ? "bg-white/[0.1] text-white" : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            {dockTab !== "effects" ? (
              <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 py-3 sm:px-4 sm:py-4">
                {dockTab === "identity" ? (
                  <div className="space-y-5">
                    <div>
                      <p className="mb-2.5 text-[10px] font-bold uppercase tracking-widest text-zinc-500">Colors</p>
                      <div className="flex flex-wrap items-center gap-4">
                        <Swatch label="Highlight" value={editor.highlightColor} onChange={(highlightColor) => updateEditor({highlightColor})} />
                        <Swatch label="Text" value={editor.textColor} onChange={(textColor) => updateEditor({textColor})} />
                        <Swatch label="Plate" value={editor.backgroundColor} onChange={(backgroundColor) => updateEditor({backgroundColor})} />
                      </div>
                    </div>

                    <div>
                      <p className="mb-2.5 text-[10px] font-bold uppercase tracking-widest text-zinc-500">Type</p>
                      <div className="mb-3 flex flex-wrap gap-2">
                        {fontOptions.map((font) => {
                          const active = editor.fontFamily === font;
                          return (
                            <button
                              key={font}
                              type="button"
                              onClick={() => updateEditor({fontFamily: font})}
                              className={`rounded-full border px-3.5 py-2 text-sm transition ${
                                active ? "border-cyan/45 bg-cyan/[0.12] text-white" : "border-white/[0.08] text-zinc-300 hover:border-white/[0.16]"
                              }`}
                              style={{fontFamily: font}}
                            >
                              {font}
                            </button>
                          );
                        })}
                      </div>
                      <label className="mb-3 block">
                        <span className="mb-1.5 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                          <span>Size</span>
                          <span className="tabular-nums text-zinc-300">{editor.fontSize}px</span>
                        </span>
                        <input
                          type="range"
                          min={28}
                          max={76}
                          value={editor.fontSize}
                          onChange={(event) => updateEditor({fontSize: Number(event.target.value)})}
                          className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-white/10 accent-cyan"
                        />
                      </label>
                      <label className="block">
                        <span className="mb-1.5 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                          <span>Stroke</span>
                          <span className="tabular-nums text-zinc-300">{editor.strokeWidth}</span>
                        </span>
                        <input
                          type="range"
                          min={0}
                          max={16}
                          value={editor.strokeWidth}
                          onChange={(event) => updateEditor({strokeWidth: Number(event.target.value)})}
                          className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-white/10 accent-cyan"
                        />
                      </label>
                    </div>

                    <div>
                      <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500">Watermark</p>
                      <input
                        value={editor.watermarkText}
                        onChange={(event) => updateEditor({watermarkText: event.target.value})}
                        placeholder="Brand name"
                        className="h-10 w-full rounded-xl border border-white/[0.08] bg-black/20 px-3 text-sm text-white outline-none placeholder:text-zinc-600 focus:border-cyan/35"
                      />
                    </div>

                    <div>
                      <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500">Pace</p>
                      <div className="flex rounded-full border border-white/[0.08] bg-black/20 p-0.5">
                        {(
                          [
                            {value: "calm", label: "Calm"},
                            {value: "balanced", label: "Balanced"},
                            {value: "energetic", label: "Energetic"},
                          ] as const
                        ).map((option) => (
                          <button
                            key={option.value}
                            type="button"
                            onClick={() => updateEditor({motionIntensity: option.value})}
                            className={`flex-1 rounded-full py-1.5 text-[11px] font-semibold transition ${
                              editor.motionIntensity === option.value ? "bg-white/[0.1] text-white" : "text-zinc-500 hover:text-zinc-300"
                            }`}
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : null}

                {dockTab === "style" ? (
                  <div className="space-y-3">
                    <p className="text-[11px] leading-relaxed text-zinc-500">Applies colors, type, and default effects.</p>
                    <div className="grid grid-cols-2 gap-2">
                      {brandPresets.map((preset) => {
                        const active = activePresetId === preset.id;
                        return (
                          <button
                            key={preset.id}
                            type="button"
                            onClick={() => applyPreset(preset.id)}
                            className={`rounded-2xl border px-3 py-2.5 text-left transition ${
                              active ? "border-cyan/50 bg-cyan/[0.12] ring-1 ring-cyan/25" : "border-white/[0.08] bg-black/15 hover:border-white/[0.16]"
                            }`}
                          >
                            <span className="mb-1.5 flex gap-1" aria-hidden>
                              <span className="h-3 w-3 rounded-full" style={{background: preset.highlightColor}} />
                              <span className="h-3 w-3 rounded-full border border-white/20" style={{background: preset.backgroundColor}} />
                            </span>
                            <span className="block truncate text-[11px] font-semibold text-zinc-200">{preset.label}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <>
                <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 py-3 sm:px-4 sm:py-4">
                  <div className="space-y-5">
                    <div>
                      <div className="mb-2.5 flex items-end justify-between gap-2">
                        <div>
                          <p className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">Base style</p>
                          <p className="mt-0.5 text-[11px] text-zinc-500">Style pack for overlays & motion defaults</p>
                        </div>
                        <span className="truncate text-[11px] font-medium text-zinc-400">{selectedStarter?.label || "Custom"}</span>
                      </div>
                      <div className="grid max-h-[13.5rem] grid-cols-2 gap-2 overflow-y-auto overscroll-contain pr-0.5">
                        {starterTemplates.map((template) => {
                          const active = editor.starterTemplate === template.id;
                          const theme = getRecipeTheme(template.id);
                          return (
                            <button
                              key={template.id}
                              type="button"
                              onClick={() => updateEditor({starterTemplate: template.id})}
                              className={`relative overflow-hidden rounded-2xl border p-2.5 text-left transition ${
                                active ? "border-white/25 ring-1 ring-cyan/35" : "border-white/[0.07] hover:border-white/[0.14]"
                              }`}
                              style={{
                                background: `linear-gradient(145deg, ${theme.accent}33 0%, rgba(12,13,16,.92) 55%)`,
                              }}
                            >
                              <span className="mb-2 flex h-8 items-end gap-1" aria-hidden>
                                <span className="h-2 w-8 rounded-full" style={{background: theme.accent}} />
                                <span className="h-2 w-4 rounded-full opacity-70" style={{background: theme.secondary}} />
                              </span>
                              <span className="block truncate text-[11px] font-semibold leading-tight text-white">{template.label}</span>
                              {active ? <span className="mt-1 block text-[10px] font-medium text-cyan">Selected</span> : null}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    <div>
                      <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500">Layers</p>
                      <div className="overflow-hidden rounded-2xl border border-white/[0.07] bg-black/20">
                        {layerRows.map((row) => {
                          const open = recipeLayer === row.id;
                          const selectedLabel = displayOptionLabel(row.options.find((option) => option.value === row.value)?.label || row.value);
                          return (
                            <div key={row.id} className="border-b border-white/[0.06] last:border-b-0">
                              <button
                                type="button"
                                onClick={() => setRecipeLayer(row.id)}
                                className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left transition hover:bg-white/[0.03]"
                                aria-expanded={open}
                              >
                                <span className="text-xs font-semibold text-zinc-300">{row.label}</span>
                                <span className="flex min-w-0 items-center gap-1.5">
                                  <span className="truncate text-[11px] text-zinc-500">{selectedLabel.clean}</span>
                                  {selectedLabel.beta ? (
                                    <span className="rounded bg-white/[0.06] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-zinc-500">Beta</span>
                                  ) : null}
                                  <ChevronDown className={`h-3.5 w-3.5 shrink-0 text-zinc-600 transition-transform ${open ? "rotate-180" : ""}`} />
                                </span>
                              </button>
                              {open ? (
                                <div className="flex flex-wrap gap-1.5 px-3 pb-3">
                                  {row.options.map((option) => {
                                    const meta = displayOptionLabel(option.label);
                                    const active = row.value === option.value;
                                    return (
                                      <button
                                        key={option.value}
                                        type="button"
                                        onClick={() => {
                                          switch (row.id) {
                                            case "captions":
                                              updateEditor({captionStyle: option.value});
                                              break;
                                            case "texture":
                                              updateEditor({textureEffect: option.value});
                                              break;
                                            case "social":
                                              updateEditor({ctaOverlay: option.value});
                                              break;
                                            case "transition":
                                              updateEditor({transitionFamily: option.value});
                                              break;
                                            case "intro":
                                              updateEditor({introLayout: option.value});
                                              break;
                                            default: {
                                              const _exhaustive: never = row.id;
                                              void _exhaustive;
                                              break;
                                            }
                                          }
                                        }}
                                        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold transition ${
                                          active
                                            ? "border-cyan/40 bg-cyan/[0.12] text-white"
                                            : "border-white/[0.08] text-zinc-400 hover:border-white/[0.14] hover:text-zinc-200"
                                        }`}
                                      >
                                        {meta.clean}
                                        {meta.beta ? <span className="text-[9px] uppercase tracking-wide text-zinc-500">β</span> : null}
                                      </button>
                                    );
                                  })}
                                </div>
                              ) : null}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="shrink-0 border-t border-white/[0.08] bg-surface/60 px-3 py-3 sm:px-4">
                  <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500">Save as</p>
                  <input
                    value={label}
                    onChange={(event) => setLabel(event.target.value)}
                    placeholder="Template name"
                    className="mb-2 h-10 w-full rounded-xl border border-white/[0.08] bg-black/20 px-3 text-sm font-semibold text-white outline-none placeholder:text-zinc-600 focus:border-cyan/35"
                  />
                  <button
                    type="button"
                    disabled={saveBusy || templateBusy}
                    onClick={() => void loadTemplate(selectedTemplate, true)}
                    className="mb-1 h-9 w-full rounded-full text-[11px] font-semibold text-zinc-500 transition hover:text-zinc-300 disabled:opacity-45"
                  >
                    Reset to baseline
                  </button>
                  <details
                    open={advancedOpen}
                    onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}
                    className="mt-1"
                  >
                    <summary className="cursor-pointer list-none text-[11px] font-semibold text-zinc-500 hover:text-zinc-300">
                      Advanced
                    </summary>
                    <div className="mt-2">
                      <FieldSelect
                        label="Baseline style file"
                        value={selectedTemplate}
                        disabled={templateBusy}
                        options={baselineOptions}
                        onChange={(path) => void loadTemplate(path)}
                      />
                    </div>
                  </details>
                </div>
              </>
            )}
          </div>
        </aside>

        <section
          className="order-1 relative flex min-h-[min(52dvh,28rem)] items-center justify-center overflow-hidden bg-canvas-deep px-4 py-5 lg:order-2 lg:min-h-0 lg:px-8 lg:py-8"
          style={{
            backgroundImage: `
              radial-gradient(ellipse 55% 50% at 50% 42%, ${editor.highlightColor}14, transparent 62%),
              radial-gradient(circle at 80% 90%, rgba(98,238,248,.04), transparent 35%)
            `,
          }}
        >
          <BrandStudioPreview
            look={editor}
            effects={{
              starterId: editor.starterTemplate,
              captionStyle: editor.captionStyle,
              textureEffect: editor.textureEffect,
              ctaOverlay: editor.ctaOverlay,
              introLayout: editor.introLayout,
            }}
          />
        </section>
      </div>

      <Link
        href="/?section=brand"
        onClick={(event) => {
          if (dirty && !window.confirm("Discard your unsaved Brand Builder changes?")) event.preventDefault();
        }}
        className="sr-only"
      >
        Brand library
      </Link>
    </main>
  );
}

export function BrandBuilderPage({starter, preset, baseTemplate}: {starter?: string; preset?: string; baseTemplate?: string}) {
  const [data, setData] = useState<{style: StyleProfile; templates: BrandTemplate[]; hyperframesTemplates: HyperframesTemplate[]; hyperframesCatalog: HyperframesCatalog}>();
  const [error, setError] = useState("");
  const [storageStarter, setStorageStarter] = useState<string>();

  async function loadData() {
    try {
      const [style, templates, hyperframesTemplates, hyperframesCatalog] = await Promise.all([
        apiGet<StyleProfile>("style"),
        apiGet<BrandTemplate[]>("brand-templates"),
        apiGet<HyperframesTemplate[]>("hyperframes-templates"),
        apiGet<HyperframesCatalog>("hyperframes-catalog"),
      ]);
      setData({style, templates, hyperframesTemplates, hyperframesCatalog});
      setError("");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Brand Builder failed to load");
    }
  }

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const handoff = window.localStorage.getItem(STARTER_STORAGE_KEY) || undefined;
      setStorageStarter(handoff);
      if (handoff) window.localStorage.removeItem(STARTER_STORAGE_KEY);
      void loadData();
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  if (error) {
    return (
      <main className="grid min-h-screen place-items-center bg-canvas-deep px-5 text-center text-zinc-100">
        <div>
          <p className="text-sm font-semibold text-danger">{error}</p>
          <button type="button" onClick={() => void loadData()} className="mt-5 rounded-full bg-cyan px-5 py-2.5 text-sm font-semibold text-ink">
            Retry
          </button>
        </div>
      </main>
    );
  }
  if (!data) {
    return (
      <main className="grid min-h-screen place-items-center bg-canvas-deep text-cyan">
        <Loader2 className="h-6 w-6 animate-spin" />
      </main>
    );
  }

  return <BrandBuilderWorkspace {...data} initialStarter={starter || storageStarter} initialPreset={preset} initialBaseTemplate={baseTemplate} onTemplateSaved={loadData} />;
}

function Swatch({label, value, onChange}: {label: string; value: string; onChange: (value: string) => void}) {
  return (
    <label className="flex cursor-pointer items-center gap-2.5">
      <span className="relative h-9 w-9 overflow-hidden rounded-full border border-white/20 shadow-inner">
        <span className="absolute inset-0 transition-colors duration-300" style={{background: value}} />
        <input
          type="color"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
          aria-label={label}
        />
      </span>
      <span className="text-[11px] font-semibold text-zinc-400">{label}</span>
    </label>
  );
}

function displayOptionLabel(label: string) {
  const beta = /\bbeta\b/i.test(label);
  const clean = label.replace(/\s*[·\-–]\s*beta\b/i, "").trim();
  return {clean, beta};
}

function FieldSelect({
  label,
  value,
  options,
  disabled = false,
  onChange,
}: {
  label: string;
  value: string;
  options: {value: string; label: string}[];
  disabled?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-1.5 text-[10px] font-bold uppercase tracking-wider text-zinc-500">
      {label}
      <span className="relative flex items-center">
        <select
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          className="h-10 w-full appearance-none rounded-xl border border-white/[0.08] bg-black/30 pl-3 pr-9 text-sm font-semibold normal-case tracking-normal text-white outline-none focus:border-cyan/35 disabled:opacity-50"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value} className="bg-[#17171a]">
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 h-4 w-4 text-zinc-500" />
      </span>
    </label>
  );
}
