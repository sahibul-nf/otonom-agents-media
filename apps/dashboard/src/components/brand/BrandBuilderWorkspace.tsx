"use client";

import Link from "next/link";
import {useRouter} from "next/navigation";
import {ArrowLeft, ChevronDown, Loader2} from "lucide-react";
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
type DockTab = "look" | "type" | "motion" | "recipe";

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
  const [activePresetId, setActivePresetId] = useState(initialPreset || "");
  const starterOptions = (hyperframesTemplates.length
    ? hyperframesTemplates
    : [{id: "spiritual_reflective", label: "Spiritual Reflective"} as HyperframesTemplate]
  ).map((template) => ({value: template.id, label: template.label}));
  const captionOptions = catalogOptions(hyperframesCatalog, "Captions", ["caption-editorial-emphasis", "caption-pill-karaoke", "caption-highlight"]);
  const textureOptions = catalogOptions(hyperframesCatalog, "Texture/effects", ["vignette", "grain-overlay", "shimmer-sweep"]);
  const socialOptions = catalogOptions(hyperframesCatalog, "Social overlays", ["yt-lower-third", "instagram-follow", "tiktok-follow"]);
  const baselineOptions = [
    {id: defaultTemplate, label: "Default style baseline", path: defaultTemplate},
    ...templates.filter((template) => template.path !== defaultTemplate),
  ].map((template) => ({value: template.path, label: template.label}));
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
            disabled={!dirty || saveBusy || templateBusy}
            onClick={() => void saveTemplate()}
            className="inline-flex h-9 items-center gap-2 rounded-full bg-cyan px-4 text-xs font-bold uppercase tracking-wider text-ink disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saveBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            Save
          </button>
        </div>
      </header>

      {/* Two-pane: tools | preview (stacked on small screens) */}
      <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(300px,400px)_minmax(0,1fr)]">
        <aside className="order-2 flex min-h-0 flex-col border-t border-white/[0.07] bg-[#101114] lg:order-1 lg:border-r lg:border-t-0">
          <div className="flex shrink-0 gap-0.5 overflow-x-auto border-b border-white/[0.06] px-2 pt-2.5 pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:px-3">
            {(
              [
                {id: "look" as const, label: "Look"},
                {id: "type" as const, label: "Type"},
                {id: "motion" as const, label: "Motion"},
                {id: "recipe" as const, label: "Recipe"},
              ] as const
            ).map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setDockTab(tab.id)}
                className={`shrink-0 rounded-full px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider transition ${
                  dockTab === tab.id ? "bg-white/[0.1] text-white" : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 py-3 sm:px-4 sm:py-4">
            {dockTab === "look" ? (
              <div className="space-y-4">
                <p className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">Presets</p>
                <div className="grid grid-cols-2 gap-2">
                  {brandPresets.map((preset) => {
                    const active = activePresetId === preset.id;
                    return (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => applyPreset(preset.id)}
                        className={`rounded-2xl border px-3 py-2.5 text-left transition ${
                          active ? "border-cyan/50 bg-cyan/[0.12]" : "border-white/[0.08] bg-white/[0.03] hover:border-white/[0.16]"
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

                <p className="pt-1 text-[10px] font-bold uppercase tracking-widest text-zinc-500">Colors</p>
                <div className="flex flex-wrap items-center gap-4">
                  <Swatch label="Highlight" value={editor.highlightColor} onChange={(highlightColor) => updateEditor({highlightColor})} />
                  <Swatch label="Text" value={editor.textColor} onChange={(textColor) => updateEditor({textColor})} />
                  <Swatch label="Plate" value={editor.backgroundColor} onChange={(backgroundColor) => updateEditor({backgroundColor})} />
                </div>
              </div>
            ) : null}

            {dockTab === "type" ? (
              <div className="space-y-4">
                <p className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">Font</p>
                <div className="flex flex-wrap gap-2">
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

            {dockTab === "motion" ? (
              <div className="space-y-4">
                <ChipGroup
                  label="Caption pace"
                  value={editor.motionIntensity}
                  options={[
                    {value: "calm", label: "Calm"},
                    {value: "balanced", label: "Balanced"},
                    {value: "energetic", label: "Energetic"},
                  ]}
                  onChange={(motionIntensity) => updateEditor({motionIntensity})}
                />
                <p className="text-[11px] leading-relaxed text-zinc-500">Highlight word pace in the preview follows this setting.</p>
              </div>
            ) : null}

            {dockTab === "recipe" ? (
              <div className="space-y-5">
                <ChipGroup
                  label="Starter"
                  value={editor.starterTemplate}
                  options={starterOptions}
                  onChange={(starterTemplate) => updateEditor({starterTemplate})}
                  scrollable
                />
                <ChipGroup label="Captions" value={editor.captionStyle} options={captionOptions} onChange={(captionStyle) => updateEditor({captionStyle})} />
                <ChipGroup label="Texture" value={editor.textureEffect} options={textureOptions} onChange={(textureEffect) => updateEditor({textureEffect})} />
                <ChipGroup label="Social callout" value={editor.ctaOverlay} options={socialOptions} onChange={(ctaOverlay) => updateEditor({ctaOverlay})} />
                <ChipGroup
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
                <ChipGroup
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

                <div className="border-t border-white/[0.06] pt-4">
                  <p className="mb-3 text-[10px] font-bold uppercase tracking-widest text-zinc-500">Save as</p>
                  <label className="mb-3 grid gap-1.5 text-[10px] font-bold uppercase tracking-wider text-zinc-500">
                    Template name
                    <input
                      value={label}
                      onChange={(event) => setLabel(event.target.value)}
                      className="h-10 rounded-xl border border-white/[0.08] bg-white/[0.03] px-3 text-sm font-semibold normal-case tracking-normal text-white outline-none focus:border-cyan/35"
                    />
                  </label>
                  <FieldSelect
                    label="Baseline style"
                    value={selectedTemplate}
                    disabled={templateBusy}
                    options={baselineOptions}
                    onChange={(path) => void loadTemplate(path)}
                  />
                  <button
                    type="button"
                    disabled={saveBusy || templateBusy}
                    onClick={() => void loadTemplate(selectedTemplate, true)}
                    className="mt-3 h-10 w-full rounded-full border border-white/[0.1] text-xs font-bold uppercase tracking-wider text-zinc-300 disabled:opacity-45"
                  >
                    Reset to baseline
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </aside>

        <section
          className="order-1 relative flex min-h-[min(52dvh,28rem)] items-center justify-center overflow-hidden px-4 py-5 lg:order-2 lg:min-h-0 lg:px-8 lg:py-8"
          style={{
            background: `
              radial-gradient(ellipse 55% 50% at 50% 42%, ${editor.highlightColor}16, transparent 62%),
              radial-gradient(circle at 80% 90%, rgba(98,238,248,.04), transparent 35%),
              #0a0b0e
            `,
          }}
        >
          <BrandStudioPreview look={editor} />
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

function ChipGroup({
  label,
  value,
  options,
  onChange,
  scrollable = false,
}: {
  label: string;
  value: string;
  options: {value: string; label: string}[];
  onChange: (value: string) => void;
  scrollable?: boolean;
}) {
  return (
    <div>
      <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500">{label}</p>
      <div
        className={
          scrollable
            ? "flex max-h-36 flex-col gap-1.5 overflow-y-auto overscroll-contain pr-1"
            : "flex flex-wrap gap-1.5"
        }
      >
        {options.map((option) => {
          const active = value === option.value;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => onChange(option.value)}
              className={`rounded-full border px-3 py-1.5 text-left text-xs font-semibold transition ${
                scrollable ? "w-full" : ""
              } ${
                active
                  ? "border-cyan/45 bg-cyan/[0.12] text-white"
                  : "border-white/[0.08] text-zinc-400 hover:border-white/[0.16] hover:text-zinc-200"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
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
