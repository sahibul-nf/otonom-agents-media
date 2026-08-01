"use client";

import Link from "next/link";
import {useRouter} from "next/navigation";
import {ArrowLeft, ChevronDown, Loader2, SlidersHorizontal, X} from "lucide-react";
import {useEffect, useState} from "react";
import {BrandStudioPreview} from "@/components/brand/BrandStudioPreview";
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
type DockTab = "look" | "type" | "more";

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
  const [dockTab, setDockTab] = useState<DockTab>("look");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [activePresetId, setActivePresetId] = useState(initialPreset || "");
  const [cleanSnapshot, setCleanSnapshot] = useState(() => snapshot(label, selectedTemplate, initialEditor));
  const currentSnapshot = snapshot(label, selectedTemplate, editor);
  const dirty = currentSnapshot !== cleanSnapshot;
  const selectedStarter = hyperframesTemplates.find((template) => template.id === editor.starterTemplate);

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
    <main className="flex h-dvh flex-col overflow-hidden bg-[#0a0b0e] text-zinc-100">
      <header className="z-40 flex shrink-0 items-center justify-between gap-3 border-b border-white/[0.06] px-3 py-2.5 sm:px-5">
        <div className="flex min-w-0 items-center gap-2.5">
          <button
            type="button"
            onClick={leaveBuilder}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-zinc-400 transition hover:bg-white/[0.06] hover:text-white"
            aria-label="Back to Brand"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-white">Brand studio</p>
            <p className="truncate text-[11px] text-zinc-500">{selectedStarter?.label || "Custom"} · live caption</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className={`hidden text-[11px] font-medium sm:inline ${dirty ? "text-warning" : "text-zinc-500"}`}>
            {dirty ? "Unsaved" : saveState}
          </span>
          <button
            type="button"
            onClick={() => setSheetOpen(true)}
            className="grid h-9 w-9 place-items-center rounded-full border border-white/[0.08] text-zinc-300 transition hover:border-white/[0.16] hover:text-white"
            aria-label="More settings"
          >
            <SlidersHorizontal className="h-4 w-4" />
          </button>
          <button
            type="button"
            disabled={!dirty || saveBusy || templateBusy}
            onClick={() => void saveTemplate()}
            className="inline-flex h-9 items-center gap-2 rounded-full bg-cyan px-4 text-xs font-bold uppercase tracking-wider text-ink disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saveBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            Save
          </button>
        </div>
      </header>

      {/* Stage — preview owns the viewport */}
      <div
        className="relative flex min-h-0 flex-1 flex-col items-center justify-center overflow-hidden px-4 py-4"
        style={{
          background: `
            radial-gradient(ellipse 60% 50% at 50% 35%, ${editor.highlightColor}14, transparent 60%),
            radial-gradient(circle at 50% 100%, rgba(98,238,248,.04), transparent 40%),
            #0a0b0e
          `,
        }}
      >
        <BrandStudioPreview look={editor} />
      </div>

      {/* Bottom dock — visual tools, not a form wall */}
      <div className="z-30 shrink-0 border-t border-white/[0.07] bg-[#101114]/95 backdrop-blur-xl">
        <div className="mx-auto flex max-w-3xl gap-1 px-3 pt-2">
          {(
            [
              {id: "look" as const, label: "Look"},
              {id: "type" as const, label: "Type"},
              {id: "more" as const, label: "Motion"},
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setDockTab(tab.id)}
              className={`flex-1 rounded-full py-1.5 text-[11px] font-bold uppercase tracking-wider transition ${
                dockTab === tab.id ? "bg-white/[0.1] text-white" : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="mx-auto max-w-3xl px-3 pb-3 pt-2 sm:px-4 sm:pb-4">
          {dockTab === "look" ? (
            <div className="space-y-3">
              <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                {brandPresets.map((preset) => {
                  const active = activePresetId === preset.id;
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => applyPreset(preset.id)}
                      className={`shrink-0 rounded-2xl border px-3 py-2 text-left transition ${
                        active ? "border-cyan/50 bg-cyan/[0.12]" : "border-white/[0.08] bg-white/[0.03] hover:border-white/[0.16]"
                      }`}
                    >
                      <span className="mb-1.5 flex gap-1" aria-hidden>
                        <span className="h-3 w-3 rounded-full" style={{background: preset.highlightColor}} />
                        <span className="h-3 w-3 rounded-full border border-white/20" style={{background: preset.backgroundColor}} />
                      </span>
                      <span className="block max-w-[7.5rem] truncate text-[11px] font-semibold text-zinc-200">{preset.label}</span>
                    </button>
                  );
                })}
              </div>

              <div className="flex flex-wrap items-center gap-4">
                <Swatch label="Highlight" value={editor.highlightColor} onChange={(highlightColor) => updateEditor({highlightColor})} />
                <Swatch label="Text" value={editor.textColor} onChange={(textColor) => updateEditor({textColor})} />
                <Swatch label="Plate" value={editor.backgroundColor} onChange={(backgroundColor) => updateEditor({backgroundColor})} />
              </div>
            </div>
          ) : null}

          {dockTab === "type" ? (
            <div className="space-y-3">
              <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                {fontOptions.map((font) => {
                  const active = editor.fontFamily === font;
                  return (
                    <button
                      key={font}
                      type="button"
                      onClick={() => updateEditor({fontFamily: font})}
                      className={`shrink-0 rounded-full border px-3.5 py-2 text-sm transition ${
                        active ? "border-cyan/45 bg-cyan/[0.12] text-white" : "border-white/[0.08] text-zinc-300 hover:border-white/[0.16]"
                      }`}
                      style={{fontFamily: font}}
                    >
                      {font}
                    </button>
                  );
                })}
              </div>
              <label className="block">
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
              <input
                value={editor.watermarkText}
                onChange={(event) => updateEditor({watermarkText: event.target.value})}
                placeholder="Watermark"
                className="h-10 w-full rounded-xl border border-white/[0.08] bg-white/[0.03] px-3 text-sm text-white outline-none placeholder:text-zinc-600 focus:border-cyan/35"
              />
            </div>
          ) : null}

          {dockTab === "more" ? (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
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
                    className={`rounded-full border px-3.5 py-2 text-xs font-semibold transition ${
                      editor.motionIntensity === option.value
                        ? "border-cyan/45 bg-cyan/[0.12] text-white"
                        : "border-white/[0.08] text-zinc-400 hover:border-white/[0.16]"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <p className="text-[11px] leading-relaxed text-zinc-500">
                Caption highlight pace follows motion. Recipe overlays & save name live in{" "}
                <button type="button" onClick={() => setSheetOpen(true)} className="font-semibold text-cyan hover:underline">
                  More settings
                </button>
                .
              </p>
            </div>
          ) : null}
        </div>
      </div>

      {sheetOpen ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 sm:items-center sm:p-6" role="dialog" aria-modal="true" aria-label="More brand settings">
          <button type="button" className="absolute inset-0 cursor-default" aria-label="Close" onClick={() => setSheetOpen(false)} />
          <div className="relative z-10 flex max-h-[min(88dvh,640px)] w-full max-w-lg flex-col overflow-hidden rounded-t-[24px] border border-white/[0.1] bg-[#141518] shadow-2xl sm:rounded-[24px]">
            <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
              <h2 className="text-sm font-semibold text-white">More settings</h2>
              <button type="button" onClick={() => setSheetOpen(false)} className="grid h-8 w-8 place-items-center rounded-full text-zinc-400 hover:bg-white/[0.06] hover:text-white" aria-label="Close">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="space-y-4 overflow-y-auto px-4 py-4">
              <FieldSelect
                label="Starter recipe"
                value={editor.starterTemplate}
                options={(hyperframesTemplates.length ? hyperframesTemplates : [{id: "spiritual_reflective", label: "Spiritual Reflective"} as HyperframesTemplate]).map((template) => ({
                  value: template.id,
                  label: template.label,
                }))}
                onChange={(starterTemplate) => updateEditor({starterTemplate})}
              />
              <FieldSelect label="Captions" value={editor.captionStyle} options={catalogOptions(hyperframesCatalog, "Captions", ["caption-editorial-emphasis", "caption-pill-karaoke", "caption-highlight"])} onChange={(captionStyle) => updateEditor({captionStyle})} />
              <FieldSelect label="Texture" value={editor.textureEffect} options={catalogOptions(hyperframesCatalog, "Texture/effects", ["vignette", "grain-overlay", "shimmer-sweep"])} onChange={(textureEffect) => updateEditor({textureEffect})} />
              <FieldSelect label="Social callout" value={editor.ctaOverlay} options={catalogOptions(hyperframesCatalog, "Social overlays", ["yt-lower-third", "instagram-follow", "tiktok-follow"])} onChange={(ctaOverlay) => updateEditor({ctaOverlay})} />
              <FieldSelect
                label="Transition"
                value={editor.transitionFamily}
                options={[
                  {value: "dissolve", label: "Dissolve"},
                  {value: "push", label: "Push"},
                  {value: "zoom", label: "Zoom"},
                  {value: "whip-pan", label: "Whip Pan"},
                ]}
                onChange={(transitionFamily) => updateEditor({transitionFamily})}
              />
              <FieldSelect
                label="Intro"
                value={editor.introLayout}
                options={[
                  {value: "editorial-hook", label: "Editorial hook"},
                  {value: "lower-third-hook", label: "Lower-third hook"},
                  {value: "data-callout", label: "Data callout"},
                  {value: "headline-slam", label: "Headline slam"},
                ]}
                onChange={(introLayout) => updateEditor({introLayout})}
              />
              <label className="grid gap-1.5 text-[10px] font-bold uppercase tracking-wider text-zinc-500">
                Template name
                <input
                  value={label}
                  onChange={(event) => setLabel(event.target.value)}
                  className="h-10 rounded-xl border border-white/[0.08] bg-black/30 px-3 text-sm font-semibold normal-case tracking-normal text-white outline-none focus:border-cyan/35"
                />
              </label>
              <FieldSelect
                label="Baseline style"
                value={selectedTemplate}
                disabled={templateBusy}
                options={[{id: defaultTemplate, label: "Default style baseline", path: defaultTemplate}, ...templates.filter((template) => template.path !== defaultTemplate)].map((template) => ({
                  value: template.path,
                  label: template.label,
                }))}
                onChange={(path) => void loadTemplate(path)}
              />
              <button
                type="button"
                disabled={saveBusy || templateBusy}
                onClick={() => void loadTemplate(selectedTemplate, true)}
                className="h-10 w-full rounded-full border border-white/[0.1] text-xs font-bold uppercase tracking-wider text-zinc-300 disabled:opacity-45"
              >
                Reset to baseline
              </button>
            </div>
          </div>
        </div>
      ) : null}

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
      <main className="grid min-h-screen place-items-center bg-[#0a0b0e] px-5 text-center text-zinc-100">
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
      <main className="grid min-h-screen place-items-center bg-[#0a0b0e] text-cyan">
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
        <span className="absolute inset-0" style={{background: value}} />
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
