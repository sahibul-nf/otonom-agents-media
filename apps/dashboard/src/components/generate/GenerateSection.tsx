"use client";

import {ArrowRight, BadgeCheck, CheckCircle2, ChevronDown, Copy, Loader2, Sparkles, Youtube} from "lucide-react";
import {useEffect, useRef, useState, type Dispatch, type ReactNode, type SetStateAction} from "react";
import {FocusModal} from "@/components/FocusModal";
import {TemplatePreview} from "@/components/templates/TemplatePreview";
import {SlideToConfirm} from "@/components/shared/SlideToConfirm";
import {apiGet, type SourceResolveResult} from "@/lib/media-api";
import {
  type ActionUiState,
  type BrandTemplate,
  type DurationPreset,
  type EngineHealth,
  type GenerationJob,
  type GenreOption,
  type HyperframesCatalog,
  type HyperframesTemplate,
} from "./types";

type GenerateConfigLike = {
  sourceUrl: string;
  count: number;
  clipLength: string;
  clipMinSeconds: number;
  clipMaxSeconds: number;
  genres: string[];
  renderer: string;
  hyperframesTemplate: string;
  hyperframesFormat: string;
  brandSystemTemplateId: string;
  brandTemplate: string;
  captionSource: string;
  speechLanguage: string;
  transcriptLanguages: string;
  llmProvider: string;
  quality: string;
};

type ReadinessLineComponent = (props: {ready: boolean; label: string; detail: string}) => ReactNode;

type SelectTileOption = string | {value: string; label: string; disabled?: boolean};

function clipCountLabel(count: number) {
  return `${count} ${count === 1 ? "clip" : "clips"}`;
}

function humanizeGenerationError(error?: string) {
  if (!error) return "";
  const lower = error.toLowerCase();
  if (lower.includes("transcript is too short")) {
    return "This video’s transcript is too short to pick strong clip candidates. Try a longer source video.";
  }
  if (lower.includes("no transcript") || lower.includes("captions unavailable")) {
    return "No usable captions or transcript were found for this video. Try another source or enable captions.";
  }
  if (lower.includes("connection") || lower.includes("offline") || lower.includes("refused")) {
    return "Couldn’t reach the media engine. Make sure the backend is running, then try again.";
  }
  return error.replace(/^(ValueError|RuntimeError|Exception|Error):\s*/i, "").trim() || error;
}

function runStatusLabel(status: string) {
  switch (status) {
    case "completed":
      return "Ready for review";
    case "running":
    case "queued":
      return "Creating clips";
    case "failed":
      return "Failed";
    default:
      return status.replaceAll("_", " ");
  }
}

function formatSourceDuration(seconds?: number | null) {
  if (seconds == null || !Number.isFinite(seconds) || seconds <= 0) return "";
  const total = Math.round(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = total % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${rest}s`;
  return `${rest}s`;
}

function looksLikeYoutubeUrl(value: string) {
  const raw = value.trim().toLowerCase();
  if (!raw) return false;
  return raw.includes("youtube.com") || raw.includes("youtu.be");
}

export function GenerateSection<T extends GenerateConfigLike>({
  config,
  templates,
  hyperframesTemplates,
  hyperframesCatalog: _hyperframesCatalog,
  durationPresets,
  genres,
  jobs,
  engineHealth,
  actionState,
  setConfig,
  command,
  defaultTemplatePath,
  statusTone,
  onGenerate,
  onOpenReview,
  onCopy,
  renderReadinessLine,
  renderActionStatus,
  renderEmptyState,
}: {
  config: T;
  templates: BrandTemplate[];
  hyperframesTemplates: HyperframesTemplate[];
  hyperframesCatalog: HyperframesCatalog | null;
  durationPresets: DurationPreset[];
  genres: GenreOption[];
  jobs: GenerationJob[];
  engineHealth: EngineHealth | null;
  actionState?: ActionUiState;
  setConfig: Dispatch<SetStateAction<T>>;
  command: string;
  defaultTemplatePath: string;
  statusTone: (status: string) => string;
  onGenerate: (source?: SourceResolveResult | null) => void;
  onOpenReview: () => void;
  onCopy: () => void;
  renderReadinessLine: ReadinessLineComponent;
  renderActionStatus: (state?: ActionUiState) => ReactNode;
  renderEmptyState: (title: string, text: string) => ReactNode;
}) {
  const latest = jobs[0];
  const isStarting = actionState?.status === "running";
  const [templatePickerOpen, setTemplatePickerOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [resolveState, setResolveState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [resolvedSource, setResolvedSource] = useState<SourceResolveResult | null>(null);
  const [resolveError, setResolveError] = useState("");
  const resolveRequestId = useRef(0);
  const update = (patch: Partial<GenerateConfigLike>) => setConfig((current) => ({...current, ...patch}));

  useEffect(() => {
    const url = config.sourceUrl.trim();
    if (!url) {
      setResolveState("idle");
      setResolvedSource(null);
      setResolveError("");
      return;
    }
    if (!looksLikeYoutubeUrl(url)) {
      setResolveState("error");
      setResolvedSource(null);
      setResolveError("Paste a full YouTube video link (youtube.com or youtu.be).");
      return;
    }

    const requestId = ++resolveRequestId.current;
    setResolveState("loading");
    setResolveError("");
    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          const payload = await apiGet<SourceResolveResult>(`resolve-source?url=${encodeURIComponent(url)}`);
          if (requestId !== resolveRequestId.current) return;
          if (!payload?.ok) {
            setResolveState("error");
            setResolvedSource(null);
            setResolveError(payload?.error || "Couldn’t validate this YouTube link.");
            return;
          }
          setResolvedSource(payload);
          setResolveState("ready");
          setResolveError("");
        } catch (error) {
          if (requestId !== resolveRequestId.current) return;
          setResolveState("error");
          setResolvedSource(null);
          setResolveError(error instanceof Error ? error.message : "Couldn’t validate this YouTube link.");
        }
      })();
    }, 550);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only re-resolve when the pasted URL changes
  }, [config.sourceUrl]);

  const canGenerate = Boolean(config.sourceUrl.trim()) && resolveState === "ready" && Boolean(resolvedSource?.ok);
  const presetOptions = durationPresets.length ? durationPresets : [{id: "auto", label: "Auto (0-3 min)", detail: "20-180s", range_label: "0-3 min", best_for: "General use", min_ms: 20_000, target_ms: 90_000, max_ms: 180_000, intent: "Automatic duration"}];
  const genreOptions = genres.length ? genres : [
    {id: "kajian", label: "Kajian", description: "Religious teaching and reflection."},
    {id: "spiritual_reflection", label: "Spiritual reflection", description: "Heart-softening clips."},
    {id: "advice", label: "Advice", description: "Practical reminders."},
  ];
  const selectedPreset = presetOptions.find((item) => item.id === config.clipLength) || presetOptions[0];
  const hyperframesTemplateOptions = [
    {value: "auto", label: "Auto by niche"},
    ...hyperframesTemplates.map((template) => ({value: template.id, label: template.label})),
  ];
  const selectedTemplate = hyperframesTemplates.find((template) => template.id === config.hyperframesTemplate);
  const latestProgress = Math.max(0, Math.min(100, latest?.progress || 0));
  const selectedGenreCount = genreOptions.filter((genre) => config.genres.includes(genre.id)).length;
  const toggleGenre = (id: string) => {
    const next = config.genres.includes(id) ? config.genres.filter((item) => item !== id) : [...config.genres, id];
    update({genres: next.length ? next : [id]});
  };

  return (
    <section className="grid w-full min-w-0 gap-5">
      <div className="min-w-0 rounded-[28px] border border-white/[0.08] bg-surface p-4 shadow-[0_0_0_1px_rgba(102,232,249,0.04)] sm:rounded-[32px] sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan">New clip batch</p>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-400">Paste a YouTube link. Results wait in Review before publishing.</p>
          </div>
          <div className="flex shrink-0 items-center gap-2 rounded-full border border-white/[0.08] bg-canvas-deep px-3 py-2 text-xs">
            <span className="font-semibold text-white">{clipCountLabel(config.count)}</span>
            <span className="text-zinc-600">·</span>
            <span className="text-zinc-400">{config.clipMinSeconds}–{config.clipMaxSeconds}s</span>
          </div>
        </div>

        <div className="mt-6 grid gap-5">
          <div className="rounded-[24px] border border-cyan/[0.18] bg-teal/[0.07] p-4">
            <label className="grid min-w-0 gap-2 text-sm font-medium text-zinc-300">
              <span>YouTube link</span>
              <div className="relative flex items-center">
                <input
                  value={config.sourceUrl}
                  onChange={(event) => update({sourceUrl: event.target.value})}
                  className="h-12 w-full rounded-full border border-white/[0.08] bg-black/24 pl-11 pr-4 text-sm text-zinc-200 outline-none transition focus:border-cyan/[0.30] focus:ring-1 focus:ring-cyan/[0.30]"
                  placeholder="https://youtube.com/watch?v=…"
                />
                <span className="absolute left-4 text-zinc-500">
                  <Youtube className="h-4 w-4" />
                </span>
              </div>
            </label>

            {resolveState === "loading" ? (
              <div className="mt-3 inline-flex items-center gap-2 text-xs font-medium text-zinc-400">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan" />
                Checking video…
              </div>
            ) : null}

            {resolveState === "error" && resolveError ? (
              <p className="mt-3 text-sm leading-6 text-danger">{resolveError}</p>
            ) : null}

            {resolveState === "ready" && resolvedSource ? (
              <div className="mt-3 flex gap-3 rounded-[18px] border border-white/[0.08] bg-black/25 p-3">
                {resolvedSource.thumbnail_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={resolvedSource.thumbnail_url}
                    alt=""
                    className="h-16 w-28 shrink-0 rounded-xl object-cover bg-black/40"
                  />
                ) : (
                  <div className="grid h-16 w-28 shrink-0 place-items-center rounded-xl bg-black/40 text-zinc-600">
                    <Youtube className="h-5 w-5" />
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-white">{resolvedSource.title || "YouTube video"}</p>
                  <p className="mt-1 truncate text-xs text-zinc-400">
                    {[resolvedSource.channel, formatSourceDuration(resolvedSource.duration_seconds)].filter(Boolean).join(" · ")}
                  </p>
                  {resolvedSource.warnings?.length ? (
                    <p className="mt-2 text-xs leading-5 text-warning">{resolvedSource.warnings[0]}</p>
                  ) : (
                    <p className="mt-2 text-xs text-teal">Ready to generate</p>
                  )}
                </div>
              </div>
            ) : null}

            <div className="mt-4">
              <span className="text-sm font-medium text-zinc-300">How many clips?</span>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {[1, 2, 3, 5, 8, 10].map((val) => {
                  const active = config.count === val;
                  return (
                    <button
                      key={val}
                      type="button"
                      onClick={() => update({count: val})}
                      className={`h-9 rounded-full px-3.5 text-xs font-semibold transition ${
                        active
                          ? "bg-cyan text-ink shadow-[0_4px_12px_rgba(102,232,249,0.2)]"
                          : "border border-white/[0.08] bg-black/24 text-zinc-400 hover:border-white/[0.16] hover:text-white"
                      }`}
                    >
                      {val}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="mt-5 grid gap-3">
              <SlideToConfirm
                label="Slide to generate"
                activeLabel="Starting…"
                onConfirm={() => onGenerate(resolvedSource)}
                isLoading={isStarting}
                disabled={!canGenerate || isStarting}
              />
              {resolveState === "loading" ? (
                <p className="text-xs text-zinc-500">Validate the link before generating.</p>
              ) : null}
              {renderActionStatus(actionState)}
            </div>
          </div>

          {latest ? (
            <div className="grid gap-4 rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4" aria-live="polite">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-zinc-500">Current run</p>
                  <p className="mt-1 text-sm font-semibold text-white">{clipCountLabel(latest.count)}</p>
                </div>
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusTone(latest.status)}`}>
                  {runStatusLabel(latest.status)}
                </span>
              </div>
              <div>
                <div className="mb-2 flex items-center justify-between text-xs text-zinc-500">
                  <span>
                    {latest.status === "completed"
                      ? "Generation complete"
                      : latest.status === "failed"
                        ? "Stopped"
                        : "Processing source"}
                  </span>
                  <span className="font-semibold tabular-nums text-cyan">{latestProgress}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-surface-strong">
                  <div className="h-full rounded-full bg-cyan transition-[width] duration-500 motion-reduce:transition-none" style={{width: `${Math.max(4, latestProgress)}%`}} />
                </div>
              </div>
              {latest.error ? <p className="text-sm leading-6 text-danger">{humanizeGenerationError(latest.error)}</p> : null}
              {latest.status === "completed" ? (
                <button type="button" onClick={onOpenReview} className="inline-flex w-fit items-center gap-2 rounded-full bg-cyan px-4 py-2 text-sm font-semibold text-ink transition hover:bg-cyan/90">
                  Review clips <ArrowRight className="h-4 w-4" />
                </button>
              ) : null}
              {(latest.error || latest.log_text) && (
                <details>
                  <summary className="cursor-pointer list-none text-xs font-semibold text-zinc-500 hover:text-zinc-300">Technical details</summary>
                  <pre className="mt-3 max-h-52 overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-black/40 p-3 text-[11px] leading-5 text-zinc-400">{latest.error || latest.log_text || "Waiting…"}</pre>
                </details>
              )}
            </div>
          ) : null}

          <details
            className="rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4"
            open={advancedOpen}
            onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}
          >
            <summary className="cursor-pointer list-none text-sm font-semibold text-zinc-200">
              Advanced
              <span className="ml-2 text-xs font-medium text-zinc-500">
                style · duration · genres · brand
              </span>
            </summary>

            <div className="mt-4 grid gap-5 border-t border-white/[0.06] pt-4">
              <div>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h4 className="font-semibold text-white">Visual style</h4>
                  <button
                    type="button"
                    onClick={() => setTemplatePickerOpen(true)}
                    className="inline-flex h-9 items-center gap-2 rounded-full border border-cyan/[0.24] bg-black/20 px-3 text-xs font-semibold text-cyan"
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    Browse
                  </button>
                </div>
                <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_170px]">
                  <SelectTile
                    label="Template"
                    value={config.hyperframesTemplate}
                    options={hyperframesTemplateOptions}
                    onChange={(value) => {
                      const picked = hyperframesTemplates.find((template) => template.id === value);
                      update({
                        renderer: "hyperframes",
                        hyperframesTemplate: value,
                        brandSystemTemplateId: picked?.source === "brand_system" ? value : "",
                        brandTemplate: picked?.brand_template_path || config.brandTemplate,
                      });
                    }}
                  />
                  <SelectTile
                    label="Format"
                    value={config.hyperframesFormat}
                    options={[
                      {value: "short_9_16", label: "Short 9:16"},
                      {value: "long_16_9", label: "Long 16:9"},
                      {value: "auto", label: "Auto"},
                    ]}
                    onChange={(value) => update({hyperframesFormat: value})}
                  />
                </div>
              </div>

              <div>
                <h4 className="mb-3 font-semibold text-white">Clip length</h4>
                <div className="grid gap-2 sm:grid-cols-2">
                  {presetOptions.map((preset) => {
                    const active = config.clipLength === preset.id;
                    return (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => {
                          update({
                            clipLength: preset.id,
                            clipMinSeconds: Math.round(preset.min_ms / 1000),
                            clipMaxSeconds: Math.round(preset.max_ms / 1000),
                          });
                        }}
                        className={`flex flex-col rounded-2xl border p-3 text-left transition ${
                          active
                            ? "border-cyan/[0.50] bg-cyan/[0.05]"
                            : "border-white/[0.08] bg-black/24 hover:border-white/[0.16]"
                        }`}
                      >
                        <span className={`text-xs font-semibold ${active ? "text-cyan" : "text-white"}`}>{preset.label}</span>
                        <span className="mt-1 text-[11px] leading-4 text-zinc-500">{preset.detail}</span>
                      </button>
                    );
                  })}
                </div>
                <p className="mt-2 text-xs text-zinc-500">
                  Using <span className="text-zinc-300">{selectedPreset?.label}</span> ({config.clipMinSeconds}–{config.clipMaxSeconds}s).
                </p>
              </div>

              <div>
                <div className="mb-3 flex items-center justify-between">
                  <h4 className="font-semibold text-white">Content angles</h4>
                  <span className="text-xs text-zinc-500">{selectedGenreCount} selected</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {genreOptions.map((genre) => {
                    const active = config.genres.includes(genre.id);
                    return (
                      <button
                        key={genre.id}
                        type="button"
                        onClick={() => toggleGenre(genre.id)}
                        className={`inline-flex min-h-10 items-center gap-2 rounded-full border px-3 py-2 text-sm font-semibold transition ${active ? "border-cyan bg-teal/[0.16] text-white" : "border-white/[0.08] bg-black/24 text-zinc-400 hover:border-white/[0.16] hover:text-white"}`}
                        aria-pressed={active}
                        title={genre.description}
                      >
                        {active ? <BadgeCheck className="h-4 w-4 text-cyan" /> : null}
                        {genre.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <h4 className="mb-3 font-semibold text-white">Brand</h4>
                <div className="grid gap-2 sm:grid-cols-2">
                  {(templates.length ? templates : [{id: "default", label: "Default Workspace Style", path: defaultTemplatePath}]).map((template) => {
                    const active = config.brandTemplate === template.path;
                    return (
                      <button
                        key={template.id}
                        type="button"
                        onClick={() => update({brandTemplate: template.path})}
                        className={`flex items-center justify-between rounded-xl border px-4 py-3 text-left transition ${
                          active
                            ? "border-cyan bg-cyan/[0.05] text-white"
                            : "border-white/[0.08] bg-black/24 text-zinc-400 hover:border-white/[0.16] hover:text-white"
                        }`}
                      >
                        <span className="text-xs font-semibold">{template.label}</span>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${active ? "bg-cyan text-ink" : "bg-white/[0.08] text-zinc-500"}`}>
                          {active ? "On" : "Use"}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <details className="rounded-[20px] border border-white/[0.06] bg-black/20 p-4">
                <summary className="cursor-pointer list-none text-sm font-semibold text-zinc-400">
                  Developer options
                  <span className="ml-2 text-xs font-medium text-zinc-600">captions · model · CLI</span>
                </summary>
                <div className="mt-4 grid gap-4 border-t border-white/[0.06] pt-4">
                  <div className="grid gap-2 text-xs sm:grid-cols-2">
                    {renderReadinessLine({
                      ready: Boolean(engineHealth?.hyperframes.ready),
                      label: "Visual engine",
                      detail: engineHealth?.hyperframes.ready ? "Ready" : "Check required",
                    })}
                    {renderReadinessLine({
                      ready: Boolean(selectedTemplate || config.hyperframesTemplate === "auto"),
                      label: "Template",
                      detail: selectedTemplate?.label || "Auto",
                    })}
                  </div>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <SelectTile label="Captions" value={config.captionSource} options={["whisper", "hybrid", "youtube"]} onChange={(value) => update({captionSource: value})} />
                    <SelectTile label="Speech language" value={config.speechLanguage} options={["id", "ar", "en", "ms"]} onChange={(value) => update({speechLanguage: value})} />
                    <SelectTile label="Transcripts" value={config.transcriptLanguages} options={["id,en", "id", "en,id", "ar,id", "ms,id"]} onChange={(value) => update({transcriptLanguages: value})} />
                    <SelectTile label="Writing model" value={config.llmProvider} options={["deepseek", "openai", "groq", "none"]} onChange={(value) => update({llmProvider: value})} />
                    <SelectTile label="Quality" value={config.quality} options={["production", "draft"]} onChange={(value) => update({quality: value})} />
                  </div>
                  <div className="rounded-[16px] border border-white/[0.06] bg-canvas-deep/60 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <h4 className="text-sm font-semibold text-white">Run outside the app</h4>
                        <p className="mt-1 text-xs text-zinc-500">Copy the CLI command only if you need it.</p>
                      </div>
                      <button type="button" onClick={onCopy} className="inline-flex w-fit rounded-full border border-white/[0.10] bg-white/[0.04] px-4 py-2 text-sm font-semibold text-zinc-200 hover:border-cyan/30 hover:text-cyan">
                        <Copy className="mr-2 h-4 w-4" /> Copy
                      </button>
                    </div>
                    <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap break-words rounded-2xl border border-white/[0.06] bg-black/40 p-3 text-[11px] leading-5 text-zinc-500">{command}</pre>
                  </div>
                </div>
              </details>
            </div>
          </details>
        </div>
      </div>

      {!latest ? renderEmptyState("Ready when you are", "Paste a YouTube link above to create your first clip batch.") : null}

      <FocusModal open={templatePickerOpen} title="Choose video template" subtitle="Pick a visual style before generating clips." width="wide" onClose={() => setTemplatePickerOpen(false)}>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {hyperframesTemplates.map((template) => {
            const active = config.hyperframesTemplate === template.id;
            return (
              <button
                key={template.id}
                type="button"
                onClick={() => {
                  update({
                    renderer: "hyperframes",
                    hyperframesTemplate: template.id,
                    brandSystemTemplateId: template.source === "brand_system" ? template.id : "",
                    brandTemplate: template.brand_template_path || config.brandTemplate,
                  });
                  setTemplatePickerOpen(false);
                }}
                className={`template-card min-w-0 rounded-[20px] border p-2.5 text-left transition sm:p-3 ${active ? "border-cyan/[0.45] bg-teal/[0.12] shadow-glow" : "border-white/[0.08] bg-canvas-deep hover:border-cyan/[0.22] hover:bg-teal/[0.05]"}`}
              >
                <TemplatePreview
                  template={template}
                  compact
                  gridCard
                  hideFooterLabel
                  frame={config.hyperframesFormat === "long_16_9" ? "long" : "short"}
                  hoverToPlay
                />
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase tracking-wide text-cyan">{template.category}</p>
                    <h4 className="mt-1 truncate text-lg font-semibold text-white">{template.label}</h4>
                  </div>
                  {active ? <CheckCircle2 className="h-4 w-4 shrink-0 text-cyan" /> : null}
                </div>
                <p className="mt-2 line-clamp-2 text-sm leading-6 text-zinc-400">{template.best_for}</p>
              </button>
            );
          })}
        </div>
      </FocusModal>
    </section>
  );
}

function SelectTile({label, value, options, onChange}: {label: string; value: string; options: SelectTileOption[]; onChange: (value: string) => void}) {
  return (
    <label className="relative grid gap-1.5 rounded-[22px] border border-white/[0.08] bg-canvas-deep p-3 text-xs font-semibold uppercase tracking-wide text-zinc-500 transition-all focus-within:border-cyan/[0.30] hover:border-white/[0.14]">
      {label}
      <div className="relative flex items-center">
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full appearance-none cursor-pointer bg-transparent text-sm font-semibold normal-case tracking-normal text-white outline-none pr-8"
        >
          {options.map((option) => {
            const item = typeof option === "string" ? {value: option, label: option, disabled: false} : option;
            return (
              <option key={item.value} value={item.value} disabled={item.disabled} className="bg-[#17171a] text-white">
                {item.label}
              </option>
            );
          })}
        </select>
        <span className="absolute right-1 pointer-events-none text-zinc-500">
          <ChevronDown className="h-4 w-4" />
        </span>
      </div>
    </label>
  );
}
