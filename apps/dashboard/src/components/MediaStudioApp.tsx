"use client";

import {
  AlertTriangle,
  BadgeCheck,
  CalendarDays,
  CheckCircle2,
  Clapperboard,
  Copy,
  Eye,
  LayoutDashboard,
  Loader2,
  MoreHorizontal,
  RefreshCcw,
  Send,
  Settings,
  Sparkles,
  Wand2,
  XCircle,
} from "lucide-react";
import {type ReactNode, useEffect, useMemo, useRef, useState} from "react";
import {
  apiGet,
  apiPost,
  AutonomySettings,
  BrandTemplate,
  CaptionSegment,
  ClipCandidate,
  CredentialStatus,
  DurationPreset,
  EngineHealth,
  formatDuration,
  formatTimestamp,
  GenerationJob,
  GenreOption,
  HyperframesCatalog,
  HyperframesTemplate,
  platformLabel,
  PublishAttempt,
  PublishTarget,
  RerenderJob,
  ScheduledPost,
  scoreValue,
  StyleProfile,
} from "@/lib/media-api";
import {ReviewStudioSection} from "@/components/review/ReviewStudioSection";
import {BrandSection} from "@/components/brand/BrandSection";
import {FocusModal} from "@/components/FocusModal";
import {DashboardSection} from "@/components/home/DashboardSection";
import {GenerateSection} from "@/components/generate/GenerateSection";
import {TemplatesSection} from "@/components/templates/TemplatesSection";
import {CalendarSection} from "@/components/calendar/CalendarSection";
import {PublishSection} from "@/components/channels/PublishSection";
import {EmptyState, InlineActionStatus, SettingTile} from "@/components/shared/StudioPrimitives";

type Section = "dashboard" | "generate" | "templates" | "review" | "calendar" | "publish" | "brand";
type NextAction = {
  label: string;
  detail: string;
  section: Section;
  tone: "primary" | "warning" | "ready";
};
type WorkflowStep = {
  id: string;
  label: string;
  status: "ready" | "active" | "blocked" | "idle";
  detail: string;
  section: Section;
};

const defaultSourceUrl = "";
const defaultTemplate = "profiles/default_workspace_style.json";
type RerenderUiState = {status: "running" | "done" | "failed"; message: string; progress?: number};
type ActionUiState = {status: "running" | "done" | "failed"; message: string};
type ToastMessage = {id: string; tone: "success" | "error" | "info"; message: string};
type ConfirmDialogState = {
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel?: string;
  tone?: "danger" | "default";
  onConfirm: () => void;
};
const publishPlatforms = ["telegram_channel", "youtube_shorts", "facebook_reels", "tiktok"];
const oauthPlatforms = new Set(["youtube_shorts", "facebook_reels", "tiktok"]);

function cleanPublishStatus(status?: string) {
  if (!status) return "Not run";
  const labels: Record<string, string> = {
    ready: "Ready",
    published: "Posted",
    failed: "Retry needed",
    blocked: "Needs action",
    legacy_blocked: "Outdated",
    skipped: "Already posted (verified)",
    publishing: "Publishing",
    pending: "Waiting",
    cooldown: "Cooling down",
  };
  return labels[status] || status.replaceAll("_", " ");
}

function formatPlatformMode(mode?: string) {
  if (!mode) return "Review";
  const labels: Record<string, string> = {
    off: "Off",
    review_required: "Review",
    auto_publish: "Auto",
    dry_run: "Dry-run",
  };
  return labels[mode] || mode.replaceAll("_", " ");
}

function formatClipStatus(status?: string) {
  if (!status) return "Unknown";
  const labels: Record<string, string> = {
    approved: "Approved",
    completed: "Completed",
    draft: "Draft",
    failed: "Failed",
    held: "Held",
    pending_auto_schedule: "Auto queue",
    published: "Published",
    ready: "Ready",
    ready_to_publish: "Ready to publish",
    rendered: "Rendered",
    running: "Running",
    scheduled: "Scheduled",
  };
  return labels[status] || status.replaceAll("_", " ");
}

function canApproveClip(clip: ClipCandidate) {
  return ["draft", "rendered", "held", "pending_auto_schedule"].includes(clip.status);
}

function canScheduleClip(clip: ClipCandidate) {
  return clip.status === "approved";
}

function publishActionHint(error?: string) {
  const value = (error || "").toLowerCase();
  if (!value) return "";
  if (value.includes("401") || value.includes("unauthorized") || value.includes("token")) return "Reconnect this platform account.";
  if (value.includes("unaudited_client_can_only_post_to_private_accounts")) return "TikTok app is not audited yet. Use a private account with SELF_ONLY visibility, or complete TikTok audit for public publishing.";
  if (value.includes("telegram upload was interrupted") || value.includes("broken pipe") || value.includes("timed out") || value.includes("urlopen")) return "Telegram upload interrupted. The system will prepare a <49MB Telegram copy, then retry this platform.";
  if (value.includes("above") && value.includes("after compression")) return "Telegram copy is still too large. Re-render a shorter clip or lower the render quality.";
  if (value.includes("rendered video file")) return "Re-render the clip before publishing.";
  if (value.includes("permission") && value.includes("evidence")) return "Legacy local guard entry. Safe to retry this platform.";
  return error || "";
}

function publicAccountLabel(target: PublishTarget) {
  const raw = String(target.account_label || "").trim();
  if (!raw || /nourbit|nouraniyyah/i.test(raw)) {
    return `${platformLabel(target.platform)} workspace`;
  }
  return raw;
}

const nav = [
  {id: "dashboard", label: "Home", icon: LayoutDashboard},
  {id: "generate", label: "Create", icon: Wand2},
  {id: "templates", label: "Templates", icon: Sparkles},
  {id: "review", label: "Review", icon: Clapperboard},
  {id: "calendar", label: "Schedule", icon: CalendarDays},
  {id: "publish", label: "Channels", icon: Send},
  {id: "brand", label: "Brand", icon: Settings},
] as const;

const sectionCopy: Record<Section, {title: string; subtitle: string}> = {
  dashboard: {
    title: "Command Center",
    subtitle: "Start with the one action that moves this production pipeline forward.",
  },
  generate: {
    title: "Create",
    subtitle: "Choose a template, add a source, and generate a focused production batch.",
  },
  templates: {
    title: "Templates",
    subtitle: "Browse HyperFrames video flows and pick the visual direction before generating.",
  },
  review: {
    title: "Review",
    subtitle: "Approve, repair, or schedule clip candidates from a focused queue.",
  },
  calendar: {
    title: "Schedule",
    subtitle: "Place approved clips into guarded publishing slots.",
  },
  publish: {
    title: "Channels",
    subtitle: "Connect platforms and choose where scheduled clips can publish.",
  },
  brand: {
    title: "Brand",
    subtitle: "Build reusable HyperFrames brand systems from production presets.",
  },
};

function statusTone(status: string) {
  if (["approved", "published", "ready", "rendered", "scheduled", "ready_to_publish", "completed", "pending_auto_schedule"].includes(status)) return "text-teal border-teal/[0.30] bg-teal/[0.10]";
  if (["running", "queued"].includes(status)) return "text-cyan border-cyan/[0.30] bg-teal/[0.10]";
  if (["failed", "rejected"].includes(status)) return "text-danger border-danger/[0.30] bg-danger/[0.10]";
  if (["held"].includes(status)) return "text-warning border-warning/[0.30] bg-warning/[0.10]";
  if (["cooldown"].includes(status)) return "text-zinc-300 border-white/[0.14] bg-white/[0.04]";
  return "text-warning border-warning/[0.30] bg-warning/[0.10]";
}

function scoreTone(score?: number) {
  if (typeof score !== "number") return "border-surface-strong text-zinc-400";
  if (score >= 80) return "border-teal text-teal";
  if (score >= 65) return "border-warning text-white";
  return "border-danger text-danger";
}

function formatSchedule(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("id-ID", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Jakarta",
  }).format(date);
}

function formatDeadline(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const diffMs = date.getTime() - Date.now();
  if (diffMs <= 0) return "Auto-schedule due";
  const hours = Math.floor(diffMs / 3_600_000);
  const minutes = Math.round((diffMs % 3_600_000) / 60_000);
  if (hours <= 0) return `${minutes}m to auto-schedule`;
  return `${hours}h ${minutes}m to auto-schedule`;
}

type GenerateConfig = {
  sourceUrl: string;
  count: number;
  clipLength: string;
  clipMinSeconds: number;
  clipMaxSeconds: number;
  genres: string[];
  brandTemplate: string;
  hyperframesTemplate: string;
  brandSystemTemplateId: string;
  hyperframesFormat: string;
  renderer: string;
  quality: string;
  captionSource: string;
  asrModel: string;
  speechLanguage: string;
  transcriptLanguages: string;
  llmProvider: string;
};

const reviewFilters = [
  {id: "all", label: "All", hint: "Every clip that is still visible in this workspace.", statuses: []},
  {id: "review", label: "Review", hint: "Clips that need approval, can still be held, or are waiting for assisted auto-queue.", statuses: ["draft", "rendered", "approved", "held", "pending_auto_schedule"]},
  {id: "repair", label: "Repair", hint: "Clips blocked by caption confidence or quality gates before they can be scheduled.", statuses: ["held"]},
  {id: "scheduled", label: "Scheduled", hint: "Approved clips already placed into the publishing queue.", statuses: ["scheduled", "ready_to_publish"]},
  {id: "published", label: "Published", hint: "Clips already sent to a live channel.", statuses: ["published"]},
] as const;

function matchesReviewFilter(clip: ClipCandidate, filter: string) {
  const group = reviewFilters.find((item) => item.id === filter);
  if (!group || group.id === "all") return true;
  return (group.statuses as readonly string[]).includes(clip.status);
}

function primaryReviewAction(clip: ClipCandidate) {
  if (canScheduleClip(clip)) return "Schedule";
  if (canApproveClip(clip)) return clip.status === "held" ? "Open fix" : "Approve";
  if (clip.status === "published") return "Published";
  if (clip.status === "ready_to_publish") return "Ready";
  if (clip.status === "scheduled") return "Scheduled";
  return formatClipStatus(clip.status);
}

function getNextAction({
  clips,
  approvedCount,
  scheduledCount,
  readyPlatforms,
  targetCount,
  engineReady,
  hasTemplate,
}: {
  clips: ClipCandidate[];
  approvedCount: number;
  scheduledCount: number;
  readyPlatforms: number;
  targetCount: number;
  engineReady: boolean;
  hasTemplate: boolean;
}): NextAction {
  const reviewCount = clips.filter((clip) => ["draft", "rendered", "held", "pending_auto_schedule"].includes(clip.status)).length;
  if (!engineReady) {
    return {label: "Check HyperFrames runtime", detail: "Renderer readiness is the first blocker before production work.", section: "generate", tone: "warning"};
  }
  if (!hasTemplate) {
    return {label: "Choose a video template", detail: "Pick the production visual system before generating clips.", section: "templates", tone: "primary"};
  }
  if (!clips.length) {
    return {label: "Generate first batch", detail: "Start from a long video source and create ranked clip candidates.", section: "generate", tone: "primary"};
  }
  if (reviewCount > 0) {
    return {label: `Review ${reviewCount} clips`, detail: "Approve the strongest candidates or open repair tools for blocked clips.", section: "review", tone: "primary"};
  }
  if (approvedCount > 0 && scheduledCount === 0) {
    return {label: `Schedule ${approvedCount} approved clips`, detail: "Move approved clips into the next guarded publishing slots.", section: "calendar", tone: "ready"};
  }
  if (targetCount > 0 && readyPlatforms < targetCount) {
    return {label: `Connect ${targetCount - readyPlatforms} channels`, detail: "Finish platform readiness so scheduled clips can publish.", section: "publish", tone: "warning"};
  }
  return {label: "Generate next batch", detail: "The current pipeline is clear enough to create the next set of candidates.", section: "generate", tone: "primary"};
}

function buildWorkflowSteps({
  clips,
  approvedCount,
  scheduledCount,
  readyPlatforms,
  targetCount,
  engineReady,
  hasTemplate,
}: {
  clips: ClipCandidate[];
  approvedCount: number;
  scheduledCount: number;
  readyPlatforms: number;
  targetCount: number;
  engineReady: boolean;
  hasTemplate: boolean;
}): WorkflowStep[] {
  const reviewCount = clips.filter((clip) => ["draft", "rendered", "held", "pending_auto_schedule"].includes(clip.status)).length;
  return [
    {id: "brand", label: "Brand", status: hasTemplate ? "ready" : "active", detail: hasTemplate ? "Template available" : "Pick a preset", section: "brand"},
    {id: "template", label: "Template", status: hasTemplate ? "ready" : "blocked", detail: hasTemplate ? "HyperFrames ready" : "Choose first", section: "templates"},
    {id: "generate", label: "Create", status: clips.length ? "ready" : engineReady && hasTemplate ? "active" : "blocked", detail: clips.length ? `${clips.length} clips` : "No batch yet", section: "generate"},
    {id: "review", label: "Review", status: reviewCount ? "active" : approvedCount || scheduledCount ? "ready" : "idle", detail: reviewCount ? `${reviewCount} need action` : approvedCount ? `${approvedCount} approved` : "Waiting", section: "review"},
    {id: "schedule", label: "Schedule", status: scheduledCount ? "ready" : approvedCount ? "active" : "idle", detail: scheduledCount ? `${scheduledCount} queued` : approvedCount ? "Ready to slot" : "Waiting", section: "calendar"},
    {id: "publish", label: "Publish", status: readyPlatforms ? "ready" : targetCount ? "active" : "idle", detail: targetCount ? `${readyPlatforms}/${targetCount} channels` : "No targets", section: "publish"},
  ];
}

function productionCommand(config: GenerateConfig) {
  return `cd "/Volumes/XPG SSD 1T/projects/otonom-agents-media/media-engine"
MEDIA_ENGINE_PYTHON="\${MEDIA_ENGINE_PYTHON:-./.venv-tools/bin/python}" PYTHONPATH=. "\${MEDIA_ENGINE_PYTHON}" -m media_engine.cli premium-batch \\
  --youtube-url "${config.sourceUrl}" \\
  --count ${config.count} \\
  --clip-length-preset ${config.clipLength} \\
  --clip-min-seconds ${config.clipMinSeconds} \\
  --clip-max-seconds ${config.clipMaxSeconds} \\
  --genres ${config.genres.join(",")} \\
  --renderer ${config.renderer} \\
  --hyperframes-template ${config.hyperframesTemplate} \\
  --brand-system-template-id "${config.brandSystemTemplateId}" \\
  --hyperframes-format ${config.hyperframesFormat} \\
  --quality ${config.quality} \\
  --caption-source ${config.captionSource} \\
  --asr-model ${config.asrModel} \\
  --speech-language ${config.speechLanguage} \\
  --transcript-languages ${config.transcriptLanguages} \\
  --style ${config.brandTemplate} \\
  --llm-provider ${config.llmProvider} \\
  --env-file ../.env.local`;
}

export function MediaStudioApp() {
  const [section, setSection] = useState<Section>("dashboard");
  const [clips, setClips] = useState<ClipCandidate[]>([]);
  const [targets, setTargets] = useState<PublishTarget[]>([]);
  const [credentials, setCredentials] = useState<CredentialStatus | null>(null);
  const [style, setStyle] = useState<StyleProfile | null>(null);
  const [templates, setTemplates] = useState<BrandTemplate[]>([]);
  const [hyperframesTemplates, setHyperframesTemplates] = useState<HyperframesTemplate[]>([]);
  const [hyperframesCatalog, setHyperframesCatalog] = useState<HyperframesCatalog | null>(null);
  const [durationPresets, setDurationPresets] = useState<DurationPreset[]>([]);
  const [genres, setGenres] = useState<GenreOption[]>([]);
  const [engineHealth, setEngineHealth] = useState<EngineHealth | null>(null);
  const [autonomy, setAutonomy] = useState<AutonomySettings | null>(null);
  const [jobs, setJobs] = useState<GenerationJob[]>([]);
  const [rerenderJobs, setRerenderJobs] = useState<RerenderJob[]>([]);
  const [schedule, setSchedule] = useState<ScheduledPost[]>([]);
  const [publishAttempts, setPublishAttempts] = useState<PublishAttempt[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [filter, setFilter] = useState("all");
  const [showPublished, setShowPublished] = useState(false);
  const [status, setStatus] = useState("Ready");
  const [busy, setBusy] = useState(false);
  const [actionStates, setActionStates] = useState<Record<string, ActionUiState>>({});
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState | null>(null);
  const [rerendering, setRerendering] = useState<Record<string, RerenderUiState>>({});
  const [captionDrafts, setCaptionDrafts] = useState<Record<string, string>>({});
  const [postCopyDrafts, setPostCopyDrafts] = useState<Record<string, string>>({});
  const [publishSelection, setPublishSelection] = useState<string[]>(publishPlatforms);
  const [generateConfig, setGenerateConfig] = useState<GenerateConfig>({
    sourceUrl: defaultSourceUrl,
    count: 5,
    clipLength: "auto",
    clipMinSeconds: 20,
    clipMaxSeconds: 180,
    genres: ["kajian", "spiritual_reflection", "advice"],
    brandTemplate: defaultTemplate,
    hyperframesTemplate: "auto",
    brandSystemTemplateId: "",
    hyperframesFormat: "short_9_16",
    renderer: "hyperframes",
    quality: "production",
    captionSource: "whisper",
    asrModel: "medium",
    speechLanguage: "id",
    transcriptLanguages: "id,en",
    llmProvider: "deepseek",
  });

  const selected = useMemo(() => clips.find((clip) => clip.id === selectedId) || clips[0], [clips, selectedId]);
  const filtered = useMemo(
    () => clips.filter((clip) => matchesReviewFilter(clip, filter)).filter((clip) => showPublished || filter === "published" || clip.status !== "published"),
    [clips, filter, showPublished],
  );
  const activeTargets = useMemo(() => targets.filter((target) => publishPlatforms.includes(target.platform)), [targets]);
  const approved = clips.filter((clip) => clip.status === "approved").length;
  const scheduledCount = clips.filter((clip) => clip.status === "scheduled" || clip.status === "ready_to_publish").length;
  const readyPlatforms = credentials ? Object.values(credentials.platforms).filter((item) => item.ready).length : 0;
  const hasTemplate = hyperframesTemplates.length > 0 || generateConfig.hyperframesTemplate !== "auto";
  const engineReady = Boolean(engineHealth?.hyperframes.ready);
  const nextAction = getNextAction({
    clips,
    approvedCount: approved,
    scheduledCount,
    readyPlatforms,
    targetCount: activeTargets.length || publishPlatforms.length,
    engineReady,
    hasTemplate,
  });
  const isErrorStatus = /failed|error|invalid|offline|unauthorized|blocked/i.test(status);
  const headerStatus = !busy && !isErrorStatus && !engineReady
    ? engineHealth?.hyperframes.reason || "HyperFrames runtime check required"
    : status;
  const workflowSteps = buildWorkflowSteps({
    clips,
    approvedCount: approved,
    scheduledCount,
    readyPlatforms,
    targetCount: activeTargets.length || publishPlatforms.length,
    engineReady,
    hasTemplate,
  });
  const command = productionCommand(generateConfig);
  const selectedCaptionDraft = selected ? captionDrafts[selected.id] ?? (selected.captions || []).map((caption) => caption.text).filter(Boolean).join("\n") : "";
  const selectedPostCopyDraft = selected ? postCopyDrafts[selected.id] ?? selected.post_caption ?? "" : "";

  function pushToast(message: string, tone: ToastMessage["tone"] = "info") {
    const id = `${Date.now()}_${Math.random().toString(16).slice(2)}`;
    setToasts((items) => [{id, message, tone}, ...items].slice(0, 4));
  }

  function setAction(key: string, state?: ActionUiState) {
    setActionStates((items) => {
      const next = {...items};
      if (state) next[key] = state;
      else delete next[key];
      return next;
    });
  }

  async function runAction<T>(key: string, message: string, task: () => Promise<T>, doneMessage?: string) {
    setAction(key, {status: "running", message});
    try {
      const result = await task();
      if (doneMessage) pushToast(doneMessage, "success");
      setAction(key, {status: "done", message: doneMessage || "Done"});
      window.setTimeout(() => setAction(key), 2200);
      return result;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Action failed";
      setAction(key, {status: "failed", message: errorMessage});
      pushToast(errorMessage, "error");
      throw error;
    }
  }
  const rerenderState = useMemo(() => {
    const persisted: Record<string, RerenderUiState> = {};
    for (const job of rerenderJobs) {
      if (persisted[job.candidate_id]) continue;
      if (job.status === "queued" || job.status === "running") {
        persisted[job.candidate_id] = {
          status: "running",
          message: job.message || "Re-rendering video...",
          progress: typeof job.progress === "number" ? job.progress : 0,
        };
      } else if (job.status === "failed") {
        persisted[job.candidate_id] = {
          status: "failed",
          message: job.error || job.message || "Re-render failed",
          progress: 100,
        };
      } else if (job.status === "completed") {
        persisted[job.candidate_id] = {
          status: "done",
          message: job.message || "Render updated",
          progress: 100,
        };
      }
    }
    return {...persisted, ...rerendering};
  }, [rerenderJobs, rerendering]);

  async function refreshAll() {
    setBusy(true);
    setStatus("Syncing media engine...");
    try {
      const [
        reviewRows,
        targetRows,
        credentialRows,
        styleRows,
        templateRows,
        hyperframesTemplateRows,
        durationRows,
        genreRows,
        engineRows,
        catalogRows,
        jobRows,
        rerenderRows,
        scheduleRows,
        autonomyRows,
        attemptResult,
      ] = await Promise.all([
        apiGet<ClipCandidate[]>("review"),
        apiGet<PublishTarget[]>("targets"),
        apiGet<CredentialStatus>("credentials"),
        apiGet<StyleProfile>("style"),
        apiGet<BrandTemplate[]>("brand-templates"),
        apiGet<HyperframesTemplate[]>("hyperframes-templates"),
        apiGet<DurationPreset[]>("duration-presets"),
        apiGet<GenreOption[]>("genres"),
        apiGet<EngineHealth>("engine-health"),
        apiGet<HyperframesCatalog>("hyperframes-catalog"),
        apiGet<GenerationJob[]>("generation-jobs"),
        apiGet<RerenderJob[]>("rerender-jobs"),
        apiGet<ScheduledPost[]>("schedule"),
        apiGet<AutonomySettings>("autonomy-settings"),
        apiGet<PublishAttempt[]>("publish-attempts").then((rows) => ({ok: true as const, rows})).catch((error) => ({ok: false as const, error})),
      ]);
      setClips(reviewRows);
      setTargets(targetRows);
      setCredentials(credentialRows);
      setStyle(styleRows);
      setTemplates(templateRows);
      setHyperframesTemplates(hyperframesTemplateRows);
      setDurationPresets(durationRows);
      setGenres(genreRows);
      setEngineHealth(engineRows);
      setHyperframesCatalog(catalogRows);
      setJobs(jobRows);
      setRerenderJobs(rerenderRows);
      setSchedule(scheduleRows);
      setAutonomy(autonomyRows);
      setPublishAttempts(attemptResult.ok ? attemptResult.rows : []);
      setRerendering({});
      setPublishSelection((current) => {
        const enabled = targetRows
          .filter((target) => publishPlatforms.includes(target.platform) && target.mode !== "off")
          .map((target) => target.platform);
        return current.length ? current.filter((platform) => enabled.includes(platform)) : enabled;
      });
      setSelectedId((current) => current || reviewRows[0]?.id || "");
      if (!attemptResult.ok) {
        const message = attemptResult.error instanceof Error ? attemptResult.error.message : "publish history temporarily unavailable";
        setStatus(`Workspace synced with warning: ${message}`);
      } else {
        setStatus("Workspace synced");
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to sync");
    } finally {
      setBusy(false);
    }
  }

  async function copyText(value: string, label = "Copied") {
    await navigator.clipboard.writeText(value);
    setStatus(label);
    pushToast(label, "success");
  }

  async function approveClip(id: string) {
    const key = `clip:${id}:approve`;
    try {
      await runAction(key, "Approving clip...", async () => {
        await apiPost("approve", {candidate_id: id});
        setClips((items) => items.map((clip) => (clip.id === id ? {...clip, status: "approved"} : clip)));
      }, "Clip approved");
      setStatus("Clip approved");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Approve failed");
    }
  }

  async function holdClip(id: string) {
    const key = `clip:${id}:hold`;
    try {
      await runAction(key, "Holding for review...", () => apiPost("hold", {candidate_id: id}), "Clip held for manual review");
      setStatus("Clip held for manual review");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Hold failed");
    }
  }

  async function updateAutonomyMode(mode: string) {
    if (!autonomy) return;
    const key = `autonomy:${mode}`;
    try {
      const next = await runAction(key, `Switching autonomy to ${mode}...`, () => apiPost<AutonomySettings>("autonomy-settings", {...autonomy, autonomy_mode: mode}), `Autonomy set to ${mode}`);
      setAutonomy(next);
      setStatus(`Autonomy mode set to ${mode}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Autonomy update failed");
    }
  }

  async function startGeneration() {
    const key = "generate:start";
    try {
      setStatus("Generation job queued...");
      const job = await runAction(key, "Starting generation batch...", () => apiPost<GenerationJob>("generation-jobs", {
          source_url: generateConfig.sourceUrl,
          count: generateConfig.count,
          clip_length_preset: generateConfig.clipLength,
          clip_min_seconds: generateConfig.clipMinSeconds,
          clip_max_seconds: generateConfig.clipMaxSeconds,
          genres: generateConfig.genres,
          brand_template: generateConfig.brandTemplate,
          hyperframes_template: generateConfig.hyperframesTemplate,
          brand_system_template_id: generateConfig.brandSystemTemplateId,
          hyperframes_format: generateConfig.hyperframesFormat,
          renderer: generateConfig.renderer,
          quality: generateConfig.quality,
          caption_source: generateConfig.captionSource,
          asr_model: generateConfig.asrModel,
          speech_language: generateConfig.speechLanguage,
          transcript_languages: generateConfig.transcriptLanguages,
          llm_provider: generateConfig.llmProvider,
          env_file: "../.env.local",
        }), "Generation batch started");
      setJobs((items) => [job, ...items.filter((item) => item.id !== job.id)]);
      setStatus("Generation running in background");
      window.setTimeout(() => void refreshAll(), 1600);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Generation failed");
    }
  }

  async function scheduleNext(id: string) {
    const key = `clip:${id}:schedule`;
    try {
      await runAction(key, "Scheduling next slot...", () => apiPost("schedule-next", {candidate_id: id, platforms: publishSelection}), "Clip scheduled");
      setStatus("Clip scheduled in next open slot");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Schedule failed");
    }
  }

  async function updateSchedulePlatforms(scheduleId: string, platforms: string[]) {
    const key = `schedule:${scheduleId}:platforms`;
    try {
      await runAction(key, "Updating publish targets...", () => apiPost("schedule-platforms", {schedule_id: scheduleId, platforms}), "Publish targets updated");
      setStatus("Publish targets updated");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Platform update failed");
    }
  }

  function togglePublishSelection(platform: string) {
    const nextEnabled = !publishSelection.includes(platform);
    const key = `target:${platform}`;
    setAction(key, {status: "running", message: nextEnabled ? "Enabling target" : "Disabling target"});
    setPublishSelection((current) => {
      if (current.includes(platform)) {
        return current.filter((item) => item !== platform);
      }
      return [...current, platform];
    });
    window.setTimeout(() => setAction(key, {status: "done", message: nextEnabled ? "Target enabled" : "Target disabled"}), 180);
    window.setTimeout(() => setAction(key), 1600);
  }

  async function unscheduleClip(id: string) {
    const key = `clip:${id}:unschedule`;
    try {
      await runAction(key, "Returning clip to approved queue...", () => apiPost("unschedule", {candidate_id: id}), "Clip unscheduled");
      setStatus("Clip returned to approved queue");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unschedule failed");
    }
  }

  function deleteClip(id: string) {
    setConfirmDialog({
      title: "Delete rendered clip?",
      message: "This removes the clip from the review queue and deletes its local rendered artifacts.",
      confirmLabel: "Delete clip",
      tone: "danger",
      onConfirm: () => void performDeleteClip(id),
    });
  }

  async function performDeleteClip(id: string) {
    const key = `clip:${id}:delete`;
    try {
      await runAction(key, "Deleting clip artifacts...", async () => {
        await apiPost("delete-candidate", {candidate_id: id, delete_artifacts: true});
        setClips((items) => items.filter((clip) => clip.id !== id));
        if (selectedId === id) setSelectedId("");
      }, "Clip deleted");
      setStatus("Clip deleted");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Delete failed");
    }
  }

  function clearQueue() {
    setConfirmDialog({
      title: "Clear review queue?",
      message: "This deletes every visible clip candidate and its local artifacts from this workspace.",
      confirmLabel: "Clear queue",
      tone: "danger",
      onConfirm: () => void performClearQueue(),
    });
  }

  async function performClearQueue() {
    const key = "queue:clear";
    try {
      await runAction(key, "Clearing review queue...", async () => {
        await apiPost("clear-review", {confirm: "DELETE", delete_artifacts: true});
        setClips([]);
        setSelectedId("");
      }, "Queue cleared");
      setStatus("Queue cleared");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Clear failed");
    }
  }

  async function testConnection(platform: string) {
    const key = `test:${platform}`;
    const message = `Testing ${platformLabel(platform)} connection...`;
    setStatus(message);
    try {
      await runAction(key, message, () => apiPost("connection-test", {platform}), `${platformLabel(platform)} connected`);
      setStatus(`${platformLabel(platform)} connected`);
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Connection check failed");
    }
  }

  async function startOauthConnect(platform: string) {
    const key = `connect:${platform}`;
    try {
      const result = await runAction(
        key,
        `Opening ${platformLabel(platform)} OAuth...`,
        () => apiPost<{platform: string; auth_url: string}>("oauth-start", {platform}),
      );
      const popup = window.open(result.auth_url, "_blank", "width=560,height=760,noopener,noreferrer");
      if (!popup) {
        setStatus("Popup blocked. Allow popups, then click Connect again.");
        setAction(key, {status: "failed", message: "Popup blocked"});
        return;
      }
      setStatus(`Continue OAuth in popup for ${platformLabel(platform)}...`);
      setAction(key, {status: "running", message: "Waiting for OAuth popup"});
      const timer = window.setInterval(() => {
        if (popup.closed) {
          window.clearInterval(timer);
          void refreshAll();
          setStatus(`${platformLabel(platform)} OAuth finished. Refreshing status...`);
          setAction(key, {status: "done", message: "OAuth finished"});
          pushToast(`${platformLabel(platform)} OAuth finished`, "success");
          window.setTimeout(() => setAction(key), 2200);
        }
      }, 800);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "OAuth start failed");
    }
  }

  function disconnectPlatform(platform: string) {
    setConfirmDialog({
      title: `Disconnect ${platformLabel(platform)}?`,
      message: "Publishing will stay disabled for this channel until you connect it again.",
      confirmLabel: "Disconnect",
      tone: "danger",
      onConfirm: () => void performDisconnectPlatform(platform),
    });
  }

  async function performDisconnectPlatform(platform: string) {
    const key = `disconnect:${platform}`;
    try {
      await runAction(key, `Disconnecting ${platformLabel(platform)}...`, () => apiPost("connection-disconnect", {platform}), `${platformLabel(platform)} disconnected`);
      setStatus(`${platformLabel(platform)} disconnected`);
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Disconnect failed");
    }
  }

  async function publishDueNow(dryRun = false) {
    const key = dryRun ? "publish:due:dry" : "publish:due:live";
    try {
      setStatus(dryRun ? "Checking due publish queue..." : "Publishing due schedule...");
      const result = await runAction(key, dryRun ? "Checking due publish queue..." : "Publishing due schedule...", () => apiPost<{count: number; processed?: unknown[]}>("publish-due", {limit: 5, dry_run: dryRun}));
      setStatus(`${dryRun ? "Checked" : "Processed"} ${result.count || 0} due publish item(s)`);
      pushToast(`${dryRun ? "Checked" : "Processed"} ${result.count || 0} due publish item(s)`, "success");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Publish due failed");
    }
  }

  function buildEditedCaptionSegments(base: CaptionSegment[], draft: string) {
    const lines = draft.split(/\n+/).map((line) => line.trim()).filter(Boolean);
    return base.slice(0, lines.length).map((segment, index) => ({
      text: lines[index],
      startMs: segment.startMs,
      endMs: segment.endMs,
      timestampMs: segment.startMs,
    }));
  }

  async function saveCaptionCorrections(id: string, draft: string) {
    const clip = clips.find((item) => item.id === id);
    const base = clip?.captions || [];
    const captions = buildEditedCaptionSegments(base, draft);
    if (!captions.length) {
      setStatus("No caption lines to save");
      return;
    }
    const key = `caption:${id}:save`;
    try {
      await runAction(key, "Saving caption edits...", () => apiPost("caption-corrections", {candidate_id: id, captions}), "Caption edits saved");
      setStatus("Caption edits saved. Re-render this clip to update the video.");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Caption save failed");
    }
  }

  async function savePostCopy(id: string, draft: string) {
    const key = `post:${id}:save`;
    try {
      const result = await runAction(
        key,
        "Saving post copy...",
        () => apiPost<{post_caption: string}>("post-copy", {candidate_id: id, post_caption: draft}),
        "Post copy saved",
      );
      setPostCopyDrafts((items) => ({...items, [id]: result.post_caption}));
      setStatus("Post copy saved for scheduled and live publishing.");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Post copy save failed");
    }
  }

  async function generatePostCopy(id: string) {
    const key = `post:${id}:generate`;
    try {
      const result = await runAction(
        key,
        "Generating post copy with AI...",
        () => apiPost<{post_caption: string; source?: string}>("post-copy-generate", {
          candidate_id: id,
          llm_provider: generateConfig.llmProvider,
        }),
        "Post copy regenerated",
      );
      setPostCopyDrafts((items) => ({...items, [id]: result.post_caption}));
      setStatus(result.source?.startsWith("llm_") ? "AI post copy generated." : "Post copy generated from transcript fallback.");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Post copy generation failed");
    }
  }

  async function rerenderClip(id: string) {
    const key = `clip:${id}:rerender`;
    setRerendering((items) => ({...items, [id]: {status: "running", message: "Queued for re-render", progress: 2}}));
    setStatus("Re-rendering selected clip...");
    try {
      const job = await runAction(key, "Starting re-render job...", () => apiPost<RerenderJob>("rerender", {
        candidate_id: id,
        renderer: "hyperframes",
        quality: "production",
        style: generateConfig.brandTemplate || defaultTemplate,
      }), "Re-render job started");
      setRerenderJobs((items) => [job, ...items.filter((item) => item.id !== job.id)]);
      setStatus("Re-render job started");
      window.setTimeout(() => void refreshAll(), 900);
    } catch (error) {
      setRerendering((items) => ({
        ...items,
        [id]: {
          status: "failed",
          message: error instanceof Error ? error.message : "Re-render failed",
          progress: 100,
        },
      }));
      setStatus(error instanceof Error ? error.message : "Re-render failed");
    }
  }

  async function refreshClipMetadata(id: string, mode: "smart" | "local" = "smart") {
    const key = `clip:${id}:metadata`;
    try {
      await runAction(
        key,
        mode === "smart" ? "Refreshing metadata with smart fallback..." : "Refreshing metadata locally...",
        () => apiPost("metadata-refresh", {candidate_id: id, mode}),
        "Metadata refreshed",
      );
      await refreshAll();
      setConfirmDialog({
        title: "Metadata refreshed",
        message: "Title, description, scoring, and post copy are updated. Re-render now if you want the new hook baked into the video file.",
        confirmLabel: "Re-render now",
        cancelLabel: "Later",
        onConfirm: () => void rerenderClip(id),
      });
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Metadata refresh failed");
    }
  }

  async function saveClipBoundary(id: string, startMs: number, endMs: number, rerenderAfter: boolean) {
    const key = `clip:${id}:boundary`;
    try {
      const result = await runAction(
        key,
        rerenderAfter ? "Saving timing and starting re-render..." : "Saving clip timing...",
        () => apiPost<{rerender_job?: RerenderJob}>("clip-boundary", {
          candidate_id: id,
          start_ms: startMs,
          end_ms: endMs,
          rerender_after: rerenderAfter,
          renderer: "hyperframes",
          quality: "production",
          style: generateConfig.brandTemplate || defaultTemplate,
        }),
        rerenderAfter ? "Timing saved. Re-render started." : "Timing saved",
      );
      if (result.rerender_job) {
        setRerenderJobs((items) => [result.rerender_job!, ...items.filter((item) => item.id !== result.rerender_job!.id)]);
      } else if (!rerenderAfter) {
        setConfirmDialog({
          title: "Timing saved",
          message: "The clip boundary changed. Re-render now to generate a video file with the new start/end timing.",
          confirmLabel: "Re-render now",
          cancelLabel: "Later",
          onConfirm: () => void rerenderClip(id),
        });
      }
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Timing update failed");
    }
  }

  function setSelectedCaptionDraft(value: string) {
    if (!selected) return;
    setCaptionDrafts((items) => ({...items, [selected.id]: value}));
  }

  function setSelectedPostCopyDraft(value: string) {
    if (!selected) return;
    setPostCopyDrafts((items) => ({...items, [selected.id]: value}));
  }

  useEffect(() => {
    const savedTemplate = window.localStorage.getItem("otonom.hyperframesTemplateDefault");
    if (!savedTemplate) return;
    setGenerateConfig((current) => ({...current, hyperframesTemplate: savedTemplate}));
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshAll();
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!toasts.length) return;
    const timer = window.setTimeout(() => {
      setToasts((items) => items.slice(0, -1));
    }, 4600);
    return () => window.clearTimeout(timer);
  }, [toasts]);

  useEffect(() => {
    const hasRunningGeneration = jobs.some((job) => job.status === "queued" || job.status === "running");
    const hasRunningRerender = rerenderJobs.some((job) => job.status === "queued" || job.status === "running");
    if (!hasRunningGeneration && !hasRunningRerender) return;
    const timer = window.setInterval(() => {
      void refreshAll();
    }, 3500);
    return () => window.clearInterval(timer);
  }, [jobs, rerenderJobs]);

  return (
    <div className="min-h-screen overflow-x-hidden text-zinc-100">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[280px] flex-col border-r border-white/[0.07] bg-[#0c0d10]/[0.92] px-4 py-5 backdrop-blur-xl lg:flex">
        <div className="flex shrink-0 items-center gap-3 px-1">
          <div className="grid h-11 w-11 place-items-center rounded-2xl border border-cyan/[0.55] bg-cyan/[0.04] text-lg font-semibold text-white shadow-[0_0_24px_rgba(102,232,249,0.12)]">N</div>
          <div>
            <h1 className="text-base font-semibold leading-5">Otonom Media</h1>
            <p className="text-xs text-zinc-400">Guided production OS</p>
          </div>
        </div>

        <nav className="mt-8 grid min-h-0 flex-1 auto-rows-min content-start gap-3 overflow-y-auto pr-1">
          {nav.map((item, index) => {
            const Icon = item.icon;
            const active = section === item.id;
            const step = workflowSteps.find((workflowStep) => workflowStep.section === item.id);
            return (
              <button
                key={item.id}
                onClick={() => setSection(item.id)}
                className={`group relative flex min-h-[56px] items-center gap-3 overflow-hidden rounded-[18px] border px-3.5 py-2 text-left text-sm font-medium transition ${
                  active
                    ? "border-cyan/[0.30] bg-cyan/[0.09] text-cyan shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]"
                    : "border-transparent text-zinc-500 hover:bg-white/[0.035] hover:text-zinc-100"
                }`}
              >
                <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-2xl transition ${active ? "bg-cyan text-ink" : "bg-white/[0.035] text-zinc-500 group-hover:text-zinc-200"}`}>
                  <Icon className="h-3.5 w-3.5" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-semibold">{item.label}</span>
                  <span className={`mt-0.5 block truncate text-[10px] font-medium ${active ? "text-cyan/70" : "text-zinc-600"}`}>{step?.detail || `Step ${index + 1}`}</span>
                </span>
                {step ? <span className={`h-1.5 w-1.5 rounded-full ${step.status === "ready" ? "bg-teal" : step.status === "active" ? "bg-cyan" : step.status === "blocked" ? "bg-warning" : "bg-white/[0.16]"}`} /> : null}
              </button>
            );
          })}
        </nav>

        <div className="mt-4 grid shrink-0 gap-3">
          <div className="rounded-[22px] border border-white/[0.07] bg-white/[0.035] p-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm font-semibold">Next action</span>
              <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${nextAction.tone === "warning" ? "bg-warning/[0.10] text-warning" : "bg-teal/[0.10] text-teal"}`}>{nextAction.tone}</span>
            </div>
            <button type="button" onClick={() => setSection(nextAction.section)} className="w-full rounded-2xl border border-white/[0.06] bg-black/20 px-3 py-3 text-left transition hover:border-cyan/[0.20]">
              <span className="block text-sm font-semibold text-cyan">{nextAction.label}</span>
              <span className="mt-1 block text-xs leading-5 text-zinc-500">{nextAction.detail}</span>
            </button>
          </div>
        </div>
      </aside>

      <main className="min-w-0 pb-20 lg:pl-[280px] lg:pb-0">
        <header className="sticky top-0 z-20 overflow-hidden border-b border-white/[0.06] bg-canvas-deep/[0.82] px-5 py-4 backdrop-blur-xl lg:px-8">
          <div className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <div className="min-w-0">
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-cyan/[0.20] bg-teal/[0.08] px-3 py-1 text-xs font-semibold text-cyan">Guided Studio OS</span>
                <span className="text-xs font-medium text-zinc-500">Active Workspace</span>
              </div>
              <h2 className="max-w-full text-balance break-words text-2xl font-semibold tracking-[-0.03em] text-white md:text-3xl">{sectionCopy[section].title}</h2>
              <p className="mt-1 max-w-[calc(100vw-40px)] break-words text-sm text-zinc-400 md:max-w-2xl">{sectionCopy[section].subtitle}</p>
            </div>
            <div className="grid min-w-0 grid-cols-1 items-center gap-2 sm:flex sm:flex-wrap">
              <button onClick={() => setSection(nextAction.section)} className="inline-flex h-11 min-w-0 items-center justify-center gap-2 rounded-full bg-cyan px-4 text-sm font-semibold text-ink">
                <Wand2 className="h-4 w-4" /> {nextAction.label}
              </button>
              <button onClick={refreshAll} className="inline-flex h-11 min-w-0 items-center justify-center gap-2 rounded-full border border-white/[0.10] bg-surface px-4 text-sm font-medium text-zinc-200 hover:bg-surface-raised">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />} Refresh
              </button>
              <StatusPill busy={busy} status={headerStatus} />
            </div>
          </div>
        </header>

        <div className="grid min-w-0 gap-5 px-5 py-5 lg:px-8">
          {section === "dashboard" && (
            <DashboardSection
              clips={clips}
              schedule={schedule}
              nextAction={nextAction}
              workflowSteps={workflowSteps}
              readyPlatforms={readyPlatforms}
              targetCount={activeTargets.length || publishPlatforms.length}
              activeJobs={jobs.filter((job) => job.status === "queued" || job.status === "running").length}
              onSection={setSection}
            />
          )}

          {section === "generate" && (
            <GenerateSection
              config={generateConfig}
              templates={templates}
              hyperframesTemplates={hyperframesTemplates}
              hyperframesCatalog={hyperframesCatalog}
              durationPresets={durationPresets}
              genres={genres}
              jobs={jobs}
              engineHealth={engineHealth}
              actionState={actionStates["generate:start"]}
              setConfig={setGenerateConfig}
              command={command}
              defaultTemplatePath={defaultTemplate}
              statusTone={statusTone}
              onGenerate={startGeneration}
              onCopy={() => copyText(command, "Production command copied")}
              renderReadinessLine={(props) => <ReadinessLine {...props} />}
              renderActionStatus={(state) => (state ? <InlineActionStatus state={state} /> : null)}
              renderEmptyState={(title, text) => <EmptyState title={title} text={text} />}
            />
          )}

          {section === "templates" && (
            <TemplatesSection
              templates={hyperframesTemplates}
              catalog={hyperframesCatalog}
              engineHealth={engineHealth}
              currentTemplate={generateConfig.hyperframesTemplate}
              onUse={(templateId) => {
                const selectedTemplate = hyperframesTemplates.find((template) => template.id === templateId);
                setGenerateConfig((current) => ({
                  ...current,
                  renderer: "hyperframes",
                  hyperframesTemplate: templateId,
                  brandSystemTemplateId: selectedTemplate?.source === "brand_system" ? templateId : "",
                  brandTemplate: selectedTemplate?.brand_template_path || current.brandTemplate,
                }));
                setSection("generate");
                pushToast("Template selected for HyperFrames", "success");
              }}
              onSetDefault={(templateId) => {
                window.localStorage.setItem("otonom.hyperframesTemplateDefault", templateId);
                setGenerateConfig((current) => ({...current, hyperframesTemplate: templateId}));
                pushToast("HyperFrames default saved in this browser", "success");
              }}
              onCustomize={(templateId) => {
                window.localStorage.setItem("otonom.brandBuilderStarterTemplate", templateId);
                setGenerateConfig((current) => ({...current, hyperframesTemplate: templateId, renderer: "hyperframes"}));
                setSection("brand");
                pushToast("Opening Brand System builder from this template", "success");
              }}
              renderStatusPill={(busy, status) => <StatusPill busy={busy} status={status} />}
              renderSettingTile={(label, value) => <SettingTile label={label} value={value} />}
              renderEmptyState={(title, text) => <EmptyState title={title} text={text} />}
            />
          )}

          {section === "review" && (
            <ReviewStudioSection
              clips={filtered}
              selected={selected}
              rerendering={rerenderState}
              filter={filter}
              showPublished={showPublished}
              reviewFilters={reviewFilters}
              actionStates={actionStates}
              setFilter={setFilter}
              setShowPublished={setShowPublished}
              setSelectedId={setSelectedId}
              captionDraft={selectedCaptionDraft}
              setCaptionDraft={setSelectedCaptionDraft}
              postCopyDraft={selectedPostCopyDraft}
              setPostCopyDraft={setSelectedPostCopyDraft}
              statusTone={statusTone}
              formatDeadline={formatDeadline}
              primaryReviewAction={primaryReviewAction}
              onApprove={approveClip}
              onSchedule={scheduleNext}
              onHold={holdClip}
              onDelete={deleteClip}
              onClear={clearQueue}
              onSaveCaptions={saveCaptionCorrections}
              onSavePostCopy={savePostCopy}
              onGeneratePostCopy={generatePostCopy}
              onRerender={rerenderClip}
              onRefreshMetadata={refreshClipMetadata}
              onSaveBoundary={saveClipBoundary}
            />
          )}

          {section === "calendar" && (
            <CalendarSection
              schedule={schedule}
              approved={clips.filter((clip) => clip.status === "approved")}
              targets={activeTargets}
              selectedPlatforms={publishSelection}
              actionStates={actionStates}
              onToggleDefaultPlatform={togglePublishSelection}
              onSchedule={scheduleNext}
              onUnschedule={unscheduleClip}
              onUpdateSchedulePlatforms={updateSchedulePlatforms}
              onPublishDue={() => publishDueNow(false)}
              onDryRunDue={() => publishDueNow(true)}
              formatSchedule={formatSchedule}
              formatClipStatus={formatClipStatus}
              cleanPublishStatus={cleanPublishStatus}
              statusTone={statusTone}
              renderScoreBubble={(value) => <ScoreBubble value={value} />}
              renderInlineActionStatus={(state) => <InlineActionStatus state={state} />}
              renderEmptyState={(title, text) => <EmptyState title={title} text={text} />}
            />
          )}

          {section === "publish" && (
            <PublishSection
              targets={activeTargets}
              credentials={credentials}
              attempts={publishAttempts}
              selectedPlatforms={publishSelection}
              actionStates={actionStates}
              onTogglePlatform={togglePublishSelection}
              onTestConnection={testConnection}
              onStartOauth={startOauthConnect}
              onDisconnect={disconnectPlatform}
              oauthPlatforms={oauthPlatforms}
              publicAccountLabel={publicAccountLabel}
              publishActionHint={publishActionHint}
              formatPlatformMode={formatPlatformMode}
              cleanPublishStatus={cleanPublishStatus}
              statusTone={statusTone}
              renderSettingTile={(label, value) => <SettingTile label={label} value={value} />}
              renderReadinessLine={(ready, label, detail) => <ReadinessLine ready={ready} label={label} detail={detail} />}
              renderEmptyState={(title, text) => <EmptyState title={title} text={text} />}
            />
          )}

          {section === "brand" && (
            <BrandSection
              style={style}
              templates={templates}
              hyperframesTemplates={hyperframesTemplates}
              hyperframesCatalog={hyperframesCatalog}
              autonomy={autonomy}
              actionStates={actionStates}
              defaultTemplate={defaultTemplate}
              onAutonomyMode={updateAutonomyMode}
              onTemplateSaved={refreshAll}
            />
          )}
        </div>

        <nav className="fixed bottom-0 left-0 right-0 z-40 grid grid-cols-7 border-t border-white/[0.08] bg-surface/[0.95] pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = section === item.id;
            return (
              <button key={item.id} onClick={() => setSection(item.id)} className={`grid h-16 min-w-0 place-items-center content-center gap-1 px-0.5 text-[9px] ${active ? "text-cyan" : "text-zinc-500"}`}>
                <Icon className="h-4 w-4" />
                <span className="max-w-full truncate">{item.label.split(" ")[0]}</span>
              </button>
            );
          })}
        </nav>
        <ToastStack toasts={toasts} onDismiss={(id) => setToasts((items) => items.filter((item) => item.id !== id))} />
        <ActionMonitor actionStates={actionStates} />
        <ConfirmDialog dialog={confirmDialog} onClose={() => setConfirmDialog(null)} />
      </main>
    </div>
  );
}

function StatusPill({busy, status}: {busy: boolean; status: string}) {
  const isError = /failed|error|invalid|offline|unauthorized|blocked/i.test(status);
  return (
    <div
      className={`inline-flex min-w-0 items-center justify-center gap-2 rounded-full border px-3 py-2 text-xs font-semibold ${
        isError
          ? "border-danger/[0.28] bg-danger/[0.10] text-danger"
          : busy
            ? "border-cyan/[0.28] bg-teal/[0.10] text-cyan"
            : "border-teal/[0.22] bg-teal/[0.08] text-teal"
      }`}
    >
      {busy ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" /> : isError ? <AlertTriangle className="h-3.5 w-3.5 shrink-0" /> : <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />}
      <span className="max-w-[220px] truncate">{status}</span>
    </div>
  );
}

function ReadinessLine({ready, label, detail}: {ready: boolean; label: string; detail: string}) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-3 rounded-2xl border border-white/[0.06] bg-black/15 px-3 py-2">
      <span className="inline-flex min-w-0 items-center gap-2">
        {ready ? <CheckCircle2 className="h-4 w-4 shrink-0 text-cyan" /> : <XCircle className="h-4 w-4 shrink-0 text-zinc-600" />}
        <span className="truncate text-sm font-semibold text-zinc-200">{label}</span>
      </span>
      <span className={ready ? "shrink-0 text-xs font-semibold text-cyan" : "shrink-0 text-xs text-zinc-500"}>{detail}</span>
    </div>
  );
}

function ToastStack({toasts, onDismiss}: {toasts: ToastMessage[]; onDismiss: (id: string) => void}) {
  if (!toasts.length) return null;
  return (
    <div className="fixed right-4 top-24 z-50 grid w-[min(360px,calc(100vw-32px))] gap-2">
      {toasts.map((toast) => (
        <button
          key={toast.id}
          onClick={() => onDismiss(toast.id)}
          className={`rounded-2xl border px-4 py-3 text-left text-sm shadow-2xl backdrop-blur-xl ${
            toast.tone === "error"
              ? "border-danger/[0.30] bg-danger/[0.14] text-red-100"
              : toast.tone === "success"
                ? "border-teal/[0.30] bg-teal/[0.14] text-teal"
                : "border-cyan/[0.28] bg-canvas-deep/[0.92] text-zinc-100"
          }`}
        >
          {toast.message}
        </button>
      ))}
    </div>
  );
}

function ActionMonitor({actionStates}: {actionStates: Record<string, ActionUiState>}) {
  const actions = Object.entries(actionStates)
    .filter(([, state]) => state.status === "running" || state.status === "failed")
    .slice(0, 4);
  if (!actions.length) return null;
  return (
    <div className="fixed bottom-20 right-4 z-40 grid w-[min(360px,calc(100vw-32px))] gap-2 lg:bottom-5">
      {actions.map(([key, state]) => (
        <div
          key={key}
          className={`rounded-[20px] border px-4 py-3 shadow-2xl backdrop-blur-xl ${
            state.status === "failed" ? "border-danger/[0.30] bg-danger/[0.14] text-red-100" : "border-cyan/[0.26] bg-canvas-deep/[0.92] text-zinc-100"
          }`}
        >
          <div className="flex items-center gap-2">
            {state.status === "running" ? <Loader2 className="h-4 w-4 shrink-0 animate-spin text-cyan" /> : <AlertTriangle className="h-4 w-4 shrink-0 text-danger" />}
            <p className="min-w-0 flex-1 truncate text-sm font-semibold">{state.message}</p>
          </div>
          {state.status === "running" ? (
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/[0.08]">
              <div className="h-full w-2/3 animate-pulse rounded-full bg-cyan" />
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function ConfirmDialog({dialog, onClose}: {dialog: ConfirmDialogState | null; onClose: () => void}) {
  if (!dialog) return null;
  const danger = dialog.tone === "danger";
  return (
    <div className="fixed inset-0 z-[60] grid place-items-center bg-black/60 px-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
      <div className="w-full max-w-md rounded-[28px] border border-white/[0.10] bg-surface p-5 shadow-2xl">
        <div className={`mb-4 grid h-12 w-12 place-items-center rounded-2xl ${danger ? "bg-danger/[0.14] text-danger" : "bg-teal/[0.14] text-cyan"}`}>
          <AlertTriangle className="h-5 w-5" />
        </div>
        <h3 id="confirm-title" className="text-xl font-semibold text-white">{dialog.title}</h3>
        <p className="mt-2 text-sm leading-6 text-zinc-400">{dialog.message}</p>
        <div className="mt-6 grid gap-2 sm:grid-cols-2">
          <button type="button" onClick={onClose} className="h-11 rounded-full border border-white/[0.10] text-sm font-semibold text-zinc-300 hover:bg-white/[0.04]">
            {dialog.cancelLabel || "Cancel"}
          </button>
          <button
            type="button"
            onClick={() => {
              const onConfirm = dialog.onConfirm;
              onClose();
              onConfirm();
            }}
            className={`h-11 rounded-full text-sm font-semibold ${danger ? "bg-danger text-white" : "bg-cyan text-ink"}`}
          >
            {dialog.confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function ScoreBubble({value, label}: {value?: number; label?: string}) {
  return (
    <div className="grid justify-items-center gap-1">
      <span className={`grid h-11 w-11 place-items-center rounded-full border text-sm font-semibold ${scoreTone(value)}`}>{scoreValue(value)}</span>
      {label ? <span className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</span> : null}
    </div>
  );
}
