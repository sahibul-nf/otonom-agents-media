"use client";

import Link from "next/link";
import {useRouter} from "next/navigation";
import {ArrowLeft, BadgeCheck, ChevronDown, Loader2} from "lucide-react";
import {useEffect, useMemo, useState} from "react";
import type {ReactNode} from "react";
import {TemplatePreview} from "@/components/templates/TemplatePreview";
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

const fontOptions = ["Sora", "Inter", "Montserrat", "Poppins", "Roboto", "Arial", "system-ui"];

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
  const [fontAvailability, setFontAvailability] = useState<"checking" | "available" | "fallback">("checking");
  const [cleanSnapshot, setCleanSnapshot] = useState(() => snapshot(label, selectedTemplate, initialEditor));
  const currentSnapshot = snapshot(label, selectedTemplate, editor);
  const dirty = currentSnapshot !== cleanSnapshot;
  const selectedStarter = hyperframesTemplates.find((template) => template.id === editor.starterTemplate);
  const productionReadyCount = hyperframesCatalog?.items.filter((item) => item.status === "production-ready").length || 0;
  const selectedFontOption = useMemo(() => fontOptions.includes(editor.fontFamily) ? editor.fontFamily : "__custom", [editor.fontFamily]);

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [dirty]);

  useEffect(() => {
    let cancelled = false;
    async function checkFont() {
      setFontAvailability("checking");
      if (editor.fontFamily === "system-ui") {
        setFontAvailability("available");
        return;
      }
      try {
        await document.fonts.ready;
        if (!cancelled) setFontAvailability(document.fonts.check(`16px "${editor.fontFamily}"`) ? "available" : "fallback");
      } catch {
        if (!cancelled) setFontAvailability("fallback");
      }
    }
    void checkFont();
    return () => {
      cancelled = true;
    };
  }, [editor.fontFamily]);

  const updateEditor = (patch: Partial<EditorState>) => setEditor((current) => ({...current, ...patch}));

  function leaveBuilder() {
    if (dirty && !window.confirm("Discard your unsaved Brand Builder changes?")) return;
    router.push("/?section=brand");
  }

  async function loadTemplate(path: string, markClean = false) {
    setSelectedTemplate(path);
    setTemplateBusy(true);
    setSaveState("Loading template...");
    try {
      const loaded = await apiGet<StyleProfile>(`style?path=${encodeURIComponent(path)}`);
      const nextEditor = editorFromStyle(loaded, editor.starterTemplate);
      const template = templates.find((item) => item.path === path);
      const nextLabel = template?.label ? `${template.label} Copy` : "Custom Workspace Template";
      setEditor(nextEditor);
      setLabel(nextLabel);
      if (markClean) setCleanSnapshot(snapshot(nextLabel, path, nextEditor));
      setSaveState("Template loaded");
    } catch (error) {
      setSaveState(error instanceof Error ? error.message : "Template load failed");
    } finally {
      setTemplateBusy(false);
    }
  }

  useEffect(() => {
    if (!validInitialBase || validInitialBase === defaultTemplate) return;
    const frame = window.requestAnimationFrame(() => void loadTemplate(validInitialBase, true));
    return () => window.cancelAnimationFrame(frame);
    // The deep-link base is loaded once when the workspace mounts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function saveTemplate() {
    setSaveBusy(true);
    setSaveState("Saving...");
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
      setSaveState("Template saved");
      await onTemplateSaved();
    } catch (error) {
      setSaveState(error instanceof Error ? error.message : "Save failed");
    } finally {
      setSaveBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-canvas-deep text-zinc-100">
      <header className="sticky top-0 z-40 border-b border-white/[0.08] bg-canvas-deep/90 px-4 py-3 backdrop-blur-xl lg:px-8">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <button type="button" onClick={leaveBuilder} className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-white/[0.10] text-zinc-300 hover:border-cyan/[0.30] hover:text-white" aria-label="Back to Brand">
              <ArrowLeft className="h-4 w-4" />
            </button>
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-widest text-cyan">Brand workspace</p>
              <h1 className="truncate text-base font-semibold text-white">Brand Builder</h1>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <span className={`hidden text-xs font-semibold sm:inline ${dirty ? "text-warning" : "text-zinc-500"}`}>{dirty ? "Unsaved changes" : saveState}</span>
            <button type="button" disabled={!dirty || saveBusy || templateBusy} onClick={() => void saveTemplate()} className="inline-flex h-10 items-center gap-2 rounded-full bg-cyan px-5 text-xs font-bold uppercase tracking-wider text-ink disabled:cursor-not-allowed disabled:opacity-45">
              {saveBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {saveBusy ? "Saving..." : "Save template"}
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1440px] gap-6 px-4 py-6 lg:px-8 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="min-w-0 rounded-[32px] border border-white/[0.08] bg-surface/30 p-5 backdrop-blur-md sm:p-7">
          <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-cyan">Interactive sandbox</p>
              <h2 className="mt-1 text-2xl font-semibold tracking-tight text-white">Style customizer</h2>
              <p className="mt-1 text-sm text-zinc-500">Fine-tune one brand system without leaving the workspace.</p>
            </div>
            {templateBusy ? <Loader2 className="h-5 w-5 animate-spin text-cyan" /> : <BadgeCheck className="h-5 w-5 text-cyan" />}
          </div>

          <div className="grid gap-5">
            <ControlGroup title="Typography" summary={`${editor.fontFamily} · ${editor.fontSize}px`} open>
              <div className="grid gap-4 lg:grid-cols-2">
                <FontField value={editor.fontFamily} selectedOption={selectedFontOption} availability={fontAvailability} onChange={(fontFamily) => updateEditor({fontFamily})} />
                <NumberField label="Font size" value={editor.fontSize} min={28} max={76} onChange={(fontSize) => updateEditor({fontSize})} />
                <ColorField label="Text color" value={editor.textColor} onChange={(textColor) => updateEditor({textColor})} />
                <ColorField label="Highlight" value={editor.highlightColor} onChange={(highlightColor) => updateEditor({highlightColor})} />
                <ColorField label="Caption background" value={editor.backgroundColor} onChange={(backgroundColor) => updateEditor({backgroundColor})} />
                <NumberField label="Stroke width" value={editor.strokeWidth} min={0} max={16} onChange={(strokeWidth) => updateEditor({strokeWidth})} />
              </div>
              <div className="mt-4"><TextField label="Watermark text" value={editor.watermarkText} onChange={(watermarkText) => updateEditor({watermarkText})} /></div>
            </ControlGroup>

            <ControlGroup title="Components" summary={`${productionReadyCount} production-ready slots`}>
              <div className="grid gap-4 lg:grid-cols-2">
                <SelectField label="Starter template" value={editor.starterTemplate} options={(hyperframesTemplates.length ? hyperframesTemplates : [{id: "spiritual_reflective", label: "Spiritual Reflective"} as HyperframesTemplate]).map((template) => ({value: template.id, label: template.label}))} onChange={(starterTemplate) => updateEditor({starterTemplate})} />
                <SelectField label="Motion intensity" value={editor.motionIntensity} options={[{value: "calm", label: "Calm"}, {value: "balanced", label: "Balanced"}, {value: "energetic", label: "Energetic"}]} onChange={(motionIntensity) => updateEditor({motionIntensity})} />
                <SelectField label="Caption overlays" value={editor.captionStyle} options={catalogOptions(hyperframesCatalog, "Captions", ["caption-editorial-emphasis", "caption-pill-karaoke", "caption-highlight"])} onChange={(captionStyle) => updateEditor({captionStyle})} />
                <SelectField label="Texture overlays" value={editor.textureEffect} options={catalogOptions(hyperframesCatalog, "Texture/effects", ["vignette", "grain-overlay", "shimmer-sweep"])} onChange={(textureEffect) => updateEditor({textureEffect})} />
                <SelectField label="Social callouts" value={editor.ctaOverlay} options={catalogOptions(hyperframesCatalog, "Social overlays", ["yt-lower-third", "instagram-follow", "tiktok-follow"])} onChange={(ctaOverlay) => updateEditor({ctaOverlay})} />
                <SelectField label="Transitions" value={editor.transitionFamily} options={[{value: "dissolve", label: "Dissolve"}, {value: "push", label: "Push"}, {value: "zoom", label: "Zoom"}, {value: "whip-pan", label: "Whip Pan"}]} onChange={(transitionFamily) => updateEditor({transitionFamily})} />
                <SelectField label="Hooks & intro" value={editor.introLayout} options={[{value: "editorial-hook", label: "Editorial hook"}, {value: "lower-third-hook", label: "Lower-third hook"}, {value: "data-callout", label: "Data callout"}, {value: "headline-slam", label: "Headline slam"}]} onChange={(introLayout) => updateEditor({introLayout})} />
              </div>
            </ControlGroup>

            <ControlGroup title="Deploy" summary={dirty ? "Changes pending" : "Up to date"} open>
              <div className="grid gap-4 sm:grid-cols-2">
                <TextField label="Template label" value={label} onChange={setLabel} />
                <SelectField label="Baseline style file" value={selectedTemplate} disabled={templateBusy} options={[{id: defaultTemplate, label: "Default style baseline", path: defaultTemplate}, ...templates.filter((template) => template.path !== defaultTemplate)].map((template) => ({value: template.path, label: template.label}))} onChange={(path) => void loadTemplate(path)} />
              </div>
              <div className="mt-5 flex flex-wrap items-center gap-3">
                <button type="button" disabled={!dirty || saveBusy || templateBusy} onClick={() => void saveTemplate()} className="inline-flex h-11 items-center gap-2 rounded-full bg-cyan px-5 text-xs font-bold uppercase tracking-wider text-ink disabled:cursor-not-allowed disabled:opacity-45">
                  {saveBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  Save template
                </button>
                <button type="button" disabled={saveBusy || templateBusy} onClick={() => void loadTemplate(selectedTemplate, true)} className="h-11 rounded-full border border-white/[0.10] px-5 text-xs font-bold uppercase tracking-wider text-zinc-300 disabled:opacity-45">Reset base</button>
                <span className="text-xs text-zinc-500">{saveState}</span>
              </div>
            </ControlGroup>
          </div>
        </section>

        <aside className="min-w-0 xl:sticky xl:top-[88px] xl:self-start">
          <div className="rounded-[32px] border border-white/[0.08] bg-surface/30 p-5 backdrop-blur-md sm:p-6">
            <div className="mb-5 flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-white">Live preview</h2>
                <p className="mt-0.5 text-xs text-zinc-500">Live brand overlay · hover to play</p>
              </div>
              <span className="rounded-full border border-cyan/[0.18] bg-teal/[0.08] px-3 py-1 text-xs font-semibold text-cyan">9:16</span>
            </div>
            <div className="relative mx-auto aspect-[9/16] w-full max-w-[17.5rem] overflow-hidden rounded-[16px] border border-white/[0.08] bg-[#050507] shadow-inner">
              {selectedStarter ? <TemplatePreview template={selectedStarter} compact gridCard hideFooterLabel hoverToPlay flush /> : <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_20%,rgba(108,226,238,.18),transparent_34%),linear-gradient(180deg,#24262c,#0a0a0c_68%)]" />}
              <div className="pointer-events-none absolute inset-0 z-10 bg-gradient-to-b from-black/55 via-black/20 to-black/70" />
              <div className="pointer-events-none absolute inset-0 z-10 flex flex-col justify-between p-5">
                <div>
                  <p className="text-center text-2xl font-black leading-tight tracking-tight text-white drop-shadow-lg" style={{fontFamily: editor.fontFamily}}>Your strongest hook goes here</p>
                  <p className="mx-auto mt-2 max-w-[200px] text-center text-[10px] font-semibold leading-relaxed text-zinc-300">{selectedStarter?.best_for || "A reusable brand system for every channel."}</p>
                </div>
                <div className="grid gap-3">
                  <div className="mx-auto max-w-full rounded-xl px-4 py-2.5 text-center font-black leading-none shadow-lg" style={{background: editor.backgroundColor, color: editor.textColor, fontFamily: editor.fontFamily, fontSize: `${Math.min(editor.fontSize - 12, 36)}px`, WebkitTextStroke: `${editor.strokeWidth / 2.5}px #000`}}>
                    <span style={{color: editor.highlightColor}}>Sharp</span> key moment
                  </div>
                  <div className="flex items-center justify-between text-[10px] font-semibold text-zinc-400"><span>{editor.watermarkText}</span><span style={{color: editor.highlightColor}}>{selectedStarter?.label || "Brand style"}</span></div>
                </div>
              </div>
            </div>
            <div className="mt-5 grid gap-2 rounded-[22px] border border-white/[0.06] bg-black/20 p-3.5 text-xs">
              <PreviewSpec label="Font" value={editor.fontFamily} />
              <PreviewSpec label="Caption" value={`${editor.fontSize}px / stroke ${editor.strokeWidth}px`} />
              <PreviewSpec label="Watermark" value={editor.watermarkText || "None"} />
            </div>
          </div>
          <Link href="/?section=brand" onClick={(event) => { if (dirty && !window.confirm("Discard your unsaved Brand Builder changes?")) event.preventDefault(); }} className="mt-3 block text-center text-xs font-semibold text-zinc-500 hover:text-white">Return to Brand library</Link>
        </aside>
      </div>
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

  if (error) return <main className="grid min-h-screen place-items-center bg-canvas-deep px-5 text-center text-zinc-100"><div><p className="text-sm font-semibold text-danger">{error}</p><button type="button" onClick={() => void loadData()} className="mt-5 rounded-full bg-cyan px-5 py-2.5 text-sm font-semibold text-ink">Retry</button></div></main>;
  if (!data) return <main className="grid min-h-screen place-items-center bg-canvas-deep text-cyan"><Loader2 className="h-6 w-6 animate-spin" /></main>;

  return <BrandBuilderWorkspace {...data} initialStarter={starter || storageStarter} initialPreset={preset} initialBaseTemplate={baseTemplate} onTemplateSaved={loadData} />;
}

function ControlGroup({title, summary, open = false, children}: {title: string; summary: string; open?: boolean; children: ReactNode}) {
  return <details open={open} className="group rounded-[26px] border border-white/[0.06] bg-black/15 p-5"><summary className="flex cursor-pointer list-none items-center justify-between gap-3"><span><span className="block font-semibold text-white">{title}</span><span className="mt-1 block text-xs text-zinc-500">{summary}</span></span><ChevronDown className="h-4 w-4 text-zinc-500 transition-transform group-open:rotate-180" /></summary><div className="mt-5 border-t border-white/[0.05] pt-5">{children}</div></details>;
}

function catalogOptions(catalog: HyperframesCatalog | null, category: string, fallback: string[]) {
  const items = (catalog?.items || []).filter((item) => item.category === category && item.status !== "experimental");
  return items.length ? items.map((item) => ({value: item.id, label: `${item.label} · ${item.status}`})) : fallback.map((value) => ({value, label: value}));
}

function FieldShell({label, children}: {label: string; children: ReactNode}) {
  return <label className="grid gap-2 text-xs font-bold uppercase tracking-wider text-zinc-500">{label}{children}</label>;
}

function TextField({label, value, onChange}: {label: string; value: string; onChange: (value: string) => void}) {
  return <FieldShell label={label}><input value={value} onChange={(event) => onChange(event.target.value)} className="h-11 rounded-2xl border border-white/[0.08] bg-black/20 px-3 text-sm font-semibold normal-case tracking-normal text-white outline-none focus:border-cyan/[0.35]" /></FieldShell>;
}

function NumberField({label, value, min, max, onChange}: {label: string; value: number; min: number; max: number; onChange: (value: number) => void}) {
  return <FieldShell label={label}><input type="number" min={min} max={max} value={value} onChange={(event) => onChange(Number(event.target.value))} className="h-11 rounded-2xl border border-white/[0.08] bg-black/20 px-3 text-sm font-semibold normal-case tracking-normal text-white outline-none focus:border-cyan/[0.35]" /></FieldShell>;
}

function ColorField({label, value, onChange}: {label: string; value: string; onChange: (value: string) => void}) {
  return <FieldShell label={label}><span className="flex h-11 items-center gap-2.5 rounded-2xl border border-white/[0.08] bg-black/20 px-3 focus-within:border-cyan/[0.35]"><input type="color" value={value} onChange={(event) => onChange(event.target.value)} className="h-6 w-8 cursor-pointer rounded border-0 bg-transparent p-0" /><input value={value} onChange={(event) => onChange(event.target.value)} className="min-w-0 flex-1 bg-transparent text-sm font-semibold normal-case tracking-normal text-white outline-none" /></span></FieldShell>;
}

function SelectField({label, value, options, disabled = false, onChange}: {label: string; value: string; options: {value: string; label: string}[]; disabled?: boolean; onChange: (value: string) => void}) {
  return <FieldShell label={label}><span className="relative flex items-center"><select value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)} className="h-11 w-full appearance-none rounded-2xl border border-white/[0.08] bg-black/20 pl-3 pr-10 text-sm font-semibold normal-case tracking-normal text-white outline-none focus:border-cyan/[0.35] disabled:opacity-50">{options.map((option) => <option key={option.value} value={option.value} className="bg-[#17171a] text-white">{option.label}</option>)}</select><ChevronDown className="pointer-events-none absolute right-3.5 h-4 w-4 text-zinc-500" /></span></FieldShell>;
}

function FontField({value, selectedOption, availability, onChange}: {value: string; selectedOption: string; availability: "checking" | "available" | "fallback"; onChange: (value: string) => void}) {
  return <div className="grid gap-2"><SelectField label="Font family" value={selectedOption} options={[...fontOptions.map((font) => ({value: font, label: font})), {value: "__custom", label: "Custom font"}]} onChange={(next) => { if (next !== "__custom") onChange(next); }} />{selectedOption === "__custom" ? <input value={value} onChange={(event) => onChange(event.target.value)} placeholder="Exact installed font name" className="h-11 rounded-2xl border border-white/[0.08] bg-black/20 px-3 text-sm font-semibold text-white outline-none focus:border-cyan/[0.35]" /> : null}<span className={`text-[10px] font-bold uppercase ${availability === "available" ? "text-cyan" : availability === "fallback" ? "text-warning" : "text-zinc-500"}`}>{availability === "checking" ? "Checking..." : availability === "available" ? "Fully loaded" : "Fallback active"}</span></div>;
}

function PreviewSpec({label, value}: {label: string; value: string}) {
  return <div className="flex min-w-0 items-center justify-between gap-3 rounded-xl bg-surface/50 px-3 py-2"><span className="text-zinc-500">{label}</span><span className="min-w-0 truncate font-semibold text-zinc-200">{value}</span></div>;
}
