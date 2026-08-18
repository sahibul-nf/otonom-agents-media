"use client";

import {BadgeCheck, ChevronRight, Layers3, Monitor, Settings, Smartphone, Sparkles, Wand2, X} from "lucide-react";
import {useEffect, useMemo, useState, type ReactNode} from "react";
import {FocusModal} from "@/components/FocusModal";
import {TemplatePreview} from "@/components/templates/TemplatePreview";
import {getRecipeTheme} from "@/components/templates/recipes";
import type {EngineHealth, HyperframesCatalog, HyperframesTemplate} from "@/lib/media-api";

const templateFilters = ["All", "Spiritual", "Podcast", "Data", "News", "Promo", "Official", "Brand"] as const;
type TemplateFrame = "short" | "long";

function friendlyTemplateStatus(status?: string) {
  switch (status) {
    case "ready":
    case "production-ready":
      return "Ready";
    case "draft":
      return "Draft";
    case "experimental":
    case "beta":
      return "Beta";
    case "unavailable":
    case "error":
      return "Unavailable";
    default:
      return status ? "Available" : "Ready";
  }
}

function stylesReadyLabel(ready: boolean, reason?: string) {
  if (ready) return "Styles ready";
  const cleaned = (reason || "").trim();
  if (!cleaned) return "Styles unavailable";
  return cleaned.replace(/template engine/gi, "styles").replace(/\bhyperframes\b/gi, "styles");
}

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
  const [filter, setFilter] = useState<(typeof templateFilters)[number]>("All");
  const [frame, setFrame] = useState<TemplateFrame>("short");
  const [selectedId, setSelectedId] = useState(currentTemplate === "auto" ? templates[0]?.id || "" : currentTemplate);
  const [detailOpen, setDetailOpen] = useState(false);
  const visible = templates.filter((template) => filter === "All" || template.category === filter);
  const selected = templates.find((template) => template.id === selectedId) || visible[0] || templates[0];
  const selectedRecipe = selected ? getRecipeTheme(selected.id) : null;
  const ready = Boolean(engineHealth?.hyperframes.ready);
  const catalogReady = catalog?.items.filter((item) => item.status === "production-ready").length || 0;
  const readyTemplateCount = templates.filter((template) => template.status === "ready").length;
  const activeInCreate =
    currentTemplate && currentTemplate !== "auto"
      ? templates.find((template) => template.id === currentTemplate)
      : undefined;
  const categoryCounts = useMemo(() => {
    const counts: Record<(typeof templateFilters)[number], number> = {All: templates.length, Spiritual: 0, Podcast: 0, Data: 0, News: 0, Promo: 0, Official: 0, Brand: 0};
    for (const template of templates) {
      const key = template.category as (typeof templateFilters)[number];
      if (templateFilters.includes(key) && key !== "All") counts[key] += 1;
    }
    return counts;
  }, [templates]);
  const frameLabelShort = frame === "long" ? "16:9 landscape" : "9:16 portrait";
  const framePreviewKey = frame === "long" ? "long_16_9" : "short_9_16";
  const detailFrameLabel = frame === "long" ? "Long/Landscape 16:9" : "Short/Reels 9:16";
  const gridClass =
    frame === "long"
      ? "grid-cols-[repeat(auto-fill,minmax(21rem,1fr))] lg:grid-cols-[repeat(auto-fill,minmax(23rem,1fr))]"
      : "grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] sm:grid-cols-[repeat(auto-fill,minmax(16rem,1fr))] lg:grid-cols-[repeat(auto-fill,minmax(18rem,1fr))]";
  const isPortraitGrid = frame === "short";
  const openTemplateDetail = (templateId: string) => {
    setSelectedId(templateId);
    setDetailOpen(true);
  };

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
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="text-sm leading-6 text-zinc-400">
              Pick a look, then use it in Create. Preview details stay optional.
            </p>
          </div>
          {renderStatusPill(false, stylesReadyLabel(ready, engineHealth?.hyperframes.reason))}
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <InsightTile label="Styles" value={String(templates.length)} detail={`${readyTemplateCount} ready to use`} />
          <InsightTile label="Format" value={frame === "short" ? "9:16" : "16:9"} detail={frameLabelShort} />
          <InsightTile
            label="Using in Create"
            value={activeInCreate?.label ? "Set" : "None"}
            detail={activeInCreate?.label || "Choose a style below"}
            highlight={Boolean(activeInCreate)}
          />
          <InsightTile label="Custom parts" value={String(catalogReady)} detail="available if you customize" />
        </div>

        {selected ? (
          <div className="mt-4 flex flex-col gap-3 rounded-[20px] border border-cyan/[0.18] bg-teal/[0.07] p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-cyan">Selected style</p>
              <p className="mt-1 truncate text-base font-semibold text-white">{selected.label}</p>
              <p className="mt-1 line-clamp-2 text-xs leading-5 text-zinc-400">{selected.best_for}</p>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => openTemplateDetail(selected.id)}
                className="text-sm font-medium text-zinc-500 underline-offset-4 transition hover:text-zinc-300 hover:underline"
              >
                View details
              </button>
              <button
                type="button"
                disabled={!ready}
                onClick={() => onUse(selected.id)}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-full bg-cyan px-4 text-sm font-semibold text-ink shadow-[0_10px_24px_rgba(102,232,249,0.18)] transition hover:bg-cyan/90 disabled:cursor-not-allowed disabled:opacity-45"
              >
                <Wand2 className="h-4 w-4" />
                Use in Create
              </button>
            </div>
          </div>
        ) : null}

        {!ready ? (
          <div className="mt-4 rounded-[18px] border border-warning/[0.22] bg-warning/[0.08] px-4 py-3 text-sm leading-6 text-warning">
            You can still browse previews, but Use in Create needs styles to reconnect first.
          </div>
        ) : null}

        <div className="sticky top-[4.5rem] z-10 -mx-1 mt-5 rounded-[20px] border border-white/[0.08] bg-surface/95 px-3 py-3 backdrop-blur-md sm:px-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Browse by niche</p>
              <div className="relative mt-2">
                <div className="flex gap-2 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                  {templateFilters.map((item) => {
                    const count = categoryCounts[item];
                    const disabled = item !== "All" && count === 0;
                    return (
                      <button
                        key={item}
                        type="button"
                        disabled={disabled}
                        onClick={() => setFilter(item)}
                        className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-35 ${
                          filter === item
                            ? "border-cyan bg-teal/[0.16] text-white"
                            : "border-white/[0.08] bg-black/20 text-zinc-400 hover:border-white/[0.18] hover:text-white"
                        }`}
                      >
                        {item}
                        <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${filter === item ? "bg-black/25 text-white" : "bg-white/[0.06] text-zinc-500"}`}>
                          {count}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
            <div className="shrink-0">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Preview as</p>
              <div
                className="inline-flex w-full items-center rounded-[18px] border border-white/[0.10] bg-black/30 p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] sm:w-auto"
                role="group"
                aria-label="Preview frame"
              >
                <button
                  type="button"
                  onClick={() => setFrame("short")}
                  aria-pressed={frame === "short"}
                  className={`inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-[14px] px-3.5 text-sm font-semibold transition sm:flex-none ${
                    frame === "short"
                      ? "bg-cyan text-ink shadow-[0_10px_24px_rgba(102,232,249,0.24)]"
                      : "text-zinc-400 hover:bg-white/[0.04] hover:text-white"
                  }`}
                >
                  <Smartphone className="h-3.5 w-3.5" />
                  9:16
                </button>
                <button
                  type="button"
                  onClick={() => setFrame("long")}
                  aria-pressed={frame === "long"}
                  className={`inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-[14px] px-3.5 text-sm font-semibold transition sm:flex-none ${
                    frame === "long"
                      ? "bg-cyan text-ink shadow-[0_10px_24px_rgba(102,232,249,0.24)]"
                      : "text-zinc-400 hover:bg-white/[0.04] hover:text-white"
                  }`}
                >
                  <Monitor className="h-3.5 w-3.5" />
                  16:9
                </button>
              </div>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-white/[0.06] pt-3">
            <p className="text-xs text-zinc-500">
              <span className="font-semibold text-zinc-300">{visible.length}</span> style{visible.length === 1 ? "" : "s"}
              {filter !== "All" ? (
                <>
                  {" "}
                  in <span className="text-cyan">{filter}</span>
                </>
              ) : null}
              <span className="text-zinc-600"> · </span>
              Tap a card to select · details optional
            </p>
            {filter !== "All" ? (
              <button
                type="button"
                onClick={() => setFilter("All")}
                className="inline-flex items-center gap-1 rounded-full border border-white/[0.10] bg-black/20 px-2.5 py-1 text-xs font-semibold text-zinc-300 transition hover:border-white/[0.18] hover:text-white"
              >
                <X className="h-3 w-3" />
                Clear filter
              </button>
            ) : null}
          </div>
        </div>

        {visible.length ? (
          <div className={`mt-4 grid gap-2.5 sm:gap-3 ${gridClass}`}>
            {visible.map((template) => {
              const isActiveInCreate = currentTemplate === template.id;
              const isSelected = selected?.id === template.id;
              const statusLabel = isActiveInCreate ? "In Create" : friendlyTemplateStatus(template.status);
              return (
                <article
                  key={template.id}
                  className={`template-card group min-w-0 rounded-[20px] border text-left transition ${
                    isPortraitGrid ? "p-2.5 sm:p-3" : "p-3 sm:p-3.5"
                  } ${
                    isActiveInCreate
                      ? "border-cyan/[0.50] bg-teal/[0.12] shadow-glow"
                      : isSelected
                        ? "border-cyan/[0.28] bg-teal/[0.06]"
                        : "border-white/[0.08] bg-canvas-deep hover:border-cyan/[0.22] hover:bg-teal/[0.05]"
                  }`}
                >
                  <TemplatePreview
                    template={template}
                    compact
                    gridCard
                    hideFooterLabel
                    frame={frame}
                    hoverToPlay
                  />
                  <button
                    type="button"
                    onClick={() => setSelectedId(template.id)}
                    className="mt-2 block w-full text-left"
                    aria-pressed={isSelected}
                    aria-label={`Select ${template.label}`}
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between gap-2">
                        <p className="truncate text-[10px] font-semibold uppercase tracking-wide text-cyan">{template.category}</p>
                        <TemplateStatusBadge status={template.status} label={statusLabel} active={isActiveInCreate} />
                      </div>
                      <h4 className="line-clamp-1 text-sm font-semibold leading-5 text-white">{template.label}</h4>
                      <p className={`text-zinc-400 ${isPortraitGrid ? "line-clamp-1 text-xs leading-4" : "line-clamp-2 text-xs leading-5"}`}>
                        {template.best_for}
                      </p>
                    </div>
                  </button>
                  <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2 pt-0.5">
                    <div className="flex min-w-0 flex-wrap gap-1">
                      {template.effects.slice(0, isPortraitGrid ? 2 : 3).map((effect) => (
                        <span key={effect} className="rounded-full border border-white/[0.08] bg-black/20 px-2 py-0.5 text-[10px] leading-4 text-zinc-400">
                          {effect}
                        </span>
                      ))}
                    </div>
                    <button
                      type="button"
                      onClick={() => openTemplateDetail(template.id)}
                      className="inline-flex h-8 shrink-0 items-center gap-0.5 rounded-full px-2.5 text-xs font-medium text-zinc-500 transition hover:text-zinc-300"
                      aria-label={`View details for ${template.label}`}
                    >
                      Details
                      <ChevronRight className="h-3 w-3" />
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="mt-4">
            {renderEmptyState(
              templates.length ? `No ${filter} styles` : ready ? "No styles available" : "Styles unavailable",
              templates.length
                ? "Try another category or switch back to All to browse the full library."
                : stylesReadyLabel(false, engineHealth?.hyperframes.reason) === "Styles unavailable"
                  ? "Reconnect or restart the media engine, then refresh this page."
                  : stylesReadyLabel(false, engineHealth?.hyperframes.reason),
            )}
            {templates.length && filter !== "All" ? (
              <button
                type="button"
                onClick={() => setFilter("All")}
                className="mt-3 inline-flex h-10 items-center justify-center rounded-full border border-cyan/[0.22] bg-teal/[0.08] px-4 text-sm font-semibold text-cyan"
              >
                Show all styles
              </button>
            ) : null}
          </div>
        )}
      </div>

      <FocusModal
        open={detailOpen && Boolean(selected)}
        title={selected?.label || "Style"}
        subtitle={`${selected?.category || "Style"} · ${detailFrameLabel}`}
        width="max"
        onClose={() => setDetailOpen(false)}
      >
        {selected ? (
          <div className="grid gap-5">
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,19.5rem)] xl:items-start">
              <div className="min-w-0 rounded-[26px] border border-white/[0.08] bg-canvas-deep p-4">
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-cyan">{selected.category}</p>
                    <h3 className="mt-1 text-2xl font-semibold text-white">{selected.label}</h3>
                  </div>
                  <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${selected.status === "ready" ? "border-teal/[0.25] bg-teal/[0.10] text-teal" : "border-warning/[0.25] bg-warning/[0.10] text-warning"}`}>
                    <BadgeCheck className="h-3.5 w-3.5" />
                    {friendlyTemplateStatus(selected.status)}
                  </span>
                </div>
                <div>
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Live preview</p>
                    {selected.preview_status === "generating" ? (
                      <p className="text-[11px] font-medium text-amber-300/90">First open may generate a 15s sample clip</p>
                    ) : null}
                    <div className="inline-flex items-center rounded-[14px] border border-white/[0.10] bg-black/30 p-0.5">
                      <button
                        type="button"
                        onClick={() => setFrame("short")}
                        aria-pressed={frame === "short"}
                        className={`inline-flex h-8 items-center gap-1.5 rounded-[11px] px-3 text-xs font-semibold transition ${
                          frame === "short" ? "bg-cyan text-ink" : "text-zinc-400 hover:text-white"
                        }`}
                      >
                        <Smartphone className="h-3.5 w-3.5" />
                        9:16
                      </button>
                      <button
                        type="button"
                        onClick={() => setFrame("long")}
                        aria-pressed={frame === "long"}
                        className={`inline-flex h-8 items-center gap-1.5 rounded-[11px] px-3 text-xs font-semibold transition ${
                          frame === "long" ? "bg-cyan text-ink" : "text-zinc-400 hover:text-white"
                        }`}
                      >
                        <Monitor className="h-3.5 w-3.5" />
                        16:9
                      </button>
                    </div>
                  </div>
                  <div className={`relative flex w-full items-center justify-center overflow-hidden rounded-[24px] border border-white/[0.04] bg-[#030304] p-3 shadow-inner ${
                    frame === "long" ? "h-[min(48vh,460px)] min-h-[14rem]" : "h-[min(62vh,540px)] min-h-[22rem]"
                  }`}>
                    <TemplatePreview template={selected} frame={frame} spacing="none" />
                  </div>
                </div>
              </div>

              <aside className="grid gap-4 rounded-[26px] border border-white/[0.08] bg-canvas-deep p-4 xl:sticky xl:top-6">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Best for</p>
                  <p className="mt-2 text-base leading-7 text-zinc-200">{selected.best_for}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Tone</p>
                  <p className="mt-2 text-sm leading-6 text-zinc-300">{selected.tone}</p>
                </div>
                <div className="rounded-[20px] border border-cyan/[0.14] bg-teal/[0.06] p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-cyan">Make it your own</p>
                  <p className="mt-2 text-sm leading-6 text-zinc-400">Open Brand Builder to adjust captions, effects, typography, colors, and watermark placement.</p>
                </div>
                <div className="grid gap-2">
                  <button data-autofocus type="button" disabled={!ready} onClick={() => onUse(selected.id)} className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-cyan px-4 text-sm font-semibold text-ink shadow-[0_12px_28px_rgba(102,232,249,0.18)] disabled:cursor-not-allowed disabled:opacity-45">
                    <Wand2 className="h-4 w-4" />
                    Use in Create
                  </button>
                  <button type="button" onClick={() => onCustomize(selected.id)} className="inline-flex h-11 items-center justify-center gap-2 rounded-full border border-cyan/[0.20] bg-teal/[0.08] px-4 text-sm font-semibold text-cyan">
                    <Settings className="h-4 w-4" />
                    Customize Brand
                  </button>
                  <button type="button" onClick={() => onSetDefault(selected.id)} className="inline-flex h-9 items-center justify-center gap-2 rounded-full px-4 text-xs font-semibold text-zinc-400 transition hover:bg-white/[0.04] hover:text-white">
                    <Sparkles className="h-4 w-4" />
                    Set default
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {renderSettingTile("Caption", selected.caption_style)}
                  {renderSettingTile("Styles", ready ? "Ready" : "Unavailable")}
                  {renderSettingTile("Parts", `${catalogReady} available`)}
                  {renderSettingTile("Format", frame === "long" ? "16:9" : "9:16")}
                </div>
              </aside>
            </div>

            <details className="group rounded-[24px] border border-white/[0.06] bg-black/15">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 p-5 marker:hidden">
                <span className="flex items-center gap-2 text-sm font-semibold text-cyan">
                <Layers3 className="h-4 w-4 text-cyan" />
                  Technical recipe
                </span>
                <ChevronRight className="h-4 w-4 text-zinc-500 transition-transform group-open:rotate-90" />
              </summary>
              <div className="border-t border-white/[0.06] p-5">
                <p className="text-xs text-zinc-500">Fonts, motion, effects, and content modules used by this style.</p>
                {selectedRecipe ? (
                  <dl className="mt-4 grid gap-2 rounded-[18px] border border-white/[0.08] bg-black/20 p-3 text-xs text-zinc-300 sm:grid-cols-2">
                    <div className="flex justify-between gap-3"><dt className="text-zinc-500">Font</dt><dd className="text-right font-semibold text-white">{selected.font_family || selectedRecipe.fontFamily}</dd></div>
                    <div className="flex justify-between gap-3"><dt className="text-zinc-500">Caption style</dt><dd className="text-right font-semibold text-white">{selected.caption_style || selectedRecipe.captionStyle}</dd></div>
                    <div className="flex justify-between gap-3"><dt className="text-zinc-500">Motion</dt><dd className="text-right font-semibold text-white">{selected.motion_preset || selectedRecipe.motionPreset}</dd></div>
                    <div className="flex justify-between gap-3"><dt className="text-zinc-500">Color</dt><dd className="text-right font-semibold text-white">{selected.color_grade || selectedRecipe.colorGrade}</dd></div>
                  </dl>
                ) : null}
                <div className="mt-4 grid gap-5 sm:grid-cols-3">
                <div>
                  <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-zinc-500">Effects</p>
                  <div className="flex flex-wrap gap-1.5">
                    {selected.effects.map((effect) => (
                      <span key={effect} className="rounded-full border border-cyan/15 bg-cyan/[0.04] px-2.5 py-1 text-xs text-cyan font-medium">
                        {effect}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-zinc-500">Modules</p>
                  <div className="flex flex-wrap gap-1.5">
                    {[...(selected.components_used || []), ...(selected.blocks_used || [])].slice(0, 8).map((item) => (
                      <span key={item} className="rounded-full border border-white/5 bg-white/[0.03] px-2.5 py-1 text-xs text-zinc-400">
                        {item}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-zinc-500">Content types</p>
                  <div className="flex flex-wrap gap-1.5">
                    {selected.default_genres.map((genre) => (
                      <span key={genre} className="rounded-full border border-white/5 bg-white/[0.03] px-2.5 py-1 text-xs text-zinc-400">
                        {genre}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
              </div>
            </details>
          </div>
        ) : (
          renderEmptyState("No styles loaded", "Refresh after restarting the media engine backend.")
        )}
      </FocusModal>
    </section>
  );
}

function InsightTile({label, value, detail, highlight = false}: {label: string; value: string; detail: string; highlight?: boolean}) {
  return (
    <div
      className={`rounded-[18px] border p-3 ${
        highlight ? "border-cyan/[0.28] bg-teal/[0.10]" : "border-white/[0.08] bg-black/20"
      }`}
    >
      <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="mt-1 truncate text-lg font-semibold text-white">{value}</p>
      <p className="mt-0.5 line-clamp-2 text-[11px] leading-4 text-zinc-500">{detail}</p>
    </div>
  );
}

function TemplateStatusBadge({status, label, active}: {status: string; label: string; active?: boolean}) {
  if (active) {
    return (
      <span className="shrink-0 rounded-full border border-cyan/[0.35] bg-cyan/[0.14] px-2 py-0.5 text-[10px] font-semibold leading-none text-cyan">
        {label}
      </span>
    );
  }
  return (
    <span
      className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold leading-none ${
        status === "ready" || status === "production-ready"
          ? "border-teal/[0.25] bg-teal/[0.10] text-teal"
          : "border-warning/[0.25] bg-warning/[0.10] text-warning"
      }`}
    >
      {label}
    </span>
  );
}
