"use client";

import {
  AlertTriangle,
  BadgeCheck,
  CalendarDays,
  CheckCircle2,
  Clapperboard,
  Copy,
  Eye,
  FileVideo,
  Gauge,
  LayoutDashboard,
  Loader2,
  MoreHorizontal,
  RadioTower,
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
  formatDuration,
  formatTimestamp,
  GenerationJob,
  GenreOption,
  platformLabel,
  PublishAttempt,
  PublishTarget,
  RerenderJob,
  ScheduledPost,
  scoreValue,
  StyleProfile,
} from "@/lib/media-api";
import {PreviewPanel} from "@/components/review/PreviewPanel";
import {ReviewStudioSection} from "@/components/review/ReviewStudioSection";
import {BrandSection} from "@/components/brand/BrandSection";

type Section = "dashboard" | "generate" | "review" | "calendar" | "publish" | "brand";

const defaultSourceUrl = "https://www.youtube.com/live/WSg7MGv4_Fs?si=i0BS4fhJx_WfQW3P";
const defaultTemplate = "profiles/nourbit_opus_style.json";
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
    needs_caption_fix: "Caption fix",
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
  return ["draft", "rendered", "needs_caption_fix", "held", "pending_auto_schedule"].includes(clip.status);
}

function canScheduleClip(clip: ClipCandidate) {
  return clip.status === "approved";
}

function publishActionHint(error?: string) {
  const value = (error || "").toLowerCase();
  if (!value) return "";
  if (value.includes("401") || value.includes("unauthorized") || value.includes("token")) return "Reconnect this platform account.";
  if (value.includes("unaudited_client_can_only_post_to_private_accounts")) return "TikTok app belum audited. Set akun TikTok private + gunakan visibility SELF_ONLY, atau ajukan audit TikTok untuk publish publik.";
  if (value.includes("telegram upload was interrupted") || value.includes("broken pipe") || value.includes("timed out") || value.includes("urlopen")) return "Telegram upload interrupted. The system will prepare a <49MB Telegram copy, then retry this platform.";
  if (value.includes("above") && value.includes("after compression")) return "Telegram copy is still too large. Re-render a shorter clip or lower the render quality.";
  if (value.includes("rendered video file")) return "Re-render the clip before publishing.";
  if (value.includes("permission") && value.includes("evidence")) return "Legacy local guard entry. Safe to retry this platform.";
  return error || "";
}

const nav = [
  {id: "dashboard", label: "Dashboard", icon: LayoutDashboard},
  {id: "generate", label: "Generate", icon: Wand2},
  {id: "review", label: "Review Studio", icon: Clapperboard},
  {id: "calendar", label: "Calendar", icon: CalendarDays},
  {id: "publish", label: "Channels", icon: Send},
  {id: "brand", label: "Brand Settings", icon: Settings},
] as const;

function statusTone(status: string) {
  if (["approved", "published", "ready", "rendered", "scheduled", "ready_to_publish", "completed", "pending_auto_schedule"].includes(status)) return "text-teal border-teal/[0.30] bg-teal/[0.10]";
  if (["running", "queued"].includes(status)) return "text-cyan border-cyan/[0.30] bg-teal/[0.10]";
  if (["failed", "rejected"].includes(status)) return "text-danger border-danger/[0.30] bg-danger/[0.10]";
  if (["held", "needs_caption_fix"].includes(status)) return "text-warning border-warning/[0.30] bg-warning/[0.10]";
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

function metricAverage(clips: ClipCandidate[]) {
  const scores = clips.map((clip) => clip.score?.overall_score).filter((score): score is number => typeof score === "number");
  if (!scores.length) return "-";
  return Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length);
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
  {id: "repair", label: "Repair", hint: "Clips blocked by caption confidence or quality gates before they can be scheduled.", statuses: ["needs_caption_fix"]},
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
  if (canApproveClip(clip)) return clip.status === "needs_caption_fix" ? "Approve after fix" : "Approve";
  if (clip.status === "published") return "Published";
  if (clip.status === "ready_to_publish") return "Ready";
  if (clip.status === "scheduled") return "Scheduled";
  return formatClipStatus(clip.status);
}

function productionCommand(config: GenerateConfig) {
  return `cd "/Volumes/XPG SSD 1T/projects/otonom-agents-media/media-engine"
PYTHONPATH=. /tmp/media-engine-tools-py313/bin/python -m media_engine.cli premium-batch \\
  --youtube-url "${config.sourceUrl}" \\
  --count ${config.count} \\
  --clip-length-preset ${config.clipLength} \\
  --clip-min-seconds ${config.clipMinSeconds} \\
  --clip-max-seconds ${config.clipMaxSeconds} \\
  --genres ${config.genres.join(",")} \\
  --renderer ${config.renderer} \\
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
  const [durationPresets, setDurationPresets] = useState<DurationPreset[]>([]);
  const [genres, setGenres] = useState<GenreOption[]>([]);
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
    renderer: "remotion",
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
        durationRows,
        genreRows,
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
        apiGet<DurationPreset[]>("duration-presets"),
        apiGet<GenreOption[]>("genres"),
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
      setDurationPresets(durationRows);
      setGenres(genreRows);
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
        setStatus(`Dashboard synced with warning: ${message}`);
      } else {
        setStatus("Dashboard synced");
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
        renderer: "remotion",
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
          renderer: "remotion",
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
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[280px] border-r border-white/[0.06] bg-canvas-deep/[0.88] px-5 py-5 backdrop-blur-xl lg:block">
        <div className="flex items-center gap-3">
          <div className="grid h-12 w-12 place-items-center rounded-2xl border border-cyan text-xl font-semibold text-white shadow-glow">N</div>
          <div>
            <h1 className="text-lg font-semibold leading-6">Otonom Media</h1>
            <p className="text-xs text-zinc-400">Autonomous studio OS</p>
          </div>
        </div>

        <nav className="mt-8 grid gap-2">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = section === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setSection(item.id)}
                className={`flex h-12 items-center gap-3 rounded-2xl px-4 text-left text-sm font-medium transition ${
                  active ? "bg-teal/[0.15] text-cyan ring-1 ring-cyan/[0.30]" : "text-zinc-400 hover:bg-white/[0.05] hover:text-white"
                }`}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </button>
            );
          })}
        </nav>

        <div className="absolute bottom-5 left-5 right-5 grid gap-3">
          <div className="rounded-[24px] border border-white/[0.08] bg-surface p-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm font-semibold">Workspace Plan</span>
              <span className="rounded-full bg-teal/[0.10] px-2.5 py-1 text-xs font-medium text-teal">review</span>
            </div>
            <div className="grid gap-2 text-xs text-zinc-400">
              <div className="flex justify-between"><span>Daily cap</span><strong className="text-cyan">{credentials?.settings.nourbit_daily_content_cap || 2}</strong></div>
              <div className="flex justify-between"><span>Platforms</span><strong className="text-cyan">{readyPlatforms}/4</strong></div>
            </div>
          </div>
          <div className="rounded-[24px] border border-white/[0.08] bg-surface p-4 text-xs text-zinc-400">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white"><RadioTower className="h-4 w-4 text-teal" /> Engine Status</div>
            <div className="grid gap-2">
              <div className="flex justify-between"><span>Python API</span><span className="text-teal">Online</span></div>
              <div className="flex justify-between"><span>Renderer</span><span className="text-teal">Ready</span></div>
              <div className="flex justify-between"><span>ASR/LLM</span><span className="text-teal">Configured</span></div>
            </div>
          </div>
        </div>
      </aside>

      <main className="min-w-0 pb-20 lg:pl-[280px] lg:pb-0">
        <header className="sticky top-0 z-20 overflow-hidden border-b border-white/[0.06] bg-canvas-deep/[0.82] px-5 py-4 backdrop-blur-xl lg:px-8">
          <div className="flex min-w-0 flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-center">
              <div className="w-fit rounded-[20px] border border-white/[0.10] bg-surface px-5 py-3">
                <p className="text-xs text-zinc-400">Workspace</p>
                <p className="text-sm font-semibold text-white">Active Workspace</p>
              </div>
              <div className="min-w-0">
                <h2 className="max-w-full text-balance break-words text-2xl font-semibold tracking-[-0.03em] text-white md:text-3xl">Media Operations Studio</h2>
                <p className="mt-1 max-w-[calc(100vw-40px)] break-words text-sm text-zinc-400 md:max-w-2xl">Generate, review, approve, and publish autonomous short-form clips from one production surface.</p>
              </div>
            </div>
            <div className="grid min-w-0 grid-cols-1 items-center gap-2 sm:flex sm:flex-wrap">
              <button onClick={refreshAll} className="inline-flex h-11 min-w-0 items-center justify-center gap-2 rounded-full border border-white/[0.10] bg-surface px-4 text-sm font-medium text-zinc-200 hover:bg-surface-raised">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />} Refresh
              </button>
              <StatusPill busy={busy} status={status} />
            </div>
          </div>
        </header>

        <div className="grid min-w-0 gap-5 px-5 py-5 lg:px-8">
          <section className="grid min-w-0 gap-3 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Total Clips" value={clips.length} detail="Candidates in review queue" icon={FileVideo} />
            <MetricCard label="Approved" value={approved} detail="Ready for schedule" icon={BadgeCheck} />
            <MetricCard label="Avg Score" value={metricAverage(clips)} detail="Overall content quality" icon={Gauge} />
            <MetricCard label="Scheduled" value={scheduledCount} detail="Automated publish slots" icon={CalendarDays} />
          </section>

          {section === "dashboard" && (
            <DashboardSection
              clips={clips}
              selected={selected}
              schedule={schedule}
              actionStates={actionStates}
              onSection={setSection}
              onApprove={approveClip}
              onPublish={() => publishDueNow(true)}
            />
          )}

          {section === "generate" && (
            <GenerateSection
              config={generateConfig}
              templates={templates}
              durationPresets={durationPresets}
              genres={genres}
              jobs={jobs}
              actionState={actionStates["generate:start"]}
              setConfig={setGenerateConfig}
              command={command}
              onGenerate={startGeneration}
              onCopy={() => copyText(command, "Production command copied")}
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
            />
          )}

          {section === "brand" && (
            <BrandSection
              style={style}
              templates={templates}
              autonomy={autonomy}
              actionStates={actionStates}
              defaultTemplate={defaultTemplate}
              onAutonomyMode={updateAutonomyMode}
              onTemplateSaved={refreshAll}
            />
          )}
        </div>

        <nav className="fixed bottom-0 left-0 right-0 z-40 grid grid-cols-6 border-t border-white/[0.08] bg-surface/[0.95] backdrop-blur-xl lg:hidden">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = section === item.id;
            return (
              <button key={item.id} onClick={() => setSection(item.id)} className={`grid h-16 min-w-0 place-items-center content-center gap-1 text-[10px] ${active ? "text-cyan" : "text-zinc-500"}`}>
                <Icon className="h-4 w-4" />
                {item.label.split(" ")[0]}
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

function MetricCard({label, value, detail, icon: Icon}: {label: string; value: string | number; detail: string; icon: typeof Gauge}) {
  return (
    <div className="relative overflow-hidden rounded-[24px] border border-white/[0.08] bg-surface p-5 shadow-glow">
      <div className="absolute right-4 top-4 grid h-11 w-11 place-items-center rounded-full bg-teal/[0.14] text-cyan"><Icon className="h-5 w-5" /></div>
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-400">{label}</p>
      <p className="mt-3 text-4xl font-semibold tracking-[-0.04em] text-white">{value}</p>
      <p className="mt-2 text-sm text-zinc-500">{detail}</p>
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

function DashboardSection({
  clips,
  selected,
  schedule,
  actionStates,
  onSection,
  onApprove,
  onPublish,
}: {
  clips: ClipCandidate[];
  selected?: ClipCandidate;
  schedule: ScheduledPost[];
  actionStates: Record<string, ActionUiState>;
  onSection: (section: Section) => void;
  onApprove: (id: string) => void;
  onPublish: () => void;
}) {
  const top = clips.slice(0, 4);
  const approvedCount = clips.filter((clip) => clip.status === "approved").length;
  return (
    <section className="grid gap-5 xl:grid-cols-[1.05fr_.95fr]">
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-xl font-semibold text-white">Today’s production flow</h3>
            <p className="mt-1 text-sm text-zinc-400">A compact operating room for your next batch.</p>
          </div>
          <button onClick={() => onSection("generate")} className="rounded-full bg-cyan px-4 py-2 text-sm font-semibold text-ink">Generate</button>
        </div>
        <div className="mb-4 grid gap-2 rounded-[22px] border border-cyan/[0.16] bg-teal/[0.07] p-3 text-xs text-zinc-400 sm:grid-cols-3">
          <ReadinessLine ready={clips.length > 0} label="Candidates" detail={clips.length ? `${clips.length} in queue` : "Generate first"} />
          <ReadinessLine ready={approvedCount > 0} label="Approval" detail={approvedCount ? `${approvedCount} approved` : "Review needed"} />
          <ReadinessLine ready={schedule.length > 0} label="Calendar" detail={schedule.length ? `${schedule.length} scheduled` : "No slots yet"} />
        </div>
        <div className="grid gap-3 md:grid-cols-4">
          {[
            ["Generate", "Long video → 5 candidates", Sparkles],
            ["Curate", "Score, rank, context trim", Eye],
            ["Review", "Preview, caption, approve", Clapperboard],
            ["Schedule", "2 guarded slots per day", CalendarDays],
          ].map(([title, copy, Icon]) => (
            <div key={title as string} className="rounded-[22px] border border-white/[0.08] bg-canvas-deep p-4">
              <div className="mb-4 grid h-10 w-10 place-items-center rounded-2xl bg-cyan text-ink"><Icon className="h-5 w-5" /></div>
              <p className="font-semibold text-white">{title as string}</p>
              <p className="mt-2 text-xs leading-5 text-zinc-400">{copy as string}</p>
            </div>
          ))}
        </div>
        <div className="mt-5 rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
          <div className="mb-3 flex items-center justify-between">
            <h4 className="font-semibold text-white">Highest-ranked clips</h4>
            <button onClick={() => onSection("review")} className="text-sm font-medium text-cyan">Open Review Studio</button>
          </div>
          <div className="grid gap-2">
            {top.length ? top.map((clip) => <CompactClip key={clip.id} clip={clip} actionState={actionStates[`clip:${clip.id}:approve`]} onApprove={onApprove} />) : (
              <EmptyState
                title="No clips yet"
                text="Start with Generate to produce a ranked batch."
                actionLabel="Open Generate"
                onAction={() => onSection("generate")}
              />
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-5">
        <PreviewPanel clip={selected} statusTone={statusTone} />
        <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-white">Next publish queue</h3>
            <button onClick={() => onSection("calendar")} className="rounded-full border border-cyan/[0.25] bg-teal/[0.10] px-4 py-2 text-sm font-semibold text-cyan">Open Calendar</button>
          </div>
          <div className="grid gap-3">
            {schedule.slice(0, 4).length ? schedule.slice(0, 4).map((item) => (
              <div key={item.id} className="flex items-center justify-between gap-3 rounded-2xl bg-canvas-deep px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-zinc-200">{item.title_hook}</p>
                  <p className="mt-1 text-xs text-zinc-500">{formatSchedule(item.scheduled_at)}</p>
                </div>
                <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.status)}`}>{formatClipStatus(item.status)}</span>
              </div>
            )) : (
              <EmptyState
                title="No scheduled clips"
                text="Approve a clip, then place it into the next publishing slot."
                actionLabel="Open Review"
                onAction={() => onSection("review")}
              />
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function GenerateSection({
  config,
  templates,
  durationPresets,
  genres,
  jobs,
  actionState,
  setConfig,
  command,
  onGenerate,
  onCopy,
}: {
  config: GenerateConfig;
  templates: BrandTemplate[];
  durationPresets: DurationPreset[];
  genres: GenreOption[];
  jobs: GenerationJob[];
  actionState?: ActionUiState;
  setConfig: (value: GenerateConfig) => void;
  command: string;
  onGenerate: () => void;
  onCopy: () => void;
}) {
  const latest = jobs[0];
  const isStarting = actionState?.status === "running";
  const update = (patch: Partial<GenerateConfig>) => setConfig({...config, ...patch});
  const presetOptions = durationPresets.length ? durationPresets : [{id: "auto", label: "Auto (0-3 min)", detail: "20-180s", range_label: "0-3 min", best_for: "General use", min_ms: 20_000, target_ms: 90_000, max_ms: 180_000, intent: "Automatic duration"}];
  const genreOptions = genres.length ? genres : [
    {id: "kajian", label: "Kajian", description: "Religious teaching and reflection."},
    {id: "spiritual_reflection", label: "Spiritual reflection", description: "Heart-softening clips."},
    {id: "advice", label: "Advice", description: "Practical reminders."},
  ];
  const selectedPreset = presetOptions.find((item) => item.id === config.clipLength) || presetOptions[0];
  const latestProgress = Math.max(0, Math.min(100, latest?.progress || 0));
  const selectedGenreCount = genreOptions.filter((genre) => config.genres.includes(genre.id)).length;
  const toggleGenre = (id: string) => {
    const next = config.genres.includes(id) ? config.genres.filter((item) => item !== id) : [...config.genres, id];
    update({genres: next.length ? next : [id]});
  };
  return (
    <section className="grid min-w-0 gap-5 2xl:grid-cols-[minmax(0,.9fr)_minmax(0,1.1fr)]">
      <div className="min-w-0 rounded-[24px] border border-white/[0.08] bg-surface p-4 sm:rounded-[28px] sm:p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <span className="inline-flex rounded-full border border-teal/[0.22] bg-teal/[0.08] px-3 py-1 text-xs font-semibold text-teal">Local-first pipeline</span>
            <h3 className="mt-3 text-2xl font-semibold text-white">Generate production batch</h3>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-400">Choose the source, curation intent, and render profile. Advanced engine settings stay available without crowding the main flow.</p>
          </div>
          <div className="grid gap-1 rounded-[20px] border border-white/[0.08] bg-canvas-deep px-4 py-3 text-left sm:min-w-[150px] sm:text-right">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Batch output</span>
            <span className="text-lg font-semibold text-white">{config.count} clips</span>
            <span className="text-xs text-cyan">{config.clipMinSeconds}s-{config.clipMaxSeconds}s window</span>
          </div>
        </div>

        <div className="mt-6 grid gap-5">
          <div className="rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
            <div className="mb-4 flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-teal/[0.12] text-cyan">1</span>
              <div>
                <h4 className="font-semibold text-white">Source and output</h4>
                <p className="text-xs text-zinc-500">Start with the long video and expected batch size.</p>
              </div>
            </div>
            <div className="grid gap-4">
              <label className="grid min-w-0 gap-2 text-sm font-medium text-zinc-300">
                YouTube source
                <input value={config.sourceUrl} onChange={(event) => update({sourceUrl: event.target.value})} className="h-12 rounded-2xl border border-white/[0.08] bg-black/24 px-4 text-sm text-zinc-300 outline-none focus:border-cyan/[0.30]" placeholder="Paste long-form YouTube URL" />
              </label>
              <div className="grid min-w-0 gap-3 md:grid-cols-2">
                <label className="grid gap-2 text-sm font-medium text-zinc-300">
                  Clip count
                  <select value={config.count} onChange={(event) => update({count: Number(event.target.value)})} className="h-12 rounded-2xl border border-white/[0.08] bg-black/24 px-4 outline-none focus:border-cyan/[0.30]">
                    {[1, 2, 3, 5, 8, 10].map((value) => <option key={value} value={value}>{value} clips</option>)}
                  </select>
                </label>
                <label className="grid gap-2 text-sm font-medium text-zinc-300">
                  Clip duration
                  <select
                    value={config.clipLength}
                    onChange={(event) => {
                      const preset = presetOptions.find((item) => item.id === event.target.value);
                      update({
                        clipLength: event.target.value,
                        clipMinSeconds: preset ? Math.round(preset.min_ms / 1000) : config.clipMinSeconds,
                        clipMaxSeconds: preset ? Math.round(preset.max_ms / 1000) : config.clipMaxSeconds,
                      });
                    }}
                    className="h-12 rounded-2xl border border-cyan/[0.35] bg-black/24 px-4 text-sm font-semibold text-white outline-none shadow-glow"
                  >
                    {presetOptions.map((preset) => (
                      <option key={preset.id} value={preset.id}>{preset.label}</option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="rounded-2xl border border-teal/[0.16] bg-teal/[0.06] px-4 py-3 text-xs leading-5 text-zinc-400">
                <span className="font-semibold text-cyan">{selectedPreset?.label}</span> lets the engine trim natural starts and endings inside <span className="font-semibold text-zinc-200">{config.clipMinSeconds}s-{config.clipMaxSeconds}s</span>.
              </div>
            </div>
          </div>

          <div className="rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-teal/[0.12] text-cyan">2</span>
                <div>
                  <h4 className="font-semibold text-white">Curation intent</h4>
                  <p className="text-xs text-zinc-500">{selectedGenreCount} genre signals selected for scoring and hook generation.</p>
                </div>
              </div>
              <span className="rounded-full border border-cyan/[0.24] bg-teal/[0.08] px-3 py-1 text-xs font-semibold text-cyan">{selectedGenreCount}/{genreOptions.length}</span>
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

          <div className="rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
            <div className="mb-4 flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-teal/[0.12] text-cyan">3</span>
              <div>
                <h4 className="font-semibold text-white">Brand and engine</h4>
                <p className="text-xs text-zinc-500">Pick the reusable template, then adjust advanced settings only when needed.</p>
              </div>
            </div>
            <label className="grid gap-2 text-sm font-medium text-zinc-300">
              Brand template
              <select value={config.brandTemplate} onChange={(event) => update({brandTemplate: event.target.value})} className="h-12 rounded-2xl border border-white/[0.08] bg-black/24 px-4 outline-none focus:border-cyan/[0.30]">
                {(templates.length ? templates : [{id: defaultTemplate, label: "Nourbit Opus Style", path: defaultTemplate}]).map((template) => (
                  <option key={template.id} value={template.path}>{template.label}</option>
                ))}
              </select>
            </label>
            <details className="mt-4 rounded-[20px] border border-white/[0.08] bg-black/20 p-3">
              <summary className="cursor-pointer list-none text-sm font-semibold text-zinc-200">
                Advanced engine settings
                <span className="ml-2 text-xs font-medium text-zinc-500">{config.renderer} · {config.captionSource} · {config.llmProvider}</span>
              </summary>
              <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                <SelectTile label="Renderer" value={config.renderer} options={["remotion", "ffmpeg"]} onChange={(value) => update({renderer: value})} />
                <SelectTile label="Caption" value={config.captionSource} options={["whisper", "hybrid", "youtube"]} onChange={(value) => update({captionSource: value})} />
                <SelectTile label="Speech language" value={config.speechLanguage} options={["id", "ar", "en", "ms"]} onChange={(value) => update({speechLanguage: value})} />
                <SelectTile label="Transcript" value={config.transcriptLanguages} options={["id,en", "id", "en,id", "ar,id", "ms,id"]} onChange={(value) => update({transcriptLanguages: value})} />
                <SelectTile label="LLM" value={config.llmProvider} options={["deepseek", "openai", "groq", "none"]} onChange={(value) => update({llmProvider: value})} />
                <SelectTile label="Quality" value={config.quality} options={["production", "draft"]} onChange={(value) => update({quality: value})} />
              </div>
            </details>
          </div>

          <div className="grid gap-3">
            <button disabled={isStarting || !config.sourceUrl.trim()} onClick={onGenerate} className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-cyan px-5 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50">
              {isStarting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
              {isStarting ? "Starting batch..." : "Generate batch"}
            </button>
            {actionState ? <InlineActionStatus state={actionState} /> : null}
          </div>
        </div>
      </div>

      <div className="grid min-w-0 gap-5">
        <div className="min-w-0 rounded-[24px] border border-white/[0.08] bg-surface p-4 sm:rounded-[28px] sm:p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <h3 className="text-xl font-semibold text-white">Production monitor</h3>
              <p className="mt-1 text-sm leading-6 text-zinc-400">Track the current batch without reading terminal logs first.</p>
            </div>
            <span className={`w-fit rounded-full border px-3 py-1 text-xs font-semibold ${statusTone(latest?.status || "empty")}`}>{latest?.status || "No job"}</span>
          </div>
          {latest ? (
            <div className="grid gap-4">
              <div className="grid min-w-0 gap-2 rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
                <div className="flex min-w-0 items-center justify-between gap-3 text-sm">
                  <span className="min-w-0 truncate font-semibold text-white">{latest.count} clips · {latest.llm_provider}/{latest.caption_source}</span>
                  <span className="font-semibold text-cyan">{latestProgress}%</span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-surface-strong">
                  <div className="h-full rounded-full bg-cyan transition-all" style={{width: `${Math.max(4, latestProgress)}%`}} />
                </div>
              </div>
              <div className="grid gap-2 text-xs md:grid-cols-3">
                <ReadinessLine ready={latestProgress >= 20} label="Curate" detail="Moments" />
                <ReadinessLine ready={latestProgress >= 55} label="Captions" detail="ASR" />
                <ReadinessLine ready={latestProgress >= 90} label="Render" detail="Output" />
              </div>
              <div className="min-w-0 rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Runtime log</span>
                  <span className="text-xs text-zinc-600">Latest lines</span>
                </div>
                <pre className="max-h-52 overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-black/40 p-3 text-[11px] leading-5 text-zinc-400">{latest.error || latest.log_text || "Waiting for logs..."}</pre>
              </div>
            </div>
          ) : (
            <EmptyState title="No active batch" text="Start a generation run to see progress, logs, and output readiness here." />
          )}
        </div>

        <details className="min-w-0 rounded-[24px] border border-white/[0.08] bg-surface p-4 sm:rounded-[28px] sm:p-5">
          <summary className="flex cursor-pointer list-none flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <h3 className="text-lg font-semibold text-white">Terminal fallback command</h3>
              <p className="mt-1 text-sm text-zinc-500">Use this when you want to run the same job outside the dashboard.</p>
            </div>
            <button type="button" onClick={(event) => { event.preventDefault(); onCopy(); }} className="inline-flex w-fit rounded-full bg-cyan px-4 py-2 text-sm font-semibold text-ink"><Copy className="mr-2 h-4 w-4" /> Copy</button>
          </summary>
          <pre className="mt-4 max-h-[360px] overflow-auto whitespace-pre-wrap break-words rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4 text-xs leading-6 text-zinc-300 sm:p-5">{command}</pre>
        </details>
      </div>
    </section>
  );
}

function SelectTile({label, value, options, onChange}: {label: string; value: string; options: string[]; onChange: (value: string) => void}) {
  return (
    <label className="grid gap-2 rounded-[22px] border border-white/[0.08] bg-canvas-deep p-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)} className="min-w-0 bg-transparent text-sm font-semibold normal-case tracking-normal text-white outline-none">
        {options.map((option) => <option key={option} value={option}>{option}</option>)}
      </select>
    </label>
  );
}

function CalendarSection({
  schedule,
  approved,
  targets,
  selectedPlatforms,
  actionStates,
  onToggleDefaultPlatform,
  onSchedule,
  onUnschedule,
  onUpdateSchedulePlatforms,
  onPublishDue,
  onDryRunDue,
}: {
  schedule: ScheduledPost[];
  approved: ClipCandidate[];
  targets: PublishTarget[];
  selectedPlatforms: string[];
  actionStates: Record<string, ActionUiState>;
  onToggleDefaultPlatform: (platform: string) => void;
  onSchedule: (id: string) => void;
  onUnschedule: (id: string) => void;
  onUpdateSchedulePlatforms: (scheduleId: string, platforms: string[]) => void;
  onPublishDue: () => void;
  onDryRunDue: () => void;
}) {
  function toggleSchedulePlatform(item: ScheduledPost, platform: string) {
    const current = item.platforms || [];
    const next = current.includes(platform) ? current.filter((value) => value !== platform) : [...current, platform];
    if (!next.length) return;
    onUpdateSchedulePlatforms(item.id, next);
  }
  const dryRunState = actionStates["publish:due:dry"];
  const publishDueState = actionStates["publish:due:live"];
  const dueBusy = dryRunState?.status === "running" || publishDueState?.status === "running";

  return (
    <section className="grid gap-5 xl:grid-cols-[1fr_420px]">
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-xl font-semibold text-white">Calendar queue</h3>
            <p className="mt-1 text-sm text-zinc-400">Scheduled publish queue for approved clips. Default cadence is 2 posts per day at 09:00 and 19:30 WIB.</p>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <button disabled={dueBusy} onClick={onDryRunDue} className="inline-flex items-center justify-center gap-2 rounded-full border border-white/[0.10] px-4 py-2 text-sm font-semibold text-zinc-300 disabled:cursor-not-allowed disabled:opacity-50">
              {dryRunState?.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Dry-run due
            </button>
            <button disabled={dueBusy} onClick={onPublishDue} className="inline-flex items-center justify-center gap-2 rounded-full bg-cyan px-4 py-2 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50">
              {publishDueState?.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {publishDueState?.status === "running" ? "Publishing..." : "Publish due now"}
            </button>
          </div>
        </div>
        {dryRunState?.status === "running" || publishDueState?.status === "running" ? (
          <div className="mb-4"><InlineActionStatus state={publishDueState?.status === "running" ? publishDueState : dryRunState} /></div>
        ) : null}
        <div className="grid gap-3">
          {schedule.length ? schedule.map((item) => (
            <div key={item.id} className="grid gap-3 rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4 md:grid-cols-[160px_minmax(0,1fr)_140px] md:items-center">
              <div>
                <p className="text-xs uppercase tracking-wide text-zinc-500">Scheduled</p>
                <p className="mt-1 font-semibold text-cyan">{formatSchedule(item.scheduled_at)}</p>
              </div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="truncate text-base font-semibold text-white">{item.title_hook}</h4>
                  <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusTone(item.status)}`}>{formatClipStatus(item.status)}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-sm leading-5 text-zinc-400">{item.viral_reason}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {targets.map((target) => {
                    const platform = target.platform;
                    const enabled = item.platforms.includes(platform);
                    const result = item.platform_results?.[platform];
                    const platformAction = actionStates[`schedule:${item.id}:platforms`];
                    const platformStatus = result?.status || (item.status === "published" ? "published" : "pending");
                    return (
                      <button
                        key={platform}
                        onClick={() => toggleSchedulePlatform(item, platform)}
                        disabled={platformAction?.status === "running"}
                        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-left text-xs font-semibold transition ${
                          enabled ? statusTone(platformStatus) : "border-white/[0.08] bg-white/[0.03] text-zinc-500"
                        } disabled:cursor-not-allowed disabled:opacity-50`}
                      >
                        {enabled ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                        {platformAction?.status === "running" ? "Updating..." : `${platformLabel(platform)} · ${enabled ? cleanPublishStatus(platformStatus) : "Off"}`}
                      </button>
                    );
                  })}
                </div>
                {item.last_error ? <p className="mt-2 line-clamp-2 text-xs text-danger">{item.last_error}</p> : null}
              </div>
              <button
                disabled={actionStates[`clip:${item.candidate_id}:unschedule`]?.status === "running"}
                onClick={() => onUnschedule(item.candidate_id)}
                className="inline-flex items-center justify-center gap-2 rounded-full border border-white/[0.10] px-4 py-2 text-sm font-semibold text-zinc-300 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {actionStates[`clip:${item.candidate_id}:unschedule`]?.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {actionStates[`clip:${item.candidate_id}:unschedule`]?.status === "running" ? "Removing..." : "Unschedule"}
              </button>
            </div>
          )) : <EmptyState title="No scheduled posts" text="Approve clips first, then assign the next open slot." />}
        </div>
      </div>
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <h3 className="text-lg font-semibold text-white">Approved clips</h3>
        <p className="mt-1 text-sm text-zinc-400">Add approved clips to the next available workspace slot.</p>
        <div className="mt-5 rounded-[22px] border border-white/[0.08] bg-canvas-deep p-4">
          <p className="text-sm font-semibold text-white">Default publish targets</p>
          <p className="mt-1 text-xs leading-5 text-zinc-500">Used when you schedule a clip. You can still override each scheduled item.</p>
          <div className="mt-3 grid gap-2">
            {targets.map((target) => {
              const active = selectedPlatforms.includes(target.platform);
              const targetState = actionStates[`target:${target.platform}`];
              return (
                <div
                  key={target.platform}
                  className={`flex items-center justify-between rounded-2xl border px-3 py-2 text-left text-xs font-semibold transition ${
                    active ? "border-cyan/[0.45] bg-teal/[0.14] text-cyan" : "border-white/[0.08] bg-black/20 text-zinc-500"
                  }`}
                >
                  <span>{platformLabel(target.platform)}</span>
                  <SwitchControl
                    checked={active}
                    disabled={targetState?.status === "running"}
                    label={targetState?.status === "running" ? "Saving" : active ? "On" : "Off"}
                    onChange={() => onToggleDefaultPlatform(target.platform)}
                  />
                </div>
              );
            })}
          </div>
        </div>
        <div className="mt-5 grid gap-3">
          {approved.length ? approved.map((clip) => (
            <div key={clip.id} className="rounded-[22px] border border-white/[0.08] bg-canvas-deep p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-semibold text-white">{clip.title_hook}</p>
                  <p className="mt-1 text-xs text-zinc-500">{formatTimestamp(clip.start_ms)} → {formatTimestamp(clip.end_ms)}</p>
                </div>
                <ScoreBubble value={clip.score?.overall_score} />
              </div>
              <button
                disabled={actionStates[`clip:${clip.id}:schedule`]?.status === "running" || !selectedPlatforms.length}
                onClick={() => onSchedule(clip.id)}
                className="mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-full bg-cyan text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50"
              >
                {actionStates[`clip:${clip.id}:schedule`]?.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {actionStates[`clip:${clip.id}:schedule`]?.status === "running" ? "Scheduling..." : selectedPlatforms.length ? "Schedule next slot" : "Turn on a target first"}
              </button>
            </div>
          )) : <EmptyState title="No approved clips" text="Review and approve a rendered clip before scheduling." />}
        </div>
      </div>
    </section>
  );
}

function PublishSection({
  targets,
  credentials,
  attempts,
  selectedPlatforms,
  actionStates,
  onTogglePlatform,
  onTestConnection,
  onStartOauth,
  onDisconnect,
}: {
  targets: PublishTarget[];
  credentials: CredentialStatus | null;
  attempts: PublishAttempt[];
  selectedPlatforms: string[];
  actionStates: Record<string, ActionUiState>;
  onTogglePlatform: (platform: string) => void;
  onTestConnection: (platform: string) => void;
  onStartOauth: (platform: string) => void;
  onDisconnect: (platform: string) => void;
}) {
  const latestByPlatform = new Map<string, PublishAttempt>();
  for (const attempt of attempts) {
    if (!latestByPlatform.has(attempt.platform)) latestByPlatform.set(attempt.platform, attempt);
  }
  return (
    <section className="grid gap-5 xl:grid-cols-[1fr_420px]">
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <h3 className="text-xl font-semibold text-white">Channels</h3>
            <p className="mt-1 text-sm text-zinc-400">Connect social accounts and choose default publish targets. Actual publishing happens from Calendar or clip actions.</p>
          </div>
          <div className="rounded-full border border-cyan/[0.25] bg-teal/[0.10] px-4 py-2 text-xs font-semibold text-cyan">
            {targets.filter((target) => credentials?.platforms[target.platform]?.ready).length}/{targets.length} connected
          </div>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {targets.map((target) => {
            const ready = credentials?.platforms[target.platform]?.ready;
            const credential = credentials?.platforms[target.platform];
            const selectedForPublish = selectedPlatforms.includes(target.platform);
            const latest = latestByPlatform.get(target.platform);
            const recovery = publishActionHint(latest?.error);
            const supportsOauth = oauthPlatforms.has(target.platform);
            const activeAction = [
              actionStates[`test:${target.platform}`],
              actionStates[`connect:${target.platform}`],
              actionStates[`disconnect:${target.platform}`],
              actionStates[`target:${target.platform}`],
            ].find((item) => item?.status === "running");
            const isBusy = Boolean(activeAction);
            return (
              <div key={target.platform} className={`rounded-[24px] border p-4 transition ${selectedForPublish ? "border-cyan/[0.30] bg-teal/[0.08]" : "border-white/[0.08] bg-canvas-deep"}`}>
                <div className="flex items-center justify-between">
                  <div className="grid h-11 w-11 place-items-center rounded-2xl bg-cyan text-ink"><Send className="h-5 w-5" /></div>
                  <SwitchControl checked={selectedForPublish} disabled={isBusy} label="Target" onChange={() => onTogglePlatform(target.platform)} />
                </div>
                <h4 className="mt-4 font-semibold text-white">{platformLabel(target.platform)}</h4>
                <p className="mt-1 text-sm text-zinc-400">{target.account_label}</p>
                <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-zinc-400">
                  <SettingTile label="Connection" value={ready ? "Connected" : "Needs setup"} />
                  <SettingTile label="Mode" value={formatPlatformMode(target.mode)} />
                </div>
                <ChannelReadiness ready={Boolean(ready)} targeted={selectedForPublish} />
                {!ready ? (
                  <div className="mt-3 rounded-2xl border border-warning/20 bg-warning/[0.08] p-3 text-xs leading-5 text-warning">
                    Missing: {(credential?.missing_keys || []).join(", ") || "credential"}. Connect via OAuth/token setup before live publishing.
                  </div>
                ) : null}
                <div className="mt-4 rounded-2xl border border-white/[0.08] bg-black/20 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs uppercase tracking-wide text-zinc-500">Current attempt</span>
                    <span className={`inline-flex max-w-[70%] items-center gap-1 truncate rounded-full border px-2 py-1 text-xs font-semibold ${statusTone(activeAction ? "running" : latest?.status || "pending")}`}>
                      {activeAction ? <Loader2 className="h-3 w-3 shrink-0 animate-spin" /> : null}
                      <span className="truncate">{activeAction?.message || cleanPublishStatus(latest?.status)}</span>
                    </span>
                  </div>
                  {recovery ? <p className="mt-2 line-clamp-2 text-xs leading-5 text-danger">{recovery}</p> : null}
                  {activeAction ? <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/[0.08]"><div className="h-full w-2/3 animate-pulse rounded-full bg-cyan" /></div> : null}
                </div>
                <div className="mt-4 flex items-center gap-2">
                  <button
                    disabled={isBusy}
                    onClick={() => onTestConnection(target.platform)}
                    className="h-10 flex-1 rounded-full border border-cyan/[0.24] bg-teal/[0.08] text-xs font-semibold text-cyan disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {actionStates[`test:${target.platform}`]?.status === "running" ? "Testing..." : "Test connection"}
                  </button>
                  <PlatformActionMenu
                    disabled={isBusy}
                    ready={Boolean(ready)}
                    supportsOauth={supportsOauth}
                    platform={target.platform}
                    onTestConnection={onTestConnection}
                    onStartOauth={onStartOauth}
                    onDisconnect={onDisconnect}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <h3 className="text-xl font-semibold text-white">Channel readiness</h3>
        <p className="mt-2 text-sm leading-6 text-zinc-400">Use this page to connect accounts. Schedule and publish controls live next to clips, where the content context is visible.</p>
        <div className="mt-5 grid gap-3">
          <div className="rounded-[22px] border border-cyan/[0.18] bg-teal/[0.08] p-4 text-sm leading-6 text-zinc-300">
            Scheduled items publish through the PM2 worker. For a one-off publish, open Calendar and run the due queue for the selected scheduled clip.
          </div>
          <div className="rounded-[22px] border border-white/[0.08] bg-canvas-deep p-4">
            <p className="text-xs uppercase tracking-wide text-zinc-500">Default targets</p>
            <div className="mt-3 grid gap-2">
              {targets.map((target) => {
                const ready = credentials?.platforms[target.platform]?.ready;
                const enabled = selectedPlatforms.includes(target.platform);
                return (
                  <ReadinessLine
                    key={target.platform}
                    ready={Boolean(ready && enabled)}
                    label={platformLabel(target.platform)}
                    detail={!enabled ? "Target off" : ready ? "Ready" : "Reconnect"}
                  />
                );
              })}
            </div>
          </div>
          {Array.from(latestByPlatform.values()).length ? Array.from(latestByPlatform.values()).map((attempt) => (
            <div key={attempt.id} className="rounded-[18px] border border-white/[0.08] bg-canvas-deep p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-white">{platformLabel(attempt.platform)}</p>
                <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusTone(attempt.status)}`}>{cleanPublishStatus(attempt.status)}</span>
              </div>
              {attempt.error ? <p className="mt-2 text-xs leading-5 text-danger">{publishActionHint(attempt.error)}</p> : null}
            </div>
          )) : <EmptyState title="No channel activity yet" text="Connection tests and scheduled publishing attempts will appear here." />}
        </div>
      </div>
    </section>
  );
}

function SwitchControl({checked, disabled, label, onChange}: {checked: boolean; disabled?: boolean; label: string; onChange: () => void}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={onChange}
      className={`inline-flex h-8 items-center gap-2 rounded-full border px-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
        checked ? "border-cyan/[0.45] bg-cyan text-ink" : "border-white/[0.12] bg-white/[0.04] text-zinc-400"
      }`}
    >
      <span>{label}</span>
      <span className={`relative h-5 w-9 rounded-full transition ${checked ? "bg-ink/25" : "bg-white/[0.10]"}`}>
        <span className={`absolute top-1 h-3 w-3 rounded-full bg-current transition ${checked ? "left-5 text-ink" : "left-1 text-zinc-500"}`} />
      </span>
    </button>
  );
}

function ChannelReadiness({ready, targeted}: {ready: boolean; targeted: boolean}) {
  return (
    <div className="mt-3 grid gap-1.5 rounded-2xl border border-white/[0.08] bg-black/15 p-3">
      <ReadinessLine ready={ready} label="Account" detail={ready ? "Connected" : "Connect"} />
      <ReadinessLine ready={targeted} label="Default target" detail={targeted ? "On" : "Off"} />
      <ReadinessLine ready label="Publish controls" detail="Calendar" />
    </div>
  );
}

function PlatformActionMenu({
  disabled,
  ready,
  supportsOauth,
  platform,
  onTestConnection,
  onStartOauth,
  onDisconnect,
}: {
  disabled?: boolean;
  ready: boolean;
  supportsOauth: boolean;
  platform: string;
  onTestConnection: (platform: string) => void;
  onStartOauth: (platform: string) => void;
  onDisconnect: (platform: string) => void;
}) {
  return (
    <details className="group relative">
      <summary
        aria-disabled={disabled}
        className={`grid h-10 w-10 list-none place-items-center rounded-full border border-white/[0.10] bg-white/[0.04] text-zinc-200 marker:hidden ${
          disabled ? "pointer-events-none opacity-50" : "cursor-pointer hover:border-cyan/[0.35] hover:text-cyan"
        }`}
      >
        <MoreHorizontal className="h-4 w-4" />
      </summary>
      <div className="absolute right-0 z-30 mt-2 w-52 overflow-hidden rounded-2xl border border-white/[0.10] bg-canvas-deep p-1 shadow-2xl">
        <MenuAction onClick={() => onTestConnection(platform)}>Test connection</MenuAction>
        <MenuAction onClick={() => (supportsOauth ? onStartOauth(platform) : onTestConnection(platform))}>{ready ? "Reconnect" : "Connect"}</MenuAction>
        <MenuAction danger onClick={() => onDisconnect(platform)}>Disconnect</MenuAction>
      </div>
    </details>
  );
}

function MenuAction({children, danger, onClick}: {children: ReactNode; danger?: boolean; onClick: () => void}) {
  return (
    <button
      type="button"
      onClick={(event) => {
        event.currentTarget.closest("details")?.removeAttribute("open");
        onClick();
      }}
      className={`flex h-10 w-full items-center rounded-xl px-3 text-left text-xs font-semibold transition ${
        danger ? "text-danger hover:bg-danger/[0.10]" : "text-zinc-200 hover:bg-white/[0.06] hover:text-cyan"
      }`}
    >
      {children}
    </button>
  );
}

function InlineActionStatus({state}: {state?: ActionUiState}) {
  if (!state) return null;
  const tone =
    state.status === "failed"
      ? "border-danger/[0.26] bg-danger/[0.10] text-danger"
      : state.status === "done"
        ? "border-teal/[0.26] bg-teal/[0.10] text-teal"
        : "border-cyan/[0.26] bg-teal/[0.10] text-cyan";
  return (
    <div className={`rounded-2xl border px-3 py-2 text-xs font-medium ${tone}`}>
      <div className="flex items-center gap-2">
        {state.status === "running" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
        <span>{state.message}</span>
      </div>
      {state.status === "running" ? (
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.08]">
          <div className="h-full w-2/3 animate-pulse rounded-full bg-cyan" />
        </div>
      ) : null}
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

function CompactClip({clip, actionState, onApprove}: {clip: ClipCandidate; actionState?: ActionUiState; onApprove: (id: string) => void}) {
  const isApproving = actionState?.status === "running";
  const canApprove = canApproveClip(clip);
  return (
    <div className="grid gap-3 rounded-[18px] border border-white/[0.08] bg-surface-raised px-4 py-3 md:grid-cols-[minmax(0,1fr)_58px_auto] md:items-center">
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-white">{clip.title_hook}</p>
        <p className="mt-1 text-xs text-zinc-500">{formatTimestamp(clip.start_ms)} → {formatTimestamp(clip.end_ms)}</p>
      </div>
      <ScoreBubble value={clip.score?.overall_score} />
      <button disabled={isApproving || !canApprove} onClick={() => canApprove && onApprove(clip.id)} className="inline-flex items-center justify-center gap-1.5 rounded-full border border-teal/[0.30] bg-teal/[0.10] px-3 py-2 text-xs font-semibold text-teal disabled:cursor-not-allowed disabled:opacity-50">
        {isApproving ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
        {isApproving ? "Approving..." : canApprove ? "Approve" : formatClipStatus(clip.status)}
      </button>
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

function SettingTile({label, value}: {label: string; value: string | number}) {
  return (
    <div className="rounded-[18px] border border-white/[0.08] bg-canvas-deep p-4">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-white">{value}</p>
    </div>
  );
}

function EmptyState({title = "Nothing here yet", text, actionLabel, onAction}: {title?: string; text: string; actionLabel?: string; onAction?: () => void}) {
  return (
    <div className="grid min-h-[140px] place-items-center rounded-[22px] border border-dashed border-white/[0.10] bg-canvas-deep p-6 text-center">
      <div>
        <AlertTriangle className="mx-auto mb-3 h-6 w-6 text-zinc-600" />
        <p className="text-sm font-semibold text-zinc-300">{title}</p>
        <p className="mt-1 max-w-sm text-sm leading-6 text-zinc-500">{text}</p>
        {actionLabel && onAction ? (
          <button type="button" onClick={onAction} className="mt-4 rounded-full border border-cyan/[0.28] bg-teal/[0.10] px-4 py-2 text-xs font-semibold text-cyan">
            {actionLabel}
          </button>
        ) : null}
      </div>
    </div>
  );
}
