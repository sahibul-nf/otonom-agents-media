"use client";

import {useEffect, useMemo, useState} from "react";
import {CheckCircle2, Loader2} from "lucide-react";
import {apiGet, apiPost, AutonomySettings, BrandTemplate, StyleProfile} from "@/lib/media-api";

type ActionUiState = {status: "running" | "done" | "failed"; message: string};

type Props = {
  style: StyleProfile | null;
  templates: BrandTemplate[];
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

export function BrandSection({
  style,
  templates,
  autonomy,
  actionStates,
  defaultTemplate,
  onAutonomyMode,
  onTemplateSaved,
}: Props) {
  const editorFromStyle = (source?: StyleProfile | null) => {
    const caption = source?.caption || {};
    const brand = source?.brand || {};
    return {
      fontFamily: String(caption.font_family || "Sora"),
      fontSize: Number(caption.font_size || 54),
      textColor: hexFromColor(caption.text_color, "#ffffff"),
      highlightColor: hexFromColor(caption.highlight_word_color, "#00ff36"),
      backgroundColor: hexFromColor(caption.background_color, "#000000"),
      strokeWidth: Number(caption.stroke_width || 10),
      watermarkText: String(brand.watermark_text || "Nourbit Clips"),
    };
  };
  const [selectedTemplate, setSelectedTemplate] = useState(defaultTemplate);
  const [label, setLabel] = useState("Custom Workspace Template");
  const [editor, setEditor] = useState(editorFromStyle(style));
  const [saveState, setSaveState] = useState("Ready");
  const [templateBusy, setTemplateBusy] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const [fontAvailability, setFontAvailability] = useState<"checking" | "available" | "fallback">("checking");
  const selectedFontOption = useMemo(() => fontOptions.some((font) => font.value === editor.fontFamily) ? editor.fontFamily : "__custom", [editor.fontFamily]);

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

  async function saveTemplate() {
    setSaveBusy(true);
    setSaveState("Saving...");
    try {
      await apiPost("brand-template", {label, style: stylePayload, base_template: selectedTemplate});
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
    <section className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
      <div className="min-w-0 overflow-hidden rounded-[28px] border border-white/[0.08] bg-surface">
        <div className="border-b border-white/[0.08] bg-[radial-gradient(circle_at_10%_0%,rgba(108,226,238,.14),transparent_34%),linear-gradient(180deg,rgba(255,255,255,.035),transparent)] p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-cyan">Brand system</p>
              <h3 className="mt-1 text-2xl font-semibold text-white">Template setup flow</h3>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-zinc-400">Choose a base style, tune the caption identity, then save a reusable template for future batches.</p>
            </div>
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${saveState.toLowerCase().includes("failed") ? "border-danger/30 bg-danger/10 text-danger" : "border-cyan/[0.22] bg-teal/[0.08] text-cyan"}`}>
              {saveState}
            </span>
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-3">
            <FlowPill step="1" title="Pick base" detail="Load a saved style" active />
            <FlowPill step="2" title="Tune look" detail="Caption, colors, overlay" active />
            <FlowPill step="3" title="Save reuse" detail="Apply in Generate" active={saveState === "Template saved"} />
          </div>
        </div>

        <div className="grid gap-4 p-4 sm:p-5">
          <div className="rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-cyan">Step 1</p>
                <h4 className="mt-1 font-semibold text-white">Choose template source</h4>
                <p className="mt-1 text-sm text-zinc-500">Load a known style first so every edit starts from a predictable baseline.</p>
              </div>
              {templateBusy ? <Loader2 className="h-4 w-4 shrink-0 animate-spin text-cyan" /> : null}
            </div>
            <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,.8fr)]">
              <label className="grid min-w-0 gap-2 text-sm font-medium text-zinc-300">
                Base template
                <select
                  value={selectedTemplate}
                  disabled={templateBusy}
                  onChange={(event) => void loadTemplate(event.target.value)}
                  className="h-12 min-w-0 rounded-2xl border border-cyan/[0.28] bg-surface px-4 text-sm font-semibold text-white outline-none disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {(templates.length ? templates : [{id: defaultTemplate, label: "Default style baseline", path: defaultTemplate}]).map((template) => (
                    <option key={template.id} value={template.path}>{template.label}</option>
                  ))}
                </select>
              </label>
              <label className="grid min-w-0 gap-2 text-sm font-medium text-zinc-300">
                Save as
                <input value={label} onChange={(event) => setLabel(event.target.value)} className="h-12 min-w-0 rounded-2xl border border-white/[0.08] bg-surface px-4 text-sm text-zinc-200 outline-none focus:border-cyan/[0.35]" />
              </label>
            </div>
          </div>

          <div className="rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-cyan">Step 2</p>
                <h4 className="mt-1 font-semibold text-white">Tune visual identity</h4>
                <p className="mt-1 text-sm text-zinc-500">Caption style and watermark update the preview instantly without a long render.</p>
              </div>
              <span className="rounded-full border border-white/[0.08] bg-surface px-3 py-1 text-xs font-semibold text-zinc-400">{editor.fontSize}px caption</span>
            </div>
            <div className="mt-4 grid min-w-0 gap-3 lg:grid-cols-2">
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
            <div className="mt-4 rounded-[20px] border border-white/[0.08] bg-surface p-3">
              <TextField label="Watermark text" value={editor.watermarkText} onChange={(value) => updateEditor({watermarkText: value})} />
            </div>
          </div>

          <div className="rounded-[24px] border border-cyan/[0.18] bg-teal/[0.08] p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-cyan">Step 3</p>
                <h4 className="mt-1 font-semibold text-white">Save template for production</h4>
                <p className="mt-1 text-sm text-zinc-400">Saved templates appear in Generate and can be reused across future clips.</p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <button type="button" disabled={saveBusy || templateBusy} onClick={saveTemplate} className="inline-flex items-center gap-2 rounded-full bg-cyan px-5 py-3 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50">
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

          <div className="rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h4 className="font-semibold text-white">Template library</h4>
                <p className="mt-1 text-sm text-zinc-500">Saved styles available for future batch generation.</p>
              </div>
              <span className="rounded-full border border-cyan/[0.22] bg-teal/[0.08] px-3 py-1 text-xs font-semibold text-cyan">{templates.length} saved</span>
            </div>
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
                    <span className="mt-1 block truncate text-xs text-zinc-500">{template.path}</span>
                  </span>
                  {selectedTemplate === template.path ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : null}
                </button>
              )) : <EmptyState text="No style templates found." />}
            </div>
          </div>

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
            <p className="text-center text-3xl font-black leading-tight text-white drop-shadow-lg">Bahagia Hanya dengan Allah</p>
            <p className="mx-auto mt-3 max-w-[260px] text-center text-sm font-semibold leading-5 text-zinc-200">Pesan singkat yang menenangkan hati dan meluruskan arah.</p>
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
              <span style={{color: editor.highlightColor}}>Jika</span> hati tenang
            </div>
            <div className="flex items-center justify-between text-xs font-semibold">
              <span className="text-white">{editor.watermarkText}</span>
              <span style={{color: editor.highlightColor}}>Source: Ribath Nouraniyyah</span>
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
  );
}

function FlowPill({step, title, detail, active}: {step: string; title: string; detail: string; active: boolean}) {
  return (
    <div className={`flex min-w-0 items-center gap-3 rounded-[20px] border p-3 ${active ? "border-cyan/[0.22] bg-teal/[0.10]" : "border-white/[0.08] bg-canvas-deep"}`}>
      <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-full text-xs font-bold ${active ? "bg-cyan text-ink" : "bg-white/[0.06] text-zinc-500"}`}>{step}</span>
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold text-white">{title}</span>
        <span className="mt-0.5 block truncate text-xs text-zinc-500">{detail}</span>
      </span>
    </div>
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
