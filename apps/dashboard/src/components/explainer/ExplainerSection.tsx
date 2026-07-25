"use client";

import {Clapperboard, Film, Loader2, RefreshCcw, Sparkles, Wand2} from "lucide-react";
import {useEffect, useMemo, useState, type ReactNode} from "react";
import {type ActionUiState, type HyperframesTemplate} from "@/components/generate/types";
import {type ExplainerJob, type PathAJob} from "@/lib/media-api";

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
  ingesting,
  pathAGenerating,
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
  ingesting?: boolean;
  pathAGenerating?: boolean;
  renderActionStatus: (state?: ActionUiState) => ReactNode;
  renderEmptyState: (title: string, text: string) => ReactNode;
}) {
  const [topic, setTopic] = useState("");
  const [sources, setSources] = useState("");
  const [templateId, setTemplateId] = useState("techtalk_intel_brief");
  const [ffmpegOnly, setFfmpegOnly] = useState(true);
  const [ingestSource, setIngestSource] = useState("");
  const [ingestTitle, setIngestTitle] = useState("");
  const [ingestMode, setIngestMode] = useState<"review_only" | "clip_batch">("review_only");
  const [pathATopic, setPathATopic] = useState("");
  const [pathATitle, setPathATitle] = useState("");
  const [pathAScript, setPathAScript] = useState("");

  const templateOptions = useMemo(() => {
    const preferred = templates.filter((item) =>
      ["techtalk_intel_brief", "velocity_business_promo", "blueprint_grid_paper", "byline_trust_quote"].includes(item.id),
    );
    return preferred.length ? preferred : templates.slice(0, 8);
  }, [templates]);

  useEffect(() => {
    if (!templates.some((item) => item.id === templateId) && templateOptions[0]) {
      setTemplateId(templateOptions[0].id);
    }
  }, [templateId, templateOptions, templates]);

  const rendering = jobs.some((job) => job.status === "rendering");
  const pathAActive = pathAJobs.some((job) =>
    ["starting", "triggering", "polling", "ingesting"].includes(job.status),
  );

  useEffect(() => {
    if (!rendering && !pathAActive) return;
    const timer = window.setInterval(() => onRefresh(), pathAActive ? 4000 : 2000);
    return () => window.clearInterval(timer);
  }, [rendering, pathAActive, onRefresh]);

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
      <section className="rounded-[32px] border border-white/[0.08] bg-surface/40 p-6 backdrop-blur-md">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold tracking-[-0.02em] text-white">
              Start <span className="font-editorial italic font-normal text-cyan">Explainer</span>
            </h3>
            <p className="mt-1 text-sm text-zinc-500">
              Path A: trigger Cursor (HeyGen) from a button, or paste a ready <code className="text-zinc-400">video_url</code>.
              Approve in Review — no auto-publish.
            </p>
          </div>
          <Film className="h-5 w-5 text-cyan" />
        </div>

        <div className="mb-8 rounded-2xl border border-cyan/20 bg-cyan/5 p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-cyan">
            <Wand2 className="h-4 w-4" />
            Generate via Cursor (Path A)
          </div>
          <p className="mb-3 text-xs text-zinc-500">
            Manual trigger → poll Cursor → local ingest → Telegram when Review is ready. No public URL required.
          </p>
          <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">Topic</label>
          <input
            value={pathATopic}
            onChange={(event) => setPathATopic(event.target.value)}
            placeholder="Apakah Membeli Bitcoin Itu Bodoh?"
            className="mt-2 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none ring-cyan/30 placeholder:text-zinc-600 focus:ring-2"
          />
          <label className="mt-4 block text-xs font-semibold uppercase tracking-wide text-zinc-500">Title (optional)</label>
          <input
            value={pathATitle}
            onChange={(event) => setPathATitle(event.target.value)}
            placeholder="Defaults to topic"
            className="mt-2 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none ring-cyan/30 placeholder:text-zinc-600 focus:ring-2"
          />
          <label className="mt-4 block text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Script / brief (optional)
          </label>
          <textarea
            value={pathAScript}
            onChange={(event) => setPathAScript(event.target.value)}
            rows={3}
            placeholder="Key talking points for Video Agent…"
            className="mt-2 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none ring-cyan/30 placeholder:text-zinc-600 focus:ring-2"
          />
          <button
            type="button"
            disabled={!pathATopic.trim() || pathAGenerating || pathAActive}
            onClick={() =>
              void onPathAGenerate({
                topic: pathATopic.trim(),
                title: pathATitle.trim(),
                script: pathAScript.trim(),
              })
            }
            className="mt-4 inline-flex items-center gap-2 rounded-2xl bg-cyan px-4 py-2.5 text-sm font-semibold text-black disabled:opacity-40"
          >
            {pathAGenerating || pathAActive ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
            Generate via Cursor
          </button>
          {pathAJobs[0] ? (
            <p className="mt-3 text-xs text-zinc-500">
              Latest: <span className="text-zinc-300">{pathAJobs[0].status}</span>
              {pathAJobs[0].error ? <span className="text-danger"> — {pathAJobs[0].error}</span> : null}
            </p>
          ) : null}
        </div>

        <div className="mb-8 rounded-2xl border border-white/[0.08] bg-black/20 p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-200">
            <Sparkles className="h-4 w-4 text-cyan" />
            Ingest HeyGen / long-form MP4
          </div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">Source URL or path</label>
          <input
            value={ingestSource}
            onChange={(event) => setIngestSource(event.target.value)}
            placeholder="https://files2.heygen.ai/.../video.mp4"
            className="mt-2 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none ring-cyan/30 placeholder:text-zinc-600 focus:ring-2"
          />
          <label className="mt-4 block text-xs font-semibold uppercase tracking-wide text-zinc-500">Title (optional)</label>
          <input
            value={ingestTitle}
            onChange={(event) => setIngestTitle(event.target.value)}
            placeholder="Apakah Membeli Bitcoin Itu Bodoh?"
            className="mt-2 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none ring-cyan/30 placeholder:text-zinc-600 focus:ring-2"
          />
          <label className="mt-4 block text-xs font-semibold uppercase tracking-wide text-zinc-500">Mode</label>
          <select
            value={ingestMode}
            onChange={(event) => setIngestMode(event.target.value as "review_only" | "clip_batch")}
            className="mt-2 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none"
          >
            <option value="review_only">review_only — whole video → Review (16:9)</option>
            <option value="clip_batch">clip_batch — Whisper + cut shorts → Review</option>
          </select>
          <button
            type="button"
            disabled={!ingestSource.trim() || ingesting}
            onClick={() => void onIngest({source: ingestSource.trim(), title: ingestTitle.trim(), mode: ingestMode})}
            className="mt-4 inline-flex items-center gap-2 rounded-2xl bg-cyan px-4 py-2.5 text-sm font-semibold text-black disabled:opacity-40"
          >
            {ingesting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Clapperboard className="h-4 w-4" />}
            Ingest to Review
          </button>
        </div>

        <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">Topic</label>
        <input
          value={topic}
          onChange={(event) => setTopic(event.target.value)}
          placeholder="Apa itu Bitcoin?"
          className="mt-2 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none ring-cyan/30 placeholder:text-zinc-600 focus:ring-2"
        />

        <label className="mt-5 block text-xs font-semibold uppercase tracking-wide text-zinc-500">
          Sources (optional, one per line)
        </label>
        <textarea
          value={sources}
          onChange={(event) => setSources(event.target.value)}
          rows={3}
          placeholder="https://…"
          className="mt-2 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none ring-cyan/30 placeholder:text-zinc-600 focus:ring-2"
        />

        <label className="mt-5 block text-xs font-semibold uppercase tracking-wide text-zinc-500">
          HyperFrames template
        </label>
        <select
          value={templateId}
          onChange={(event) => setTemplateId(event.target.value)}
          className="mt-2 w-full rounded-2xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none"
        >
          {templateOptions.map((template) => (
            <option key={template.id} value={template.id}>
              {template.label}
            </option>
          ))}
        </select>

        <label className="mt-5 flex items-center gap-3 text-sm text-zinc-300">
          <input
            type="checkbox"
            checked={ffmpegOnly}
            onChange={(event) => setFfmpegOnly(event.target.checked)}
            className="h-4 w-4 rounded border-white/20 bg-black/40"
          />
          Stitch with FFmpeg title cards (reliable; skip HyperFrames runtime)
        </label>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={!topic.trim() || actionState?.status === "running"}
            onClick={() => void onCreate({topic: topic.trim(), sources, hyperframes_template: templateId})}
            className="inline-flex items-center gap-2 rounded-full bg-cyan px-5 py-2.5 text-sm font-semibold text-black disabled:opacity-50"
          >
            {actionState?.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            Create job
          </button>
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex items-center gap-2 rounded-full border border-white/[0.12] px-4 py-2.5 text-sm text-zinc-300 hover:border-white/25"
          >
            <RefreshCcw className="h-4 w-4" />
            Refresh
          </button>
        </div>
        <div className="mt-4">{renderActionStatus(actionState)}</div>

        <div className="mt-8 rounded-3xl border border-white/[0.06] bg-black/20 p-4 text-sm text-zinc-400">
          <p className="font-medium text-zinc-200">Flywheel</p>
          <ol className="mt-2 list-decimal space-y-1 pl-5">
            <li>Create job → Cursor/HeyGen MCP imports avatar MP4s into fixtures.</li>
            <li>Stitch → candidate lands in Review → approve / schedule (existing publishers).</li>
            <li>After YouTube long-form publish, paste that URL in Create to clip shorts.</li>
          </ol>
        </div>
      </section>

      <section className="rounded-[32px] border border-white/[0.08] bg-surface/40 p-6 backdrop-blur-md">
        <div className="mb-5 flex items-center justify-between gap-3">
          <h3 className="text-lg font-semibold text-white">
            Path A <span className="font-editorial italic font-normal text-cyan">Cursor jobs</span>
          </h3>
          {pathAActive ? (
            <span className="inline-flex items-center gap-2 text-xs text-cyan">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Running…
            </span>
          ) : null}
        </div>
        {!pathAJobs.length
          ? renderEmptyState("No Path A jobs yet", "Use Generate via Cursor with a topic.")
          : (
            <div className="mb-8 space-y-3">
              {pathAJobs.map((job) => (
                <article key={job.job_id} className="rounded-3xl border border-white/[0.08] bg-black/25 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-white">{job.title || job.topic || job.job_id}</p>
                      <p className="mt-1 text-xs text-zinc-500">{job.job_id}</p>
                    </div>
                    <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${statusTone(job.status)}`}>
                      {job.status}
                    </span>
                  </div>
                  {job.error ? <p className="mt-2 text-xs text-danger">{job.error}</p> : null}
                  <div className="mt-3 flex flex-wrap gap-2">
                    {job.candidate_ids?.[0] ? (
                      <button
                        type="button"
                        onClick={() => onOpenReview(job.candidate_ids?.[0])}
                        className="inline-flex items-center gap-2 rounded-full border border-white/15 px-3 py-1.5 text-xs font-semibold text-zinc-200"
                      >
                        <Clapperboard className="h-3.5 w-3.5" />
                        Open in Review
                      </button>
                    ) : null}
                    {job.agent_url ? (
                      <a
                        href={job.agent_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-2 rounded-full border border-cyan/30 bg-cyan/10 px-3 py-1.5 text-xs font-semibold text-cyan"
                      >
                        Cursor agent
                      </a>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          )}

        <div className="mb-5 flex items-center justify-between gap-3">
          <h3 className="text-lg font-semibold text-white">
            Explainer <span className="font-editorial italic font-normal text-cyan">jobs</span>
          </h3>
          {rendering ? (
            <span className="inline-flex items-center gap-2 text-xs text-cyan">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Rendering…
            </span>
          ) : null}
        </div>

        {!jobs.length
          ? renderEmptyState("No Explainer jobs yet", "Create a topic plan to get a fixtures folder and scene breakdown.")
          : (
            <div className="space-y-3">
              {jobs.map((job) => (
                <article
                  key={job.job_id}
                  className="rounded-3xl border border-white/[0.08] bg-black/25 p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-white">{job.topic || job.job_id}</p>
                      <p className="mt-1 text-xs text-zinc-500">{job.job_id}</p>
                    </div>
                    <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${statusTone(job.status)}`}>
                      {job.status}
                    </span>
                  </div>
                  <p className="mt-3 text-xs text-zinc-500">
                    {job.scene_count ?? "?"} scenes · {job.avatar_scene_count ?? "?"} avatar · template {job.hyperframes_template || "techtalk"}
                  </p>
                  {job.error ? <p className="mt-2 text-xs text-danger">{job.error}</p> : null}
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={job.status === "rendering"}
                      onClick={() => void onRun(job.job_id, ffmpegOnly)}
                      className="inline-flex items-center gap-2 rounded-full border border-cyan/30 bg-cyan/10 px-3 py-1.5 text-xs font-semibold text-cyan disabled:opacity-50"
                    >
                      Stitch now
                    </button>
                    {job.candidate_id ? (
                      <button
                        type="button"
                        onClick={() => onOpenReview(job.candidate_id)}
                        className="inline-flex items-center gap-2 rounded-full border border-white/15 px-3 py-1.5 text-xs font-semibold text-zinc-200"
                      >
                        <Clapperboard className="h-3.5 w-3.5" />
                        Open in Review
                      </button>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          )}
      </section>
    </div>
  );
}
