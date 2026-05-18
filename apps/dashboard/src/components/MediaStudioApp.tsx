"use client";

import {
  AlertTriangle,
  BadgeCheck,
  CalendarDays,
  Clapperboard,
  Copy,
  Database,
  Eye,
  FileVideo,
  Gauge,
  LayoutDashboard,
  Loader2,
  Plus,
  RadioTower,
  RefreshCcw,
  Rocket,
  Send,
  Settings,
  Sparkles,
  Wand2,
} from "lucide-react";
import {useEffect, useMemo, useRef, useState} from "react";
import {
  apiGet,
  apiPath,
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

function publishActionHint(error?: string) {
  const value = (error || "").toLowerCase();
  if (!value) return "";
  if (value.includes("401") || value.includes("unauthorized") || value.includes("token")) return "Reconnect this platform account.";
  if (value.includes("broken pipe") || value.includes("timed out") || value.includes("urlopen")) return "Network/upload interrupted. Retry this platform.";
  if (value.includes("rendered video file")) return "Re-render the clip before publishing.";
  if (value.includes("permission") && value.includes("evidence")) return "Legacy local guard entry. Safe to retry this platform.";
  return error || "";
}

const nav = [
  {id: "dashboard", label: "Dashboard", icon: LayoutDashboard},
  {id: "generate", label: "Generate", icon: Wand2},
  {id: "review", label: "Review Studio", icon: Clapperboard},
  {id: "calendar", label: "Calendar", icon: CalendarDays},
  {id: "publish", label: "Publish Center", icon: Send},
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
  {id: "rejected", label: "Rejected", hint: "Clips intentionally removed from production consideration.", statuses: ["rejected"]},
] as const;

function matchesReviewFilter(clip: ClipCandidate, filter: string) {
  const group = reviewFilters.find((item) => item.id === filter);
  if (!group || group.id === "all") return true;
  return (group.statuses as readonly string[]).includes(clip.status);
}

function primaryReviewAction(clip: ClipCandidate) {
  if (clip.status === "approved") return "Schedule";
  if (clip.status === "held" || clip.status === "rejected") return "Restore";
  return "Approve";
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
  const [status, setStatus] = useState("Ready");
  const [busy, setBusy] = useState(false);
  const [rerendering, setRerendering] = useState<Record<string, RerenderUiState>>({});
  const [captionDrafts, setCaptionDrafts] = useState<Record<string, string>>({});
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
  const filtered = useMemo(() => clips.filter((clip) => matchesReviewFilter(clip, filter)), [clips, filter]);
  const activeTargets = useMemo(() => targets.filter((target) => publishPlatforms.includes(target.platform)), [targets]);
  const approved = clips.filter((clip) => clip.status === "approved").length;
  const scheduledCount = clips.filter((clip) => clip.status === "scheduled" || clip.status === "ready_to_publish").length;
  const readyPlatforms = credentials ? Object.values(credentials.platforms).filter((item) => item.ready).length : 0;
  const command = productionCommand(generateConfig);
  const selectedCaptionDraft = selected ? captionDrafts[selected.id] ?? (selected.captions || []).map((caption) => caption.text).filter(Boolean).join("\n") : "";
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
  }

  async function approveClip(id: string) {
    setBusy(true);
    try {
      await apiPost("approve", {candidate_id: id});
      setClips((items) => items.map((clip) => (clip.id === id ? {...clip, status: "approved"} : clip)));
      setStatus("Clip approved");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  }

  async function holdClip(id: string) {
    setBusy(true);
    try {
      await apiPost("hold", {candidate_id: id});
      setStatus("Clip held for manual review");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Hold failed");
    } finally {
      setBusy(false);
    }
  }

  async function rejectClip(id: string) {
    setBusy(true);
    try {
      await apiPost("reject", {candidate_id: id});
      setStatus("Clip rejected");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Reject failed");
    } finally {
      setBusy(false);
    }
  }

  async function updateAutonomyMode(mode: string) {
    if (!autonomy) return;
    setBusy(true);
    try {
      const next = await apiPost<AutonomySettings>("autonomy-settings", {...autonomy, autonomy_mode: mode});
      setAutonomy(next);
      setStatus(`Autonomy mode set to ${mode}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Autonomy update failed");
    } finally {
      setBusy(false);
    }
  }

  async function startGeneration() {
    setBusy(true);
    setStatus("Generation job queued...");
    try {
      const job = await apiPost<GenerationJob>("generation-jobs", {
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
      });
      setJobs((items) => [job, ...items.filter((item) => item.id !== job.id)]);
      setStatus("Generation running in background");
      window.setTimeout(() => void refreshAll(), 1600);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Generation failed");
    } finally {
      setBusy(false);
    }
  }

  async function scheduleNext(id: string) {
    setBusy(true);
    try {
      await apiPost("schedule-next", {candidate_id: id, platforms: publishSelection});
      setStatus("Clip scheduled in next open slot");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Schedule failed");
    } finally {
      setBusy(false);
    }
  }

  async function updateSchedulePlatforms(scheduleId: string, platforms: string[]) {
    setBusy(true);
    try {
      await apiPost("schedule-platforms", {schedule_id: scheduleId, platforms});
      setStatus("Publish targets updated");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Platform update failed");
    } finally {
      setBusy(false);
    }
  }

  function togglePublishSelection(platform: string) {
    setPublishSelection((current) => {
      if (current.includes(platform)) {
        const next = current.filter((item) => item !== platform);
        return next.length ? next : current;
      }
      return [...current, platform];
    });
  }

  async function unscheduleClip(id: string) {
    setBusy(true);
    try {
      await apiPost("unschedule", {candidate_id: id});
      setStatus("Clip returned to approved queue");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unschedule failed");
    } finally {
      setBusy(false);
    }
  }

  async function deleteClip(id: string) {
    const ok = window.confirm("Delete this clip and local artifacts?");
    if (!ok) return;
    setBusy(true);
    try {
      await apiPost("delete-candidate", {candidate_id: id, delete_artifacts: true});
      setClips((items) => items.filter((clip) => clip.id !== id));
      if (selectedId === id) setSelectedId("");
      setStatus("Clip deleted");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  async function clearQueue() {
    const ok = window.confirm("Delete all clips and local artifacts from the review queue?");
    if (!ok) return;
    setBusy(true);
    try {
      await apiPost("clear-review", {confirm: "DELETE", delete_artifacts: true});
      setClips([]);
      setSelectedId("");
      setStatus("Queue cleared");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Clear failed");
    } finally {
      setBusy(false);
    }
  }

  async function publishSelectedPlatform(platform: string, dryRun: boolean) {
    if (!selected) return;
    setBusy(true);
    try {
      await apiPost("publish-live", {candidate_id: selected.id, platform, dry_run: dryRun});
      setStatus(dryRun ? `${platformLabel(platform)} dry-run ready` : `${platformLabel(platform)} publish requested`);
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Publish failed");
    } finally {
      setBusy(false);
    }
  }

  async function testConnection(platform: string) {
    setBusy(true);
    try {
      await apiPost("connection-test", {platform});
      setStatus(`${platformLabel(platform)} connected`);
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Connection check failed");
    } finally {
      setBusy(false);
    }
  }

  async function startOauthConnect(platform: string) {
    setBusy(true);
    try {
      const result = await apiPost<{platform: string; auth_url: string}>("oauth-start", {platform});
      const popup = window.open(result.auth_url, "_blank", "width=560,height=760,noopener,noreferrer");
      if (!popup) {
        setStatus("Popup blocked. Allow popups, then click Connect again.");
        return;
      }
      setStatus(`Continue OAuth in popup for ${platformLabel(platform)}...`);
      const timer = window.setInterval(() => {
        if (popup.closed) {
          window.clearInterval(timer);
          void refreshAll();
          setStatus(`${platformLabel(platform)} OAuth finished. Refreshing status...`);
        }
      }, 800);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "OAuth start failed");
    } finally {
      setBusy(false);
    }
  }

  async function disconnectPlatform(platform: string) {
    const ok = window.confirm(`Disconnect ${platformLabel(platform)} from this workspace?`);
    if (!ok) return;
    setBusy(true);
    try {
      await apiPost("connection-disconnect", {platform});
      setStatus(`${platformLabel(platform)} disconnected`);
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Disconnect failed");
    } finally {
      setBusy(false);
    }
  }

  async function publishDueNow(dryRun = false) {
    setBusy(true);
    setStatus(dryRun ? "Checking due publish queue..." : "Publishing due schedule...");
    try {
      const result = await apiPost<{count: number; processed?: unknown[]}>("publish-due", {limit: 5, dry_run: dryRun});
      setStatus(`${dryRun ? "Checked" : "Processed"} ${result.count || 0} due publish item(s)`);
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Publish due failed");
    } finally {
      setBusy(false);
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
    setBusy(true);
    try {
      await apiPost("caption-corrections", {candidate_id: id, captions});
      setStatus("Caption edits saved. Re-render this clip to update the video.");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Caption save failed");
    } finally {
      setBusy(false);
    }
  }

  async function rerenderClip(id: string) {
    setBusy(true);
    setRerendering((items) => ({...items, [id]: {status: "running", message: "Queued for re-render", progress: 2}}));
    setStatus("Re-rendering selected clip...");
    try {
      const job = await apiPost<RerenderJob>("rerender", {
        candidate_id: id,
        renderer: "remotion",
        quality: "production",
        style: generateConfig.brandTemplate || defaultTemplate,
      });
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
    } finally {
      setBusy(false);
    }
  }

  function setSelectedCaptionDraft(value: string) {
    if (!selected) return;
    setCaptionDrafts((items) => ({...items, [selected.id]: value}));
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshAll();
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

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
              <button onClick={() => copyText(command, "Production command copied")} className="inline-flex h-11 min-w-0 items-center justify-center gap-2 overflow-hidden rounded-full bg-cyan px-4 text-sm font-semibold text-ink hover:bg-cyan/90 sm:px-5">
                <Copy className="h-4 w-4 shrink-0" />
                <span className="hidden sm:inline">Copy command</span>
                <span className="sm:hidden">Copy</span>
              </button>
              <div className="min-w-0 truncate text-left text-xs text-cyan sm:min-w-[150px] sm:text-right">{status}</div>
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
              credentials={credentials}
              schedule={schedule}
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
              busy={busy}
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
              reviewFilters={reviewFilters}
              setFilter={setFilter}
              setSelectedId={setSelectedId}
              captionDraft={selectedCaptionDraft}
              setCaptionDraft={setSelectedCaptionDraft}
              statusTone={statusTone}
              formatDeadline={formatDeadline}
              primaryReviewAction={primaryReviewAction}
              onApprove={approveClip}
              onSchedule={scheduleNext}
              onHold={holdClip}
              onReject={rejectClip}
              onDelete={deleteClip}
              onClear={clearQueue}
              onSaveCaptions={saveCaptionCorrections}
              onRerender={rerenderClip}
            />
          )}

          {section === "calendar" && (
            <CalendarSection
              schedule={schedule}
              approved={clips.filter((clip) => clip.status === "approved")}
              targets={activeTargets}
              selectedPlatforms={publishSelection}
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
              selected={selected}
              attempts={publishAttempts}
              selectedPlatforms={publishSelection}
              onTogglePlatform={togglePublishSelection}
              onTestConnection={testConnection}
              onStartOauth={startOauthConnect}
              onDisconnect={disconnectPlatform}
              onPublishPlatform={publishSelectedPlatform}
            />
          )}

          {section === "brand" && (
            <BrandSection
              style={style}
              templates={templates}
              autonomy={autonomy}
              command={command}
              defaultTemplate={defaultTemplate}
              onCopy={() => copyText(command, "Production command copied")}
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

function DashboardSection({
  clips,
  selected,
  credentials,
  schedule,
  onSection,
  onApprove,
  onPublish,
}: {
  clips: ClipCandidate[];
  selected?: ClipCandidate;
  credentials: CredentialStatus | null;
  schedule: ScheduledPost[];
  onSection: (section: Section) => void;
  onApprove: (id: string) => void;
  onPublish: () => void;
}) {
  const top = clips.slice(0, 4);
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
            {top.length ? top.map((clip) => <CompactClip key={clip.id} clip={clip} onApprove={onApprove} />) : <EmptyState text="No clips yet. Start with Generate to produce a new batch." />}
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
                <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${statusTone(item.status)}`}>{item.status}</span>
              </div>
            )) : <EmptyState text="No scheduled clips yet. Approve a clip, then schedule the next slot." />}
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
  busy,
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
  busy: boolean;
  setConfig: (value: GenerateConfig) => void;
  command: string;
  onGenerate: () => void;
  onCopy: () => void;
}) {
  const latest = jobs[0];
  const update = (patch: Partial<GenerateConfig>) => setConfig({...config, ...patch});
  const presetOptions = durationPresets.length ? durationPresets : [{id: "auto", label: "Auto (0-3 min)", detail: "20-180s", range_label: "0-3 min", best_for: "General use", min_ms: 20_000, target_ms: 90_000, max_ms: 180_000, intent: "Automatic duration"}];
  const genreOptions = genres.length ? genres : [
    {id: "kajian", label: "Kajian", description: "Religious teaching and reflection."},
    {id: "spiritual_reflection", label: "Spiritual reflection", description: "Heart-softening clips."},
    {id: "advice", label: "Advice", description: "Practical reminders."},
  ];
  const toggleGenre = (id: string) => {
    const next = config.genres.includes(id) ? config.genres.filter((item) => item !== id) : [...config.genres, id];
    update({genres: next.length ? next : [id]});
  };
  return (
    <section className="grid gap-5 2xl:grid-cols-[.85fr_1.15fr]">
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <h3 className="text-xl font-semibold text-white">Generate production batch</h3>
        <p className="mt-2 text-sm leading-6 text-zinc-400">Run a local-first production job from the dashboard, or copy the exact terminal command.</p>
        <div className="mt-6 grid gap-4">
          <label className="grid gap-2 text-sm font-medium text-zinc-300">
            YouTube source
            <input value={config.sourceUrl} onChange={(event) => update({sourceUrl: event.target.value})} className="h-12 rounded-2xl border border-white/[0.08] bg-canvas-deep px-4 text-sm text-zinc-300 outline-none focus:border-cyan/[0.30]" />
          </label>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="grid gap-2 text-sm font-medium text-zinc-300">
              Clip count
              <select value={config.count} onChange={(event) => update({count: Number(event.target.value)})} className="h-12 rounded-2xl border border-white/[0.08] bg-canvas-deep px-4 outline-none">
                {[1, 2, 3, 5, 8, 10].map((value) => <option key={value} value={value}>{value} clips</option>)}
              </select>
            </label>
          </div>
          <div className="grid gap-2">
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
                className="h-12 rounded-2xl border border-cyan/[0.35] bg-canvas-deep px-4 text-sm font-semibold text-white outline-none shadow-glow"
              >
                {presetOptions.map((preset) => (
                  <option key={preset.id} value={preset.id}>{preset.label}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="grid gap-2">
            <div>
              <p className="text-sm font-medium text-zinc-300">Genres</p>
              <p className="mt-1 text-xs text-zinc-500">Used by curation and scoring for this batch only.</p>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {genreOptions.map((genre) => {
                const active = config.genres.includes(genre.id);
                return (
                  <button
                    key={genre.id}
                    type="button"
                    onClick={() => toggleGenre(genre.id)}
                    className={`rounded-[18px] border px-4 py-3 text-left transition ${active ? "border-cyan bg-teal/[0.14] text-white" : "border-white/[0.08] bg-canvas-deep text-zinc-400 hover:border-white/[0.16] hover:text-white"}`}
                  >
                    <span className="text-sm font-semibold">{genre.label}</span>
                    <span className="mt-1 block text-xs leading-5 text-zinc-500">{genre.description}</span>
                  </button>
                );
              })}
            </div>
          </div>
          <label className="grid gap-2 text-sm font-medium text-zinc-300">
            Brand template
            <select value={config.brandTemplate} onChange={(event) => update({brandTemplate: event.target.value})} className="h-12 rounded-2xl border border-white/[0.08] bg-canvas-deep px-4 outline-none">
              {(templates.length ? templates : [{id: defaultTemplate, label: "Nourbit Opus Style", path: defaultTemplate}]).map((template) => (
                <option key={template.id} value={template.path}>{template.label}</option>
              ))}
            </select>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <SelectTile label="Renderer" value={config.renderer} options={["remotion", "ffmpeg"]} onChange={(value) => update({renderer: value})} />
            <SelectTile label="Caption" value={config.captionSource} options={["whisper", "hybrid", "youtube"]} onChange={(value) => update({captionSource: value})} />
            <SelectTile label="Speech language" value={config.speechLanguage} options={["id", "ar", "en", "ms"]} onChange={(value) => update({speechLanguage: value})} />
            <SelectTile label="Transcript" value={config.transcriptLanguages} options={["id,en", "id", "en,id", "ar,id", "ms,id"]} onChange={(value) => update({transcriptLanguages: value})} />
            <SelectTile label="LLM" value={config.llmProvider} options={["deepseek", "openai", "groq", "none"]} onChange={(value) => update({llmProvider: value})} />
            <SelectTile label="Quality" value={config.quality} options={["production", "draft"]} onChange={(value) => update({quality: value})} />
          </div>
          <button disabled={busy || !config.sourceUrl.trim()} onClick={onGenerate} className="mt-2 inline-flex h-12 items-center justify-center gap-2 rounded-full bg-cyan px-5 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
            Generate batch
          </button>
        </div>
      </div>
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-xl font-semibold text-white">Local run command</h3>
          <button onClick={onCopy} className="inline-flex rounded-full bg-cyan px-4 py-2 text-sm font-semibold text-ink"><Copy className="mr-2 h-4 w-4" /> Copy</button>
        </div>
        <pre className="max-h-[520px] overflow-auto rounded-[24px] border border-white/[0.08] bg-canvas-deep p-5 text-xs leading-6 text-zinc-300">{command}</pre>
        <div className="mt-4 rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
          <div className="mb-3 flex items-center justify-between">
            <h4 className="font-semibold text-white">Latest job</h4>
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusTone(latest?.status || "empty")}`}>{latest?.status || "No job"}</span>
          </div>
          {latest ? (
            <div className="grid gap-3">
              <div className="h-2 overflow-hidden rounded-full bg-surface-strong">
                <div className="h-full rounded-full bg-cyan transition-all" style={{width: `${Math.max(4, Math.min(100, latest.progress || 0))}%`}} />
              </div>
              <p className="text-xs text-zinc-400">{latest.progress || 0}% · {latest.count} clips · {latest.llm_provider}/{latest.caption_source}</p>
              <pre className="max-h-40 overflow-auto rounded-2xl bg-black/40 p-3 text-[11px] leading-5 text-zinc-400">{latest.error || latest.log_text || "Waiting for logs..."}</pre>
            </div>
          ) : (
            <p className="text-sm text-zinc-500">Start a batch to see live progress here.</p>
          )}
        </div>
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

  return (
    <section className="grid gap-5 xl:grid-cols-[1fr_420px]">
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-xl font-semibold text-white">Calendar queue</h3>
            <p className="mt-1 text-sm text-zinc-400">Scheduled publish queue for approved clips. Default cadence is 2 posts per day at 09:00 and 19:30 WIB.</p>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <button onClick={onDryRunDue} className="rounded-full border border-white/[0.10] px-4 py-2 text-sm font-semibold text-zinc-300">Dry-run due</button>
            <button onClick={onPublishDue} className="rounded-full bg-cyan px-4 py-2 text-sm font-semibold text-ink">Publish due now</button>
          </div>
        </div>
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
                  <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusTone(item.status)}`}>{item.status}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-sm leading-5 text-zinc-400">{item.viral_reason}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {targets.map((target) => {
                    const platform = target.platform;
                    const enabled = item.platforms.includes(platform);
                    const result = item.platform_results?.[platform];
                    const platformStatus = result?.status || (item.status === "published" ? "published" : "pending");
                    return (
                      <button
                        key={platform}
                        onClick={() => toggleSchedulePlatform(item, platform)}
                        className={`rounded-full border px-2.5 py-1 text-left text-xs font-semibold transition ${
                          enabled ? statusTone(platformStatus) : "border-white/[0.08] bg-white/[0.03] text-zinc-500"
                        }`}
                      >
                        {platformLabel(platform)} · {enabled ? cleanPublishStatus(platformStatus) : "Off"}
                      </button>
                    );
                  })}
                </div>
                {item.last_error ? <p className="mt-2 line-clamp-2 text-xs text-danger">{item.last_error}</p> : null}
              </div>
              <button onClick={() => onUnschedule(item.candidate_id)} className="rounded-full border border-white/[0.10] px-4 py-2 text-sm font-semibold text-zinc-300">Unschedule</button>
            </div>
          )) : <EmptyState text="No scheduled posts yet. Approve clips first, then assign the next open slot." />}
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
              return (
                <button
                  key={target.platform}
                  onClick={() => onToggleDefaultPlatform(target.platform)}
                  className={`flex items-center justify-between rounded-2xl border px-3 py-2 text-left text-xs font-semibold transition ${
                    active ? "border-cyan/[0.45] bg-teal/[0.14] text-cyan" : "border-white/[0.08] bg-black/20 text-zinc-500"
                  }`}
                >
                  <span>{platformLabel(target.platform)}</span>
                  <span>{active ? "On" : "Off"}</span>
                </button>
              );
            })}
          </div>
        </div>
        <div className="mt-5 grid gap-3">
          {approved.length ? approved.map((clip) => (
            <div key={clip.id} className="rounded-[22px] border border-white/[0.08] bg-canvas-deep p-4">
              <p className="font-semibold text-white">{clip.title_hook}</p>
              <p className="mt-1 text-xs text-zinc-500">{formatTimestamp(clip.start_ms)} → {formatTimestamp(clip.end_ms)}</p>
              <button onClick={() => onSchedule(clip.id)} className="mt-4 h-10 w-full rounded-full bg-cyan text-sm font-semibold text-ink">Schedule next slot</button>
            </div>
          )) : <EmptyState text="No approved clips waiting for schedule." />}
        </div>
      </div>
    </section>
  );
}

function PublishSection({
  targets,
  credentials,
  selected,
  attempts,
  selectedPlatforms,
  onTogglePlatform,
  onTestConnection,
  onStartOauth,
  onDisconnect,
  onPublishPlatform,
}: {
  targets: PublishTarget[];
  credentials: CredentialStatus | null;
  selected?: ClipCandidate;
  attempts: PublishAttempt[];
  selectedPlatforms: string[];
  onTogglePlatform: (platform: string) => void;
  onTestConnection: (platform: string) => void;
  onStartOauth: (platform: string) => void;
  onDisconnect: (platform: string) => void;
  onPublishPlatform: (platform: string, dryRun: boolean) => void;
}) {
  const selectedAttempts = selected ? attempts.filter((attempt) => attempt.candidate_id === selected.id) : [];
  const latestByPlatform = new Map<string, PublishAttempt>();
  for (const attempt of selectedAttempts) {
    if (!latestByPlatform.has(attempt.platform)) latestByPlatform.set(attempt.platform, attempt);
  }
  const latestSelectedAttempts = targets
    .map((target) => latestByPlatform.get(target.platform))
    .filter((attempt): attempt is PublishAttempt => Boolean(attempt));
  return (
    <section className="grid gap-5 xl:grid-cols-[1fr_420px]">
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <h3 className="text-xl font-semibold text-white">Publish Center</h3>
            <p className="mt-1 text-sm text-zinc-400">Connect accounts, choose target platforms, and publish the selected approved clip.</p>
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
            const latest = latestByPlatform.get(target.platform) || attempts.find((attempt) => attempt.platform === target.platform);
            const recovery = publishActionHint(latest?.error);
            const supportsOauth = oauthPlatforms.has(target.platform);
            return (
              <div key={target.platform} className={`rounded-[24px] border p-4 transition ${selectedForPublish ? "border-cyan/[0.30] bg-teal/[0.08]" : "border-white/[0.08] bg-canvas-deep"}`}>
                <div className="flex items-center justify-between">
                  <div className="grid h-11 w-11 place-items-center rounded-2xl bg-cyan text-ink"><Send className="h-5 w-5" /></div>
                  <button
                    onClick={() => onTogglePlatform(target.platform)}
                    className={`rounded-full border px-3 py-1 text-xs font-semibold ${selectedForPublish ? "border-cyan/[0.40] bg-cyan text-ink" : "border-white/[0.10] bg-white/[0.04] text-zinc-400"}`}
                  >
                    {selectedForPublish ? "Target on" : "Target off"}
                  </button>
                </div>
                <h4 className="mt-4 font-semibold text-white">{platformLabel(target.platform)}</h4>
                <p className="mt-1 text-sm text-zinc-400">{target.account_label}</p>
                <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-zinc-400">
                  <SettingTile label="Connection" value={ready ? "Connected" : "Needs setup"} />
                  <SettingTile label="Daily cap" value={target.daily_cap} />
                </div>
                {!ready ? (
                  <div className="mt-3 rounded-2xl border border-warning/20 bg-warning/[0.08] p-3 text-xs leading-5 text-warning">
                    Missing: {(credential?.missing_keys || []).join(", ") || "credential"}. Connect via OAuth/token setup before live publishing.
                  </div>
                ) : null}
                <div className="mt-3 grid grid-cols-3 gap-2">
                  <button
                    onClick={() => onTestConnection(target.platform)}
                    className="h-9 rounded-full border border-white/[0.10] text-xs font-semibold text-zinc-300 hover:border-cyan/[0.35] hover:text-cyan"
                  >
                    Test
                  </button>
                  <button
                    onClick={() => (supportsOauth ? onStartOauth(target.platform) : onTestConnection(target.platform))}
                    className="h-9 rounded-full border border-cyan/[0.25] bg-cyan/[0.10] text-xs font-semibold text-cyan hover:bg-cyan/[0.16]"
                  >
                    {ready ? "Reconnect" : "Connect"}
                  </button>
                  <button
                    onClick={() => onDisconnect(target.platform)}
                    className="h-9 rounded-full border border-white/[0.10] text-xs font-semibold text-zinc-300 hover:border-danger/[0.35] hover:text-danger"
                  >
                    Disconnect
                  </button>
                </div>
                <div className="mt-4 rounded-2xl border border-white/[0.08] bg-black/20 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs uppercase tracking-wide text-zinc-500">Current attempt</span>
                    <span className={`rounded-full border px-2 py-1 text-xs font-semibold ${statusTone(latest?.status || "pending")}`}>{cleanPublishStatus(latest?.status)}</span>
                  </div>
                  {recovery ? <p className="mt-2 line-clamp-2 text-xs leading-5 text-danger">{recovery}</p> : null}
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <button disabled={!selected} onClick={() => onPublishPlatform(target.platform, true)} className="h-10 rounded-full border border-cyan/[0.30] text-xs font-semibold text-cyan disabled:cursor-not-allowed disabled:opacity-40">Dry-run</button>
                  <button disabled={!selected || !ready || !selectedForPublish} onClick={() => onPublishPlatform(target.platform, false)} className="h-10 rounded-full bg-cyan text-xs font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-40">Live</button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <h3 className="text-xl font-semibold text-white">Selected publish item</h3>
        <p className="mt-2 text-sm leading-6 text-zinc-400">{selected ? selected.title_hook : "Select or generate a clip before publishing."}</p>
        <div className="mt-5 grid gap-3">
          <div className="rounded-[22px] border border-cyan/[0.18] bg-teal/[0.08] p-4 text-sm leading-6 text-zinc-300">
            Scheduled items publish through the PM2 worker. Manual live buttons are for retrying one selected platform after you review the current state.
          </div>
          {latestSelectedAttempts.length ? latestSelectedAttempts.map((attempt) => (
            <div key={attempt.id} className="rounded-[18px] border border-white/[0.08] bg-canvas-deep p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-white">{platformLabel(attempt.platform)}</p>
                <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusTone(attempt.status)}`}>{cleanPublishStatus(attempt.status)}</span>
              </div>
              {attempt.error ? <p className="mt-2 text-xs leading-5 text-danger">{publishActionHint(attempt.error)}</p> : null}
            </div>
          )) : <EmptyState text="No publish attempts for this clip yet." />}
        </div>
      </div>
    </section>
  );
}

function CompactClip({clip, onApprove}: {clip: ClipCandidate; onApprove: (id: string) => void}) {
  return (
    <div className="grid gap-3 rounded-[18px] border border-white/[0.08] bg-surface-raised px-4 py-3 md:grid-cols-[minmax(0,1fr)_58px_auto] md:items-center">
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-white">{clip.title_hook}</p>
        <p className="mt-1 text-xs text-zinc-500">{formatTimestamp(clip.start_ms)} → {formatTimestamp(clip.end_ms)}</p>
      </div>
      <ScoreBubble value={clip.score?.overall_score} />
      <button onClick={() => onApprove(clip.id)} className="rounded-full border border-teal/[0.30] bg-teal/[0.10] px-3 py-2 text-xs font-semibold text-teal">Approve</button>
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
      <div>
        <AlertTriangle className="mx-auto mb-3 h-6 w-6 text-zinc-600" />
        {text}
      </div>
    </div>
  );
}
