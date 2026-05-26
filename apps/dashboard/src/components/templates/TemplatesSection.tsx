"use client";

import {Monitor, Settings, Smartphone, Sparkles, Wand2} from "lucide-react";
import {useEffect, useState, type ReactNode} from "react";
import {FocusModal} from "@/components/FocusModal";
import {TemplatePreview} from "@/components/templates/TemplatePreview";
import type {EngineHealth, HyperframesCatalog, HyperframesTemplate} from "@/lib/media-api";

const templateFilters = ["All", "Spiritual", "Podcast", "Data", "News", "Promo", "Official", "Brand"] as const;
type TemplateFrame = "short" | "long";

export function TemplatesSection({
  templates,
  catalog,
  engineHealth,
  currentTemplate,
  onUse,
  onSetDefault,
  onCustomize,
  renderStatusPill,
  renderSettingTile,
  renderEmptyState,
}: {
  templates: HyperframesTemplate[];
  catalog: HyperframesCatalog | null;
  engineHealth: EngineHealth | null;
  currentTemplate: string;
  onUse: (templateId: string) => void;
  onSetDefault: (templateId: string) => void;
  onCustomize: (templateId: string) => void;
  renderStatusPill: (busy: boolean, status: string) => ReactNode;
  renderSettingTile: (label: string, value: string | number) => ReactNode;
  renderEmptyState: (title: string, text: string) => ReactNode;
}) {
  const fallback = templates.length ? templates : [
    {
      id: "spiritual_reflective",
      label: "Spiritual Reflective",
      category: "Spiritual",
      best_for: "Spiritual teaching, reflective advice, and heart-softening clips.",
      effects: ["warm vignette", "subtle grain", "editorial hook", "word emphasis"],
      caption_style: "Editorial weighted captions",
      default_genres: ["kajian", "spiritual_reflection", "advice"],
      status: "ready",
      tone: "Calm, warm, devotional",
    },
  ];
  const [filter, setFilter] = useState<(typeof templateFilters)[number]>("All");
  const [frame, setFrame] = useState<TemplateFrame>("short");
  const [selectedId, setSelectedId] = useState(currentTemplate === "auto" ? fallback[0]?.id || "" : currentTemplate);
  const [detailOpen, setDetailOpen] = useState(false);
  const visible = fallback.filter((template) => filter === "All" || template.category === filter);
  const selected = fallback.find((template) => template.id === selectedId) || visible[0] || fallback[0];
  const ready = Boolean(engineHealth?.hyperframes.ready);
  const catalogReady = catalog?.items.filter((item) => item.status === "production-ready").length || 0;
  const framePreviewKey = frame === "long" ? "long_16_9" : "short_9_16";
  const gridClass =
    frame === "long"
      ? "grid-cols-1 xl:grid-cols-2"
      : "grid-cols-[repeat(auto-fit,minmax(320px,1fr))]";

  useEffect(() => {
    const previews = visible
      .slice(0, 2)
      .map((template) => template.preview_video_urls?.[framePreviewKey] || template.preview_urls?.[framePreviewKey])
      .filter(Boolean) as string[];
    const videos = previews.map((src) => {
      const video = document.createElement("video");
      video.preload = "metadata";
      video.src = src;
      return video;
    });
    return () => {
      videos.forEach((video) => {
        video.src = "";
      });
    };
  }, [visible, framePreviewKey]);

  return (
    <section className="grid min-w-0 gap-5">
      <div className="min-w-0 rounded-[24px] border border-white/[0.08] bg-surface p-4 sm:rounded-[28px] sm:p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <span className="inline-flex rounded-full border border-cyan/[0.24] bg-teal/[0.08] px-3 py-1 text-xs font-semibold text-cyan">HyperFrames public template system</span>
            <h3 className="mt-3 text-2xl font-semibold text-white">Templates</h3>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-400">Browse ready-to-use video flows, then send one straight into Generate or customize it as a Brand System Template.</p>
          </div>
          {renderStatusPill(false, ready ? "HyperFrames ready" : engineHealth?.hyperframes.reason || "Runtime not ready")}
        </div>

        <div className="mt-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap gap-2">
            {templateFilters.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setFilter(item)}
                className={`rounded-full border px-3 py-2 text-sm font-semibold transition ${filter === item ? "border-cyan bg-teal/[0.16] text-white" : "border-white/[0.08] bg-black/20 text-zinc-400 hover:border-white/[0.18] hover:text-white"}`}
              >
                {item}
              </button>
            ))}
          </div>
          <div className="inline-flex w-full items-center rounded-[18px] border border-white/[0.10] bg-black/30 p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] sm:w-auto">
            <button
              type="button"
              onClick={() => setFrame("short")}
              aria-pressed={frame === "short"}
              className={`inline-flex h-10 flex-1 items-center justify-center gap-2 rounded-[14px] px-4 text-sm font-semibold transition sm:flex-none ${
                frame === "short"
                  ? "bg-cyan text-ink shadow-[0_10px_24px_rgba(102,232,249,0.24)]"
                  : "text-zinc-400 hover:bg-white/[0.04] hover:text-white"
              }`}
            >
              <Smartphone className="h-4 w-4" />
              Short 9:16
            </button>
            <button
              type="button"
              onClick={() => setFrame("long")}
              aria-pressed={frame === "long"}
              className={`inline-flex h-10 flex-1 items-center justify-center gap-2 rounded-[14px] px-4 text-sm font-semibold transition sm:flex-none ${
                frame === "long"
                  ? "bg-cyan text-ink shadow-[0_10px_24px_rgba(102,232,249,0.24)]"
                  : "text-zinc-400 hover:bg-white/[0.04] hover:text-white"
              }`}
            >
              <Monitor className="h-4 w-4" />
              Long 16:9
            </button>
          </div>
        </div>

        <div className={`mt-5 grid gap-3 ${gridClass}`}>
          {visible.map((template) => {
            const active = selected?.id === template.id;
            const current = currentTemplate === template.id;
            return (
              <button
                key={template.id}
                type="button"
                onClick={() => {
                  setSelectedId(template.id);
                  setDetailOpen(true);
                }}
                className={`template-card min-w-0 rounded-[24px] border p-3 text-left transition sm:p-4 ${active ? "border-cyan/[0.45] bg-teal/[0.10] shadow-glow" : "border-white/[0.08] bg-canvas-deep hover:border-white/[0.16]"}`}
              >
                <TemplatePreview template={template} compact frame={frame} hoverToPlay />
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase tracking-wide text-cyan">{template.category}</p>
                    <h4 className="mt-2 text-lg font-semibold text-white">{template.label}</h4>
                  </div>
                  <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${template.status === "ready" ? "border-teal/[0.25] bg-teal/[0.10] text-teal" : "border-warning/[0.25] bg-warning/[0.10] text-warning"}`}>
                    {current ? "selected" : template.status}
                  </span>
                </div>
                <p className="mt-3 line-clamp-2 text-sm leading-6 text-zinc-400">{template.best_for}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {template.effects.slice(0, 3).map((effect) => (
                    <span key={effect} className="rounded-full border border-white/[0.08] bg-black/20 px-2.5 py-1 text-xs text-zinc-400">{effect}</span>
                  ))}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <FocusModal open={detailOpen && Boolean(selected)} title={selected?.label || "Template"} subtitle="Preview the real-usecase flow, then use it in Generate or customize it as a Brand System Template." width="wide" onClose={() => setDetailOpen(false)}>
        {selected ? (
          <div className="grid gap-5">
            <div className="grid gap-4 lg:grid-cols-[minmax(240px,360px)_minmax(280px,1fr)] lg:items-start">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">Short/Reels output</p>
                <TemplatePreview template={selected} frame="short" />
              </div>
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">Long output</p>
                <TemplatePreview template={selected} compact frame="long" />
              </div>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Selected template</p>
              <h3 className="mt-2 text-2xl font-semibold text-white">{selected.label}</h3>
              <p className="mt-2 text-sm leading-6 text-zinc-400">{selected.tone}</p>
            </div>
            <div className="grid gap-2">
              <button data-autofocus type="button" onClick={() => onUse(selected.id)} className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-cyan px-4 text-sm font-semibold text-ink">
                <Wand2 className="h-4 w-4" />
                Use in Generate
              </button>
              <button type="button" onClick={() => onCustomize(selected.id)} className="inline-flex h-11 items-center justify-center gap-2 rounded-full border border-cyan/[0.20] bg-teal/[0.08] px-4 text-sm font-semibold text-cyan">
                <Settings className="h-4 w-4" />
                Customize as Brand Template
              </button>
            </div>
            <div className="grid gap-3">
              {renderSettingTile("Niche", selected.category)}
              {renderSettingTile("Caption", selected.caption_style)}
              {renderSettingTile("Runtime", ready ? "lint + inspect ready" : "runtime check required")}
              {renderSettingTile("Catalog", `${catalogReady} production-ready items`)}
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Best for</p>
              <p className="mt-2 text-sm leading-6 text-zinc-300">{selected.best_for}</p>
            </div>
            <details className="rounded-[22px] border border-white/[0.08] bg-canvas-deep p-4">
              <summary className="cursor-pointer list-none font-semibold text-white">Technical ingredients</summary>
              <div className="mt-4 grid gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Effects used</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {selected.effects.map((effect) => (
                      <span key={effect} className="rounded-full border border-cyan/[0.18] bg-teal/[0.08] px-2.5 py-1 text-xs font-semibold text-cyan">{effect}</span>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Catalog ingredients</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {[...(selected.components_used || []), ...(selected.blocks_used || [])].slice(0, 8).map((item) => (
                      <span key={item} className="rounded-full border border-white/[0.08] bg-black/20 px-2.5 py-1 text-xs text-zinc-400">{item}</span>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Auto genres</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {selected.default_genres.map((genre) => (
                      <span key={genre} className="rounded-full border border-white/[0.08] bg-black/20 px-2.5 py-1 text-xs text-zinc-400">{genre}</span>
                    ))}
                  </div>
                </div>
              </div>
            </details>
            <div className="grid gap-2">
              <button type="button" onClick={() => onSetDefault(selected.id)} className="inline-flex h-11 items-center justify-center gap-2 rounded-full border border-white/[0.10] bg-canvas-deep px-4 text-sm font-semibold text-zinc-200">
                <Sparkles className="h-4 w-4" />
                Set as HyperFrames default
              </button>
            </div>
          </div>
        ) : (
          renderEmptyState("No templates loaded", "Refresh after restarting the media engine backend.")
        )}
      </FocusModal>
    </section>
  );
}
