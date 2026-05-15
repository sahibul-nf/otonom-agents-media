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
  MessageSquareText,
  Play,
  Plus,
  RadioTower,
  RefreshCcw,
  Rocket,
  Send,
  Settings,
  Sparkles,
  Trash2,
  Wand2,
} from "lucide-react";
import {useEffect, useMemo, useState} from "react";
import {
  apiGet,
  apiPath,
  apiPost,
  BrandTemplate,
  ClipCandidate,
  CredentialStatus,
  DurationPreset,
  formatDuration,
  formatTimestamp,
  GenerationJob,
  platformLabel,
  PublishTarget,
  ScheduledPost,
  scoreValue,
  StyleProfile,
} from "@/lib/media-api";

type Section = "dashboard" | "generate" | "review" | "calendar" | "publish" | "brand";

const defaultSourceUrl = "https://www.youtube.com/live/WSg7MGv4_Fs?si=i0BS4fhJx_WfQW3P";
const defaultTemplate = "profiles/nourbit_opus_style.json";

const nav = [
  {id: "dashboard", label: "Dashboard", icon: LayoutDashboard},
  {id: "generate", label: "Generate", icon: Wand2},
  {id: "review", label: "Review Studio", icon: Clapperboard},
  {id: "calendar", label: "Calendar", icon: CalendarDays},
  {id: "publish", label: "Publish Center", icon: Send},
  {id: "brand", label: "Brand Settings", icon: Settings},
] as const;

function statusTone(status: string) {
  if (["approved", "published", "ready", "rendered", "scheduled", "ready_to_publish", "completed"].includes(status)) return "text-teal border-teal/[0.30] bg-teal/[0.10]";
  if (["running", "queued"].includes(status)) return "text-cyan border-cyan/[0.30] bg-teal/[0.10]";
  if (["failed", "rejected"].includes(status)) return "text-danger border-danger/[0.30] bg-danger/[0.10]";
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

type GenerateConfig = {
  sourceUrl: string;
  count: number;
  clipLength: string;
  brandTemplate: string;
  renderer: string;
  quality: string;
  captionSource: string;
  asrModel: string;
  llmProvider: string;
};

const reviewFilters = [
  {id: "all", label: "All", statuses: []},
  {id: "needs_review", label: "Needs Review", statuses: ["draft", "rendered"]},
  {id: "approved", label: "Approved", statuses: ["approved"]},
  {id: "scheduled", label: "Scheduled", statuses: ["scheduled", "ready_to_publish"]},
  {id: "published", label: "Published", statuses: ["published"]},
] as const;

function matchesReviewFilter(clip: ClipCandidate, filter: string) {
  const group = reviewFilters.find((item) => item.id === filter);
  if (!group || group.id === "all") return true;
  return (group.statuses as readonly string[]).includes(clip.status);
}

function productionCommand(config: GenerateConfig) {
  return `cd "/Volumes/XPG SSD 1T/projects/otonom-agents-media/media-engine"
PYTHONPATH=. /tmp/media-engine-tools-py313/bin/python -m media_engine.cli premium-batch \\
  --youtube-url "${config.sourceUrl}" \\
  --count ${config.count} \\
  --clip-length-preset ${config.clipLength} \\
  --renderer ${config.renderer} \\
  --quality ${config.quality} \\
  --caption-source ${config.captionSource} \\
  --asr-model ${config.asrModel} \\
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
  const [jobs, setJobs] = useState<GenerationJob[]>([]);
  const [schedule, setSchedule] = useState<ScheduledPost[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [filter, setFilter] = useState("all");
  const [status, setStatus] = useState("Ready");
  const [busy, setBusy] = useState(false);
  const [generateConfig, setGenerateConfig] = useState<GenerateConfig>({
    sourceUrl: defaultSourceUrl,
    count: 5,
    clipLength: "deep_context",
    brandTemplate: defaultTemplate,
    renderer: "remotion",
    quality: "production",
    captionSource: "whisper",
    asrModel: "medium",
    llmProvider: "deepseek",
  });

  const selected = useMemo(() => clips.find((clip) => clip.id === selectedId) || clips[0], [clips, selectedId]);
  const filtered = useMemo(() => clips.filter((clip) => matchesReviewFilter(clip, filter)), [clips, filter]);
  const approved = clips.filter((clip) => clip.status === "approved").length;
  const scheduledCount = clips.filter((clip) => clip.status === "scheduled" || clip.status === "ready_to_publish").length;
  const readyPlatforms = credentials ? Object.values(credentials.platforms).filter((item) => item.ready).length : 0;
  const command = productionCommand(generateConfig);

  async function refreshAll() {
    setBusy(true);
    setStatus("Syncing media engine...");
    try {
      const [reviewRows, targetRows, credentialRows, styleRows, templateRows, durationRows, jobRows, scheduleRows] = await Promise.all([
        apiGet<ClipCandidate[]>("review"),
        apiGet<PublishTarget[]>("targets"),
        apiGet<CredentialStatus>("credentials"),
        apiGet<StyleProfile>("style"),
        apiGet<BrandTemplate[]>("brand-templates"),
        apiGet<DurationPreset[]>("duration-presets"),
        apiGet<GenerationJob[]>("generation-jobs"),
        apiGet<ScheduledPost[]>("schedule"),
      ]);
      setClips(reviewRows);
      setTargets(targetRows);
      setCredentials(credentialRows);
      setStyle(styleRows);
      setTemplates(templateRows);
      setDurationPresets(durationRows);
      setJobs(jobRows);
      setSchedule(scheduleRows);
      setSelectedId((current) => current || reviewRows[0]?.id || "");
      setStatus("Dashboard synced");
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

  async function startGeneration() {
    setBusy(true);
    setStatus("Generation job queued...");
    try {
      const job = await apiPost<GenerationJob>("generation-jobs", {
        source_url: generateConfig.sourceUrl,
        count: generateConfig.count,
        clip_length_preset: generateConfig.clipLength,
        brand_template: generateConfig.brandTemplate,
        renderer: generateConfig.renderer,
        quality: generateConfig.quality,
        caption_source: generateConfig.captionSource,
        asr_model: generateConfig.asrModel,
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
      await apiPost("schedule-next", {candidate_id: id});
      setStatus("Clip scheduled in next open slot");
      await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Schedule failed");
    } finally {
      setBusy(false);
    }
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

  async function publishTelegram(dryRun: boolean) {
    if (!selected) return;
    setBusy(true);
    try {
      await apiPost("publish-live", {candidate_id: selected.id, platform: "telegram_channel", dry_run: dryRun});
      setStatus(dryRun ? "Telegram dry-run ready" : "Telegram published");
      if (!dryRun) await refreshAll();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Publish failed");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshAll();
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!jobs.some((job) => job.status === "queued" || job.status === "running")) return;
    const timer = window.setInterval(() => {
      void refreshAll();
    }, 3500);
    return () => window.clearInterval(timer);
  }, [jobs]);

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
              <span className="text-sm font-semibold">Nourbit Plan</span>
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
                <p className="text-sm font-semibold text-white">Nourbit Media</p>
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
            <MetricCard label="Scheduled" value={scheduledCount} detail="Queue-only publish slots" icon={CalendarDays} />
          </section>

          {section === "dashboard" && (
            <DashboardSection
              clips={clips}
              selected={selected}
              credentials={credentials}
              schedule={schedule}
              onSection={setSection}
              onApprove={approveClip}
              onPublish={() => publishTelegram(true)}
            />
          )}

          {section === "generate" && (
            <GenerateSection
              config={generateConfig}
              templates={templates}
              durationPresets={durationPresets}
              jobs={jobs}
              busy={busy}
              setConfig={setGenerateConfig}
              command={command}
              onGenerate={startGeneration}
              onCopy={() => copyText(command, "Production command copied")}
            />
          )}

          {section === "review" && (
            <ReviewSection
              clips={filtered}
              selected={selected}
              filter={filter}
              setFilter={setFilter}
              setSelectedId={setSelectedId}
              onApprove={approveClip}
              onSchedule={scheduleNext}
              onDelete={deleteClip}
              onClear={clearQueue}
            />
          )}

          {section === "calendar" && (
            <CalendarSection schedule={schedule} approved={clips.filter((clip) => clip.status === "approved")} onSchedule={scheduleNext} onUnschedule={unscheduleClip} />
          )}

          {section === "publish" && (
            <PublishSection targets={targets} credentials={credentials} selected={selected} onDryRun={() => publishTelegram(true)} onLive={() => publishTelegram(false)} />
          )}

          {section === "brand" && <BrandSection style={style} templates={templates} command={command} onCopy={() => copyText(command, "Production command copied")} />}
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
            <p className="mt-1 text-sm text-zinc-400">A compact operating room for Nourbit’s next batch.</p>
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
        <PreviewPanel clip={selected} />
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
  jobs: GenerationJob[];
  busy: boolean;
  setConfig: (value: GenerateConfig) => void;
  command: string;
  onGenerate: () => void;
  onCopy: () => void;
}) {
  const latest = jobs[0];
  const update = (patch: Partial<GenerateConfig>) => setConfig({...config, ...patch});
  const presetOptions = durationPresets.length ? durationPresets : [{id: "deep_context", label: "Deep Context", detail: "Podcasts, lectures", range_label: "45-120s", best_for: "Podcasts, lectures"}];
  return (
    <section className="grid gap-5 xl:grid-cols-[.85fr_1.15fr]">
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
            <div>
              <p className="text-sm font-medium text-zinc-300">Clip length strategy</p>
              <p className="mt-1 text-xs text-zinc-500">Choose by content pacing. The engine still trims exact start/end adaptively.</p>
            </div>
            <div className="grid gap-2">
              {presetOptions.map((preset) => {
                const active = config.clipLength === preset.id;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => update({clipLength: preset.id})}
                    className={`rounded-[18px] border px-4 py-3 text-left transition ${active ? "border-cyan bg-teal/[0.14] shadow-glow" : "border-white/[0.08] bg-canvas-deep hover:border-white/[0.16]"}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-white">{preset.label}</span>
                      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${active ? "bg-cyan text-ink" : "bg-surface text-zinc-400"}`}>{preset.range_label}</span>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-zinc-400">{preset.best_for || preset.detail}</p>
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

function ReviewSection({
  clips,
  selected,
  filter,
  setFilter,
  setSelectedId,
  onApprove,
  onSchedule,
  onDelete,
  onClear,
}: {
  clips: ClipCandidate[];
  selected?: ClipCandidate;
  filter: string;
  setFilter: (value: string) => void;
  setSelectedId: (id: string) => void;
  onApprove: (id: string) => void;
  onSchedule: (id: string) => void;
  onDelete: (id: string) => void;
  onClear: () => void;
}) {
  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_430px]">
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <div className="mb-5 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h3 className="text-xl font-semibold text-white">Review Studio</h3>
            <p className="mt-1 text-sm text-zinc-400">Ranked clip candidates with scoring, QA, cost, and destructive controls.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {reviewFilters.map((item) => (
              <button key={item.id} onClick={() => setFilter(item.id)} className={`rounded-full px-4 py-2 text-sm font-medium ${filter === item.id ? "bg-cyan text-ink" : "border border-white/[0.10] text-zinc-300"}`}>{item.label}</button>
            ))}
            <button onClick={onClear} className="inline-flex items-center gap-2 rounded-full border border-danger/[0.30] bg-danger/[0.10] px-4 py-2 text-sm font-semibold text-danger"><Trash2 className="h-4 w-4" /> Clear</button>
          </div>
        </div>

        <div className="grid gap-2">
          {clips.length ? clips.map((clip) => (
            <article
              key={clip.id}
              role="button"
              tabIndex={0}
              onClick={() => setSelectedId(clip.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setSelectedId(clip.id);
                }
              }}
              className={`grid cursor-pointer gap-3 rounded-[22px] border p-4 text-left transition lg:grid-cols-[88px_minmax(0,1fr)_minmax(280px,auto)] lg:items-center ${selected?.id === clip.id ? "border-cyan bg-teal/[0.10]" : "border-white/[0.08] bg-canvas-deep hover:border-white/[0.16]"}`}
            >
              <div className="grid h-14 place-items-center rounded-2xl bg-surface-raised text-sm font-semibold text-cyan">{formatDuration(clip.render_quality?.duration_ms)}</div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="truncate text-base font-semibold text-white">{clip.title_hook}</h4>
                  <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${statusTone(clip.status)}`}>{clip.status}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-sm leading-5 text-zinc-400">{clip.viral_reason || "No curation reason yet."}</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-center lg:min-w-[280px]">
                <div className="grid grid-cols-3 gap-2">
                  <ScoreBubble label="Score" value={clip.score?.overall_score} />
                  <ScoreBubble label="QA" value={clip.render_quality?.quality_score} />
                  <MetricBubble label="Cost" value={`$${Number(clip.cost?.estimated_total || 0).toFixed(4)}`} />
                </div>
                <div className="flex justify-end gap-2">
                {clip.status === "approved" ? (
                  <button type="button" onClick={(event) => { event.stopPropagation(); onSchedule(clip.id); }} className="rounded-full border border-cyan/[0.30] bg-teal/[0.10] px-3 py-2 text-xs font-semibold text-cyan">Schedule</button>
                ) : (
                  <button type="button" onClick={(event) => { event.stopPropagation(); onApprove(clip.id); }} className="rounded-full border border-teal/[0.30] bg-teal/[0.10] px-3 py-2 text-xs font-semibold text-teal">Approve</button>
                )}
                <button type="button" onClick={(event) => { event.stopPropagation(); onDelete(clip.id); }} className="rounded-full border border-danger/[0.30] bg-danger/[0.10] px-3 py-2 text-danger"><Trash2 className="h-4 w-4" /></button>
                </div>
              </div>
            </article>
          )) : <EmptyState text="No clips in this queue. Generate a new batch or refresh the media engine." />}
        </div>
      </div>
      <div className="grid gap-5">
        <PreviewPanel clip={selected} />
        <InsightPanel clip={selected} />
      </div>
    </section>
  );
}

function CalendarSection({
  schedule,
  approved,
  onSchedule,
  onUnschedule,
}: {
  schedule: ScheduledPost[];
  approved: ClipCandidate[];
  onSchedule: (id: string) => void;
  onUnschedule: (id: string) => void;
}) {
  return (
    <section className="grid gap-5 xl:grid-cols-[1fr_420px]">
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-xl font-semibold text-white">Calendar queue</h3>
            <p className="mt-1 text-sm text-zinc-400">Queue-only schedule for Nourbit. Default cadence is 2 posts per day at 09:00 and 19:30 WIB.</p>
          </div>
          <span className="rounded-full border border-cyan/[0.30] bg-teal/[0.10] px-4 py-2 text-sm font-semibold text-cyan">Queue only</span>
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
              </div>
              <button onClick={() => onUnschedule(item.candidate_id)} className="rounded-full border border-white/[0.10] px-4 py-2 text-sm font-semibold text-zinc-300">Unschedule</button>
            </div>
          )) : <EmptyState text="No scheduled posts yet. Approve clips first, then assign the next open slot." />}
        </div>
      </div>
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <h3 className="text-lg font-semibold text-white">Approved clips</h3>
        <p className="mt-1 text-sm text-zinc-400">Add approved clips to the next available Nourbit slot.</p>
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

function PublishSection({targets, credentials, selected, onDryRun, onLive}: {targets: PublishTarget[]; credentials: CredentialStatus | null; selected?: ClipCandidate; onDryRun: () => void; onLive: () => void}) {
  return (
    <section className="grid gap-5 xl:grid-cols-[1fr_420px]">
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <h3 className="text-xl font-semibold text-white">Publish Center</h3>
        <p className="mt-1 text-sm text-zinc-400">Prepared for SaaS-style channel connection, but currently powered by local env credentials.</p>
        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {targets.map((target) => {
            const ready = credentials?.platforms[target.platform]?.ready;
            return (
              <div key={target.platform} className="rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
                <div className="flex items-center justify-between">
                  <div className="grid h-11 w-11 place-items-center rounded-2xl bg-cyan text-ink"><Send className="h-5 w-5" /></div>
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${ready ? "bg-teal/[0.10] text-teal" : "bg-warning/[0.10] text-warning"}`}>{ready ? "Connected" : "Needs token"}</span>
                </div>
                <h4 className="mt-4 font-semibold text-white">{platformLabel(target.platform)}</h4>
                <p className="mt-1 text-sm text-zinc-400">{target.account_label}</p>
                <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-zinc-400">
                  <SettingTile label="Mode" value={target.mode} />
                  <SettingTile label="Daily cap" value={target.daily_cap} />
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
          <button disabled={!selected} onClick={onDryRun} className="h-12 rounded-full border border-cyan/[0.30] bg-teal/[0.10] font-semibold text-cyan disabled:cursor-not-allowed disabled:opacity-40">Dry-run Telegram</button>
          <button disabled={!selected} onClick={onLive} className="h-12 rounded-full bg-cyan font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-40">Publish Telegram Live</button>
          <div className="rounded-[22px] border border-warning/20 bg-warning/[0.10] p-4 text-sm leading-6 text-warning">
            Live publish is enabled for Telegram first. Facebook, YouTube, and TikTok remain connector/dry-run surfaces until OAuth flows are productized.
          </div>
        </div>
      </div>
    </section>
  );
}

function BrandSection({style, templates, command, onCopy}: {style: StyleProfile | null; templates: BrandTemplate[]; command: string; onCopy: () => void}) {
  const caption = style?.caption || {};
  const layout = style?.layout || {};
  return (
    <section className="grid gap-5 xl:grid-cols-[1fr_420px]">
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <h3 className="text-xl font-semibold text-white">Nourbit brand system</h3>
        <p className="mt-1 text-sm text-zinc-400">Current Opus-inspired template settings loaded from the Python engine.</p>
        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <SettingTile label="Aspect ratio" value={String(layout.aspect_ratio || "9:16")} />
          <SettingTile label="Layout mode" value={String(layout.layout_mode || "fill")} />
          <SettingTile label="Caption preset" value={String(caption.preset || "premium")} />
          <SettingTile label="Font" value={`${caption.font_family || "Sora"} ${caption.font_size || 32}px`} />
          <SettingTile label="Highlight" value={String(caption.highlight_word_color || "#00ff45")} />
          <SettingTile label="Animation" value={String(caption.animation || "bounce")} />
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
      </div>
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-xl font-semibold text-white">Run command</h3>
          <button onClick={onCopy} className="rounded-full bg-cyan px-4 py-2 text-sm font-semibold text-ink">Copy</button>
        </div>
        <pre className="max-h-[420px] overflow-auto rounded-[24px] border border-white/[0.08] bg-canvas-deep p-5 text-xs leading-6 text-zinc-300">{command}</pre>
      </div>
    </section>
  );
}

function PreviewPanel({clip}: {clip?: ClipCandidate}) {
  const output = clip?.output_path || clip?.render_quality?.output_path;
  return (
    <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">9:16 Preview</h3>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusTone(clip?.status || "empty")}`}>{clip?.status || "No clip"}</span>
      </div>
      <div className="mx-auto grid aspect-[9/16] max-h-[620px] w-full max-w-[350px] place-items-center overflow-hidden rounded-[26px] border border-white/[0.10] bg-black">
        {output ? (
          <video controls playsInline preload="metadata" className="h-full w-full object-contain" src={apiPath(`artifact?path=${encodeURIComponent(output)}`)} />
        ) : (
          <div className="grid place-items-center gap-3 px-8 text-center text-sm text-zinc-500">
            <Play className="h-10 w-10 text-zinc-700" />
            No rendered clip selected.
          </div>
        )}
      </div>
    </div>
  );
}

function InsightPanel({clip}: {clip?: ClipCandidate}) {
  return (
    <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
      <h3 className="text-lg font-semibold text-white">Clip intelligence</h3>
      {clip ? (
        <div className="mt-4 grid gap-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-zinc-500">Hook</p>
            <p className="mt-1 text-lg font-semibold text-white">{clip.title_hook}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-zinc-500">Why it works</p>
            <p className="mt-1 text-sm leading-6 text-zinc-300">{clip.viral_reason || "No reason recorded."}</p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <SettingTile label="Start" value={formatTimestamp(clip.start_ms)} />
            <SettingTile label="End" value={formatTimestamp(clip.end_ms)} />
            <SettingTile label="Caption" value={clip.caption_source || "-"} />
            <SettingTile label="Coverage" value={`${Math.round((clip.render_quality?.caption_coverage || 0) * 100)}%`} />
          </div>
          <div className="rounded-[22px] border border-white/[0.08] bg-canvas-deep p-4">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-white"><MessageSquareText className="h-4 w-4 text-cyan" /> Post copy</div>
            <p className="whitespace-pre-wrap text-sm leading-6 text-zinc-400">{clip.post_caption || "Post caption will appear after render metadata is available."}</p>
          </div>
        </div>
      ) : <EmptyState text="Select a clip to inspect curation, captions, and publish copy." />}
    </div>
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

function MetricBubble({value, label}: {value: string; label: string}) {
  return (
    <div className="grid justify-items-center gap-1">
      <span className="grid h-11 min-w-14 place-items-center rounded-full border border-white/[0.10] px-3 text-xs font-semibold text-zinc-300">{value}</span>
      <span className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</span>
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
