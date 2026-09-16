"use client";

import Link from "next/link";
import {useRouter} from "next/navigation";
import {ArrowLeft, ChevronDown, HelpCircle, Loader2} from "lucide-react";
import {useEffect, useState} from "react";
import {BrandStudioPreview, SAMPLE_PHRASE_PRESETS} from "@/components/brand/BrandStudioPreview";
import type {RecipePreviewFormat} from "@/components/brand/useRecipePreviewVideo";
import {
  apiGet,
  apiPost,
  requestBrandStudioPreviewRender,
  type BrandTemplate,
  type HyperframesCatalog,
  type HyperframesTemplate,
  type StyleProfile,
} from "@/lib/media-api";

const DEFAULT_TEMPLATE = "profiles/default_workspace_style.json";
const STARTER_STORAGE_KEY = "otonom.brandBuilderStarterTemplate";

export const BRAND_PALETTE_SWATCHES = [
  "#ff2a85",
  "#00ff36",
  "#a7f36b",
  "#d8b45f",
  "#67e8f9",
  "#ffffff",
  "#94a3b8",
] as const;

export const brandPresets = [
  {id: "editorial", category: "Devotional", label: "Editorial Calm", note: "Reflective, education, and story-led clips.", starterTemplate: "spiritual_reflective", fontFamily: "Sora", fontSize: 54, highlightColor: "#d8b45f", backgroundColor: "#111214", strokeWidth: 6, captionStyle: "caption-editorial-emphasis", introLayout: "editorial-hook", ctaOverlay: "yt-lower-third", textureEffect: "grain-overlay", transitionFamily: "dissolve", motionIntensity: "calm"},
  {id: "social", category: "High-Energy", label: "Social Punch", note: "Creator clips, podcast highlights, and short hooks.", starterTemplate: "play_mode_social", fontFamily: "Poppins", fontSize: 56, highlightColor: "#67e8f9", backgroundColor: "#05070a", strokeWidth: 8, captionStyle: "caption-pill-karaoke", introLayout: "lower-third-hook", ctaOverlay: "instagram-follow", textureEffect: "none", transitionFamily: "push", motionIntensity: "energetic"},
  {id: "analyst", category: "Edutainment", label: "Analyst Clean", note: "Data, market, business, and technical explainers.", starterTemplate: "spiritual_reflective", fontFamily: "Inter", fontSize: 48, highlightColor: "#74f2ce", backgroundColor: "#07100f", strokeWidth: 4, captionStyle: "caption-clip-wipe", introLayout: "data-callout", ctaOverlay: "yt-lower-third", textureEffect: "vignette", transitionFamily: "zoom", motionIntensity: "balanced"},
  {id: "eva_cyber", category: "High-Energy", label: "Eva Neon Cyber", note: "Neon overlays, glowing captions, and futuristic accents.", starterTemplate: "eva_neon_cyber", fontFamily: "Poppins", fontSize: 54, highlightColor: "#ff2a85", backgroundColor: "#030305", strokeWidth: 8, captionStyle: "caption-neon-glow", introLayout: "headline-slam", ctaOverlay: "instagram-follow", textureEffect: "vignette", transitionFamily: "whip-pan", motionIntensity: "energetic"},
  {id: "volt_kinetic", category: "High-Energy", label: "Volt Lime Kinetic", note: "Bold bounce, electric lime highlights, and title drops.", starterTemplate: "volt_lime_kinetic", fontFamily: "Montserrat", fontSize: 58, highlightColor: "#a7f36b", backgroundColor: "#040507", strokeWidth: 10, captionStyle: "caption-kinetic-slam", introLayout: "headline-slam", ctaOverlay: "tiktok-follow", textureEffect: "none", transitionFamily: "zoom", motionIntensity: "energetic"},
  {id: "ember_sunset", category: "Devotional", label: "Ember Sunset", note: "Sunset gradient text with soft warm ambient glows.", starterTemplate: "ember_sunset_gradient", fontFamily: "Sora", fontSize: 52, highlightColor: "#ff5e36", backgroundColor: "#120a06", strokeWidth: 6, captionStyle: "caption-gradient-fill", introLayout: "editorial-hook", ctaOverlay: "yt-lower-third", textureEffect: "vignette", transitionFamily: "dissolve", motionIntensity: "calm"},
  {id: "align_minimal", category: "Minimal", label: "Align Minimal Box", note: "Monochrome active-word boxes and clean snap reveals.", starterTemplate: "align_minimal_box", fontFamily: "Inter", fontSize: 48, highlightColor: "#f8fafc", backgroundColor: "#09090b", strokeWidth: 4, captionStyle: "caption-clip-wipe", introLayout: "lower-third-hook", ctaOverlay: "x-post", textureEffect: "vignette", transitionFamily: "dissolve", motionIntensity: "balanced"},
] as const;

type CaptionPosition = "bottom" | "center" | "top";

type EditorState = {
  fontFamily: string;
  fontSize: number;
  textColor: string;
  highlightColor: string;
  backgroundColor: string;
  strokeWidth: number;
  watermarkText: string;
  position: CaptionPosition;
  uppercase: boolean;
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
  initialDuplicate?: boolean;
  onTemplateSaved: () => void | Promise<void>;
};

const fontOptions = ["Sora", "Inter", "Montserrat", "Poppins", "Roboto", "Arial", "system-ui"] as const;
type DockTab = "presets" | "identity" | "captions" | "finishing";

const TEXTURE_OPTIONS = [
  {value: "none", label: "None"},
  {value: "vignette", label: "Vignette"},
  {value: "grain-overlay", label: "Film grain"},
] as const;

const SOCIAL_OPTIONS = [
  {value: "none", label: "None"},
  {value: "yt-lower-third", label: "YouTube Subscribe"},
  {value: "instagram-follow", label: "Instagram Follow"},
  {value: "tiktok-follow", label: "TikTok Follow"},
  {value: "x-post", label: "X Follow"},
] as const;

function normalizeTextureEffect(value: unknown): string {
  const id = String(value || "none").trim().toLowerCase();
  if (id === "shimmer-sweep" || id === "shimmer") return "none";
  if (id === "vignette" || id === "grain-overlay" || id === "none") return id;
  return "none";
}

function normalizeCtaOverlay(value: unknown): string {
  const id = String(value || "none").trim();
  if (!id || id === "none") return "none";
  return SOCIAL_OPTIONS.some((option) => option.value === id) ? id : "none";
}

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
  const brandSystem = source?.brand_system || {};
  const watermark = String(brand.watermark_text || "").trim();
  return {
    fontFamily: String(caption.font_family || "Sora"),
    fontSize: Number(caption.font_size || 45),
    textColor: hexFromColor(caption.text_color, "#ffffff"),
    highlightColor: hexFromColor(caption.highlight_word_color, "#00ff36"),
    backgroundColor: hexFromColor(caption.background_color, "#000000"),
    strokeWidth: Number(caption.stroke_width || 10),
    watermarkText: watermark && !/nourbit|nouraniyyah/i.test(watermark) ? watermark : "Brand Clips",
    position: caption.position === "top" || caption.position === "center" ? caption.position : "bottom",
    uppercase: Boolean(caption.uppercase),
    starterTemplate: String(brandSystem.starter_template || starterTemplate || "spiritual_reflective"),
    captionStyle: String(brandSystem.caption_style || "caption-editorial-emphasis"),
    introLayout: String(brandSystem.intro_layout || "editorial-hook"),
    ctaOverlay: normalizeCtaOverlay(brandSystem.cta_overlay || "none"),
    textureEffect: normalizeTextureEffect(brandSystem.texture_effect || "none"),
    transitionFamily: String(brandSystem.transition_family || "dissolve"),
    motionIntensity: String(brandSystem.motion_intensity || "balanced"),
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
        label: item.status === "production-ready" || item.status === "beta" ? item.label : `${item.label} (${item.status})`,
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
  initialDuplicate = false,
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
  const [dockTab, setDockTab] = useState<DockTab>("presets");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [activePresetId, setActivePresetId] = useState(initialPreset || "");
  const [editingPath, setEditingPath] = useState<string | undefined>(() =>
    !initialDuplicate && validInitialBase && validInitialBase !== defaultTemplate && /custom_/i.test(validInitialBase)
      ? validInitialBase
      : undefined,
  );
  const [savedHandoff, setSavedHandoff] = useState<{path: string; brandId: string} | null>(null);
  const [samplePhrase, setSamplePhrase] = useState(SAMPLE_PHRASE_PRESETS[0].text);
  const [bakedPreviewUrl, setBakedPreviewUrl] = useState<string | null>(null);
  const [bakeBusy, setBakeBusy] = useState(false);
  const [bakeError, setBakeError] = useState<string | null>(null);
  const starterTemplates = hyperframesTemplates.length
    ? hyperframesTemplates
    : ([{id: "spiritual_reflective", label: "Spiritual Reflective", best_for: "Reflective clips"}] as HyperframesTemplate[]);
  const captionOptions = catalogOptions(hyperframesCatalog, "Captions", ["caption-editorial-emphasis", "caption-pill-karaoke", "caption-highlight"]);
  const textureOptions = [...TEXTURE_OPTIONS];
  const socialOptions = [...SOCIAL_OPTIONS];
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
    {id: defaultTemplate, label: "Platform default", path: defaultTemplate},
    ...templates.filter((template) => template.path !== defaultTemplate),
  ].map((template) => ({value: template.path, label: template.label}));
  const starterSelectOptions = starterTemplates.map((template) => ({value: template.id, label: template.label}));
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

  useEffect(() => {
    if (!dirty) return;
    setBakedPreviewUrl(null);
    setBakeError(null);
  }, [dirty]);

  async function renderFiveSecondLook(format: RecipePreviewFormat) {
    setBakeBusy(true);
    setBakeError(null);
    try {
      const result = await requestBrandStudioPreviewRender({
        starter_template: editor.starterTemplate,
        hyperframes_format: format,
        sample_phrase: samplePhrase,
        style: {
          caption: {
            font_family: editor.fontFamily,
            font_size: editor.fontSize,
            text_color: editor.textColor,
            highlight_word_color: editor.highlightColor,
            background_color: editor.backgroundColor,
            stroke_width: editor.strokeWidth,
            position: editor.position,
            uppercase: editor.uppercase,
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
      });
      if (result.preview_url) {
        setBakedPreviewUrl(result.preview_url);
      } else {
        setBakeError("Preview finished without a playable video.");
      }
    } catch (error) {
      setBakeError(error instanceof Error ? error.message : "Couldn’t render preview");
    } finally {
      setBakeBusy(false);
    }
  }

  const updateEditor = (patch: Partial<EditorState>) => {
    setActivePresetId("");
    setSavedHandoff(null);
    setEditor((current) => ({...current, ...patch}));
  };

  function applyPreset(presetId: string) {
    setActivePresetId(presetId);
    setSavedHandoff(null);
    setEditor((current) => applyPresetToEditor(current, presetId));
  }

  function leaveBuilder() {
    if (dirty && !window.confirm("Discard your unsaved Brand Builder changes?")) return;
    router.push("/?section=brand");
  }

  async function loadTemplate(path: string, markClean = false, asDuplicate = false) {
    setSelectedTemplate(path);
    setTemplateBusy(true);
    setSaveState("Loading…");
    try {
      const loaded = await apiGet<StyleProfile>(`style?path=${encodeURIComponent(path)}`);
      const nextEditor = editorFromStyle(loaded, editor.starterTemplate);
      const template = templates.find((item) => item.path === path);
      const isCustom = /custom_/i.test(path);
      const nextLabel =
        loaded.label ||
        template?.label ||
        (isCustom ? "Custom Workspace Template" : "Custom Workspace Template");
      const duplicateLabel = copyLabelName(nextLabel);
      const editLabel = asDuplicate || !isCustom ? duplicateLabel : nextLabel;
      setEditor(nextEditor);
      setLabel(editLabel);
      setActivePresetId("");
      setEditingPath(asDuplicate || !isCustom ? undefined : path);
      setSavedHandoff(null);
      if (markClean) setCleanSnapshot(snapshot(editLabel, path, nextEditor));
      setSaveState(asDuplicate ? "Ready to save copy" : "Loaded");
    } catch (error) {
      setSaveState(error instanceof Error ? error.message : "Load failed");
    } finally {
      setTemplateBusy(false);
    }
  }

  useEffect(() => {
    if (!validInitialBase || validInitialBase === defaultTemplate) return;
    const frame = window.requestAnimationFrame(() => void loadTemplate(validInitialBase, !initialDuplicate, initialDuplicate));
    return () => window.cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function copyLabelName(baseLabel: string) {
    const trimmed = baseLabel.trim() || "Custom Workspace Template";
    const match = trimmed.match(/^(.*?)(?:\s+Copy(?:\s+(\d+))?)?$/i);
    const root = (match?.[1] || trimmed).trim();
    const existing = templates
      .filter((item) => /custom_/i.test(item.path))
      .map((item) => item.label.toLowerCase());
    let candidate = `${root} Copy`;
    let counter = 2;
    while (existing.includes(candidate.toLowerCase())) {
      candidate = `${root} Copy ${counter}`;
      counter += 1;
    }
    return candidate;
  }

  async function saveTemplate(asCopy = false) {
    setSaveBusy(true);
    setSaveState("Saving…");
    const nextLabel = asCopy ? copyLabelName(label) : label;
    const targetPath = asCopy ? undefined : editingPath;
    try {
      const saved = await apiPost<{id: string; label: string; path: string}>("brand-system-templates", {
        label: nextLabel,
        style: {
          caption: {
            font_family: editor.fontFamily,
            font_size: editor.fontSize,
            text_color: editor.textColor,
            highlight_word_color: editor.highlightColor,
            background_color: editor.backgroundColor,
            stroke_width: editor.strokeWidth,
            position: editor.position,
            uppercase: editor.uppercase,
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
        path: targetPath || undefined,
      });
      const nextPath = saved.path;
      const brandId = `brand:${nextPath.split("/").pop()?.replace(/\.json$/, "") || saved.id}`;
      setLabel(nextLabel);
      setEditingPath(nextPath);
      setSavedHandoff({path: nextPath, brandId});
      setCleanSnapshot(snapshot(nextLabel, selectedTemplate, editor));
      setSaveState(asCopy ? "Saved as copy" : "Saved");
      await onTemplateSaved();
    } catch (error) {
      setSaveState(error instanceof Error ? error.message : "Save failed");
    } finally {
      setSaveBusy(false);
    }
  }

  function useInCreate() {
    if (!savedHandoff) return;
    window.localStorage.setItem(
      "otonom.generateBrandHandoff",
      JSON.stringify({
        brandTemplate: savedHandoff.path,
        hyperframesTemplate: savedHandoff.brandId,
        brandSystemTemplateId: savedHandoff.brandId,
        renderer: "hyperframes",
      }),
    );
    router.push("/?section=generate");
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
          <span
            className={`hidden text-xs font-medium sm:inline ${dirty ? "text-warning" : "text-zinc-500"}`}
            title={dirty ? "Save to keep these edits. Preview will update after you render again." : undefined}
          >
            {dirty ? "Unsaved changes" : editingPath ? "Saved" : saveState}
          </span>
          {editingPath ? (
            <button
              type="button"
              disabled={!dirty || saveBusy || templateBusy}
              onClick={() => void saveTemplate(true)}
              className="hidden h-9 items-center rounded-full border border-white/[0.12] px-3.5 text-[11px] font-semibold text-zinc-200 hover:border-cyan/30 hover:text-white disabled:cursor-not-allowed disabled:opacity-40 sm:inline-flex"
            >
              Save as copy
            </button>
          ) : null}
          {savedHandoff && !dirty ? (
            <button
              type="button"
              onClick={useInCreate}
              className="hidden h-9 items-center rounded-full border border-cyan/35 px-3.5 text-[11px] font-semibold text-cyan sm:inline-flex"
            >
              Use in Create
            </button>
          ) : null}
          <button
            type="button"
            disabled={!dirty || saveBusy || templateBusy}
            onClick={() => void saveTemplate(false)}
            title={!dirty ? "No changes to save" : editingPath ? "Update brand template" : "Save brand template"}
            className="inline-flex h-9 items-center gap-2 rounded-full bg-cyan px-4 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saveBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            {saveBusy ? "Saving…" : editingPath ? "Update" : "Save"}
          </button>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(300px,400px)_minmax(0,1fr)]">
        <aside className="order-2 flex min-h-0 flex-col border-t border-white/[0.08] bg-surface/40 lg:order-1 lg:border-r lg:border-t-0">
          <div className="flex shrink-0 gap-0.5 overflow-x-auto border-b border-white/[0.08] px-2 pt-2.5 pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:px-3">
            {(
              [
                {id: "presets" as const, label: "Presets"},
                {id: "identity" as const, label: "Identity"},
                {id: "captions" as const, label: "Captions"},
                {id: "finishing" as const, label: "Finishing"},
              ] as const
            ).map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setDockTab(tab.id)}
                className={`shrink-0 rounded-full px-3.5 py-2 text-xs font-semibold tracking-wide transition ${
                  dockTab === tab.id ? "bg-white/[0.1] text-white" : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 py-3 sm:px-4 sm:py-4">
              {dockTab === "presets" ? (
                <div className="space-y-4">
                  <p className="text-xs leading-relaxed text-zinc-400">
                    Pick a starting look, then refine colors, captions, and finishing.
                  </p>
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
                          <span className="mb-1.5 flex items-center justify-between gap-2">
                            <span className="flex gap-1" aria-hidden>
                              <span className="h-3 w-3 rounded-full" style={{background: preset.highlightColor}} />
                              <span className="h-3 w-3 rounded-full border border-white/20" style={{background: preset.backgroundColor}} />
                            </span>
                            <span className="rounded-full border border-white/[0.08] px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-zinc-500">
                              {preset.category}
                            </span>
                          </span>
                          <span className="block truncate text-[11px] font-semibold text-zinc-200">{preset.label}</span>
                          <span className="mt-1 block truncate text-[10px] text-zinc-500">{preset.fontFamily} · {preset.fontSize}px</span>
                        </button>
                      );
                    })}
                  </div>
                  <InspectorSelect
                    label="Template"
                    tooltip="The visual style behind this look — motion, layout, and sample footage."
                    value={editor.starterTemplate}
                    options={starterSelectOptions}
                    onChange={(starterTemplate) => updateEditor({starterTemplate})}
                  />
                  {selectedStarter ? <StarterRecipeReference template={selectedStarter} /> : null}
                  <div className="border-t border-white/[0.06] pt-4">
                    <button
                      type="button"
                      disabled={saveBusy || templateBusy}
                      onClick={() => void loadTemplate(selectedTemplate, true)}
                      className="h-9 w-full rounded-full text-[11px] font-semibold text-zinc-500 transition hover:text-zinc-300 disabled:opacity-45"
                    >
                      Reset
                    </button>
                    <details
                      open={advancedOpen}
                      onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}
                      className="mt-2"
                    >
                      <summary className="cursor-pointer list-none text-[11px] font-semibold text-zinc-500 hover:text-zinc-300">
                        More options
                      </summary>
                      <div className="mt-3">
                        <InspectorSelect
                          label="Start from"
                          value={selectedTemplate}
                          disabled={templateBusy}
                          options={baselineOptions}
                          onChange={(path) => void loadTemplate(path)}
                        />
                      </div>
                    </details>
                  </div>
                </div>
              ) : null}

              {dockTab === "identity" ? (
                <div className="space-y-5">
                  <p className="text-xs leading-relaxed text-zinc-400">
                    Colors, type, and watermark update in the preview as you edit.
                  </p>
                  <div>
                    <SectionLabel label="Colors" />
                    <div className="space-y-4">
                      <Swatch label="Highlight" value={editor.highlightColor} onChange={(highlightColor) => updateEditor({highlightColor})} />
                      <Swatch label="Text" value={editor.textColor} onChange={(textColor) => updateEditor({textColor})} />
                      <Swatch label="Plate" value={editor.backgroundColor} onChange={(backgroundColor) => updateEditor({backgroundColor})} />
                    </div>
                  </div>
                  <div>
                    <SectionLabel label="Type" />
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
                      <span className="mb-1.5 flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-zinc-400">
                        <span className="inline-flex items-center gap-1.5">
                          Size
                          <BuilderTooltip text="Caption size on published clips. 45px reads well on Shorts and Reels." />
                        </span>
                        <span className="tabular-nums text-zinc-200">{editor.fontSize}px</span>
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
                      <span className="mb-1.5 flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-zinc-400">
                        <span className="inline-flex items-center gap-1.5">
                          Stroke
                          <BuilderTooltip text="Outline around letters so captions stay readable on busy footage." />
                        </span>
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
                    <SectionLabel
                      label="Watermark"
                      tooltip="Shown in the corner of every clip — usually your brand or channel name."
                    />
                    <input
                      value={editor.watermarkText}
                      onChange={(event) => updateEditor({watermarkText: event.target.value})}
                      placeholder="Brand name"
                      className="h-10 w-full rounded-xl border border-white/[0.08] bg-black/20 px-3 text-sm text-white outline-none placeholder:text-zinc-600 focus:border-cyan/35"
                    />
                  </div>
                </div>
              ) : null}

              {dockTab === "captions" ? (
                <div className="space-y-5">
                  <p className="text-xs leading-relaxed text-zinc-400">
                    Captions stay on one line. Style, position, and pacing update in the preview.
                  </p>
                  <InspectorSelect
                    label="Style"
                    tooltip="How captions look — pill, editorial, neon, and more."
                    value={editor.captionStyle}
                    options={captionOptions}
                    onChange={(captionStyle) => updateEditor({captionStyle})}
                  />
                  <div>
                    <SectionLabel label="Position" />
                    <div className="flex rounded-full border border-white/[0.08] bg-black/20 p-0.5">
                      {(
                        [
                          {value: "bottom" as const, label: "Bottom"},
                          {value: "center" as const, label: "Center"},
                          {value: "top" as const, label: "Top"},
                        ]
                      ).map((option) => (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => updateEditor({position: option.value})}
                            className={`flex-1 rounded-full py-2 text-xs font-semibold transition ${
                              editor.position === option.value ? "bg-white/[0.1] text-white" : "text-zinc-500 hover:text-zinc-300"
                            }`}
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <SectionLabel label="Text casing" />
                    <div className="flex rounded-full border border-white/[0.08] bg-black/20 p-0.5">
                      <button
                        type="button"
                        onClick={() => updateEditor({uppercase: false})}
                        className={`flex-1 rounded-full py-2 text-xs font-semibold transition ${
                          !editor.uppercase ? "bg-white/[0.1] text-white" : "text-zinc-500 hover:text-zinc-300"
                        }`}
                      >
                        Default
                      </button>
                      <button
                        type="button"
                        onClick={() => updateEditor({uppercase: true})}
                        className={`flex-1 rounded-full py-2 text-xs font-semibold transition ${
                          editor.uppercase ? "bg-white/[0.1] text-white" : "text-zinc-500 hover:text-zinc-300"
                        }`}
                      >
                        UPPERCASE
                      </button>
                    </div>
                  </div>
                  <div>
                    <SectionLabel
                      label="Motion pace"
                      tooltip="How quickly words highlight as the caption plays."
                    />
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
                          className={`flex-1 rounded-full py-2 text-xs font-semibold transition ${
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

              {dockTab === "finishing" ? (
                <div className="space-y-3">
                  <p className="text-xs leading-relaxed text-zinc-400">
                    Texture and subscribe prompts show in preview. Transitions and intros appear in the rendered clip.
                  </p>
                  <InspectorSelect
                    label="Subscribe"
                    tooltip="An end-of-clip prompt — not a clickable button. Choose None for a clean look."
                    value={editor.ctaOverlay}
                    options={socialOptions}
                    onChange={(ctaOverlay) => updateEditor({ctaOverlay})}
                  />
                  <InspectorSelect
                    label="Texture"
                    tooltip="Optional grade on the footage. Vignette darkens the edges; grain adds a film look."
                    value={editor.textureEffect}
                    options={textureOptions}
                    onChange={(textureEffect) => updateEditor({textureEffect})}
                  />
                  <LiveOverlayHint label="Texture" />
                  <InspectorSelect
                    label="Transition"
                    tooltip="How scenes connect in the published clip. Not shown in the live preview."
                    value={editor.transitionFamily}
                    options={transitionOptions}
                    onChange={(transitionFamily) => updateEditor({transitionFamily})}
                  />
                  <RenderTimeHint label="Transition" />
                  <InspectorSelect
                    label="Intro"
                    tooltip="Opening treatment on the published clip — lower-third, headline, and similar."
                    value={editor.introLayout}
                    options={introOptions}
                    onChange={(introLayout) => updateEditor({introLayout})}
                  />
                  <RenderTimeHint label="Intro hook" />
                </div>
              ) : null}
            </div>
          </div>
        </aside>

        <section
          className="order-1 relative flex min-h-[min(52dvh,28rem)] items-center justify-center overflow-hidden bg-canvas-deep px-4 py-5 lg:order-2 lg:min-h-0 lg:h-full lg:px-8 lg:py-7"
          style={{
            backgroundImage: `
              radial-gradient(ellipse 55% 50% at 50% 42%, ${editor.highlightColor}14, transparent 62%),
              radial-gradient(circle at 80% 90%, rgba(98,238,248,.04), transparent 35%)
            `,
          }}
        >
          <div className="flex h-full max-h-full w-full items-center justify-center">
            <BrandStudioPreview
              look={editor}
              recipeTemplate={selectedStarter}
              sampleText={samplePhrase}
              onSampleTextChange={setSamplePhrase}
              bakedPreviewUrl={bakedPreviewUrl}
              bakeBusy={bakeBusy}
              bakeError={bakeError}
              onRenderFiveSecondLook={(format) => void renderFiveSecondLook(format)}
              dirty={dirty}
              effects={{
                starterId: editor.starterTemplate,
                captionStyle: editor.captionStyle,
                textureEffect: editor.textureEffect,
                ctaOverlay: editor.ctaOverlay,
                introLayout: editor.introLayout,
                transitionFamily: editor.transitionFamily,
              }}
            />
          </div>
        </section>
      </div>

      {savedHandoff && !dirty && saveState.startsWith("Saved") ? (
        <div className="border-t border-cyan/[0.18] bg-teal/[0.08] px-4 py-3 text-center sm:px-5">
          <p className="text-sm font-semibold text-white">Brand style saved</p>
          <p className="mt-1 text-xs text-zinc-400">Use it in Create or keep editing this template.</p>
          <button
            type="button"
            onClick={useInCreate}
            className="mt-3 inline-flex h-9 items-center rounded-full bg-cyan px-4 text-sm font-semibold text-ink"
          >
            Use in Create
          </button>
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

export function BrandBuilderPage({
  starter,
  preset,
  baseTemplate,
  duplicate = false,
}: {
  starter?: string;
  preset?: string;
  baseTemplate?: string;
  duplicate?: boolean;
}) {
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

  return (
    <BrandBuilderWorkspace
      {...data}
      initialStarter={starter || storageStarter}
      initialPreset={preset}
      initialBaseTemplate={baseTemplate}
      initialDuplicate={duplicate}
      onTemplateSaved={loadData}
    />
  );
}

function Swatch({label, value, onChange}: {label: string; value: string; onChange: (value: string) => void}) {
  return (
    <div className="space-y-2">
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
        <span className="text-xs font-semibold text-zinc-300">{label}</span>
        <span className="font-mono text-xs text-zinc-500">{value}</span>
      </label>
      <div className="flex flex-wrap gap-1.5 pl-11">
        {BRAND_PALETTE_SWATCHES.map((swatch) => (
          <button
            key={`${label}-${swatch}`}
            type="button"
            onClick={() => onChange(swatch)}
            className={`h-5 w-5 rounded-full border transition ${value === swatch ? "border-cyan ring-1 ring-cyan/40" : "border-white/15 hover:border-white/30"}`}
            style={{background: swatch}}
            aria-label={`Set ${label} to ${swatch}`}
          />
        ))}
      </div>
    </div>
  );
}

function StarterRecipeReference({template}: {template: HyperframesTemplate}) {
  const previewSrc = template.preview_urls?.short_9_16 || template.preview_video_urls?.short_9_16;
  return (
    <div className="flex items-center gap-3 rounded-xl border border-white/[0.06] bg-black/15 px-3 py-2.5">
      <div className="relative h-14 w-9 shrink-0 overflow-hidden rounded-md border border-white/10 bg-black/40">
        {previewSrc ? (
          <video
            key={previewSrc}
            src={previewSrc}
            muted
            playsInline
            loop
            autoPlay
            preload="metadata"
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="grid h-full place-items-center text-[9px] font-semibold text-zinc-600">HF</div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[11px] font-semibold text-zinc-200">{template.label}</p>
        <p className="truncate text-[10px] text-zinc-500">{template.best_for || "Style preview"}</p>
      </div>
    </div>
  );
}

function BuilderTooltip({text}: {text: string}) {
  return (
    <span className="group relative inline-flex shrink-0" tabIndex={0} aria-label={text}>
      <HelpCircle className="h-3.5 w-3.5 text-zinc-500 transition group-hover:text-zinc-300 group-focus-within:text-zinc-300" aria-hidden />
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-[calc(100%+6px)] left-1/2 z-50 hidden w-52 -translate-x-1/2 rounded-lg border border-white/10 bg-zinc-900 px-2.5 py-2 text-xs leading-relaxed text-zinc-300 shadow-xl group-hover:block group-focus-within:block"
      >
        {text}
      </span>
    </span>
  );
}

function SectionLabel({label, tooltip}: {label: string; tooltip?: string}) {
  return (
    <div className="mb-2 flex items-center gap-1.5">
      <p className="text-xs font-bold uppercase tracking-widest text-zinc-400">{label}</p>
      {tooltip ? <BuilderTooltip text={tooltip} /> : null}
    </div>
  );
}

/** Quiet inspector row: label left, value select right — Figma-like, not chip walls. */
function LiveOverlayHint({label}: {label: string}) {
  return (
    <p className="-mt-1 text-xs leading-relaxed text-zinc-500">
      {label} shows in the preview.
    </p>
  );
}

function RenderTimeHint({label}: {label: string}) {
  return (
    <p className="-mt-1 text-xs leading-relaxed text-zinc-500">
      {label} appears on published clips, not in the live preview. Render a preview to see it.
    </p>
  );
}

function InspectorSelect({
  label,
  tooltip,
  value,
  options,
  disabled = false,
  onChange,
}: {
  label: string;
  tooltip?: string;
  value: string;
  options: {value: string; label: string}[];
  disabled?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex items-center gap-3 rounded-xl border border-white/[0.06] bg-black/15 px-3 py-2.5">
      <span className="flex w-[5.5rem] shrink-0 items-center gap-1 text-xs font-semibold text-zinc-400">
        {label}
        {tooltip ? <BuilderTooltip text={tooltip} /> : null}
      </span>
      <span className="relative min-w-0 flex-1">
        <select
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          className="h-8 w-full appearance-none truncate bg-transparent pr-7 text-right text-sm font-semibold text-zinc-200 outline-none focus:text-white disabled:opacity-50"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value} className="bg-[#17171a] text-left text-white">
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-0 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-600" />
      </span>
    </label>
  );
}
