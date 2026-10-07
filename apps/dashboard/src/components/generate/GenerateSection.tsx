"use client";

import {ArrowRight, BadgeCheck, ChevronDown, Copy, Loader2, Sparkles, Youtube} from "lucide-react";
import {useEffect, useMemo, useRef, useState, type Dispatch, type ReactNode, type SetStateAction} from "react";
import {HyperframesTemplatePickerModal} from "@/components/templates/HyperframesTemplatePickerModal";
import {SlideToConfirm} from "@/components/shared/SlideToConfirm";
import {apiGet, apiPost, templateSupportsFormat, type ShellComponents, DEFAULT_SHELL_COMPONENTS, isTemplateOnlyBrand, TEMPLATE_ONLY_BRAND, type SourceResolveResult} from "@/lib/media-api";
import {
  type ActionUiState,
  type BrandTemplate,
  type DurationPreset,
  type EngineHealth,
  type AngleRecommendation,
  type GenerationJob,
  type ShortlistCandidate,
  type GenreOption,
  type HyperframesCatalog,
  type HyperframesTemplate,
} from "./types";

const GENRE_AUTO = "auto";

function genresIsAuto(genres: string[]) {
  return genres.includes(GENRE_AUTO);
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
  minEditorialScore?: number;
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
    case "shortlist":
      return "Ideas ready";
    case "running":
    case "queued":
      return "Finding clips";
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
  onRenderSelected,
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
  onRenderSelected?: (source: SourceResolveResult | null, candidateIds: string[]) => void;
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
  const [angleRecs, setAngleRecs] = useState<AngleRecommendation[]>([]);
  const [angleSource, setAngleSource] = useState("");
  const [selectedClipIds, setSelectedClipIds] = useState<string[]>([]);
  const resolveRequestId = useRef(0);
  const floor = config.minEditorialScore ?? 80;
  const shortlist = latest?.status === "shortlist" ? latest.result?.candidates || [] : [];
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

  useEffect(() => {
    if (!resolvedSource?.ok || !resolvedSource.video_id) {
      setAngleRecs([]);
      setAngleSource("");
      return;
    }
    const videoId = resolvedSource.video_id;
    let cancelled = false;
    void (async () => {
      try {
        const result = await apiPost<{angles: AngleRecommendation[]; source: string}>("recommend-angles", {
          title: resolvedSource.title || "",
          video_id: videoId,
          llm_provider: config.llmProvider,
        });
        if (cancelled) return;
        const angles = result.angles || [];
        setAngleRecs(angles);
        setAngleSource(result.source || "");
        if (angles.length && genresIsAuto(config.genres)) {
          update({genres: angles.map((angle) => angle.id)});
        }
      } catch {
        if (!cancelled) {
          setAngleRecs([]);
          setAngleSource("");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // Recommend once per resolved video. Manual chip edits should not refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resolvedSource?.video_id, resolvedSource?.ok]);

  useEffect(() => {
    if (latest?.status !== "shortlist") return;
    const clips = latest.result?.candidates || [];
    setSelectedClipIds(clips.filter((clip) => (clip.editorial_score ?? 0) >= floor).map((clip) => clip.id));
  }, [latest?.id, latest?.status, floor]);

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
  const activeSavedBrand = !templateOnlyBrand
    ? savedBrandStyles.find((item) => item.path === config.brandTemplate)
    : undefined;
  const activeBrandHyperframes = hyperframesTemplates.find(
    (item) => item.source === "brand_system" && item.brand_template_path === config.brandTemplate,
  );
  const activeBrandStarterLabel = activeBrandHyperframes?.starter_template
    ? hyperframesTemplates.find((item) => item.id === activeBrandHyperframes.starter_template)?.label
      || activeBrandHyperframes.starter_template
    : "";
  const brandHasOssCta = Boolean(
    activeBrandHyperframes?.blocks_used?.some((block) => block && block !== "none"),
  );
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
    <section className="grid w-full min-w-0 gap-6">
      <div className="grid w-full min-w-0 gap-6 xl:grid-cols-[896px_minmax(0,1fr)] lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] items-start">
        {/* Left Column: Configuration & Controls */}
        <div className="min-w-0 rounded-[28px] border border-white/[0.08] bg-surface p-5 sm:p-6 shadow-[0_0_0_1px_rgba(102,232,249,0.04)] space-y-6 divide-y divide-white/[0.06]">
          {/* Header */}
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan">New clip batch</p>
              <p className="mt-1 text-xs text-zinc-400">Set source, angles, and template.</p>
            </div>
            <div className="flex shrink-0 items-center gap-1.5 rounded-full border border-white/[0.08] bg-canvas-deep px-2.5 py-1 text-xs">
              <span className="font-semibold text-white">{clipCountLabel(config.count)}</span>
              <span className="text-zinc-600">·</span>
              <span className="text-zinc-400">{config.clipMinSeconds}–{config.clipMaxSeconds}s</span>
            </div>
          </div>

          {/* 1. Source Video Input */}
          <div className="pt-6 space-y-4">
            <label className="grid min-w-0 gap-2 text-sm font-medium text-zinc-300">
              <span className="flex items-center justify-between">
                <span>YouTube link</span>
                <span className="text-[11px] font-normal text-zinc-500">Public or unlisted</span>
              </span>
              <div className="relative flex items-center">
                <input
                  value={config.sourceUrl}
                  onChange={(event) => update({sourceUrl: event.target.value})}
                  className="h-11 w-full rounded-2xl border border-white/[0.08] bg-black/30 pl-10 pr-4 text-sm text-zinc-200 outline-none transition placeholder:text-zinc-600 focus:border-cyan/[0.40] focus:ring-1 focus:ring-cyan/[0.40]"
                  placeholder="https://youtube.com/watch?v=…"
                />
                <span className="absolute left-3.5 text-zinc-500">
                  <Youtube className="h-4 w-4" />
                </span>
              </div>
            </label>

            {resolveState === "loading" ? (
              <div className="inline-flex items-center gap-2 text-xs font-medium text-zinc-400">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan" />
                Checking video details &amp; captions…
              </div>
            ) : null}

            {resolveState === "error" && resolveError ? (
              <p className="text-xs leading-5 text-danger">{resolveError}</p>
            ) : null}

            {resolveState === "ready" && resolvedSource ? (
              <div className="flex items-start gap-3 rounded-2xl border border-white/[0.06] bg-black/20 p-3">
                {resolvedSource.thumbnail_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={resolvedSource.thumbnail_url}
                    alt=""
                    className="h-14 w-24 shrink-0 rounded-lg object-cover bg-black/40"
                  />
                ) : (
                  <div className="grid h-14 w-24 shrink-0 place-items-center rounded-lg bg-black/40 text-zinc-600">
                    <Youtube className="h-4 w-4" />
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-white">{resolvedSource.title || "YouTube video"}</p>
                  <p className="mt-0.5 truncate text-[11px] text-zinc-400">
                    {[resolvedSource.channel, formatSourceDuration(resolvedSource.duration_seconds)].filter(Boolean).join(" · ")}
                  </p>
                  <div className="mt-1 flex items-center gap-2">
                    {resolvedSource.transcript?.status ? (
                      <span className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold ${transcriptStatusTone(resolvedSource.transcript.status)}`}>
                        {transcriptStatusLabel(resolvedSource.transcript.status)}
                      </span>
                    ) : null}
                    {resolvedSource.transcript?.status === "available" ? (
                      <span className="text-[10px] text-teal">Ready</span>
                    ) : null}
                  </div>
                </div>
              </div>
            ) : null}

            {resolveState === "ready" && resolvedSource?.transcript?.status && resolvedSource.transcript.status !== "available" ? (
              <div className="space-y-2 rounded-xl border border-warning/20 bg-warning/[0.04] p-3 text-xs">
                <p className="font-semibold text-white">Clip discovery source</p>
                <div className="grid gap-1.5">
                  {[
                    {value: "auto", label: "Auto", detail: "YouTube CC → Whisper fallback"},
                    {value: "audio", label: "Audio (Whisper)", detail: "Full Whisper ASR from track"},
                    {value: "youtube", label: "YouTube CC only", detail: "Fast, requires CC"},
                  ].map((option) => {
                    const active = config.curationSource === option.value;
                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => update({curationSource: option.value})}
                        className={`flex items-center justify-between rounded-lg border px-2.5 py-1.5 text-left transition ${
                          active ? "border-cyan/[0.50] bg-cyan/[0.08] text-white" : "border-white/[0.06] bg-black/20 text-zinc-400 hover:border-white/[0.12]"
                        }`}
                      >
                        <span className="text-xs font-medium">{option.label}</span>
                        <span className="text-[10px] text-zinc-500">{option.detail}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </div>

          {/* 2. Suggested Content Angles */}
          {resolveState === "ready" && angleRecs.length ? (
            <div className="pt-6 space-y-2.5">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 text-cyan">
                  <Sparkles className="h-3.5 w-3.5" />
                  <span className="text-xs font-bold uppercase tracking-wider text-zinc-300">Content angles</span>
                </div>
                <span className="text-[10px] text-zinc-500">{angleSource || "AI suggested"}</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {angleRecs.map((angle) => {
                  const active = config.genres.includes(angle.id);
                  return (
                    <button
                      key={angle.id}
                      type="button"
                      onClick={() => {
                        const next = active
                          ? config.genres.filter((id) => id !== angle.id && id !== GENRE_AUTO)
                          : [...config.genres.filter((id) => id !== GENRE_AUTO), angle.id];
                        update({genres: next.length ? next : [GENRE_AUTO]});
                      }}
                      className={`group inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition ${
                        active
                          ? "border-cyan bg-cyan/[0.12] text-white shadow-[0_0_10px_rgba(98,238,248,0.12)]"
                          : "border-white/[0.08] bg-black/20 text-zinc-400 hover:border-white/[0.16] hover:text-zinc-200"
                      }`}
                      title={angle.reason}
                    >
                      <span className={`h-1.5 w-1.5 rounded-full ${active ? "bg-cyan" : "bg-zinc-600"}`} />
                      <span>{angle.label}</span>
                      {active ? <span className="text-cyan text-[10px] font-bold">✓</span> : null}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}

          {/* 3. Batch Size & Score Floor */}
          <div className="pt-6 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-white">How many clips?</span>
              <div className="flex items-center gap-1.5 text-xs text-zinc-400">
                <span>Floor:</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={floor}
                  onChange={(event) => update({minEditorialScore: Number(event.target.value) || 0})}
                  className="h-7 w-14 rounded-lg border border-white/[0.08] bg-black/30 px-1.5 text-right text-xs font-semibold text-white outline-none focus:border-cyan/[0.40]"
                />
                <span className="text-zinc-500">pts</span>
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {[1, 2, 3, 5, 8, 10].map((val) => {
                const active = config.count === val;
                return (
                  <button
                    key={val}
                    type="button"
                    onClick={() => update({count: val})}
                    className={`h-8 min-w-[36px] rounded-full px-3 text-xs font-semibold transition ${
                      active
                        ? "bg-cyan text-ink shadow-[0_2px_8px_rgba(102,232,249,0.22)]"
                        : "border border-white/[0.08] bg-black/20 text-zinc-400 hover:border-white/[0.16] hover:text-white"
                    }`}
                  >
                    {val}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 4. Visual Template */}
          <div className="pt-6 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h4 className="text-xs font-semibold text-white">Visual template</h4>
              <button
                type="button"
                onClick={() => setTemplatePickerOpen(true)}
                className="inline-flex h-7 items-center gap-1 rounded-full border border-cyan/[0.24] bg-cyan/[0.06] px-2.5 text-[11px] font-semibold text-cyan hover:bg-cyan/[0.12] transition"
              >
                <Sparkles className="h-3 w-3" />
                Browse
              </button>
            </div>
            <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_130px]">
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
          </div>

          {/* 5. SlideToConfirm Action */}
          <div className="pt-6 space-y-3">
            <SlideToConfirm
              label={hasActiveJob ? "Finding clips…" : "Slide to find clips"}
              activeLabel="Starting…"
              onConfirm={() => onGenerate(resolvedSource)}
              isLoading={isStarting}
              disabled={!canGenerate || isStarting}
            />
            {hasActiveJob ? (
              <p className="text-center text-[11px] text-zinc-500">Batch running in right panel…</p>
            ) : resolveState === "loading" ? (
              <p className="text-center text-[11px] text-zinc-500">Checking link…</p>
            ) : null}
            {renderActionStatus(actionState)}
          </div>

          {/* Advanced Collapse */}
          <div className="pt-6">
            <details
              className="rounded-2xl border border-white/[0.06] bg-black/20 p-3.5"
              open={advancedOpen}
              onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}
            >
              <summary className="cursor-pointer list-none text-xs font-semibold text-zinc-300">
                Advanced settings
                <span className="ml-1.5 text-[10px] text-zinc-500">duration · angles · brand &amp; dev</span>
              </summary>
              <div className="mt-4 space-y-5 border-t border-white/[0.06] pt-4 text-xs">
                {/* 1. Clip length */}
                <div>
                  <h4 className="mb-2 font-semibold text-white">Clip length</h4>
                  <div className="grid gap-1.5 sm:grid-cols-2">
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
                          className={`rounded-xl border p-2 text-left transition ${
                            active ? "border-cyan/[0.50] bg-cyan/[0.08] text-white" : "border-white/[0.06] bg-black/20 text-zinc-400 hover:border-white/[0.12]"
                          }`}
                        >
                          <span className={`block font-semibold ${active ? "text-cyan" : "text-white"}`}>{preset.label}</span>
                          <span className="text-[10px] text-zinc-500">{preset.detail}</span>
                        </button>
                      );
                    })}
                  </div>
                  <p className="mt-1.5 text-[11px] text-zinc-500">
                    Using <span className="text-zinc-300">{selectedPreset?.label}</span> ({config.clipMinSeconds}–{config.clipMaxSeconds}s).
                  </p>
                </div>

                {/* 2. Full Content Angles Catalog */}
                <div>
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <h4 className="font-semibold text-white">All content angles</h4>
                    <span className="text-[11px] text-zinc-500">
                      {genresAuto ? "Auto" : `${manualGenreCount} selected`}
                      {genrePackLabel ? ` · ${genrePackLabel} pack` : ""}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      onClick={() => update({genres: [GENRE_AUTO]})}
                      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold transition ${genresAuto ? "border-cyan bg-teal/[0.16] text-white" : "border-white/[0.08] bg-black/24 text-zinc-400 hover:border-white/[0.16] hover:text-white"}`}
                      aria-pressed={genresAuto}
                    >
                      {genresAuto ? <BadgeCheck className="h-3.5 w-3.5 text-cyan" /> : null}
                      Auto
                    </button>
                    {genreOptions.map((genre) => {
                      const active = !genresAuto && config.genres.includes(genre.id);
                      return (
                        <button
                          key={genre.id}
                          type="button"
                          onClick={() => toggleGenre(genre.id)}
                          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold transition ${active ? "border-cyan bg-teal/[0.16] text-white" : "border-white/[0.08] bg-black/24 text-zinc-400 hover:border-white/[0.16] hover:text-white"}`}
                          aria-pressed={active}
                          title={genre.description}
                        >
                          {active ? <BadgeCheck className="h-3.5 w-3.5 text-cyan" /> : null}
                          {genre.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* 3. Captions & Saved Brand Style */}
                <div>
                  <div className="mb-2">
                    <h4 className="font-semibold text-white">Captions &amp; brand style</h4>
                    <p className="mt-0.5 text-[11px] text-zinc-500">
                      Optional — applies saved brand font/watermark overlay from Brand Builder.
                    </p>
                  </div>
                  {savedBrandStyles.length === 0 ? (
                    <div className="rounded-xl border border-white/[0.06] bg-black/20 p-3">
                      <p className="text-xs text-zinc-300">
                        Using <span className="font-semibold text-white">template defaults</span>
                      </p>
                      <p className="mt-0.5 text-[11px] text-zinc-500">
                        Caption font and watermark come from the selected visual template.
                      </p>
                      {onOpenBrand ? (
                        <button
                          type="button"
                          onClick={onOpenBrand}
                          className="mt-2 text-xs font-semibold text-cyan transition hover:text-cyan/80"
                        >
                          Save a custom style in Brand →
                        </button>
                      ) : null}
                    </div>
                  ) : (
                    <div className="grid gap-1.5 sm:grid-cols-2">
                      {brandStyleOptions.map((template) => {
                        const active = templateOnlyBrand
                          ? template.path === TEMPLATE_ONLY_BRAND
                          : config.brandTemplate === template.path;
                        const isTemplateDefault = template.path === TEMPLATE_ONLY_BRAND;
                        return (
                          <button
                            key={template.id}
                            type="button"
                            onClick={() => {
                              const isDefault = template.path === TEMPLATE_ONLY_BRAND;
                              const brandId = isDefault ? "" : (template.brand_system_template_id || "");
                              update({
                                brandTemplate: template.path,
                                brandSystemTemplateId: brandId,
                                hyperframesTemplate:
                                  isDefault || config.hyperframesTemplate !== "auto"
                                    ? config.hyperframesTemplate
                                    : brandId || config.hyperframesTemplate,
                              });
                            }}
                            className={`flex flex-col rounded-xl border p-2 text-left transition ${
                              active
                                ? "border-cyan/[0.50] bg-cyan/[0.08] text-white"
                                : "border-white/[0.06] bg-black/20 text-zinc-400 hover:border-white/[0.12] hover:text-white"
                            }`}
                          >
                            <span className="flex items-center justify-between gap-1">
                              <span className="text-xs font-semibold truncate">{template.label}</span>
                              <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-bold ${active ? "bg-cyan text-ink" : "bg-white/[0.06] text-zinc-500"}`}>
                                {active ? "Active" : "Use"}
                              </span>
                            </span>
                            <span className="mt-0.5 text-[10px] text-zinc-500 truncate">
                              {isTemplateDefault ? "Recipe defaults" : "Saved brand"}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* 4. Shell Layers */}
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <h4 className="font-semibold text-white">Shell layers</h4>
                    <span className="text-[10px] text-zinc-500">{templateOnlyBrand ? "From template" : "Custom override"}</span>
                  </div>
                  {templateOnlyBrand ? (
                    <div className="rounded-xl border border-white/[0.06] bg-black/20 p-3">
                      <div className="grid grid-cols-2 gap-1.5">
                        {(["hook", "watermark", "source", "cta"] as const).map((key) => (
                          <div
                            key={key}
                            className="flex items-center justify-between rounded-lg border border-white/[0.06] bg-black/30 px-2.5 py-1.5 text-[11px]"
                          >
                            <span className="font-medium capitalize text-zinc-400">{key}</span>
                            <span className={templateShellDefaults[key] ? "text-cyan font-bold" : "text-zinc-600"}>
                              {templateShellDefaults[key] ? "On" : "Off"}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="grid gap-1.5 sm:grid-cols-2">
                      <ShellComponentToggle
                        label="Hook"
                        detail="Title card in shell"
                        enabled={config.shellComponents.hook}
                        onChange={(hook) => update({shellComponents: {...config.shellComponents, hook}})}
                      />
                      <ShellComponentToggle
                        label="Watermark"
                        detail="Corner brand label"
                        enabled={config.shellComponents.watermark}
                        onChange={(watermark) => update({shellComponents: {...config.shellComponents, watermark}})}
                      />
                      <ShellComponentToggle
                        label="Source"
                        detail="YouTube channel credit"
                        enabled={config.shellComponents.source}
                        onChange={(source) => update({shellComponents: {...config.shellComponents, source}})}
                      />
                      <ShellComponentToggle
                        label="CTA"
                        detail="End-card prompt"
                        enabled={config.shellComponents.cta}
                        onChange={(cta) => update({shellComponents: {...config.shellComponents, cta}})}
                      />
                    </div>
                  )}
                </div>

                {/* 5. Developer options & CLI */}
                <details className="rounded-xl border border-white/[0.06] bg-black/20 p-3">
                  <summary className="cursor-pointer list-none text-xs font-semibold text-zinc-400">
                    Developer options &amp; CLI
                    <span className="ml-1.5 text-[10px] text-zinc-600">captions · model · command</span>
                  </summary>
                  <div className="mt-3 space-y-3 border-t border-white/[0.06] pt-3">
                    <div className="grid gap-2 text-[11px] sm:grid-cols-2">
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
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
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
                      <SelectTile label="Writing model" value={config.llmProvider} options={["deepseek", "openai", "groq", "agent", "none"]} onChange={(value) => update({llmProvider: value})} />
                      <SelectTile label="Quality" value={config.quality} options={["production", "draft"]} onChange={(value) => update({quality: value})} />
                    </div>
                    <div className="rounded-xl border border-white/[0.06] bg-canvas-deep/60 p-2.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-semibold text-white">CLI Command</span>
                        <button type="button" onClick={onCopy} className="inline-flex rounded-full border border-white/[0.10] bg-white/[0.04] px-2.5 py-1 text-[11px] font-semibold text-zinc-200 hover:border-cyan/30 hover:text-cyan">
                          <Copy className="mr-1.5 h-3 w-3" /> Copy
                        </button>
                      </div>
                      <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-white/[0.06] bg-black/40 p-2 text-[10px] leading-4 text-zinc-500">{command}</pre>
                    </div>
                  </div>
                </details>
              </div>
            </details>
          </div>
        </div>

        {/* Right Column: Dynamic Stage (Shortlist / Active Run / Studio Guidance) */}
        <div className="min-w-0 space-y-6">
          {/* Active Job Progress */}
          {latest ? (
            <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5 sm:p-6 shadow-[0_0_0_1px_rgba(102,232,249,0.04)] space-y-4" aria-live="polite">
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
              {latest.error ? <p className="text-xs leading-5 text-danger">{humanizeGenerationError(latest.error)}</p> : null}
              {latest.status === "completed" ? (
                <button type="button" onClick={onOpenReview} className="inline-flex w-fit items-center gap-2 rounded-full bg-cyan px-4 py-2 text-xs font-semibold text-ink transition hover:bg-cyan/90">
                  Review clips <ArrowRight className="h-3.5 w-3.5" />
                </button>
              ) : null}
              {(latest.error || latest.log_text) && (
                <details>
                  <summary className="cursor-pointer list-none text-xs font-semibold text-zinc-500 hover:text-zinc-300">Technical details</summary>
                  <pre className="mt-2.5 max-h-44 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-black/40 p-3 text-[10px] leading-4 text-zinc-400">{latest.error || latest.log_text || "Waiting…"}</pre>
                </details>
              )}
            </div>
          ) : null}

          {/* Curated Clip Shortlist */}
          {shortlist.length ? (
            <div className="rounded-[28px] border border-cyan/[0.22] bg-surface p-5 sm:p-6 shadow-[0_0_0_1px_rgba(102,232,249,0.06)] space-y-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-white/[0.06] pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="flex h-2 w-2 rounded-full bg-cyan shadow-[0_0_8px_rgba(98,238,248,0.8)]" />
                    <h4 className="text-sm font-bold uppercase tracking-wider text-white">Curated Clip Shortlist</h4>
                  </div>
                  <p className="mt-1 text-xs text-zinc-400">
                    <span className="font-semibold text-cyan">{latest?.result?.passed ?? shortlist.length}</span> of {latest?.result?.considered ?? shortlist.length} candidates cleared the floor ({latest?.result?.floor ?? floor}+).
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      if (selectedClipIds.length === shortlist.length) {
                        setSelectedClipIds([]);
                      } else {
                        setSelectedClipIds(shortlist.map((c) => c.id));
                      }
                    }}
                    className="rounded-full border border-white/[0.10] bg-white/[0.04] px-3 py-1 text-xs font-medium text-zinc-300 hover:border-white/[0.20] hover:text-white transition"
                  >
                    {selectedClipIds.length === shortlist.length ? "Deselect all" : "Select all"}
                  </button>
                </div>
              </div>

              {/* Flat list rows with subtle divider */}
              <div className="divide-y divide-white/[0.06] rounded-2xl border border-white/[0.08] bg-black/20 overflow-hidden">
                {shortlist.map((clip: ShortlistCandidate) => {
                  const checked = selectedClipIds.includes(clip.id);
                  const score = clip.editorial_score ?? 0;
                  return (
                    <div
                      key={clip.id}
                      onClick={() => {
                        setSelectedClipIds((current) =>
                          current.includes(clip.id) ? current.filter((id) => id !== clip.id) : [...current, clip.id],
                        );
                      }}
                      className={`group flex cursor-pointer items-start gap-3.5 p-4 transition-colors ${
                        checked ? "bg-cyan/[0.04]" : "hover:bg-white/[0.02]"
                      }`}
                    >
                      <div className="pt-0.5">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => {
                            e.stopPropagation();
                            setSelectedClipIds((current) =>
                              current.includes(clip.id) ? current.filter((id) => id !== clip.id) : [...current, clip.id],
                            );
                          }}
                          className="h-4 w-4 rounded border-white/20 bg-black/40 text-cyan focus:ring-cyan"
                        />
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-3">
                          <h5 className={`text-sm font-semibold transition ${checked ? "text-cyan" : "text-white group-hover:text-cyan"}`}>
                            {clip.title_hook}
                          </h5>
                          <span
                            className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-bold tabular-nums ${
                              score >= 80
                                ? "border-teal/[0.35] bg-teal/[0.10] text-teal"
                                : "border-warning/[0.35] bg-warning/[0.10] text-warning"
                            }`}
                          >
                            {score} pts
                          </span>
                        </div>

                        {clip.hook_subtitle ? (
                          <p className="mt-1 text-xs text-zinc-300 leading-relaxed font-medium">
                            {clip.hook_subtitle}
                          </p>
                        ) : null}

                        {clip.viral_reason ? (
                          <p className="mt-1.5 text-[11px] leading-relaxed text-zinc-500">
                            💡 <span className="text-zinc-400">{clip.viral_reason}</span>
                          </p>
                        ) : null}

                        {clip.transcript_excerpt ? (
                          <blockquote className="mt-2 rounded-lg bg-black/30 px-2.5 py-1.5 text-[11px] italic text-zinc-400 border-l-2 border-white/10">
                            &ldquo;{clip.transcript_excerpt}&rdquo;
                          </blockquote>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="flex items-center justify-between gap-4 pt-1">
                <span className="text-xs text-zinc-400">
                  <span className="font-semibold text-white">{selectedClipIds.length}</span> of {shortlist.length} selected for rendering
                </span>
                <button
                  type="button"
                  disabled={!selectedClipIds.length || isStarting || !onRenderSelected}
                  onClick={() => onRenderSelected?.(resolvedSource, selectedClipIds)}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-full bg-cyan px-5 text-xs font-bold uppercase tracking-wider text-ink shadow-[0_4px_16px_rgba(102,232,249,0.20)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  Render selected ({selectedClipIds.length})
                </button>
              </div>
            </div>
          ) : null}

          {/* Empty / Idle State Placeholder in Right Column when no job / shortlist yet */}
          {!latest && !shortlist.length ? (
            <div className="rounded-[28px] border border-white/[0.08] bg-surface/40 p-8 sm:p-12 text-center">
              <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl border border-white/[0.08] bg-canvas-deep text-zinc-500 mb-4">
                <Youtube className="h-6 w-6 text-cyan/70" />
              </div>
              <h4 className="text-base font-semibold text-white">Ready for your source video</h4>
              <p className="mt-1.5 max-w-sm mx-auto text-xs text-zinc-400 leading-relaxed">
                Paste a YouTube URL on the left. The studio will check subtitles, suggest angles, and discover clip candidates for you to curate before rendering.
              </p>
            </div>
          ) : null}
        </div>
      </div>

      {!latest ? renderEmptyState("Ready when you are", "Paste a YouTube link above to create your first clip batch.") : null}

      <HyperframesTemplatePickerModal
        open={templatePickerOpen}
        title="Choose video template"
        subtitle="Pick a visual style before generating clips."
        templates={templatesForFormat}
        selectedId={config.hyperframesTemplate}
        frame={config.hyperframesFormat === "long_16_9" ? "long" : "short"}
        onClose={() => setTemplatePickerOpen(false)}
        onSelect={(template) => {
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
      />
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
