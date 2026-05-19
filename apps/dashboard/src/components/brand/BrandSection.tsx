"use client";

import {useState} from "react";
import {Loader2} from "lucide-react";
import {apiGet, apiPost, AutonomySettings, BrandTemplate, StyleProfile} from "@/lib/media-api";

type ActionUiState = {status: "running" | "done" | "failed"; message: string};

type Props = {
  style: StyleProfile | null;
  templates: BrandTemplate[];
  autonomy: AutonomySettings | null;
  actionStates: Record<string, ActionUiState>;
  command: string;
  defaultTemplate: string;
  onCopy: () => void;
  onAutonomyMode: (mode: string) => void;
  onTemplateSaved: () => void;
};

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
  command,
  defaultTemplate,
  onCopy,
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
    <section className="grid gap-5 xl:grid-cols-[1fr_420px]">
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <h3 className="text-xl font-semibold text-white">Brand template editor</h3>
        <p className="mt-1 text-sm text-zinc-400">Tune the caption and watermark look with an instant browser preview. Saving creates a reusable local template.</p>
        <div className="mt-5 grid gap-4">
          <label className="grid gap-2 text-sm font-medium text-zinc-300">
            Base template
            <select
              value={selectedTemplate}
              disabled={templateBusy}
              onChange={(event) => void loadTemplate(event.target.value)}
              className="h-12 rounded-2xl border border-cyan/[0.28] bg-canvas-deep px-4 text-sm font-semibold text-white outline-none disabled:cursor-not-allowed disabled:opacity-50"
            >
              {(templates.length ? templates : [{id: defaultTemplate, label: "Default style baseline", path: defaultTemplate}]).map((template) => (
                <option key={template.id} value={template.path}>{template.label}</option>
              ))}
            </select>
          </label>
          <label className="grid gap-2 text-sm font-medium text-zinc-300">
            Template name
            <input value={label} onChange={(event) => setLabel(event.target.value)} className="h-12 rounded-2xl border border-white/[0.08] bg-canvas-deep px-4 text-sm text-zinc-200 outline-none focus:border-cyan/[0.35]" />
          </label>
          <div className="grid gap-3 md:grid-cols-2">
            <TextField label="Font family" value={editor.fontFamily} onChange={(value) => updateEditor({fontFamily: value})} />
            <NumberField label="Font size" value={editor.fontSize} min={28} max={76} onChange={(value) => updateEditor({fontSize: value})} />
            <ColorField label="Text color" value={editor.textColor} onChange={(value) => updateEditor({textColor: value})} />
            <ColorField label="Highlight" value={editor.highlightColor} onChange={(value) => updateEditor({highlightColor: value})} />
            <ColorField label="Caption background" value={editor.backgroundColor} onChange={(value) => updateEditor({backgroundColor: value})} />
            <NumberField label="Stroke width" value={editor.strokeWidth} min={0} max={16} onChange={(value) => updateEditor({strokeWidth: value})} />
          </div>
          <TextField label="Watermark text" value={editor.watermarkText} onChange={(value) => updateEditor({watermarkText: value})} />
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" disabled={saveBusy || templateBusy} onClick={saveTemplate} className="inline-flex items-center gap-2 rounded-full bg-cyan px-5 py-3 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50">
              {saveBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {saveBusy ? "Saving..." : "Save as template"}
            </button>
            <button type="button" disabled={saveBusy || templateBusy} onClick={() => void loadTemplate(selectedTemplate)} className="inline-flex items-center gap-2 rounded-full border border-white/[0.10] px-5 py-3 text-sm font-semibold text-zinc-300 disabled:cursor-not-allowed disabled:opacity-50">
              {templateBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {templateBusy ? "Loading..." : "Reset"}
            </button>
            <span className={`text-sm ${saveState.toLowerCase().includes("failed") ? "text-danger" : "text-cyan"}`}>{saveState}</span>
          </div>
        </div>
        <div className="mt-5 rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
          <h4 className="font-semibold text-white">Available templates</h4>
          <div className="mt-3 grid gap-2">
            {templates.length ? templates.map((template) => (
              <div key={template.id} className="flex items-center justify-between rounded-2xl bg-surface px-4 py-3">
                <span className="text-sm text-zinc-200">{template.label}</span>
                <span className="text-xs text-zinc-500">{template.path}</span>
              </div>
            )) : <EmptyState text="No style templates found." />}
          </div>
        </div>
        <div className="mt-5 rounded-[24px] border border-cyan/[0.18] bg-teal/[0.08] p-4">
          <h4 className="font-semibold text-white">Autonomous mode</h4>
          <p className="mt-1 text-sm leading-6 text-zinc-400">Assisted mode gives you {autonomy?.review_grace_hours || 12}h to approve before high-score clips enter the schedule queue.</p>
          <div className="mt-4 grid grid-cols-3 gap-2">
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
          <div className="mt-4 grid grid-cols-2 gap-2">
            <SettingTile label="Review window" value={`${autonomy?.review_grace_hours || 12}h`} />
            <SettingTile label="Auto schedule" value={autonomy?.auto_schedule_enabled ? "On" : "Off"} />
            <SettingTile label="Overall gate" value={autonomy?.overall_threshold || 82} />
            <SettingTile label="Caption gate" value={autonomy?.caption_threshold || 90} />
          </div>
        </div>
      </div>
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <h3 className="text-xl font-semibold text-white">Live brand preview</h3>
        <div className="mt-5 mx-auto flex aspect-[9/16] max-h-[620px] w-full max-w-[350px] flex-col justify-between overflow-hidden rounded-[28px] border border-white/[0.10] bg-[radial-gradient(circle_at_50%_20%,rgba(108,226,238,.18),transparent_34%),linear-gradient(180deg,#31343a,#111214_68%)] p-7 shadow-glow">
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
        <div className="mt-5 rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
          <div className="mb-3 flex items-center justify-between">
            <h4 className="font-semibold text-white">Run command</h4>
            <button onClick={onCopy} className="rounded-full bg-cyan px-4 py-2 text-sm font-semibold text-ink">Copy</button>
          </div>
          <pre className="max-h-[180px] overflow-auto rounded-[18px] bg-black/30 p-4 text-[11px] leading-5 text-zinc-400">{command}</pre>
        </div>
      </div>
    </section>
  );
}

function SettingTile({label, value}: {label: string; value: string | number}) {
  return (
    <div className="rounded-[18px] border border-white/[0.08] bg-canvas-deep p-4">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-white">{value}</p>
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
