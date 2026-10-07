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
  BookOpen,
} from "lucide-react";
import {type ReactNode, useEffect, useMemo, useRef, useState} from "react";
import {ContentPackagesSection, type ContentPackageRow} from "@/components/review/ContentPackagesSection";
import {ReviewStudioSection} from "@/components/review/ReviewStudioSection";
import {BrandSection} from "@/components/brand/BrandSection";
import {FocusModal} from "@/components/FocusModal";
import {DashboardSection} from "@/components/home/DashboardSection";
import {ContentPackageCreateSection, type ContentPackageCreateResult} from "@/components/generate/ContentPackageCreateSection";
import {GenerateSection} from "@/components/generate/GenerateSection";
import {WatchChannelsSection} from "@/components/generate/WatchChannelsSection";
import {WorkspaceManagerModal} from "@/components/workspace/WorkspaceManagerModal";
import {WorkspaceSwitcher} from "@/components/workspace/WorkspaceSwitcher";
import {ExplainerSection} from "@/components/explainer/ExplainerSection";
import {TemplatesSection} from "@/components/templates/TemplatesSection";
import {CalendarSection} from "@/components/calendar/CalendarSection";
import {PublishSection} from "@/components/channels/PublishSection";
import {EmptyState, InlineActionStatus, LoadingState, SettingTile} from "@/components/shared/StudioPrimitives";
import {
  apiGet,
  apiPost,
  AutonomySettings,
  BrandTemplate,
  ClipCandidate,
  CredentialStatus,
  PostizIntegration,
  DEFAULT_SHELL_COMPONENTS,
  isTemplateOnlyBrand,
  TEMPLATE_ONLY_BRAND,
  DurationPreset,
  EngineHealth,
  ExplainerJob,
  PathAJob,
  formatDuration,
  formatTimestamp,
  GenerationJob,
  GenreCatalog,
  GenreOption,
  HyperframesCatalog,
  parseGenreCatalog,
  HyperframesTemplate,
  MediaProfile,
  platformLabel,
  canMakeShortsFromClip,
  filterPlatformsForClip,
  type MakeShortsFromLongformResult,
  type DeleteCandidatesResult,
  type BatchRerenderResult,
  type BatchApproveResult,
  canBatchRerenderClip,
  canQuickApproveClip,
  isClipRerendering,
  PublishAttempt,
  PublishTarget,
  ScheduledPost,
  scoreValue,
  ShellComponents,
  SourceResolveResult,
  StyleProfile,
  WatchChannel,
} from "@/lib/media-api";
import {isPublishPlatformDisabled, oauthPlatforms, publishDestinationPlatforms, publishPlatforms} from "@/lib/publish-platforms";

import {
  buildSetupDetails,
  buildWorkflowSteps,
  getNextAction,
  searchForSection,
  sectionFromSearch,
  type FlowInput,
  type NextAction,
  type Section,
  type WorkflowStep,
} from "@/lib/studio-flow";

function stepDotClass(status: WorkflowStep["status"]) {
  if (status === "ready") return "bg-teal";
  if (status === "active") return "bg-cyan";
  if (status === "blocked") return "bg-warning";
  return "bg-white/[0.16]";
}

const defaultSourceUrl = "";
const defaultTemplate = "profiles/default_workspace_style.json";
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
const PROFILE_STORAGE_KEY = "otonom.activeProfileId";

function readStoredProfileId() {
  if (typeof window === "undefined") return "nourbit";
  return window.localStorage.getItem(PROFILE_STORAGE_KEY) || "nourbit";
}

function cleanPublishStatus(status?: string) {
  if (!status) return "Not run";
  const labels: Record<string, string> = {
    ready: "Ready",
    published: "Posted",
    live: "Live",
    accepted: "Sent to Postiz",
    failed: "Postiz error",
    blocked: "Needs action",
    legacy_blocked: "Outdated",
    skipped: "Already posted (verified)",
    publishing: "Publishing",
    pending: "Waiting",
    queued: "On Postiz calendar",
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
    accepted: "Sent to Postiz",
    live: "Live",
    queued: "On Postiz calendar",
    ready: "Ready",
    ready_to_publish: "Ready to publish",
    rendered: "Rendered",
    running: "Running",
    scheduled: "Scheduled",
    partial_failed: "Partially published",
  };
  return labels[status] || status.replaceAll("_", " ");
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

const primaryNav = [
  {id: "dashboard", label: "Home", icon: LayoutDashboard},
  {id: "generate", label: "Create", icon: Wand2},
  {id: "review", label: "Review", icon: Clapperboard},
  {id: "calendar", label: "Schedule", icon: CalendarDays},
  {id: "publish", label: "Publish", icon: Send},
] as const;

const secondaryNav = [
  {id: "explainer", label: "Long video", icon: BookOpen},
  {id: "templates", label: "Templates", icon: Sparkles},
  {id: "brand", label: "Brand", icon: Settings},
] as const;

const nav = [...primaryNav, ...secondaryNav] as const;

const mobilePrimaryNav = primaryNav.filter((item) => item.id !== "dashboard");


const sectionCopy: Record<Section, {title: string; subtitle: string}> = {
  dashboard: {
    title: "Home",
    subtitle: "One clear next step: Create → Review → Schedule → Publish.",
  },
  generate: {
    title: "Create",
    subtitle: "Paste a long video link and generate short clips for Review.",
  },
  explainer: {
    title: "Long video",
    subtitle: "Describe a topic, generate a long video, then approve in Review.",
  },
  templates: {
    title: "Templates",
    subtitle: "Pick a look, then use it in Create.",
  },
  review: {
    title: "Review",
    subtitle: "Approve, fix, or schedule — nothing goes live without you.",
  },
  calendar: {
    title: "Schedule",
    subtitle: "Place approved clips into publishing slots.",
  },
  publish: {
    title: "Publish accounts",
    subtitle: "Connect the accounts this workspace publishes to.",
  },
  brand: {
    title: "Brand",
    subtitle: "Pick a direction, save a style, refine it in Brand Builder.",
  },
};

function nextActionToneLabel(tone: NextAction["tone"]) {
  switch (tone) {
    case "warning":
      return "Needs attention";
    case "ready":
      return "Ready";
    case "primary":
      return "Next";
    default: {
      const _exhaustive: never = tone;
      return _exhaustive;
    }
  }
}

function renderEditorialTitle(title: string) {
  if (title === "Home") {
    return (
      <>
        <span className="font-editorial italic font-normal text-cyan">Home</span>
      </>
    );
  }
  if (title === "Create") {
    return (
      <>
        <span className="font-editorial italic font-normal text-cyan">Create</span> clips
      </>
    );
  }
  if (title === "Explainer" || title === "Long video") {
    return (
      <>
        <span className="font-editorial italic font-normal text-cyan">Long</span> video
      </>
    );
  }
  if (title === "Templates") {
    return (
      <>
        <span className="font-editorial italic font-normal text-cyan">Templates</span> library
      </>
    );
  }
  if (title === "Review") {
    return (
      <>
        Clip <span className="font-editorial italic font-normal text-cyan">workspace</span>
      </>
    );
  }
  if (title === "Schedule") {
    return (
      <>
        Publishing <span className="font-editorial italic font-normal text-cyan">schedule</span>
      </>
    );
  }
  if (title === "Publish accounts") {
    return (
      <>
        Publish <span className="font-editorial italic font-normal text-cyan">accounts</span>
      </>
    );
  }
  if (title === "Brand") {
    return (
      <>
        Brand <span className="font-editorial italic font-normal text-cyan">kit</span>
      </>
    );
  }
  return title;
}

function statusTone(status: string) {
  if (["approved", "published", "live", "ready", "rendered", "scheduled", "ready_to_publish", "completed", "pending_auto_schedule"].includes(status)) return "text-teal border-teal/[0.30] bg-teal/[0.10]";
  if (["running", "queued", "accepted", "starting", "triggering", "polling", "ingesting", "rendering", "planned"].includes(status)) return "text-cyan border-cyan/[0.30] bg-teal/[0.10]";
  if (["failed", "rejected", "partial_failed"].includes(status)) return "text-danger border-danger/[0.30] bg-danger/[0.10]";
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
  curationSource: string;
  asrModel: string;
  speechLanguage: string;
  transcriptLanguages: string;
  llmProvider: string;
  minEditorialScore: number;
  shellComponents: ShellComponents;
};

const reviewFilters = [
  {id: "all", label: "All", hint: "Every clip that is still visible in this workspace.", statuses: []},
  {id: "review", label: "Review", hint: "Clips waiting for approve or skip — not caption copy-edit.", statuses: ["draft", "rendered", "approved", "held", "pending_auto_schedule"]},
  {id: "scheduled", label: "Scheduled", hint: "Approved clips already placed into the publishing queue.", statuses: ["scheduled", "ready_to_publish"]},
  {id: "published", label: "Published", hint: "Clips already sent to a live channel.", statuses: ["published"]},
] as const;

function matchesReviewFilter(clip: ClipCandidate, filter: string) {
  const group = reviewFilters.find((item) => item.id === filter);
  if (!group || group.id === "all") return true;
  return (group.statuses as readonly string[]).includes(clip.status);
}

function shellComponentsForTemplate(templates: HyperframesTemplate[], templateId: string): ShellComponents {
  const template = templates.find((item) => item.id === templateId);
  return template?.shell_components ? {...DEFAULT_SHELL_COMPONENTS, ...template.shell_components} : {...DEFAULT_SHELL_COMPONENTS};
}

function productionCommand(config: GenerateConfig, profileId: string, niche: string) {
  const videoMatch = config.sourceUrl.match(/(?:v=|youtu\.be\/|shorts\/)([A-Za-z0-9_-]{11})/);
  const sourceId = videoMatch ? `${profileId}_${videoMatch[1]}` : `${profileId}_source`;
  const shellLine = isTemplateOnlyBrand(config.brandTemplate, defaultTemplate)
    ? ""
    : `  --shell-components '${JSON.stringify(config.shellComponents)}' \\\n`;
  return `cd media-engine
MEDIA_ENGINE_PYTHON="\${MEDIA_ENGINE_PYTHON:-./.venv-tools/bin/python}" PYTHONPATH=. "\${MEDIA_ENGINE_PYTHON}" -m media_engine.cli premium-batch \\
  --profile "${profileId}" \\
  --source-id "${sourceId}" \\
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
  --curation-source ${config.curationSource} \\
  --asr-model ${config.asrModel} \\
  --speech-language ${config.speechLanguage} \\
  --transcript-languages ${config.transcriptLanguages} \\
  --style ${config.brandTemplate} \\
${shellLine}  --llm-provider ${config.llmProvider} \\
  --niche "${niche}" \\
  --env-file ../.env.local`;
}

export function MediaStudioApp() {
  const [section, setSectionState] = useState<Section>("dashboard");
  const [initialLoaded, setInitialLoaded] = useState(false);
  function renderEmpty(title: string, text: string) {
    return initialLoaded ? <EmptyState title={title} text={text} /> : <LoadingState text="Syncing your workspace…" />;
  }
  function setSection(next: Section) {
    setSectionState(next);
    const search = searchForSection(window.location.search, next);
    if (search === window.location.search) return;
    window.history.pushState(null, "", `${window.location.pathname}${search}${window.location.hash}`);
  }
  const [profileId, setProfileId] = useState("nourbit");
  const [profileReady, setProfileReady] = useState(false);
  const profileIdRef = useRef(profileId);
  profileIdRef.current = profileId;
  const [profiles, setProfiles] = useState<MediaProfile[]>([]);
  const [workspaceModalOpen, setWorkspaceModalOpen] = useState(false);
  const [mobileMoreOpen, setMobileMoreOpen] = useState(false);
  const [watchChannels, setWatchChannels] = useState<WatchChannel[]>([]);
  const [clips, setClips] = useState<ClipCandidate[]>([]);
  const [contentPackages, setContentPackages] = useState<ContentPackageRow[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [targets, setTargets] = useState<PublishTarget[]>([]);
  const [credentials, setCredentials] = useState<CredentialStatus | null>(null);
  const [style, setStyle] = useState<StyleProfile | null>(null);
  const [templates, setTemplates] = useState<BrandTemplate[]>([]);
  const [hyperframesTemplates, setHyperframesTemplates] = useState<HyperframesTemplate[]>([]);
  const [hyperframesCatalog, setHyperframesCatalog] = useState<HyperframesCatalog | null>(null);
  const [durationPresets, setDurationPresets] = useState<DurationPreset[]>([]);
  const [genres, setGenres] = useState<GenreOption[]>([]);
  const [genrePackLabel, setGenrePackLabel] = useState("General");
  const [engineHealth, setEngineHealth] = useState<EngineHealth | null>(null);
  const [autonomy, setAutonomy] = useState<AutonomySettings | null>(null);
  const [jobs, setJobs] = useState<GenerationJob[]>([]);
  const generateInFlightRef = useRef(false);
  const [explainerJobs, setExplainerJobs] = useState<ExplainerJob[]>([]);
  const [pathAJobs, setPathAJobs] = useState<PathAJob[]>([]);
  const [schedule, setSchedule] = useState<ScheduledPost[]>([]);
  const [publishAttempts, setPublishAttempts] = useState<PublishAttempt[]>([]);
  const [filter, setFilter] = useState("all");
  const [showPublished, setShowPublished] = useState(false);
  const [batchDeleteVersion, setBatchDeleteVersion] = useState(0);
  const [status, setStatus] = useState("Ready");
  const [busy, setBusy] = useState(false);
  const [actionStates, setActionStates] = useState<Record<string, ActionUiState>>({});
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState | null>(null);
  const [publishSelection, setPublishSelection] = useState<string[]>([...publishPlatforms]);
  const [generateConfig, setGenerateConfig] = useState<GenerateConfig>({
    sourceUrl: defaultSourceUrl,
    count: 5,
    clipLength: "auto",
    clipMinSeconds: 20,
    clipMaxSeconds: 180,
    genres: ["auto"],
    brandTemplate: TEMPLATE_ONLY_BRAND,
    hyperframesTemplate: "auto",
    brandSystemTemplateId: "",
    hyperframesFormat: "short_9_16",
    renderer: "hyperframes",
    quality: "production",
    captionSource: "hybrid",
    curationSource: "auto",
    asrModel: "medium",
    speechLanguage: "auto",
    transcriptLanguages: "auto",
    llmProvider: "deepseek",
    minEditorialScore: 80,
    shellComponents: {...DEFAULT_SHELL_COMPONENTS},
  });

  useEffect(() => {
    const stored = readStoredProfileId();
    profileIdRef.current = stored;
    setProfileId(stored);
    setProfileReady(true);
  }, []);

  const profileClips = useMemo(
    () => clips.filter((clip) => !clip.profile_id || clip.profile_id === profileId),
    [clips, profileId],
  );
  const selected = useMemo(() => profileClips.find((clip) => clip.id === selectedId) || profileClips[0], [profileClips, selectedId]);
  const reviewFilter = filter === "repair" ? "review" : filter;
  const filtered = useMemo(
    () =>
      profileClips
        .filter((clip) => matchesReviewFilter(clip, reviewFilter))
        .filter((clip) => showPublished || reviewFilter === "published" || clip.status !== "published"),
    [profileClips, reviewFilter, showPublished],
  );
  const activeTargets = useMemo(
    () =>
      targets.filter(
        (target) =>
          publishDestinationPlatforms.includes(target.platform) &&
          (!target.profile_id || target.profile_id === profileId),
      ),
    [targets, profileId],
  );
  const profileJobs = useMemo(
    () => jobs.filter((job) => !job.profile_id || job.profile_id === profileId),
    [jobs, profileId],
  );
  const approved = profileClips.filter((clip) => clip.status === "approved").length;
  const scheduledCount = profileClips.filter((clip) => clip.status === "scheduled" || clip.status === "ready_to_publish").length;
  const readyPlatforms = credentials
    ? Object.entries(credentials.platforms).filter(([platform, item]) => item.ready && !isPublishPlatformDisabled(platform)).length
    : 0;
  const hasTemplate = hyperframesTemplates.length > 0 || generateConfig.hyperframesTemplate !== "auto";
  const engineReady = Boolean(engineHealth?.hyperframes.ready);
  const flowInput: FlowInput = {
    clips: profileClips,
    jobs: profileJobs,
    approvedCount: approved,
    scheduledCount,
    readyPlatforms,
    targetCount: activeTargets.length,
    engineReady,
    hasTemplate,
  };
  const nextAction = getNextAction(flowInput);
  const isErrorStatus = /failed|error|invalid|offline|unauthorized|blocked/i.test(status);
  const headerStatus = !busy && !isErrorStatus && !engineReady
    ? engineHealth?.hyperframes.reason || "Video engine check required"
    : status;
  const workflowSteps = buildWorkflowSteps(flowInput);
  const setupDetails = buildSetupDetails(hasTemplate);
  const command = productionCommand(
    generateConfig,
    profileId,
    profiles.find((profile) => profile.id === profileId)?.niche || "",
  );

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
  async function refreshAll() {
    setBusy(true);
    setStatus("Syncing media engine...");
    try {
      // Prefer the live ref so mount/interval callers never sync the wrong workspace
      // after localStorage hydrate (e.g. nourbit default → workspace).
      const activeProfile = profileIdRef.current || readStoredProfileId();
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
        scheduleRows,
        autonomyRows,
        attemptResult,
        explainerResult,
        pathAResult,
        profilesResult,
        watchResult,
        packagesResult,
      ] = await Promise.all([
        apiGet<ClipCandidate[]>("review"),
        apiGet<PublishTarget[]>(`targets?profile_id=${encodeURIComponent(activeProfile)}`),
        apiGet<CredentialStatus>(`credentials?profile_id=${encodeURIComponent(activeProfile)}`),
        apiGet<StyleProfile>("style"),
        apiGet<BrandTemplate[]>("brand-templates"),
        apiGet<HyperframesTemplate[]>("hyperframes-templates"),
        apiGet<DurationPreset[]>("duration-presets"),
        apiGet<GenreCatalog | GenreOption[]>(`genres?profile_id=${encodeURIComponent(activeProfile)}`),
        apiGet<EngineHealth>("engine-health"),
        apiGet<HyperframesCatalog>("hyperframes-catalog"),
        apiGet<GenerationJob[]>("generation-jobs"),
        apiGet<ScheduledPost[]>(`schedule?profile_id=${encodeURIComponent(activeProfile)}`),
        apiGet<AutonomySettings>(`autonomy-settings?profile_id=${encodeURIComponent(activeProfile)}`),
        apiGet<PublishAttempt[]>("publish-attempts").then((rows) => ({ok: true as const, rows})).catch((error) => ({ok: false as const, error})),
        apiGet<{jobs: ExplainerJob[]}>("explainers").then((payload) => ({ok: true as const, jobs: payload.jobs || []})).catch((error) => ({ok: false as const, error})),
        apiGet<{jobs: PathAJob[]}>("path-a-jobs").then((payload) => ({ok: true as const, jobs: payload.jobs || []})).catch((error) => ({ok: false as const, error})),
        apiGet<{profiles: MediaProfile[]}>("profiles").then((payload) => ({ok: true as const, profiles: payload.profiles || []})).catch((error) => ({ok: false as const, error})),
        apiGet<{channels: WatchChannel[]}>(`watch-channels?profile_id=${encodeURIComponent(activeProfile)}`).then((payload) => ({ok: true as const, channels: payload.channels || []})).catch((error) => ({ok: false as const, error})),
        apiGet<{packages: ContentPackageRow[]}>(`content-packages?profile_id=${encodeURIComponent(activeProfile)}&limit=30`).then((payload) => ({ok: true as const, packages: payload.packages || []})).catch((error) => ({ok: false as const, error})),
      ]);
      // Opportunistic due-channel poll (respects interval server-side).
      void apiGet<{results: unknown[]}>(`watch-poll?profile_id=${encodeURIComponent(activeProfile)}`).catch(() => null);
      setClips(reviewRows);
      setTargets(targetRows);
      setCredentials(credentialRows);
      setStyle(styleRows);
      setTemplates(templateRows);
      setHyperframesTemplates(hyperframesTemplateRows);
      setDurationPresets(durationRows);
      const genreCatalog = parseGenreCatalog(genreRows);
      setGenres(genreCatalog.options);
      setGenrePackLabel(genreCatalog.pack_label);
      setGenerateConfig((current) => {
        const allowed = new Set(genreCatalog.options.map((item) => item.id));
        const kept = current.genres.filter((id) => allowed.has(id) || id === "auto");
        return {...current, genres: kept.length ? kept : genreCatalog.defaults};
      });
      setEngineHealth(engineRows);
      setHyperframesCatalog(catalogRows);
      setJobs(jobRows);
      setSchedule(scheduleRows);
      setAutonomy(autonomyRows);
      setPublishAttempts(attemptResult.ok ? attemptResult.rows : []);
      setExplainerJobs(explainerResult.ok ? explainerResult.jobs : []);
      setPathAJobs(pathAResult.ok ? pathAResult.jobs : []);
      setProfiles(profilesResult.ok ? profilesResult.profiles : []);
      setWatchChannels(watchResult.ok ? watchResult.channels : []);
      setContentPackages(packagesResult.ok ? packagesResult.packages : []);
      setPublishSelection((current) => {
        const enabled = targetRows
          .filter((target) => publishPlatforms.includes(target.platform) && target.mode !== "off" && (target.enabled ?? true))
          .map((target) => target.platform);
        return current.length ? current.filter((platform) => enabled.includes(platform)) : enabled;
      });
      const scoped = reviewRows.filter((clip) => !clip.profile_id || clip.profile_id === activeProfile);
      setSelectedId((current) => (scoped.some((clip) => clip.id === current) ? current : scoped[0]?.id || ""));
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
      setInitialLoaded(true);
    }
  }

  function switchProfile(nextProfileId: string) {
    profileIdRef.current = nextProfileId;
    setProfileId(nextProfileId);
    setTargets([]);
    setCredentials(null);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(PROFILE_STORAGE_KEY, nextProfileId);
    }
  }

  async function copyText(value: string, label = "Copied") {
    await navigator.clipboard.writeText(value);
    setStatus(label);
    pushToast(label, "success");
  }

  async function updateAutonomyMode(mode: string) {
    if (!autonomy) return;
    const key = `autonomy:${mode}`;
    const label =
      mode === "off" ? "Off" : mode === "assisted" ? "Assisted" : mode === "full" ? "Full auto" : mode;
    try {
      const next = await runAction(
        key,
        `Switching autonomy to ${label}...`,
        () => apiPost<AutonomySettings>("autonomy-settings", {...autonomy, profile_id: profileId, autonomy_mode: mode}),
        `Autonomy set to ${label}`,
      );
      setAutonomy(next);
      setStatus(`Autonomy mode set to ${label}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Autonomy update failed");
    }
  }

  async function updateAutonomySettings(patch: Partial<AutonomySettings>) {
    if (!autonomy) return;
    const key = "autonomy:settings";
    try {
      const next = await runAction(
        key,
        "Saving autonomy settings...",
        () => apiPost<AutonomySettings>("autonomy-settings", {...autonomy, profile_id: profileId, ...patch}),
        "Autonomy settings saved",
      );
      setAutonomy(next);
      setStatus("Autonomy settings updated");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Autonomy update failed");
    }
  }

  async function startGeneration(source?: SourceResolveResult | null) {
    const key = "generate:start";
    if (!source?.ok || !source.video_id) {
      setStatus("Validate the YouTube link before generating.");
      return;
    }
    if (generateInFlightRef.current) return;
    if (jobs.some((job) => (!job.profile_id || job.profile_id === profileId) && (job.status === "queued" || job.status === "running"))) {
      setStatus("A generation batch is already running.");
      return;
    }
    generateInFlightRef.current = true;
    try {
      setStatus("Generation job queued...");
      const job = await runAction(key, "Starting generation batch...", () => apiPost<GenerationJob>("generation-jobs", {
          source_url: source.canonical_url || source.source_url || generateConfig.sourceUrl,
          profile_id: profileId,
          source_id: `${profileId}_${source.video_id}`,
          source_metadata: {
            provider: source.provider || "youtube",
            video_id: source.video_id,
            title: source.title || "",
            channel: source.channel || "",
            duration_seconds: source.duration_seconds ?? null,
            thumbnail_url: source.thumbnail_url || "",
            canonical_url: source.canonical_url || source.source_url || generateConfig.sourceUrl,
          },
          count: generateConfig.count,
          clip_length_preset: generateConfig.clipLength,
          clip_min_seconds: generateConfig.clipMinSeconds,
          clip_max_seconds: generateConfig.clipMaxSeconds,
          genres: generateConfig.genres,
          niche: profiles.find((profile) => profile.id === profileId)?.niche || "",
          workspace_name: profiles.find((profile) => profile.id === profileId)?.name || "",
          brand_template: generateConfig.brandTemplate,
          hyperframes_template: generateConfig.hyperframesTemplate,
          brand_system_template_id: generateConfig.brandSystemTemplateId,
          hyperframes_format: generateConfig.hyperframesFormat,
          renderer: generateConfig.renderer,
          quality: generateConfig.quality,
          caption_source: generateConfig.captionSource,
          curation_source: generateConfig.curationSource,
          asr_model: generateConfig.asrModel,
          speech_language: generateConfig.speechLanguage,
          transcript_languages: generateConfig.transcriptLanguages,
          llm_provider: generateConfig.llmProvider,
          stage: "shortlist",
          min_editorial_score: generateConfig.minEditorialScore,
          ...(isTemplateOnlyBrand(generateConfig.brandTemplate, defaultTemplate)
            ? {}
            : {shell_components: generateConfig.shellComponents}),
          env_file: "../.env.local",
        }), "Generation batch started");
      setJobs((items) => [job, ...items.filter((item) => item.id !== job.id)]);
      setStatus("Looking for clip ideas");
      window.setTimeout(() => void refreshAll(), 1600);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Generation failed");
    } finally {
      generateInFlightRef.current = false;
    }
  }

  async function renderSelectedClips(source: SourceResolveResult | null, candidateIds: string[]) {
    if (!source?.ok || !candidateIds.length) return;
    const key = "generate:render";
    try {
      const job = await runAction(key, "Rendering selected clips...", () => apiPost<GenerationJob>("generation-jobs/render", {
        source_url: source.canonical_url || source.source_url || generateConfig.sourceUrl,
        profile_id: profileId,
        source_id: `${profileId}_${source.video_id}`,
        source_metadata: {
          provider: source.provider || "youtube",
          video_id: source.video_id,
          title: source.title || "",
          channel: source.channel || "",
          duration_seconds: source.duration_seconds ?? null,
          thumbnail_url: source.thumbnail_url || "",
          canonical_url: source.canonical_url || source.source_url || generateConfig.sourceUrl,
        },
        candidate_ids: candidateIds,
        count: candidateIds.length,
        clip_length_preset: generateConfig.clipLength,
        clip_min_seconds: generateConfig.clipMinSeconds,
        clip_max_seconds: generateConfig.clipMaxSeconds,
        genres: generateConfig.genres,
        niche: profiles.find((profile) => profile.id === profileId)?.niche || "",
        workspace_name: profiles.find((profile) => profile.id === profileId)?.name || "",
        brand_template: generateConfig.brandTemplate,
        hyperframes_template: generateConfig.hyperframesTemplate,
        brand_system_template_id: generateConfig.brandSystemTemplateId,
        hyperframes_format: generateConfig.hyperframesFormat,
        renderer: generateConfig.renderer,
        quality: generateConfig.quality,
        caption_source: generateConfig.captionSource,
        curation_source: generateConfig.curationSource,
        asr_model: generateConfig.asrModel,
        speech_language: generateConfig.speechLanguage,
        transcript_languages: generateConfig.transcriptLanguages,
        llm_provider: generateConfig.llmProvider,
        stage: "render",
        env_file: "../.env.local",
      }), "Render started");
      setJobs((items) => [job, ...items.filter((item) => item.id !== job.id)]);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Render failed");
    }
  }

  async function addWatchChannel(channelUrl: string, label: string) {
    await runAction("watch:add", "Adding watch channel...", () => apiPost<WatchChannel>("watch-channels", {
      channel_url: channelUrl,
      label,
      profile_id: profileId,
      generation_defaults: {
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
        curation_source: generateConfig.curationSource,
        asr_model: generateConfig.asrModel,
        speech_language: generateConfig.speechLanguage,
        transcript_languages: generateConfig.transcriptLanguages,
        llm_provider: generateConfig.llmProvider,
        niche: profiles.find((profile) => profile.id === profileId)?.niche || "",
        workspace_name: profiles.find((profile) => profile.id === profileId)?.name || "",
      },
    }), "Watch channel added");
    await refreshAll();
  }

  async function toggleWatchChannel(channel: WatchChannel, enabled: boolean) {
    const key = `watch:${channel.id}:toggle`;
    await runAction(key, enabled ? "Resuming channel..." : "Pausing channel...", () => apiPost<WatchChannel>("watch-channel-update", {
      id: channel.id,
      enabled,
    }), enabled ? "Channel resumed" : "Channel paused");
    await refreshAll();
  }

  async function pollWatchChannelNow(channel: WatchChannel) {
    const key = `watch:${channel.id}:poll`;
    await runAction(key, "Polling channel...", () => apiPost("watch-poll", {id: channel.id, force: true}), "Channel poll finished");
    await refreshAll();
  }

  async function deleteWatchChannel(channel: WatchChannel) {
    const key = `watch:${channel.id}:delete`;
    await runAction(key, "Removing channel...", () => apiPost("watch-channel-delete", {id: channel.id}), "Channel removed");
    await refreshAll();
  }

  function deleteSavedBrandStyle(template: {id?: string; path?: string; brand_template_path?: string; label?: string}) {
    const label = template.label || template.id || "saved style";
    setConfirmDialog({
      title: "Delete saved style?",
      message: `Remove “${label}” from your workspace. This cannot be undone.`,
      confirmLabel: "Delete style",
      tone: "danger",
      onConfirm: () =>
        void performDeleteBrandTemplate({
          path: template.path || template.brand_template_path,
          templateId: template.id,
          label,
        }),
    });
  }

  async function performDeleteBrandTemplate(args: {path?: string; templateId?: string; label?: string}) {
    const key = `brand:${args.path || args.templateId || "template"}:delete`;
    try {
      await runAction(key, "Deleting saved style...", async () => {
        const payload: Record<string, string> = {};
        if (args.path) payload.path = args.path;
        if (args.templateId) payload.template_id = args.templateId;
        const result = await apiPost<{brand_id: string; path: string}>("brand-template-delete", payload);
        const deletedBrandId = result.brand_id;
        const deletedPath = result.path;
        setGenerateConfig((current) => {
          const usesDeleted =
            (deletedPath && current.brandTemplate === deletedPath) ||
            current.hyperframesTemplate === deletedBrandId ||
            current.brandSystemTemplateId === deletedBrandId;
          if (!usesDeleted) return current;
          return {
            ...current,
            brandTemplate: TEMPLATE_ONLY_BRAND,
            hyperframesTemplate: "auto",
            brandSystemTemplateId: "",
            shellComponents: shellComponentsForTemplate(hyperframesTemplates, current.hyperframesTemplate),
          };
        });
        const storedDefault = window.localStorage.getItem("otonom.hyperframesTemplateDefault");
        if (storedDefault === deletedBrandId) {
          window.localStorage.removeItem("otonom.hyperframesTemplateDefault");
        }
      }, "Saved style deleted");
      setStatus("Saved style deleted");
      pushToast("Saved style deleted", "success");
      await refreshAll();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Delete failed";
      setStatus(message);
      pushToast(message, "error");
    }
  }

  async function updateDeliverySettings(target: PublishTarget, patch: {daily_cap?: number; enabled?: boolean; mode?: string}) {
    const key = `target:${target.platform}:delivery`;
    const next = await runAction(key, "Updating delivery settings...", () => apiPost<PublishTarget>("publish-target", {
      id: target.id,
      profile_id: target.profile_id,
      platform: target.platform,
      ...patch,
    }), "Delivery settings saved");
    setTargets((items) => items.map((item) => (item.id === next.id ? next : item)));
  }

  const refreshExplainerJobs = () => {
    void refreshAll();
  };

  async function createExplainerJob(payload: {topic: string; sources: string; hyperframes_template: string}) {
    const key = "explainer:create";
    try {
      const job = await runAction(
        key,
        "Creating long video plan…",
        () =>
          apiPost<ExplainerJob>("explainers", {
            topic: payload.topic,
            sources: payload.sources,
            hyperframes_template: payload.hyperframes_template,
          }),
        "Long video plan ready",
      );
      setExplainerJobs((items) => [job, ...items.filter((item) => item.job_id !== job.job_id)]);
      setStatus(`Long video planned: ${job.job_id}`);
      pushToast("Plan ready — open Advanced to stitch when needed", "success");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Long video create failed");
    }
  }

  async function runExplainerJob(jobId: string, ffmpegOnly: boolean) {
    const key = `explainer:${jobId}:run`;
    try {
      const job = await runAction(
        key,
        "Queueing long video stitch…",
        () => apiPost<ExplainerJob>("explainer-run", {job_id: jobId, ffmpeg_only: ffmpegOnly}),
        "Stitch started",
      );
      setExplainerJobs((items) => items.map((item) => (item.job_id === jobId ? {...item, ...job} : item)));
      setStatus("Long video rendering in background");
      window.setTimeout(() => void refreshAll(), 2000);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Long video run failed");
    }
  }

  async function ingestLongformMedia(payload: {source: string; title: string; mode: "review_only" | "clip_batch"}) {
    const key = "ingest:longform";
    try {
      const result = await runAction(
        key,
        payload.mode === "clip_batch" ? "Ingesting + clipping…" : "Ingesting long-form to Review…",
        () =>
          apiPost<{candidate_ids: string[]; job_id: string; mode: string}>("ingest-longform", {
            source: payload.source,
            title: payload.title,
            mode: payload.mode,
          }),
        "Ingested — open Review to approve",
      );
      const first = result.candidate_ids?.[0];
      setStatus(`Ingest ${result.job_id}: ${result.candidate_ids?.length || 0} candidate(s)`);
      pushToast("Long video imported — approve in Review", "success");
      window.setTimeout(() => void refreshAll(), 800);
      if (first) window.location.assign(`/review/${encodeURIComponent(first)}`);
      else setSection("review");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Ingest failed");
    }
  }

  async function startPathAGenerate(payload: {topic: string; title: string; script: string}) {
    const key = "path-a:generate";
    try {
      const job = await runAction(
        key,
        "Starting long video…",
        () =>
          apiPost<PathAJob>("path-a-generate", {
            topic: payload.topic,
            title: payload.title,
            script: payload.script,
          }),
        "Long video started — watching progress",
      );
      setPathAJobs((items) => [job, ...items.filter((item) => item.job_id !== job.job_id)]);
      setStatus(`Long video started: ${job.job_id}`);
      pushToast("Generate started — Telegram will ping when Review is ready", "success");
      window.setTimeout(() => void refreshAll(), 2000);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Long video generate failed");
    }
  }

  async function scheduleNext(id: string, scheduledAt?: string, platformsOverride?: string[], republish = false) {
    const key = `clip:${id}:schedule`;
    const clip = clips.find((item) => item.id === id);
    const platforms = filterPlatformsForClip(platformsOverride?.length ? platformsOverride : publishSelection, clip);
    if (!platforms.length) {
      setStatus("No publish destinations match this clip format. Enable YouTube Video for long-form or Shorts/Reels for vertical clips in Channels.");
      pushToast("No compatible publish destinations for this clip", "info");
      return;
    }
    try {
      await runAction(
        key,
        republish ? "Rescheduling..." : "Scheduling...",
        () =>
          apiPost("schedule-next", {
            candidate_id: id,
            platforms,
            ...(scheduledAt ? {scheduled_at: scheduledAt} : {}),
            ...(republish ? {republish: true} : {}),
          }),
        republish ? "Clip rescheduled" : "Clip scheduled",
      );
      setStatus(scheduledAt ? "Clip scheduled" : "Clip scheduled in next open slot");
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

  async function updateScheduleTime(scheduleId: string, scheduledAt: string) {
    const key = `schedule:${scheduleId}:time`;
    try {
      await runAction(key, "Updating schedule time...", () => apiPost("schedule-update", {schedule_id: scheduleId, scheduled_at: scheduledAt}), "Schedule time updated");
      setStatus("Schedule time updated");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Schedule update failed");
    }
  }

  async function publishNow(scheduleId: string) {
    const key = `schedule:${scheduleId}:publish-now`;
    try {
      await runAction(key, "Sending to Postiz...", () => apiPost("publish-now", {schedule_id: scheduleId, profile_id: profileId}), "Sent to Postiz");
      setStatus("Accepted by Postiz — not live until each platform delivers");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Publish now failed");
    }
  }

  async function publishClipNow(id: string, platforms: string[], republish = false) {
    const key = `clip:${id}:publish-now`;
    const clip = clips.find((item) => item.id === id);
    const resolvedPlatforms = filterPlatformsForClip(platforms, clip);
    if (!resolvedPlatforms.length) {
      setStatus("No publish destinations match this clip format. Enable YouTube Video for long-form or Shorts/Reels for vertical clips in Channels.");
      pushToast("No compatible publish destinations for this clip", "info");
      return;
    }
    const existingSchedule = schedule.find((item) => item.candidate_id === id);
    const force = republish || clip?.status === "published";
    try {
      await runAction(key, force ? "Republishing to Postiz..." : "Sending to Postiz...", async () => {
        if (clip?.status === "approved" || force) {
          await apiPost("schedule-next", {
            candidate_id: id,
            platforms: resolvedPlatforms,
            ...(force ? {republish: true} : {}),
          });
        } else if (existingSchedule) {
          const samePlatforms =
            resolvedPlatforms.length === existingSchedule.platforms.length &&
            resolvedPlatforms.every((platform) => existingSchedule.platforms.includes(platform));
          if (!samePlatforms) {
            await apiPost("schedule-platforms", {schedule_id: existingSchedule.id, platforms: resolvedPlatforms});
          }
        }
        await apiPost("publish-now", {candidate_id: id, profile_id: profileId, ...(force ? {force: true} : {})});
      }, force ? "Republished to Postiz" : "Sent to Postiz");
      setStatus("Accepted by Postiz — not live until each platform delivers");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Publish now failed");
    }
  }

  function defaultPublishPlatformsForClip(clip: ClipCandidate) {
    const existingSchedule = schedule.find((item) => item.candidate_id === clip.id);
    const base = existingSchedule?.platforms?.length ? existingSchedule.platforms : publishSelection;
    return filterPlatformsForClip(base, clip);
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

  function clearQueue() {
    setConfirmDialog({
      title: "Clear review queue?",
      message: "This deletes every visible clip candidate and its local artifacts from this workspace.",
      confirmLabel: "Clear queue",
      tone: "danger",
      onConfirm: () => void performClearQueue(),
    });
  }

  function deleteClip(clip: ClipCandidate) {
    setConfirmDialog({
      title: "Delete this clip?",
      message: `Remove “${clip.title_hook}” and its rendered files from this workspace.`,
      confirmLabel: "Delete clip",
      tone: "danger",
      onConfirm: () => void performDeleteClip(clip.id),
    });
  }

  function deleteSelectedClips(candidateIds: string[]) {
    if (!candidateIds.length) return;
    setConfirmDialog({
      title: `Delete ${candidateIds.length} clip${candidateIds.length === 1 ? "" : "s"}?`,
      message: `Remove ${candidateIds.length} selected clip${candidateIds.length === 1 ? "" : "s"} and their rendered files from this workspace.`,
      confirmLabel: `Delete ${candidateIds.length}`,
      tone: "danger",
      onConfirm: () => void performDeleteClips(candidateIds),
    });
  }

  function rerenderSelectedClips(candidateIds: string[]) {
    if (!candidateIds.length) return;
    const eligible = candidateIds.filter((id) => {
      const clip = clips.find((item) => item.id === id);
      return clip ? canBatchRerenderClip(clip) : false;
    });
    if (!eligible.length) {
      pushToast("No selected clips can be re-rendered", "error");
      return;
    }
    const skipped = candidateIds.length - eligible.length;
    setConfirmDialog({
      title: `Re-render ${eligible.length} clip${eligible.length === 1 ? "" : "s"}?`,
      message: `Regenerate ${eligible.length} selected short${eligible.length === 1 ? "" : "s"} with current hook titles and caption timing.${skipped ? ` ${skipped} ineligible clip${skipped === 1 ? "" : "s"} will be skipped.` : ""} Renders run in the background.`,
      confirmLabel: `Re-render ${eligible.length}`,
      tone: "default",
      onConfirm: () => void performBatchRerender(eligible),
    });
  }

  function approveClip(clip: ClipCandidate) {
    if (!canQuickApproveClip(clip)) return;
    void performApproveClip(clip.id);
  }

  function approveSelectedClips(candidateIds: string[]) {
    if (!candidateIds.length) return;
    const eligible = candidateIds.filter((id) => {
      const clip = clips.find((item) => item.id === id);
      return clip ? canQuickApproveClip(clip) : false;
    });
    if (!eligible.length) {
      pushToast("No selected clips can be approved", "error");
      return;
    }
    const skipped = candidateIds.length - eligible.length;
    setConfirmDialog({
      title: `Approve ${eligible.length} clip${eligible.length === 1 ? "" : "s"}?`,
      message: `Mark ${eligible.length} selected clip${eligible.length === 1 ? "" : "s"} as approved for scheduling.${skipped ? ` ${skipped} ineligible clip${skipped === 1 ? "" : "s"} will be skipped.` : ""}`,
      confirmLabel: `Approve ${eligible.length}`,
      tone: "default",
      onConfirm: () => void performBatchApprove(eligible),
    });
  }

  function markClipsApproved(approvedIds: string[]) {
    const approved = new Set(approvedIds);
    if (!approved.size) return;
    setClips((items) =>
      items.map((item) =>
        approved.has(item.id) ? {...item, status: "approved", review_deadline_at: ""} : item,
      ),
    );
  }

  async function saveLlmCredentials(values: Record<string, string>) {
    const key = `llm:save:${profileId}`;
    try {
      await runAction(
        key,
        "Saving LLM settings…",
        () => apiPost("llm-credentials", {profile_id: profileId, values}),
        "LLM settings saved",
      );
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "LLM save failed");
      throw error;
    }
  }

  async function publishContentPackage(packageId: string) {
    const key = `package:publish:${packageId}`;
    try {
      await runAction(
        key,
        "Publishing package…",
        () =>
          apiPost("content-package-publish", {
            package_id: packageId,
            profile_id: profileId,
            platform: "telegram_channel",
          }),
        "Package published",
      );
      setContentPackages((rows) =>
        rows.map((row) => (row.id === packageId ? {...row, status: "published"} : row)),
      );
      pushToast("Content package sent via Postiz", "success");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Publish failed";
      pushToast(message, "error");
    }
  }

  function handleContentPackageCreated(pkg: ContentPackageCreateResult) {
    setContentPackages((rows) => {
      const row = {
        id: pkg.id,
        format: pkg.format,
        status: pkg.status,
        caption: pkg.caption || "",
        qa: pkg.qa,
      };
      const rest = rows.filter((r) => r.id !== pkg.id);
      return [row, ...rest];
    });
  }

  async function createContentPackageRequest(payload: Record<string, unknown>) {
    return runAction(
      "package:create",
      "Creating content package…",
      () => apiPost<ContentPackageCreateResult>("content-package-create", payload),
      "Content package created",
    );
  }

  async function approveContentPackage(packageId: string) {
    const key = `package:approve:${packageId}`;
    try {
      await runAction(
        key,
        "Approving package…",
        () => apiPost("content-package-approve", {package_id: packageId}),
        "Package approved",
      );
      setContentPackages((rows) =>
        rows.map((row) => (row.id === packageId ? {...row, status: "approved"} : row)),
      );
      pushToast("Content package approved", "success");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Approve failed";
      pushToast(message, "error");
    }
  }

  async function performApproveClip(candidateId: string) {
    const key = `clip:${candidateId}:approve`;
    try {
      await runAction(key, "Approving clip…", () => apiPost("approve", {candidate_id: candidateId}), "Approved");
      markClipsApproved([candidateId]);
      setStatus("Clip approved");
      pushToast("Clip approved", "success");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Approve failed";
      setStatus(message);
      pushToast(message, "error");
    }
  }

  async function performBatchApprove(candidateIds: string[]) {
    const key = "review:batch-approve";
    try {
      const result = await runAction(
        key,
        `Approving ${candidateIds.length} clip${candidateIds.length === 1 ? "" : "s"}…`,
        () => apiPost<BatchApproveResult>("batch-approve", {candidate_ids: candidateIds}),
        `Approved ${candidateIds.length} clip${candidateIds.length === 1 ? "" : "s"}`,
      );
      markClipsApproved(result.approved_ids);
      setBatchDeleteVersion((value) => value + 1);
      const skipped = result.skipped.length + result.failed.length;
      if (skipped) {
        const message = `Approved ${result.approved_ids.length}; ${skipped} skipped or failed`;
        setStatus(message);
        pushToast(message, result.approved_ids.length ? "success" : "error");
      } else {
        setStatus(`Approved ${result.approved_ids.length} clip${result.approved_ids.length === 1 ? "" : "s"}`);
        pushToast(`Approved ${result.approved_ids.length} clip${result.approved_ids.length === 1 ? "" : "s"}`, "success");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Batch approve failed";
      setStatus(message);
      pushToast(message, "error");
    }
  }

  async function performBatchRerender(candidateIds: string[]) {
    const key = "review:batch-rerender";
    try {
      const result = await runAction(
        key,
        `Queuing ${candidateIds.length} re-render${candidateIds.length === 1 ? "" : "s"}…`,
        () =>
          apiPost<BatchRerenderResult>("batch-rerender", {
            candidate_ids: candidateIds,
            renderer: "hyperframes",
            quality: "production",
            style: "auto",
          }),
        `Queued ${candidateIds.length} re-render${candidateIds.length === 1 ? "" : "s"}`,
      );
      const queued = result.queued.length;
      const skipped = result.skipped.length + result.failed.length;
      if (skipped) {
        const message = `Queued ${queued}; ${skipped} skipped or failed`;
        setStatus(message);
        pushToast(message, queued ? "success" : "error");
      } else {
        setStatus(`Queued ${queued} re-render${queued === 1 ? "" : "s"}`);
      }
      await refreshAll();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Batch re-render failed";
      setStatus(message);
    }
  }

  async function performDeleteClips(candidateIds: string[]) {
    const key = "review:batch-delete";
    try {
      const result = await runAction(
        key,
        "Deleting selected clips...",
        () => apiPost<DeleteCandidatesResult>("delete-candidates", {candidate_ids: candidateIds, delete_artifacts: true}),
        "Selected clips deleted",
      );
      const deleted = new Set(result.deleted_ids);
      setClips((items) => items.filter((item) => !deleted.has(item.id)));
      setSchedule((items) => items.filter((item) => !item.candidate_id || !deleted.has(item.candidate_id)));
      setBatchDeleteVersion((value) => value + 1);
      if (result.failed.length) {
        const message = `Deleted ${result.deleted_ids.length}; ${result.failed.length} failed`;
        setStatus(message);
        pushToast(message, "error");
      } else {
        setStatus(`Deleted ${result.deleted_ids.length} clip${result.deleted_ids.length === 1 ? "" : "s"}`);
        pushToast(`Deleted ${result.deleted_ids.length} clip${result.deleted_ids.length === 1 ? "" : "s"}`, "success");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Delete failed";
      setStatus(message);
      pushToast(message, "error");
    }
  }

  async function makeShortsFromClip(clip: ClipCandidate) {
    if (!canMakeShortsFromClip(clip)) return;
    const key = `clip:${clip.id}:shorts`;
    try {
      const result = await runAction(
        key,
        "Queuing shorts from long-form…",
        () => apiPost<MakeShortsFromLongformResult>("make-shorts-from-longform", {candidate_id: clip.id}),
        "Shorts queued",
      );
      setStatus(result.message);
      pushToast(result.message, "success");
      await refreshAll();
      setSection(result.route === "generation_job" ? "generate" : "review");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Make shorts failed";
      setStatus(message);
      pushToast(message, "error");
    }
  }

  async function performDeleteClip(candidateId: string) {
    const key = `clip:${candidateId}:delete`;
    try {
      await runAction(key, "Deleting clip...", async () => {
        await apiPost("delete-candidate", {candidate_id: candidateId, delete_artifacts: true});
        setClips((items) => items.filter((item) => item.id !== candidateId));
        setSchedule((items) => items.filter((item) => item.candidate_id !== candidateId));
      }, "Clip deleted");
      setStatus("Clip deleted");
      pushToast("Clip deleted", "success");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Delete failed";
      setStatus(message);
      pushToast(message, "error");
    }
  }

  async function performClearQueue() {
    const key = "queue:clear";
    try {
      await runAction(key, "Clearing review queue...", async () => {
        await apiPost("clear-review", {confirm: "DELETE", delete_artifacts: true});
        setClips([]);
      }, "Queue cleared");
      setStatus("Queue cleared");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Clear failed");
    }
  }

  async function testConnection(platform: string) {
    if (!credentials?.platforms[platform]?.ready) {
      setStatus(`Connect ${platformLabel(platform)} before testing`);
      pushToast(`Connect ${platformLabel(platform)} first`, "info");
      return;
    }
    const key = `test:${platform}`;
    const message = `Testing ${platformLabel(platform)} connection...`;
    setStatus(message);
    try {
      await runAction(key, message, () => apiPost("connection-test", {platform, profile_id: profileId}), `${platformLabel(platform)} connected`);
      setStatus(`${platformLabel(platform)} connected`);
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Connection check failed");
    }
  }

  async function saveConnectionCredentials(platform: string, values: Record<string, string>) {
    const key = `credentials:${platform}`;
    try {
      await runAction(
        key,
        `Saving ${platformLabel(platform)} credentials...`,
        () => apiPost("connection-credentials", {platform, profile_id: profileId, values}),
        `${platformLabel(platform)} connected`,
      );
      setStatus(`${platformLabel(platform)} credentials saved`);
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Credential save failed");
      throw error;
    }
  }

  async function connectPostiz(values: {api_url: string; api_key: string}) {
    try {
      await runAction(
        "postiz:connect",
        "Connecting Postiz...",
        () => apiPost("postiz-connect", {profile_id: profileId, ...values}),
        "Postiz connected",
      );
      setStatus("Postiz connected");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Postiz connect failed");
      throw error;
    }
  }

  async function disconnectPostiz() {
    try {
      await runAction("postiz:disconnect", "Disconnecting Postiz...", () => apiPost("postiz-disconnect", {profile_id: profileId}), "Postiz disconnected");
      setStatus("Postiz disconnected");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Postiz disconnect failed");
    }
  }

  async function mapPostizChannel(platform: string, integration: PostizIntegration | null) {
    try {
      await runAction(
        `postiz-map:${platform}`,
        `Mapping ${platformLabel(platform)}...`,
        () => apiPost("postiz-map", {profile_id: profileId, platform, integration}),
        `${platformLabel(platform)} mapped`,
      );
      setStatus(`${platformLabel(platform)} mapped to Postiz`);
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Postiz map failed");
      throw error;
    }
  }

  async function loadPostizIntegrations(platform: string): Promise<PostizIntegration[]> {
    const result = await apiGet<{integrations: PostizIntegration[]}>(`postiz-integrations?profile_id=${encodeURIComponent(profileId)}`);
    const items = result.integrations || [];
    const aliases: Record<string, string[]> = {
      youtube_shorts: ["youtube"],
      youtube_video: ["youtube"],
      facebook_reels: ["facebook"],
      tiktok: ["tiktok"],
      telegram_channel: ["telegram"],
      instagram_reels: ["instagram"],
    };
    const wanted = new Set(aliases[platform] || []);
    const matched = items.filter((item) => wanted.has(String(item.identifier || "").toLowerCase()));
    return matched.length ? matched : items;
  }

  async function startOauthConnect(platform: string) {
    const key = `connect:${platform}`;
    try {
      const result = await runAction(
        key,
        `Opening ${platformLabel(platform)} OAuth...`,
        () => apiPost<{platform: string; auth_url: string}>("oauth-start", {platform, profile_id: profileId}),
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
      await runAction(key, `Disconnecting ${platformLabel(platform)}...`, () => apiPost("connection-disconnect", {platform, profile_id: profileId}), `${platformLabel(platform)} disconnected`);
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
      const result = await runAction(key, dryRun ? "Checking due publish queue..." : "Publishing due schedule...", () => apiPost<{count: number; processed?: unknown[]}>("publish-due", {limit: 5, dry_run: dryRun, profile_id: profileId}));
      setStatus(`${dryRun ? "Checked" : "Processed"} ${result.count || 0} due publish item(s)`);
      pushToast(`${dryRun ? "Checked" : "Processed"} ${result.count || 0} due publish item(s)`, "success");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Publish due failed");
    }
  }

  useEffect(() => {
    const savedTemplate = window.localStorage.getItem("otonom.hyperframesTemplateDefault");
    const brandHandoffRaw = window.localStorage.getItem("otonom.generateBrandHandoff");
    const frame = window.requestAnimationFrame(() => {
      setGenerateConfig((current) => {
        let next = current;
        if (savedTemplate) {
          next = {...next, hyperframesTemplate: savedTemplate};
        }
        if (brandHandoffRaw) {
          try {
            const handoff = JSON.parse(brandHandoffRaw) as {
              brandTemplate?: string;
              hyperframesTemplate?: string;
              brandSystemTemplateId?: string;
              renderer?: string;
            };
            window.localStorage.removeItem("otonom.generateBrandHandoff");
            next = {
              ...next,
              brandTemplate: handoff.brandTemplate || next.brandTemplate,
              hyperframesTemplate: handoff.hyperframesTemplate || next.hyperframesTemplate,
              brandSystemTemplateId: handoff.brandSystemTemplateId || next.brandSystemTemplateId,
              renderer: handoff.renderer === "hyperframes" ? "hyperframes" : next.renderer,
            };
          } catch {
            window.localStorage.removeItem("otonom.generateBrandHandoff");
          }
        }
        return next;
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    const syncFromUrl = () => setSectionState(sectionFromSearch(window.location.search));
    const frame = window.requestAnimationFrame(syncFromUrl);
    window.addEventListener("popstate", syncFromUrl);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("popstate", syncFromUrl);
    };
  }, []);

  useEffect(() => {
    if (!profileReady) return;
    const timer = window.setTimeout(() => {
      void refreshAll();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [profileId, profileReady]);

  useEffect(() => {
    if (!toasts.length) return;
    const timer = window.setTimeout(() => {
      setToasts((items) => items.slice(0, -1));
    }, 4600);
    return () => window.clearTimeout(timer);
  }, [toasts]);

  useEffect(() => {
    const hasRunningGeneration = jobs.some((job) => job.status === "queued" || job.status === "running");
    if (!hasRunningGeneration) return;
    const timer = window.setInterval(() => {
      void refreshAll();
    }, 3500);
    return () => window.clearInterval(timer);
  }, [jobs]);

  const hasActiveRerender = clips.some((clip) => isClipRerendering(clip));
  useEffect(() => {
    if (!hasActiveRerender) return;
    const timer = window.setInterval(() => {
      void refreshAll();
    }, 3500);
    return () => window.clearInterval(timer);
  }, [hasActiveRerender]);

  useEffect(() => {
    if (section !== "calendar") return;
    const timer = window.setInterval(() => {
      void refreshAll();
    }, 45000);
    return () => window.clearInterval(timer);
  }, [section]);

  const focusedWorkflow = section !== "dashboard";

  return (
    <div className="app-shell min-h-screen overflow-x-hidden text-text-primary">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[280px] flex-col border-r border-border bg-canvas-deep/95 px-4 py-5 backdrop-blur-xl lg:flex">
        <div className="flex shrink-0 items-center gap-3 px-1">
          <div className="grid h-11 w-11 place-items-center rounded-2xl border border-cyan/[0.55] bg-cyan/[0.04] text-lg font-semibold text-white shadow-[0_0_24px_rgba(102,232,249,0.12)]">N</div>
          <div>
            <h1 className="text-base font-semibold leading-5 font-sans">
              <span className="font-editorial italic font-normal text-cyan">Otonom</span> Media
            </h1>
            <p className="text-xs text-zinc-400">Create · Review · Publish</p>
          </div>
        </div>

        <div className="mt-5 shrink-0">
          <WorkspaceSwitcher
            profiles={profiles}
            profileId={profileId}
            onSwitch={switchProfile}
            onManage={() => setWorkspaceModalOpen(true)}
          />
        </div>

        <nav className="mt-6 grid min-h-0 flex-1 auto-rows-min content-start gap-1 overflow-y-auto pr-1">
          <p className="px-3 pb-1 text-[10px] font-bold uppercase tracking-wider text-zinc-600">Loop</p>
          {primaryNav.map((item) => {
            const Icon = item.icon;
            const active = section === item.id;
            const step = workflowSteps.find((workflowStep) => workflowStep.section === item.id);
            return (
              <button
                key={item.id}
                onClick={() => setSection(item.id)}
                className={`group relative flex min-h-[52px] items-center gap-3 overflow-hidden rounded-[18px] border px-3.5 py-2 text-left text-sm font-medium transition ${
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
                  <span className={`mt-0.5 block truncate text-[10px] font-medium ${active ? "text-cyan/70" : "text-zinc-600"}`}>{step?.detail || "—"}</span>
                </span>
                {step ? <span className={`h-1.5 w-1.5 rounded-full ${step.status === "ready" ? "bg-teal" : step.status === "active" ? "bg-cyan" : step.status === "blocked" ? "bg-warning" : "bg-white/[0.16]"}`} /> : null}
              </button>
            );
          })}
          <p className="mt-3 px-3 pb-1 text-[10px] font-bold uppercase tracking-wider text-zinc-600">Setup &amp; tools</p>
          {secondaryNav.map((item) => {
            const Icon = item.icon;
            const active = section === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setSection(item.id)}
                aria-current={active ? "page" : undefined}
                className={`group relative flex min-h-[48px] items-center gap-3 overflow-hidden rounded-[18px] border px-3.5 py-2 text-left text-sm font-medium transition ${
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
                  <span className={`mt-0.5 block truncate text-[10px] font-medium ${active ? "text-cyan/70" : "text-zinc-600"}`}>{setupDetails[item.id] || "—"}</span>
                </span>

              </button>
            );
          })}
        </nav>

        <div className="mt-4 grid shrink-0 gap-3">
          <div className="rounded-[22px] border border-white/[0.07] bg-white/[0.035] p-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm font-semibold">Next action</span>
              <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${nextAction.tone === "warning" ? "bg-warning/[0.10] text-warning" : "bg-teal/[0.10] text-teal"}`}>
                {nextActionToneLabel(nextAction.tone)}
              </span>
            </div>
            <button type="button" onClick={() => setSection(nextAction.section)} className="w-full rounded-2xl border border-white/[0.06] bg-black/20 px-3 py-3 text-left transition hover:border-cyan/[0.20]">
              <span className="block text-sm font-semibold text-cyan">{nextAction.label}</span>
              <span className="mt-1 block text-xs leading-5 text-zinc-500">{nextAction.detail}</span>
            </button>
          </div>
        </div>
      </aside>

      <main className="min-w-0 pb-32 lg:pl-[280px] lg:pb-0">
        <header className="sticky top-0 z-20 overflow-hidden border-b border-white/[0.06] bg-canvas-deep/[0.82] px-5 py-4 backdrop-blur-xl lg:px-8">
          <div
            className={`flex min-w-0 flex-col gap-3 xl:flex-row xl:items-center xl:justify-between ${
              section === "review" ? "mx-auto w-full max-w-[1180px]" : section === "generate" ? "mx-auto w-full max-w-[1600px]" : ""
            }`}
          >
            <div className="min-w-0">
              <div className="mb-2 lg:hidden">
                <WorkspaceSwitcher
                  variant="mobile"
                  profiles={profiles}
                  profileId={profileId}
                  onSwitch={switchProfile}
                  onManage={() => setWorkspaceModalOpen(true)}
                />
              </div>
              <h2 className="max-w-full text-balance break-words text-2xl font-semibold tracking-[-0.03em] text-text-primary md:text-3xl">
                {renderEditorialTitle(sectionCopy[section].title)}
              </h2>
              <p className="mt-1 max-w-[calc(100vw-40px)] break-words text-sm text-zinc-400 md:max-w-2xl">{sectionCopy[section].subtitle}</p>
            </div>
            {!focusedWorkflow ? (
              <div className="grid min-w-0 grid-cols-1 items-center gap-2 sm:flex sm:flex-wrap">
                <button onClick={() => setSection(nextAction.section)} className="inline-flex h-11 min-w-0 items-center justify-center gap-2 rounded-full bg-cyan px-4 text-sm font-semibold text-ink">
                  <Wand2 className="h-4 w-4" /> {nextAction.label}
                </button>
                <button onClick={refreshAll} className="inline-flex h-11 min-w-0 items-center justify-center gap-2 rounded-full border border-white/[0.10] bg-surface px-4 text-sm font-medium text-zinc-200 hover:bg-surface-raised">
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />} Refresh
                </button>
                <StatusPill busy={busy} status={headerStatus} />
              </div>
            ) : null}
          </div>
        </header>

        <div className="grid min-w-0 gap-5 px-5 py-5 lg:px-8">
          {section === "dashboard" && (
            <DashboardSection
              clips={profileClips}
              schedule={schedule}
              nextAction={nextAction}
              workflowSteps={workflowSteps}
              readyPlatforms={readyPlatforms}
              targetCount={activeTargets.length}
              activeJobs={jobs.filter((job) => job.status === "queued" || job.status === "running").length}
              onSection={setSection}
            />
          )}

          {section === "generate" && (
            <div className="mx-auto grid w-full max-w-[1600px] gap-6">
            <GenerateSection
              config={generateConfig}
              templates={templates}
              hyperframesTemplates={hyperframesTemplates}
              hyperframesCatalog={hyperframesCatalog}
              durationPresets={durationPresets}
              genres={genres}
              genrePackLabel={genrePackLabel}
              jobs={jobs.filter((job) => !job.profile_id || job.profile_id === profileId)}
              engineHealth={engineHealth}
              actionState={actionStates["generate:start"]}
              setConfig={setGenerateConfig}
              command={command}
              defaultTemplatePath={defaultTemplate}
              statusTone={statusTone}
              onGenerate={startGeneration}
              onRenderSelected={(source, ids) => void renderSelectedClips(source, ids)}
              onOpenReview={() => setSection("review")}
              onOpenBrand={() => setSection("brand")}
              onCopy={() => copyText(command, "Production command copied")}
              renderReadinessLine={(props) => <ReadinessLine {...props} />}
              renderActionStatus={(state) => (state ? <InlineActionStatus state={state} /> : null)}
              renderEmptyState={renderEmpty}
            />
            <ContentPackageCreateSection
              profileId={profileId}
              actionState={actionStates["package:create"]}
              onCreate={createContentPackageRequest}
              onCreated={handleContentPackageCreated}
              onOpenReview={() => setSection("review")}
              onOpenPublish={() => setSection("publish")}
            />
            <details className="rounded-[28px] border border-white/[0.08] bg-surface/30 p-5">
              <summary className="cursor-pointer list-none text-sm font-semibold text-zinc-300">
                Watch YouTube sources
                <span className="ml-2 text-xs font-medium text-zinc-600">optional auto-clip</span>
              </summary>
              <div className="mt-4 border-t border-white/[0.06] pt-4">
                <WatchChannelsSection
                  channels={watchChannels}
                  workspaceName={profiles.find((profile) => profile.id === profileId)?.name || profileId}
                  actionStates={actionStates}
                  onAdd={addWatchChannel}
                  onToggle={toggleWatchChannel}
                  onPoll={pollWatchChannelNow}
                  onDelete={deleteWatchChannel}
                  renderActionStatus={(state) => (state ? <InlineActionStatus state={state} /> : null)}
                />
              </div>
            </details>
            </div>
          )}

          {section === "explainer" && (
            <ExplainerSection
              jobs={explainerJobs}
              pathAJobs={pathAJobs}
              templates={hyperframesTemplates}
              actionState={
                actionStates["path-a:generate"] ||
                actionStates["ingest:longform"] ||
                actionStates["explainer:create"] ||
                Object.entries(actionStates).find(([key]) => key.startsWith("explainer:") && key.endsWith(":run"))?.[1]
              }
              statusTone={statusTone}
              onCreate={createExplainerJob}
              onRun={runExplainerJob}
              onRefresh={refreshExplainerJobs}
              onOpenReview={(candidateId) => {
                if (candidateId) window.location.assign(`/review/${encodeURIComponent(candidateId)}`);
                else setSection("review");
              }}
              onIngest={ingestLongformMedia}
              onPathAGenerate={startPathAGenerate}
              ingesting={actionStates["ingest:longform"]?.status === "running"}
              pathAGenerating={actionStates["path-a:generate"]?.status === "running"}
              renderActionStatus={(state) => (state ? <InlineActionStatus state={state} /> : null)}
              renderEmptyState={renderEmpty}
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
                  brandTemplate:
                    selectedTemplate?.source === "brand_system" && selectedTemplate?.brand_template_path
                      ? selectedTemplate.brand_template_path
                      : isTemplateOnlyBrand(current.brandTemplate, defaultTemplate)
                        ? TEMPLATE_ONLY_BRAND
                        : current.brandTemplate,
                  shellComponents: shellComponentsForTemplate(hyperframesTemplates, templateId),
                }));
                setSection("generate");
                pushToast("Template selected for Create", "success");
              }}
              onSetDefault={(templateId) => {
                window.localStorage.setItem("otonom.hyperframesTemplateDefault", templateId);
                setGenerateConfig((current) => ({...current, hyperframesTemplate: templateId}));
                pushToast("Default template saved in this browser", "success");
              }}
              onCustomize={(templateId) => {
                const selectedTemplate = hyperframesTemplates.find((template) => template.id === templateId);
                if (selectedTemplate?.brand_template_path) {
                  window.location.href = `/brand/builder?base=${encodeURIComponent(selectedTemplate.brand_template_path)}`;
                  return;
                }
                const starter = selectedTemplate?.starter_template || templateId;
                window.localStorage.setItem("otonom.brandBuilderStarterTemplate", starter);
                window.location.href = `/brand/builder?starter=${encodeURIComponent(starter)}`;
              }}
              onDelete={deleteSavedBrandStyle}
              renderStatusPill={(busy, status) => <StatusPill busy={busy} status={status} />}
              renderSettingTile={(label, value) => <SettingTile label={label} value={value} />}
              renderEmptyState={renderEmpty}
            />
          )}

          {section === "review" && (
            <div className="mx-auto w-full max-w-[1180px]">
              <ContentPackagesSection
                packages={contentPackages}
                actionStates={actionStates}
                onApprove={(packageId) => void approveContentPackage(packageId)}
                onPublish={(packageId) => void publishContentPackage(packageId)}
              />
              <ReviewStudioSection
                clips={filtered}
                filter={reviewFilter}
                showPublished={showPublished}
                selectionResetKey={`${profileId}:${reviewFilter}:${showPublished}:${batchDeleteVersion}`}
                reviewFilters={reviewFilters}
                actionStates={actionStates}
                setFilter={setFilter}
                setShowPublished={setShowPublished}
                statusTone={statusTone}
                onClear={clearQueue}
                onDeleteClip={deleteClip}
                onApproveClip={approveClip}
                onDeleteSelected={deleteSelectedClips}
                onApproveSelected={approveSelectedClips}
                onRerenderSelected={rerenderSelectedClips}
                onMakeShorts={makeShortsFromClip}
                onScheduleClip={(clip, scheduledAt, platforms) =>
                  void scheduleNext(clip.id, scheduledAt, platforms, clip.status === "published")
                }
                onPublishClipNow={(clip, platforms, options) =>
                  void publishClipNow(clip.id, platforms, Boolean(options?.republish || clip.status === "published"))
                }
                publishTargets={activeTargets.map((target) => target.platform)}
                defaultPublishPlatforms={defaultPublishPlatformsForClip}
              />
            </div>
          )}

          {section === "calendar" && (
            <CalendarSection
              schedule={schedule}
              approved={clips.filter((clip) => clip.status === "approved")}
              targets={activeTargets}
              selectedPlatforms={publishSelection}
              actionStates={actionStates}
              credentials={credentials}
              showRecoveryTools={typeof window !== "undefined" && new URLSearchParams(window.location.search).get("ops") === "1"}
              onToggleDefaultPlatform={togglePublishSelection}
              onSchedule={scheduleNext}
              onUnschedule={unscheduleClip}
              onUpdateSchedulePlatforms={updateSchedulePlatforms}
              onUpdateScheduleTime={updateScheduleTime}
              onPublishNow={publishNow}
              onPublishDue={() => publishDueNow(false)}
              onDryRunDue={() => publishDueNow(true)}
              formatSchedule={formatSchedule}
              formatClipStatus={formatClipStatus}
              cleanPublishStatus={cleanPublishStatus}
              statusTone={statusTone}
              renderScoreBubble={(value) => <ScoreBubble value={value} />}
              renderInlineActionStatus={(state) => <InlineActionStatus state={state} />}
              renderEmptyState={renderEmpty}
            />
          )}

          {section === "publish" && (
            <PublishSection
              targets={activeTargets}
              profileId={profileId}
              credentials={credentials}
              attempts={publishAttempts}
              selectedPlatforms={publishSelection}
              actionStates={actionStates}
              onTogglePlatform={togglePublishSelection}
              onTestConnection={testConnection}
              onStartOauth={startOauthConnect}
              onDisconnect={disconnectPlatform}
              onSaveCredentials={saveConnectionCredentials}
              onSaveLlm={saveLlmCredentials}
              onConnectPostiz={connectPostiz}
              onDisconnectPostiz={disconnectPostiz}
              onMapPostiz={mapPostizChannel}
              onLoadPostizIntegrations={loadPostizIntegrations}
              onUpdateDelivery={updateDeliverySettings}
              onRefresh={() => void refreshAll()}
              oauthPlatforms={oauthPlatforms}
              publicAccountLabel={publicAccountLabel}
              publishActionHint={publishActionHint}
              formatPlatformMode={formatPlatformMode}
              cleanPublishStatus={cleanPublishStatus}
              statusTone={statusTone}
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
              onAutonomySettingsChange={updateAutonomySettings}
              onTemplateSaved={refreshAll}
              onDeleteTemplate={deleteSavedBrandStyle}
            />
          )}
        </div>

        <nav aria-label="Primary" className="fixed bottom-0 left-0 right-0 z-40 grid grid-cols-6 border-t border-white/[0.08] bg-surface/[0.95] pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden">
          {mobilePrimaryNav.map((item) => {
            const Icon = item.icon;
            const active = section === item.id;
            const step = workflowSteps.find((workflowStep) => workflowStep.section === item.id);
            return (
              <button
                key={item.id}
                type="button"
                aria-current={active ? "page" : undefined}
                onClick={() => {
                  setMobileMoreOpen(false);
                  setSection(item.id);
                }}
                className={`relative grid h-14 min-h-[44px] min-w-0 place-items-center content-center gap-1 px-1 text-[10px] font-medium ${active ? "text-cyan" : "text-zinc-500"}`}
              >
                <Icon className="h-4 w-4" />
                <span className="max-w-full truncate">{item.label}</span>
                {step ? <span aria-hidden className={`absolute right-[28%] top-2 h-1.5 w-1.5 rounded-full ${stepDotClass(step.status)}`} /> : null}
              </button>
            );
          })}
          <button
            type="button"
            aria-expanded={mobileMoreOpen}
            onClick={() => setMobileMoreOpen((open) => !open)}
            className={`grid h-14 min-h-[44px] min-w-0 place-items-center content-center gap-1 px-1 text-[10px] font-medium ${
              mobileMoreOpen || secondaryNav.some((item) => item.id === section) ? "text-cyan" : "text-zinc-500"
            }`}
          >
            <MoreHorizontal className="h-4 w-4" />
            <span className="max-w-full truncate">More</span>
          </button>
        </nav>
        {mobileMoreOpen ? (
          <div className="fixed inset-x-0 bottom-14 z-40 border-t border-white/[0.08] bg-surface/[0.98] p-3 backdrop-blur-xl lg:hidden">
            <p className="px-1 pb-2 text-[10px] font-bold uppercase tracking-wider text-zinc-600">Setup &amp; tools</p>
            <div className="grid grid-cols-3 gap-2">
              {secondaryNav.map((item) => {
                const Icon = item.icon;
                const active = section === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      setSection(item.id);
                      setMobileMoreOpen(false);
                    }}
                    className={`inline-flex items-center gap-2 rounded-2xl border px-3 py-3 text-left text-sm font-semibold ${
                      active ? "border-cyan/30 bg-cyan/10 text-cyan" : "border-white/[0.08] text-zinc-300"
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
        <ToastStack toasts={toasts} onDismiss={(id) => setToasts((items) => items.filter((item) => item.id !== id))} />
        <ActionMonitor actionStates={actionStates} />
        <WorkspaceManagerModal
          open={workspaceModalOpen}
          profiles={profiles}
          activeProfileId={profileId}
          onClose={() => setWorkspaceModalOpen(false)}
          onProfilesChange={setProfiles}
          onSwitchProfile={switchProfile}
          onStatus={(message) => {
            setStatus(message);
            pushToast(message, "success");
          }}
        />
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
