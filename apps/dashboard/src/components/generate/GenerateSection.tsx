"use client";

import {ArrowRight, BadgeCheck, CheckCircle2, ChevronDown, Copy, Loader2, Sparkles, Youtube} from "lucide-react";
import {useEffect, useMemo, useRef, useState, type Dispatch, type ReactNode, type SetStateAction} from "react";
import {FocusModal} from "@/components/FocusModal";
import {TemplatePreview} from "@/components/templates/TemplatePreview";
import {SlideToConfirm} from "@/components/shared/SlideToConfirm";
import {apiGet, templateSupportsFormat, type ShellComponents, DEFAULT_SHELL_COMPONENTS, isTemplateOnlyBrand, TEMPLATE_ONLY_BRAND, type SourceResolveResult} from "@/lib/media-api";
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

const GENRE_AUTO = "auto";

function genresIsAuto(genres: string[]) {
  return genres.includes(GENRE_AUTO);
}

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
  curationSource: string;
  speechLanguage: string;
  transcriptLanguages: string;
  llmProvider: string;
  quality: string;
  shellComponents: ShellComponents;
};

function shellComponentsFromTemplate(template?: HyperframesTemplate): ShellComponents {
  return template?.shell_components
    ? {...DEFAULT_SHELL_COMPONENTS, ...template.shell_components}
    : {...DEFAULT_SHELL_COMPONENTS};
}

function ShellComponentToggle({
  label,
  detail,
  enabled,
  onChange,
}: {
  label: string;
  detail: string;
  enabled: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!enabled)}
      className={`flex flex-col rounded-2xl border p-3 text-left transition ${
        enabled
          ? "border-cyan/[0.50] bg-cyan/[0.05] text-white"
          : "border-white/[0.08] bg-black/24 text-zinc-400 hover:border-white/[0.16] hover:text-white"
      }`}
      aria-pressed={enabled}
    >
      <span className="text-xs font-semibold">{label}</span>
      <span className="mt-1 text-[11px] leading-4 text-zinc-500">{detail}</span>
      <span className={`mt-2 w-fit rounded-full px-2 py-0.5 text-[10px] font-bold ${enabled ? "bg-cyan text-ink" : "bg-white/[0.08] text-zinc-500"}`}>
        {enabled ? "On" : "Off"}
      </span>
    </button>
  );
}

type ReadinessLineComponent = (props: {ready: boolean; label: string; detail: string}) => ReactNode;

type SelectTileOption = string | {value: string; label: string; disabled?: boolean};

function transcriptStatusLabel(status?: string) {
  switch (status) {
    case "available":
      return "Captions ready";
    case "missing":
      return "No captions yet";
    case "disabled":
      return "Captions disabled";
    case "restricted":
      return "Captions restricted";
    default:
      return "Captions unknown";
  }
}

function transcriptStatusTone(status?: string) {
  switch (status) {
    case "available":
      return "border-success/30 bg-success/[0.08] text-success";
    case "missing":
      return "border-warning/30 bg-warning/[0.08] text-warning";
    case "disabled":
    case "restricted":
      return "border-danger/30 bg-danger/[0.08] text-danger";
    default:
      return "border-white/[0.10] bg-white/[0.04] text-zinc-400";
  }
}

function clipCountLabel(count: number) {
  return `${count} ${count === 1 ? "clip" : "clips"}`;
}

function producedClipCount(job: GenerationJob) {
  const produced = job.result?.count;
  return typeof produced === "number" && produced >= 0 ? produced : job.count;
}

function humanizeGenerationError(error?: string) {
  if (!error) return "";
  const lower = error.toLowerCase();
  if (lower.includes("transcript is too short")) {
    return "This video’s transcript is too short to pick strong clip candidates. Try a longer source video.";
  }
  if (
    lower.includes("did not produce enough valid") ||
    lower.includes("no valid clip suggestions") ||
    lower.includes("no candidate windows") ||
    lower.includes("couldn't find a usable clip")
  ) {
    return "Couldn’t find a usable clip in this video. Try a longer source or a looser duration. How many clips is a maximum — one clip is still a successful run.";
  }
  if (lower.includes("no transcript") || lower.includes("captions unavailable") || lower.includes("no youtube subtitles") || lower.includes("transcribe from audio") || lower.includes("github.com/jdepoix/youtube-transcript-api")) {
    return "No YouTube subtitles are available for this video yet. Fresh live replays often need 12–48 hours for auto-captions. Use Transcribe from audio when creating clips.";
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
  genrePackLabel,
  jobs,
  engineHealth,
  actionState,
  setConfig,
  command,
  defaultTemplatePath,
  statusTone,
  onGenerate,
  onOpenReview,
  onOpenBrand,
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
  genrePackLabel?: string;
  jobs: GenerationJob[];
  engineHealth: EngineHealth | null;
  actionState?: ActionUiState;
  setConfig: Dispatch<SetStateAction<T>>;
  command: string;
  defaultTemplatePath: string;
  statusTone: (status: string) => string;
  onGenerate: (source?: SourceResolveResult | null) => void;
  onOpenReview: () => void;
  onOpenBrand?: () => void;
  onCopy: () => void;
  renderReadinessLine: ReadinessLineComponent;
  renderActionStatus: (state?: ActionUiState) => ReactNode;
  renderEmptyState: (title: string, text: string) => ReactNode;
}) {
  const latest = jobs[0];
  const hasActiveJob = jobs.some((job) => job.status === "queued" || job.status === "running");
  const isStarting = actionState?.status === "running" || hasActiveJob;
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

  const canGenerate = Boolean(config.sourceUrl.trim()) && resolveState === "ready" && Boolean(resolvedSource?.ok)
    && !(resolvedSource?.transcript?.status && resolvedSource.transcript.status !== "available" && config.curationSource === "youtube");
  const transcriptStatus = resolvedSource?.transcript?.status;
  const needsAudioCuration = transcriptStatus && transcriptStatus !== "available" && config.curationSource !== "audio";
  const presetOptions = durationPresets.length ? durationPresets : [{id: "auto", label: "Auto (0-3 min)", detail: "20-180s", range_label: "0-3 min", best_for: "General use", min_ms: 20_000, target_ms: 90_000, max_ms: 180_000, intent: "Automatic duration"}];
  const genreOptions = genres.length ? genres : [
    {id: "story", label: "Story", description: "Narrative moments and analogies."},
    {id: "advice", label: "Advice", description: "Practical takeaways."},
    {id: "social_commentary", label: "Social commentary", description: "Culture and public habits."},
  ];
  const selectedPreset = presetOptions.find((item) => item.id === config.clipLength) || presetOptions[0];
  const formatKey = config.hyperframesFormat === "long_16_9" ? "long_16_9" : "short_9_16";
  const templatesForFormat = useMemo(
    () => hyperframesTemplates.filter((template) => templateSupportsFormat(template, formatKey)),
    [hyperframesTemplates, formatKey],
  );
  useEffect(() => {
    if (config.hyperframesTemplate === "auto") return;
    if (!templatesForFormat.some((template) => template.id === config.hyperframesTemplate)) {
      update({hyperframesTemplate: "auto"});
    }
  }, [config.hyperframesTemplate, templatesForFormat, update]);
  const hyperframesTemplateOptions = [
    {value: "auto", label: "Auto by niche"},
    ...templatesForFormat.map((template) => ({value: template.id, label: template.label})),
  ];
  const selectedTemplate = templatesForFormat.find((template) => template.id === config.hyperframesTemplate)
    ?? hyperframesTemplates.find((template) => template.id === config.hyperframesTemplate);
  const savedBrandStyles = templates.filter((item) => /custom_/i.test(item.path));
  const templateOnlyBrand = isTemplateOnlyBrand(config.brandTemplate, defaultTemplatePath);
  const brandStyleOptions = [
    {id: "template-default", label: "Template default", path: TEMPLATE_ONLY_BRAND, has_brand_system: "0"},
    ...savedBrandStyles,
  ];
  const templateShellDefaults = shellComponentsFromTemplate(selectedTemplate);
  const latestProgress = Math.max(0, Math.min(100, latest?.progress || 0));
  const genresAuto = genresIsAuto(config.genres);
  const manualGenreCount = genreOptions.filter((genre) => config.genres.includes(genre.id)).length;
  const toggleGenre = (id: string) => {
    if (config.genres.includes(id)) {
      const next = config.genres.filter((item) => item !== id && item !== GENRE_AUTO);
      update({genres: next.length ? next : [GENRE_AUTO]});
      return;
    }
    const manual = config.genres.filter((item) => item !== GENRE_AUTO);
    update({genres: [...manual, id]});
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
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-sm font-semibold text-white">{resolvedSource.title || "YouTube video"}</p>
                    {resolvedSource.transcript?.status ? (
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${transcriptStatusTone(resolvedSource.transcript.status)}`}>
                        {transcriptStatusLabel(resolvedSource.transcript.status)}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 truncate text-xs text-zinc-400">
                    {[resolvedSource.channel, formatSourceDuration(resolvedSource.duration_seconds)].filter(Boolean).join(" · ")}
                  </p>
                  {resolvedSource.transcript?.status && resolvedSource.transcript.status !== "available" ? (
                    <p className="mt-2 text-xs leading-5 text-warning">
                      {resolvedSource.transcript.message || "No YouTube subtitles yet. Use Transcribe from audio below."}
                    </p>
                  ) : resolvedSource.warnings?.length ? (
                    <p className="mt-2 text-xs leading-5 text-warning">{resolvedSource.warnings[0]}</p>
                  ) : (
                    <p className="mt-2 text-xs text-teal">Ready to generate</p>
                  )}
                </div>
              </div>
            ) : null}

            {resolveState === "ready" && resolvedSource?.transcript?.status && resolvedSource.transcript.status !== "available" ? (
              <div className="mt-3 rounded-[18px] border border-warning/20 bg-warning/[0.05] p-3">
                <p className="text-sm font-semibold text-white">Clip selection source</p>
                <p className="mt-1 text-xs leading-5 text-zinc-400">
                  YouTube captions are not ready. Choose how the app should find clip moments before rendering.
                </p>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {[
                    {value: "auto", label: "Auto (recommended)", detail: "Try YouTube captions, then transcribe audio if missing."},
                    {value: "audio", label: "Transcribe from audio", detail: "Slower, but works without YouTube CC."},
                    {value: "youtube", label: "YouTube captions only", detail: "Fast, but requires subtitles on YouTube."},
                  ].map((option) => {
                    const active = config.curationSource === option.value;
                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => update({curationSource: option.value})}
                        className={`rounded-2xl border p-3 text-left transition ${active ? "border-cyan/[0.40] bg-cyan/[0.06]" : "border-white/[0.08] bg-black/20 hover:border-white/[0.14]"}`}
                      >
                        <span className="text-xs font-semibold text-white">{option.label}</span>
                        <span className="mt-1 block text-[11px] leading-4 text-zinc-500">{option.detail}</span>
                      </button>
                    );
                  })}
                </div>
                {config.curationSource === "youtube" ? (
                  <p className="mt-2 text-xs leading-5 text-danger">YouTube captions only is blocked until subtitles appear on this video.</p>
                ) : needsAudioCuration ? (
                  <p className="mt-2 text-xs leading-5 text-zinc-400">Audio transcription can take several minutes for long videos.</p>
                ) : null}
              </div>
            ) : null}

            <div className="mt-4">
              <span className="text-sm font-medium text-zinc-300">How many clips?</span>
              <p className="mt-1 text-xs text-zinc-500">Maximum for this batch. Fewer clips still succeed.</p>
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
            <div className="mt-5 rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <h4 className="font-semibold text-white">Visual template</h4>
                  <p className="mt-1 text-xs leading-5 text-zinc-500">
                    Layout, overlays, and motion. Caption font, watermark, and CTA overlays come from a saved brand style in Advanced.
                  </p>
                </div>
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
                    const picked = templatesForFormat.find((template) => template.id === value)
                      ?? hyperframesTemplates.find((template) => template.id === value);
                    update({
                      renderer: "hyperframes",
                      hyperframesTemplate: value,
                      brandSystemTemplateId: picked?.source === "brand_system" ? value : "",
                      brandTemplate:
                        picked?.source === "brand_system" && picked?.brand_template_path
                          ? picked.brand_template_path
                          : templateOnlyBrand
                            ? TEMPLATE_ONLY_BRAND
                            : config.brandTemplate,
                      shellComponents: shellComponentsFromTemplate(picked),
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
              {selectedTemplate ? (
                <p className="mt-2 text-xs text-zinc-500">
                  Using <span className="text-zinc-300">{selectedTemplate.label}</span>
                  {selectedTemplate.source === "brand_system" ? " · includes saved caption style" : " · set caption style in Advanced if needed"}
                </p>
              ) : config.hyperframesTemplate === "auto" ? (
                <p className="mt-2 text-xs text-zinc-500">Auto picks a recipe from your content angles and workspace niche.</p>
              ) : null}
            </div>

            <div className="mt-5 grid gap-3">
              <SlideToConfirm
                label={hasActiveJob ? "Generating…" : "Slide to generate"}
                activeLabel="Starting…"
                onConfirm={() => onGenerate(resolvedSource)}
                isLoading={isStarting}
                disabled={!canGenerate || isStarting}
              />
              {hasActiveJob ? (
                <p className="text-xs text-zinc-500">Wait for the current batch to finish before starting another.</p>
              ) : resolveState === "loading" ? (
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
                  <p className="mt-1 text-sm font-semibold text-white">
                    {latest.status === "completed"
                      ? producedClipCount(latest) < latest.count
                        ? `${clipCountLabel(producedClipCount(latest))} of ${latest.count} requested`
                        : clipCountLabel(producedClipCount(latest))
                      : `Up to ${clipCountLabel(latest.count)}`}
                  </p>
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
                duration · angles · captions
              </span>
            </summary>

            <div className="mt-4 grid gap-5 border-t border-white/[0.06] pt-4">
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
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h4 className="font-semibold text-white">Content angles</h4>
                  <span className="text-xs text-zinc-500">
                    {genresAuto ? "Auto" : `${manualGenreCount} selected`}
                    {genrePackLabel ? ` · ${genrePackLabel} pack` : ""}
                  </span>
                </div>
                <p className="mb-3 text-xs leading-5 text-zinc-500">
                  How to cut this batch. Auto lets the model pick the best angle per clip; manual chips steer the whole batch.
                </p>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => update({genres: [GENRE_AUTO]})}
                    className={`inline-flex min-h-10 items-center gap-2 rounded-full border px-3 py-2 text-sm font-semibold transition ${genresAuto ? "border-cyan bg-teal/[0.16] text-white" : "border-white/[0.08] bg-black/24 text-zinc-400 hover:border-white/[0.16] hover:text-white"}`}
                    aria-pressed={genresAuto}
                    title="Let the model pick the best content angle for each clip."
                  >
                    {genresAuto ? <BadgeCheck className="h-4 w-4 text-cyan" /> : null}
                    Auto
                  </button>
                  {genreOptions.map((genre) => {
                    const active = !genresAuto && config.genres.includes(genre.id);
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
                <div className="mb-3">
                  <h4 className="font-semibold text-white">Captions & watermark</h4>
                  <p className="mt-1 text-xs leading-5 text-zinc-500">
                    Optional — only applies when you pick a saved brand style below. Otherwise the visual template drives the look.
                  </p>
                </div>
                {savedBrandStyles.length === 0 ? (
                  <div className="rounded-2xl border border-white/[0.08] bg-black/24 p-4">
                    <p className="text-sm text-zinc-300">
                      Using <span className="font-semibold text-white">template defaults</span>
                    </p>
                    <p className="mt-1 text-xs leading-5 text-zinc-500">
                      Caption font, colors, watermark, and shell layers come from the selected visual template — no platform brand overlay.
                    </p>
                    {onOpenBrand ? (
                      <button
                        type="button"
                        onClick={onOpenBrand}
                        className="mt-3 text-xs font-semibold text-cyan transition hover:text-cyan/80"
                      >
                        Save a custom style in Brand →
                      </button>
                    ) : null}
                  </div>
                ) : (
                  <div className="grid gap-2 sm:grid-cols-2">
                    {brandStyleOptions.map((template) => {
                      const active = templateOnlyBrand
                        ? template.path === TEMPLATE_ONLY_BRAND
                        : config.brandTemplate === template.path;
                      const isTemplateDefault = template.path === TEMPLATE_ONLY_BRAND;
                      return (
                        <button
                          key={template.id}
                          type="button"
                          onClick={() => update({brandTemplate: template.path})}
                          className={`flex flex-col rounded-2xl border p-3 text-left transition ${
                            active
                              ? "border-cyan/[0.50] bg-cyan/[0.05] text-white"
                              : "border-white/[0.08] bg-black/24 text-zinc-400 hover:border-white/[0.16] hover:text-white"
                          }`}
                        >
                          <span className="flex items-center justify-between gap-2">
                            <span className="text-xs font-semibold">{template.label}</span>
                            <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${active ? "bg-cyan text-ink" : "bg-white/[0.08] text-zinc-500"}`}>
                              {active ? "Active" : "Use"}
                            </span>
                          </span>
                          {isTemplateDefault ? (
                            <span className="mt-1 text-[11px] leading-4 text-zinc-500">Recipe captions and shell only — no saved brand overlay</span>
                          ) : (
                            <span className="mt-1 text-[11px] leading-4 text-zinc-500">Saved in Brand Builder</span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              <div>
                <div className="mb-3 flex items-center justify-between">
                  <h4 className="font-semibold text-white">Shell layers</h4>
                  <span className="text-xs text-zinc-500">
                    {templateOnlyBrand ? "From template" : "Override for this batch"}
                  </span>
                </div>
                {templateOnlyBrand ? (
                  <div className="rounded-2xl border border-white/[0.08] bg-black/24 p-4">
                    <p className="text-sm text-zinc-300">
                      {selectedTemplate ? (
                        <>
                          Defaults for <span className="font-semibold text-white">{selectedTemplate.label}</span>
                        </>
                      ) : (
                        "Template shell defaults"
                      )}
                    </p>
                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                      {(["hook", "watermark", "source", "cta"] as const).map((key) => (
                        <div
                          key={key}
                          className="flex items-center justify-between rounded-2xl border border-white/[0.06] bg-black/20 px-3 py-2 text-xs"
                        >
                          <span className="font-semibold capitalize text-zinc-400">{key}</span>
                          <span className={templateShellDefaults[key] ? "text-cyan" : "text-zinc-600"}>
                            {templateShellDefaults[key] ? "On" : "Off"}
                          </span>
                        </div>
                      ))}
                    </div>
                    <p className="mt-3 text-xs leading-5 text-zinc-500">
                      Pick a saved brand style above to override caption, watermark, and shell layers for this batch.
                    </p>
                  </div>
                ) : (
                  <>
                    <p className="mb-3 text-xs leading-5 text-zinc-500">
                      Hook and CTA are optional shell nodes. Most templates keep the hook inside the recipe overlay instead.
                    </p>
                    <div className="grid gap-2 sm:grid-cols-2">
                      <ShellComponentToggle
                        label="Hook"
                        detail="Title + subtitle card in the shell"
                        enabled={config.shellComponents.hook}
                        onChange={(hook) => update({shellComponents: {...config.shellComponents, hook}})}
                      />
                      <ShellComponentToggle
                        label="Watermark"
                        detail="Brand name in the corner"
                        enabled={config.shellComponents.watermark}
                        onChange={(watermark) => update({shellComponents: {...config.shellComponents, watermark}})}
                      />
                      <ShellComponentToggle
                        label="Source"
                        detail="Attribution line under the watermark"
                        enabled={config.shellComponents.source}
                        onChange={(source) => update({shellComponents: {...config.shellComponents, source}})}
                      />
                      <ShellComponentToggle
                        label="CTA"
                        detail="End-card follow / subscribe prompt"
                        enabled={config.shellComponents.cta}
                        onChange={(cta) => update({shellComponents: {...config.shellComponents, cta}})}
                      />
                    </div>
                  </>
                )}
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
                    <SelectTile
                      label="Captions"
                      value={config.captionSource}
                      options={[
                        {value: "hybrid", label: "YouTube + Whisper"},
                        {value: "whisper", label: "Whisper only"},
                        {value: "youtube", label: "YouTube only"},
                      ]}
                      onChange={(value) => update({captionSource: value})}
                    />
                    <SelectTile label="Speech language" value={config.speechLanguage} options={["auto", "id", "ar", "en", "ms"]} onChange={(value) => update({speechLanguage: value})} />
                    <SelectTile label="Transcripts" value={config.transcriptLanguages} options={["auto", "id,en", "id", "en,id", "ar,id", "ms,id"]} onChange={(value) => update({transcriptLanguages: value})} />
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
          {templatesForFormat.map((template) => {
            const active = config.hyperframesTemplate === template.id;
            return (
              <div
                key={template.id}
                className={`template-card min-w-0 rounded-[20px] border text-left transition sm:p-3 ${active ? "border-cyan/[0.45] bg-teal/[0.12] shadow-glow" : "border-white/[0.08] bg-canvas-deep hover:border-cyan/[0.22] hover:bg-teal/[0.05]"} p-2.5`}
              >
                <TemplatePreview
                  template={template}
                  compact
                  gridCard
                  hideFooterLabel
                  frame={config.hyperframesFormat === "long_16_9" ? "long" : "short"}
                  hoverToPlay
                />
                <button
                  type="button"
                  onClick={() => {
                    update({
                      renderer: "hyperframes",
                      hyperframesTemplate: template.id,
                      brandSystemTemplateId: template.source === "brand_system" ? template.id : "",
                      brandTemplate:
                        template.source === "brand_system" && template.brand_template_path
                          ? template.brand_template_path
                          : templateOnlyBrand
                            ? TEMPLATE_ONLY_BRAND
                            : config.brandTemplate,
                      shellComponents: shellComponentsFromTemplate(template),
                    });
                    setTemplatePickerOpen(false);
                  }}
                  className="mt-2 block w-full text-left"
                  aria-pressed={active}
                  aria-label={`Use ${template.label}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-xs font-semibold uppercase tracking-wide text-cyan">{template.category}</p>
                        <span className="rounded-full border border-white/[0.10] bg-black/30 px-2 py-0.5 text-[10px] font-semibold text-zinc-400">
                          {friendlyTemplateStatus(template.status)}
                        </span>
                      </div>
                      <h4 className="mt-1 truncate text-lg font-semibold text-white">{template.label}</h4>
                    </div>
                    {active ? <CheckCircle2 className="h-4 w-4 shrink-0 text-cyan" /> : null}
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm leading-6 text-zinc-400">{template.best_for}</p>
                </button>
              </div>
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
