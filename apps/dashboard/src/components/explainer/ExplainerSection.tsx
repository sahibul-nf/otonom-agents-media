"use client";

import {ChevronDown, Clapperboard, Film, Loader2, Sparkles, Wand2} from "lucide-react";
import {useEffect, useMemo, useState, type ReactNode} from "react";
import {type ActionUiState, type HyperframesTemplate} from "@/components/generate/types";
import {type ExplainerJob, type PathAJob, type TopicProposal} from "@/lib/media-api";

function friendlyStatus(status: string): string {
  const map: Record<string, string> = {
    starting: "Starting",
    triggering: "Starting",
    polling: "Generating",
    ingesting: "Preparing review",
    ready: "Ready to review",
    failed: "Failed",
    planned: "Planned",
    rendering: "Rendering",
    rendered: "Ready to review",
    queued: "Queued",
  };
  return map[status] || status.replaceAll("_", " ");
}

function ActivityCard({
  title,
  subtitle,
  status,
  statusClass,
  error,
  primaryLabel,
  onPrimary,
  secondary,
}: {
  title: string;
  subtitle?: string;
  status: string;
  statusClass: string;
  error?: string;
  primaryLabel?: string;
  onPrimary?: () => void;
  secondary?: ReactNode;
}) {
  return (
    <article className="rounded-3xl border border-white/[0.08] bg-black/25 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-medium text-white">{title}</p>
          {subtitle ? <p className="mt-1 text-xs text-zinc-500">{subtitle}</p> : null}
        </div>
        <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${statusClass}`}>
          {friendlyStatus(status)}
        </span>
      </div>
      {error ? <p className="mt-2 text-xs text-danger line-clamp-2">{error}</p> : null}
      <div className="mt-3 flex flex-wrap gap-2">
        {primaryLabel && onPrimary ? (
          <button
            type="button"
            onClick={onPrimary}
            className="inline-flex items-center gap-2 rounded-full border border-white/15 px-3 py-1.5 text-xs font-semibold text-zinc-200"
          >
            <Clapperboard className="h-3.5 w-3.5" />
            {primaryLabel}
          </button>
        ) : null}
        {secondary}
      </div>
    </article>
  );
}

export function ExplainerSection({
  jobs,
  pathAJobs,
  templates,
  actionState,
  statusTone,
  onCreate,
  onRun,
  onRefresh,
  onOpenReview,
  onIngest,
  onPathAGenerate,
  onProposeTopics,
  onGenerateNext,
  ingesting,
  pathAGenerating,
  proposingTopics,
  renderActionStatus,
  renderEmptyState,
}: {
  jobs: ExplainerJob[];
  pathAJobs: PathAJob[];
  templates: HyperframesTemplate[];
  actionState?: ActionUiState;
  statusTone: (status: string) => string;
  onCreate: (payload: {topic: string; sources: string; hyperframes_template: string}) => Promise<void>;
  onRun: (jobId: string, ffmpegOnly: boolean) => Promise<void>;
  onRefresh: () => void;
  onOpenReview: (candidateId?: string | null) => void;
  onIngest: (payload: {source: string; title: string; mode: "review_only" | "clip_batch"}) => Promise<void>;
  onPathAGenerate: (payload: {topic: string; title: string; script: string}) => Promise<void>;
  onProposeTopics: () => Promise<TopicProposal[]>;
  onGenerateNext: (candidateId?: string) => Promise<void>;
  ingesting?: boolean;
  pathAGenerating?: boolean;
  proposingTopics?: boolean;
  renderActionStatus: (state?: ActionUiState) => ReactNode;
  renderEmptyState: (title: string, text: string) => ReactNode;
}) {
  const [brief, setBrief] = useState("");
  const [extraNotes, setExtraNotes] = useState("");
  const [showNotes, setShowNotes] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [topic, setTopic] = useState("");
  const [sources, setSources] = useState("");
  const [templateId, setTemplateId] = useState("techtalk_intel_brief");
  const [ffmpegOnly, setFfmpegOnly] = useState(true);
  const [ingestSource, setIngestSource] = useState("");
  const [ingestTitle, setIngestTitle] = useState("");
  const [ingestMode, setIngestMode] = useState<"review_only" | "clip_batch">("review_only");
  const [proposals, setProposals] = useState<TopicProposal[]>([]);
  const [selectedProposalId, setSelectedProposalId] = useState("");
  const [proposeError, setProposeError] = useState("");

  const templateOptions = useMemo(() => {
    const preferred = templates.filter((item) =>
      ["techtalk_intel_brief", "velocity_business_promo", "blueprint_grid_paper", "byline_trust_quote"].includes(item.id),
    );
    return preferred.length ? preferred : templates.slice(0, 8);
  }, [templates]);
  const activeTemplateId = templates.some((item) => item.id === templateId) ? templateId : templateOptions[0]?.id || templateId;

  const rendering = jobs.some((job) => job.status === "rendering");
  const pathAActive = pathAJobs.some((job) =>
    ["starting", "triggering", "polling", "ingesting"].includes(job.status),
  );
  const busy = pathAGenerating || pathAActive || actionState?.status === "running";

  useEffect(() => {
    if (!rendering && !pathAActive) return;
    const timer = window.setInterval(() => onRefresh(), pathAActive ? 4000 : 2000);
    return () => window.clearInterval(timer);
  }, [rendering, pathAActive, onRefresh]);

  const activity = useMemo(() => {
    const pathItems = pathAJobs.map((job) => ({
      key: `patha-${job.job_id}`,
      kind: "generate" as const,
      title: job.title || job.topic || "Long video",
      subtitle: pathAActive && job === pathAJobs[0] ? "Working — you’ll get a Telegram ping when ready" : undefined,
      status: job.status,
      error: job.error,
      candidateId: job.candidate_ids?.[0],
      agentUrl: job.agent_url,
      updated: job.job_id,
    }));
    const explainerItems = jobs.map((job) => ({
      key: `expl-${job.job_id}`,
      kind: "plan" as const,
      title: job.topic || "Scene plan",
      subtitle: job.status === "planned" ? "Plan ready — finish when scenes are assembled" : undefined,
      status: job.status,
      error: job.error,
      candidateId: job.candidate_id || undefined,
      jobId: job.job_id,
      updated: job.job_id,
    }));
    return [...pathItems, ...explainerItems].slice(0, 12);
  }, [jobs, pathAJobs, pathAActive]);
  const currentActivity = activity.find((item) => ["starting", "triggering", "polling", "ingesting", "rendering", "queued"].includes(item.status)) || activity[0];
  const historyActivity = activity.filter((item) => item.key !== currentActivity?.key);

  function handleGenerate() {
    const topicText = brief.trim();
    if (!topicText) return;
    void onPathAGenerate({
      topic: topicText,
      title: topicText,
      script: extraNotes.trim(),
    });
  }

  async function handlePropose() {
    setProposeError("");
    try {
      const items = await onProposeTopics();
      setProposals(items);
      setSelectedProposalId(items[0]?.id || "");
      if (items[0]) {
        setBrief(items[0].title);
        if (items[0].storyboard) {
          setExtraNotes(items[0].storyboard);
          setShowNotes(true);
        }
      }
    } catch (error) {
      setProposeError(error instanceof Error ? error.message : "Propose topics failed");
      setProposals([]);
    }
  }

  function applyProposal(item: TopicProposal) {
    setSelectedProposalId(item.id);
    setBrief(item.title);
    if (item.storyboard) {
      setExtraNotes(item.storyboard);
      setShowNotes(true);
    }
  }

  return (
    <div className="mx-auto grid w-full max-w-4xl gap-5">
      <section className="rounded-[32px] border border-white/[0.08] bg-surface/40 p-6 backdrop-blur-md">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan">New long video</p>
            <p className="mt-2 text-sm leading-6 text-zinc-500">
              Type a topic, or leave it empty and use Generate next from niche signals. Finished videos wait in Review — nothing auto-publishes.
            </p>
          </div>
          <Film className="h-5 w-5 shrink-0 text-cyan" />
        </div>

        <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">What’s this about?</label>
        <textarea
          value={brief}
          onChange={(event) => setBrief(event.target.value)}
          rows={3}
          placeholder="e.g. Apakah membeli Bitcoin itu bodoh? Angle: risk vs FOMO for beginners — or leave blank for Generate next"
          className="mt-2 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none ring-cyan/30 placeholder:text-zinc-600 focus:ring-2"
        />

        <button
          type="button"
          onClick={() => setShowNotes((open) => !open)}
          className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-zinc-500 hover:text-zinc-300"
        >
          <ChevronDown className={`h-3.5 w-3.5 transition ${showNotes ? "rotate-180" : ""}`} />
          {showNotes ? "Hide talking points" : "Add talking points (optional)"}
        </button>
        {showNotes ? (
          <textarea
            value={extraNotes}
            onChange={(event) => setExtraNotes(event.target.value)}
            rows={3}
            placeholder="Key points, tone, must-mention facts…"
            className="mt-2 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none ring-cyan/30 placeholder:text-zinc-600 focus:ring-2"
          />
        ) : null}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={!brief.trim() || busy}
            onClick={handleGenerate}
            className="inline-flex items-center gap-2 rounded-full bg-cyan px-5 py-2.5 text-sm font-semibold text-black disabled:opacity-40"
          >
            {pathAGenerating || pathAActive ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
            Generate video
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void onGenerateNext(selectedProposalId || undefined)}
            className="inline-flex items-center gap-2 rounded-full border border-cyan/40 bg-cyan/10 px-5 py-2.5 text-sm font-semibold text-cyan disabled:opacity-40"
            title="Rank niche signals and start Path A with the top (or selected) proposal"
          >
            {pathAGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            Generate next
          </button>
          <button
            type="button"
            disabled={busy || proposingTopics}
            onClick={() => void handlePropose()}
            className="inline-flex items-center gap-2 rounded-full border border-white/15 px-4 py-2.5 text-sm font-semibold text-zinc-200 disabled:opacity-40"
          >
            {proposingTopics ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            Propose topics
          </button>
        </div>
        {proposeError ? <p className="mt-2 text-xs text-danger">{proposeError}</p> : null}
        {proposals.length ? (
          <ul className="mt-4 space-y-2">
            {proposals.map((item) => {
              const active = item.id === selectedProposalId;
              const topSource = item.sources?.[0];
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => applyProposal(item)}
                    className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                      active ? "border-cyan/50 bg-cyan/10" : "border-white/[0.08] bg-black/20 hover:border-white/20"
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <p className="text-sm font-medium text-white">{item.title}</p>
                      <span className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
                        {Math.round((item.confidence || 0) * 100)}% fit
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-zinc-500">{item.angle}</p>
                    {topSource?.url ? (
                      <p className="mt-1 truncate text-[11px] text-zinc-600">
                        {topSource.source || "source"}: {topSource.title || topSource.url}
                      </p>
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>
        ) : null}
        <div className="mt-3">{renderActionStatus(actionState)}</div>
        {currentActivity ? (
          <div className="mt-5 rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4" aria-live="polite">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Current video</p>
                <p className="mt-1 text-sm font-semibold text-white">{currentActivity.title}</p>
              </div>
              <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${statusTone(currentActivity.status)}`}>
                {friendlyStatus(currentActivity.status)}
              </span>
            </div>
            {["starting", "triggering", "polling", "ingesting", "rendering", "queued"].includes(currentActivity.status) ? (
              <div className="h-2 overflow-hidden rounded-full bg-white/[0.06]">
                <div className="h-full w-2/3 animate-pulse rounded-full bg-cyan motion-reduce:animate-none" />
              </div>
            ) : null}
            {currentActivity.error ? <p className="mt-3 text-xs text-danger">{currentActivity.error}</p> : null}
            <div className="mt-3 flex flex-wrap gap-2">
              {currentActivity.candidateId ? (
                <button type="button" onClick={() => onOpenReview(currentActivity.candidateId)} className="inline-flex items-center gap-2 rounded-full bg-cyan px-4 py-2 text-xs font-semibold text-ink">
                  <Clapperboard className="h-3.5 w-3.5" /> Open in Review
                </button>
              ) : null}
              {"agentUrl" in currentActivity && currentActivity.agentUrl ? (
                <a href={currentActivity.agentUrl} target="_blank" rel="noreferrer" className="rounded-full border border-white/[0.10] px-4 py-2 text-xs font-semibold text-zinc-300">View generation</a>
              ) : null}
            </div>
          </div>
        ) : null}

        <details
          className="mt-8 rounded-2xl border border-white/[0.08] bg-black/20 p-4"
          open={advancedOpen}
          onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}
        >
          <summary className="cursor-pointer list-none text-sm font-semibold text-zinc-200">
            Advanced
            <span className="ml-2 text-xs font-medium text-zinc-500">import existing video</span>
          </summary>

          <div className="mt-5 space-y-6 border-t border-white/[0.06] pt-5">
            <div>
              <p className="text-sm font-medium text-zinc-200">Import an existing video</p>
              <p className="mt-1 text-xs text-zinc-500">Paste a finished MP4 URL to send it straight to Review.</p>
              <input
                value={ingestSource}
                onChange={(event) => setIngestSource(event.target.value)}
                placeholder="https://…/video.mp4"
                className="mt-3 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none placeholder:text-zinc-600"
              />
              <input
                value={ingestTitle}
                onChange={(event) => setIngestTitle(event.target.value)}
                placeholder="Title (optional)"
                className="mt-2 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none placeholder:text-zinc-600"
              />
              <select
                value={ingestMode}
                onChange={(event) => setIngestMode(event.target.value as "review_only" | "clip_batch")}
                className="mt-2 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none"
              >
                <option value="review_only">Whole video → Review</option>
                <option value="clip_batch">Also cut short clips → Review</option>
              </select>
              <button
                type="button"
                disabled={!ingestSource.trim() || ingesting}
                onClick={() => void onIngest({source: ingestSource.trim(), title: ingestTitle.trim(), mode: ingestMode})}
                className="mt-3 inline-flex items-center gap-2 rounded-full border border-cyan/30 bg-cyan/10 px-4 py-2 text-sm font-semibold text-cyan disabled:opacity-40"
              >
                {ingesting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Clapperboard className="h-4 w-4" />}
                Send to Review
              </button>
            </div>

            <details className="rounded-2xl border border-white/[0.06] bg-black/25 p-4">
              <summary className="cursor-pointer list-none text-sm font-semibold text-zinc-400">
                Labs
                <span className="ml-2 text-xs font-medium text-zinc-600">local scene plan</span>
              </summary>
              <div className="mt-4 space-y-3 border-t border-white/[0.06] pt-4">
                <p className="text-xs text-zinc-500">Optional local plan for operators who assemble scenes offline. Most people can ignore this.</p>
                <input
                  value={topic}
                  onChange={(event) => setTopic(event.target.value)}
                  placeholder="Topic for scene plan"
                  className="w-full rounded-2xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none placeholder:text-zinc-600"
                />
                <textarea
                  value={sources}
                  onChange={(event) => setSources(event.target.value)}
                  rows={2}
                  placeholder="Sources (optional, one per line)"
                  className="w-full rounded-2xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none placeholder:text-zinc-600"
                />
                <select
                  value={activeTemplateId}
                  onChange={(event) => setTemplateId(event.target.value)}
                  className="w-full rounded-2xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none"
                >
                  {templateOptions.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.label}
                    </option>
                  ))}
                </select>
                <label className="flex items-center gap-3 text-sm text-zinc-300">
                  <input
                    type="checkbox"
                    checked={ffmpegOnly}
                    onChange={(event) => setFfmpegOnly(event.target.checked)}
                    className="h-4 w-4 rounded border-white/20 bg-black/40"
                  />
                  Prefer reliable local finish
                </label>
                <button
                  type="button"
                  disabled={!topic.trim() || actionState?.status === "running"}
                  onClick={() => void onCreate({topic: topic.trim(), sources, hyperframes_template: activeTemplateId})}
                  className="inline-flex items-center gap-2 rounded-full border border-white/15 px-4 py-2 text-sm font-semibold text-zinc-200 disabled:opacity-50"
                >
                  {actionState?.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  Create plan
                </button>
              </div>
            </details>
          </div>
        </details>
      </section>

      {historyActivity.length ? (
        <details className="rounded-[28px] border border-white/[0.08] bg-surface/50 p-5">
          <summary className="cursor-pointer list-none text-sm font-semibold text-zinc-300">
            Previous videos <span className="ml-2 text-xs font-medium text-zinc-600">{historyActivity.length}</span>
          </summary>
          <div className="mt-4 space-y-3 border-t border-white/[0.06] pt-4">
              {historyActivity.map((item) => (
                <ActivityCard
                  key={item.key}
                  title={item.title}
                  subtitle={item.subtitle}
                  status={item.status}
                  statusClass={statusTone(item.status)}
                  error={item.error}
                  primaryLabel={item.candidateId ? "Open in Review" : undefined}
                  onPrimary={item.candidateId ? () => onOpenReview(item.candidateId) : undefined}
                  secondary={
                    <>
                      {item.kind === "plan" && item.jobId ? (
                        <button
                          type="button"
                          disabled={item.status === "rendering"}
                          onClick={() => void onRun(item.jobId!, ffmpegOnly)}
                          className="inline-flex items-center gap-2 rounded-full border border-cyan/30 bg-cyan/10 px-3 py-1.5 text-xs font-semibold text-cyan disabled:opacity-50"
                        >
                          Finish plan
                        </button>
                      ) : null}
                      {"agentUrl" in item && item.agentUrl ? (
                        <a
                          href={item.agentUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-2 rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-zinc-400"
                        >
                          View run
                        </a>
                      ) : null}
                    </>
                  }
                />
              ))}
          </div>
        </details>
      ) : !currentActivity ? (
        renderEmptyState("Ready when you are", "Describe a topic above to create your first long video.")
      ) : null}
    </div>
  );
}
