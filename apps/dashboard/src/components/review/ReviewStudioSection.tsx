"use client";

import {AlertTriangle, CheckCircle2, Clock3, ListFilter, Loader2, MessageSquareText, MoreHorizontal, RefreshCcw, Trash2} from "lucide-react";
import {useEffect, useRef, useState} from "react";
import {ClipCandidate, formatDuration, formatTimestamp, scoreValue} from "@/lib/media-api";
import {PreviewPanel} from "@/components/review/PreviewPanel";

type ReviewFilter = {
  id: string;
  label: string;
  hint: string;
  statuses: readonly string[];
};

type RerenderState = {status: "running" | "done" | "failed"; message: string; progress?: number};
type ActionUiState = {status: "running" | "done" | "failed"; message: string};
type ReadinessItem = {
  id: "hook" | "timing" | "captions" | "qa" | "post";
  label: string;
  status: "ready" | "review" | "blocked";
  tab: DetailTab;
  note: string;
};

type Props = {
  clips: ClipCandidate[];
  selected?: ClipCandidate;
  rerendering: Record<string, RerenderState>;
  filter: string;
  showPublished: boolean;
  reviewFilters: readonly ReviewFilter[];
  actionStates: Record<string, ActionUiState>;
  setFilter: (value: string) => void;
  setShowPublished: (value: boolean) => void;
  setSelectedId: (id: string) => void;
  captionDraft: string;
  setCaptionDraft: (value: string) => void;
  statusTone: (status: string) => string;
  formatDeadline: (value?: string) => string;
  primaryReviewAction: (clip: ClipCandidate) => string;
  onApprove: (id: string) => void;
  onSchedule: (id: string) => void;
  onHold: (id: string) => void;
  onDelete: (id: string) => void;
  onClear: () => void;
  onSaveCaptions: (id: string, draft: string) => void;
  onRerender: (id: string) => void;
  onRefreshMetadata: (id: string, mode?: "smart" | "local") => void;
  onSaveBoundary: (id: string, startMs: number, endMs: number, rerenderAfter: boolean) => void;
};

type DetailTab = "metadata" | "timing" | "captions" | "post" | "quality";

function clipWarnings(clip?: ClipCandidate) {
  if (!clip) return [];
  const warnings: {label: string; tone: "warning" | "danger" | "info"}[] = [];
  const coverage = clip.render_quality?.caption_coverage;
  const confidence = clip.score?.caption_confidence || clip.score?.asr_confidence;
  if (clip.status === "needs_caption_fix") warnings.push({label: "Caption repair needed", tone: "warning"});
  if (typeof coverage === "number" && coverage < 0.9) warnings.push({label: `Coverage ${Math.round(coverage * 100)}%`, tone: "warning"});
  if ((clip.render_quality?.caption_overlap_count || 0) > 0) warnings.push({label: "Caption overlap", tone: "danger"});
  if (typeof confidence === "number" && confidence < 82) warnings.push({label: `ASR ${Math.round(confidence)}`, tone: "warning"});
  if (clip.caption_corrections?.manual_edit) warnings.push({label: "Manual caption edit", tone: "info"});
  return warnings;
}

function canRunPrimaryAction(clip: ClipCandidate) {
  return ["draft", "rendered", "needs_caption_fix", "held", "pending_auto_schedule", "approved"].includes(clip.status);
}

function clipReadinessItems(clip: ClipCandidate): ReadinessItem[] {
  const duration = clip.end_ms - clip.start_ms;
  const coverage = clip.render_quality?.caption_coverage;
  const confidence = clip.score?.caption_confidence || clip.score?.asr_confidence;
  const qualityScore = clip.render_quality?.quality_score;
  const captionBlocked = clip.status === "needs_caption_fix" || (clip.render_quality?.caption_overlap_count || 0) > 0;
  return [
    {
      id: "hook",
      label: "Hook",
      status: clip.title_hook && (clip.hook_subtitle || clip.viral_reason) ? "ready" : "review",
      tab: "metadata",
      note: clip.title_hook ? "Title and reason present" : "Needs stronger metadata",
    },
    {
      id: "timing",
      label: "Timing",
      status: duration >= 20_000 && duration <= 180_000 ? "ready" : "blocked",
      tab: "timing",
      note: `${formatDuration(duration)} clip span`,
    },
    {
      id: "captions",
      label: "Captions",
      status: captionBlocked ? "blocked" : typeof coverage === "number" && coverage < 0.9 || typeof confidence === "number" && confidence < 82 ? "review" : "ready",
      tab: "captions",
      note: captionBlocked ? "Repair captions before approval" : typeof coverage === "number" ? `${Math.round(coverage * 100)}% coverage` : "Caption timing available",
    },
    {
      id: "qa",
      label: "QA",
      status: typeof qualityScore === "number" && qualityScore < 85 ? "review" : "ready",
      tab: "quality",
      note: typeof qualityScore === "number" ? `${Math.round(qualityScore)} quality score` : "Review preview manually",
    },
    {
      id: "post",
      label: "Post copy",
      status: clip.post_caption ? "ready" : "review",
      tab: "post",
      note: clip.post_caption ? "Caption copy ready" : "Missing publish copy",
    },
  ];
}

function firstReadinessBlock(items: ReadinessItem[]) {
  return items.find((item) => item.status === "blocked") || items.find((item) => item.status === "review");
}

export function ReviewStudioSection({
  clips,
  selected,
  rerendering,
  filter,
  showPublished,
  reviewFilters,
  actionStates,
  setFilter,
  setShowPublished,
  setSelectedId,
  captionDraft,
  setCaptionDraft,
  statusTone,
  formatDeadline,
  primaryReviewAction,
  onApprove,
  onSchedule,
  onHold,
  onDelete,
  onClear,
  onSaveCaptions,
  onRerender,
  onRefreshMetadata,
  onSaveBoundary,
}: Props) {
  const [queueMenuOpen, setQueueMenuOpen] = useState(false);
  const [rowMenuId, setRowMenuId] = useState("");
  const [detailTab, setDetailTab] = useState<DetailTab>("metadata");
  const queueMenuRef = useRef<HTMLDivElement>(null);
  const rowMenuRef = useRef<HTMLDivElement>(null);
  const activeFilter = reviewFilters.find((item) => item.id === filter) || reviewFilters[0];
  const clearState = actionStates["queue:clear"];

  function formatStatus(status?: string) {
    const labels: Record<string, string> = {
      approved: "Approved",
      completed: "Completed",
      draft: "Draft",
      failed: "Failed",
      held: "Held",
      needs_caption_fix: "Caption fix",
      pending_auto_schedule: "Auto queue",
      published: "Published",
      ready_to_publish: "Ready to publish",
      rendered: "Rendered",
      running: "Running",
      scheduled: "Scheduled",
    };
    return labels[status || ""] || String(status || "Unknown").replaceAll("_", " ");
  }

  useEffect(() => {
    function closeMenus(event: MouseEvent) {
      const target = event.target as Node;
      if (queueMenuRef.current && !queueMenuRef.current.contains(target)) {
        setQueueMenuOpen(false);
      }
      if (rowMenuRef.current && !rowMenuRef.current.contains(target)) {
        setRowMenuId("");
      }
    }
    document.addEventListener("mousedown", closeMenus);
    return () => document.removeEventListener("mousedown", closeMenus);
  }, []);

  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(520px,1fr)_minmax(560px,0.9fr)] xl:items-start">
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <div className="mb-5 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h3 className="text-xl font-semibold text-white">Review Studio</h3>
            <p className="mt-1 text-sm text-zinc-400">Ranked clip candidates with scoring, QA, cost, and destructive controls.</p>
          </div>
          <div ref={queueMenuRef} className="relative">
            <button
              type="button"
              onClick={() => setQueueMenuOpen((open) => !open)}
              className="inline-flex h-12 min-w-[230px] items-center justify-between gap-3 rounded-full border border-cyan/[0.28] bg-canvas-deep px-4 text-left text-sm font-semibold text-white shadow-glow"
              aria-expanded={queueMenuOpen}
              aria-label={`Queue filter: ${activeFilter.label}`}
            >
              <span className="inline-flex min-w-0 items-center gap-2">
                <ListFilter className="h-4 w-4 shrink-0 text-cyan" />
                <span className="text-xs uppercase tracking-wide text-zinc-500">Queue</span>
                <span className="truncate">{activeFilter.label}</span>
              </span>
              <MoreHorizontal className="h-4 w-4 shrink-0 text-zinc-500" />
            </button>
            {queueMenuOpen ? (
              <div className="absolute right-0 top-14 z-30 w-[320px] overflow-hidden rounded-[24px] border border-white/[0.10] bg-canvas-deep p-2 shadow-glow">
                {reviewFilters.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      setFilter(item.id);
                      setQueueMenuOpen(false);
                    }}
                    className={`grid w-full gap-1 rounded-[18px] px-4 py-3 text-left transition ${filter === item.id ? "bg-teal/[0.16] text-cyan" : "text-zinc-300 hover:bg-white/[0.05] hover:text-white"}`}
                  >
                    <span className="text-sm font-semibold">{item.label}</span>
                    <span className="text-xs leading-5 text-zinc-500">{item.hint}</span>
                  </button>
                ))}
                <div className="mt-2 border-t border-white/[0.08] px-2 py-3">
                  <label className="flex cursor-pointer items-center justify-between gap-4 rounded-[18px] px-2 py-2 text-sm font-semibold text-zinc-200">
                    <span>Show published</span>
                    <span className={`relative h-6 w-11 rounded-full border transition ${showPublished ? "border-cyan bg-cyan" : "border-white/[0.12] bg-white/[0.06]"}`}>
                      <input
                        type="checkbox"
                        checked={showPublished}
                        onChange={(event) => setShowPublished(event.target.checked)}
                        className="sr-only"
                      />
                      <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition ${showPublished ? "left-5" : "left-0.5"}`} />
                    </span>
                  </label>
                </div>
                <div className="mt-2 border-t border-white/[0.08] pt-2">
                  <button
                    type="button"
                    disabled={clearState?.status === "running"}
                    onClick={() => {
                      setQueueMenuOpen(false);
                      onClear();
                    }}
                    className="inline-flex w-full items-center gap-2 rounded-[18px] px-4 py-3 text-sm font-semibold text-danger hover:bg-danger/[0.10] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {clearState?.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                    {clearState?.status === "running" ? "Clearing..." : "Clear queue"}
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <div className="grid gap-2">
          {clips.length ? clips.map((clip) => {
            const renderState = rerendering[clip.id];
            const primaryKey = clip.status === "approved" ? `clip:${clip.id}:schedule` : `clip:${clip.id}:approve`;
            const primaryState = actionStates[primaryKey];
            const rowAction = primaryState || actionStates[`clip:${clip.id}:hold`] || actionStates[`clip:${clip.id}:delete`] || actionStates[`clip:${clip.id}:rerender`];
            const rowBusy = rowAction?.status === "running" || renderState?.status === "running";
            const warnings = clipWarnings(clip);
            return (
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
                className={`relative grid cursor-pointer grid-cols-[88px_minmax(0,1fr)] gap-3 overflow-visible rounded-[22px] border p-4 text-left transition 2xl:grid-cols-[88px_minmax(0,1fr)_minmax(220px,auto)] 2xl:items-center ${selected?.id === clip.id ? "z-10 border-cyan bg-teal/[0.10]" : "border-white/[0.08] bg-canvas-deep hover:border-white/[0.16]"} ${rowMenuId === clip.id ? "z-20" : ""}`}
              >
                <div className="grid h-14 place-items-center rounded-2xl bg-surface-raised text-sm font-semibold text-cyan">{formatDuration(clip.render_quality?.duration_ms)}</div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h4 className="truncate text-base font-semibold text-white">{clip.title_hook}</h4>
                    {clip.status !== "draft" ? <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${statusTone(clip.status)}`}>{formatStatus(clip.status)}</span> : null}
                    {renderState ? <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${statusTone(renderState.status === "running" ? "running" : renderState.status === "failed" ? "failed" : "completed")}`}>{renderState.status === "running" ? "Rendering" : formatStatus(renderState.status)}</span> : null}
                    {rowAction && renderState?.status !== "running" ? <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${statusTone(rowAction.status === "running" ? "running" : rowAction.status)}`}>{rowAction.message}</span> : null}
                  </div>
                  <p className="mt-1 line-clamp-2 text-sm leading-5 text-zinc-400">{rowAction?.status === "running" ? rowAction.message : renderState?.message || clip.viral_reason || "No curation reason yet."}</p>
                  {warnings.length ? (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {warnings.slice(0, 3).map((warning) => (
                        <span
                          key={warning.label}
                          className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${
                            warning.tone === "danger"
                              ? "border-danger/[0.24] bg-danger/[0.08] text-danger"
                              : warning.tone === "warning"
                                ? "border-warning/[0.24] bg-warning/[0.08] text-warning"
                                : "border-cyan/[0.22] bg-teal/[0.08] text-cyan"
                          }`}
                        >
                          {warning.label}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {renderState?.status === "running" ? (
                    <div className="mt-3 rounded-[18px] border border-cyan/[0.18] bg-teal/[0.08] px-3 py-2.5">
                      <div className="mb-2 flex items-center justify-between gap-3">
                        <p className="truncate text-xs font-medium text-cyan">{renderState.message}</p>
                        <p className="shrink-0 text-xs font-semibold text-white">{Math.max(0, Math.min(100, renderState.progress ?? 0))}%</p>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-white/[0.06]">
                        <div
                          className="h-full rounded-full bg-cyan transition-all duration-500"
                          style={{width: `${Math.max(6, Math.min(100, renderState.progress ?? 0))}%`}}
                        />
                      </div>
                    </div>
                  ) : null}
                  {renderState?.status === "failed" ? (
                    <p className="mt-3 text-xs font-medium text-danger">Re-render stopped before completion. You can retry from the row menu.</p>
                  ) : null}
                </div>
                <div className="col-span-2 grid gap-3 sm:grid-cols-[auto_1fr] sm:items-center 2xl:col-span-1 2xl:min-w-[220px] 2xl:grid-cols-[1fr_auto]">
                  <div className="grid w-fit grid-cols-2 gap-2">
                    <ScoreBubble label="Score" value={clip.score?.overall_score} />
                    <ScoreBubble label="QA" value={clip.render_quality?.quality_score} />
                  </div>
                  <div className="relative flex justify-start gap-2 overflow-visible sm:justify-end">
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        if (!canRunPrimaryAction(clip)) return;
                        if (clip.status === "approved") onSchedule(clip.id);
                        else onApprove(clip.id);
                      }}
                      disabled={rowBusy || !canRunPrimaryAction(clip)}
                      className="rounded-full border border-teal/[0.30] bg-teal/[0.10] px-3 py-2 text-xs font-semibold text-teal disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {primaryState?.status === "running" ? (
                        <span className="inline-flex items-center gap-1.5"><Loader2 className="h-3 w-3 animate-spin" /> {clip.status === "approved" ? "Scheduling..." : "Approving..."}</span>
                      ) : primaryReviewAction(clip)}
                    </button>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        setRowMenuId(rowMenuId === clip.id ? "" : clip.id);
                      }}
                      disabled={rowBusy}
                      className="rounded-full border border-white/[0.10] bg-surface px-3 py-2 text-zinc-300 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                      aria-label={`More actions for ${clip.title_hook}`}
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </button>
                    {rowMenuId === clip.id ? (
                      <div
                        ref={rowMenuRef}
                        onClick={(event) => event.stopPropagation()}
                        className="absolute right-0 top-11 z-20 w-44 overflow-hidden rounded-[18px] border border-white/[0.10] bg-canvas-deep p-1 shadow-glow"
                      >
                        {clip.status === "pending_auto_schedule" ? (
                          <button type="button" onClick={() => { setRowMenuId(""); onHold(clip.id); }} className="w-full rounded-2xl px-3 py-2 text-left text-sm font-medium text-warning hover:bg-warning/[0.10]">Hold</button>
                        ) : null}
                        <button type="button" onClick={() => { setRowMenuId(""); onRefreshMetadata(clip.id, "smart"); }} className="flex w-full items-center gap-2 rounded-2xl px-3 py-2 text-left text-sm font-medium text-zinc-300 hover:bg-white/[0.05] hover:text-white"><RefreshCcw className="h-3.5 w-3.5" /> Refresh metadata</button>
                        <button type="button" onClick={() => { setRowMenuId(""); setSelectedId(clip.id); setDetailTab("timing"); }} className="flex w-full items-center gap-2 rounded-2xl px-3 py-2 text-left text-sm font-medium text-zinc-300 hover:bg-white/[0.05] hover:text-white"><Clock3 className="h-3.5 w-3.5" /> Edit timing</button>
                        <button type="button" onClick={() => { setRowMenuId(""); onRerender(clip.id); }} className="w-full rounded-2xl px-3 py-2 text-left text-sm font-medium text-zinc-300 hover:bg-white/[0.05] hover:text-white">Re-render</button>
                        {clip.status === "scheduled" || clip.status === "ready_to_publish" ? (
                          <button type="button" disabled className="w-full rounded-2xl px-3 py-2 text-left text-sm font-medium text-zinc-500">Managed in Calendar</button>
                        ) : null}
                        {clip.status === "published" ? (
                          <button type="button" disabled className="w-full rounded-2xl px-3 py-2 text-left text-sm font-medium text-zinc-500">Already published</button>
                        ) : null}
                        <button type="button" onClick={() => { setRowMenuId(""); onDelete(clip.id); }} className="w-full rounded-2xl px-3 py-2 text-left text-sm font-medium text-danger hover:bg-danger/[0.10]">Delete</button>
                      </div>
                    ) : null}
                  </div>
                </div>
                {clip.status === "pending_auto_schedule" && clip.review_deadline_at ? (
                  <div className="2xl:col-start-2 2xl:col-span-2 rounded-2xl border border-teal/[0.20] bg-teal/[0.08] px-3 py-2 text-xs font-medium text-teal">
                    {formatDeadline(clip.review_deadline_at)}
                  </div>
                ) : null}
              </article>
            );
          }) : <EmptyState text="No clips in this queue. Generate a new batch or refresh the media engine." />}
        </div>
      </div>
      <ReviewDetailPane
        clip={selected}
        statusTone={statusTone}
        activeTab={detailTab}
        setActiveTab={setDetailTab}
        captionDraft={captionDraft}
        setCaptionDraft={setCaptionDraft}
        actionStates={actionStates}
        onSaveCaptions={onSaveCaptions}
        onRerender={onRerender}
        onRefreshMetadata={onRefreshMetadata}
        onSaveBoundary={onSaveBoundary}
        primaryReviewAction={primaryReviewAction}
        onApprove={onApprove}
        onSchedule={onSchedule}
      />
    </section>
  );
}

function ReviewDetailPane({
  clip,
  statusTone,
  activeTab,
  setActiveTab,
  captionDraft,
  setCaptionDraft,
  actionStates,
  onSaveCaptions,
  onRerender,
  onRefreshMetadata,
  onSaveBoundary,
  primaryReviewAction,
  onApprove,
  onSchedule,
}: {
  clip?: ClipCandidate;
  statusTone: (status: string) => string;
  activeTab: DetailTab;
  setActiveTab: (tab: DetailTab) => void;
  captionDraft: string;
  setCaptionDraft: (value: string) => void;
  actionStates: Record<string, ActionUiState>;
  onSaveCaptions: (id: string, draft: string) => void;
  onRerender: (id: string) => void;
  onRefreshMetadata: (id: string, mode?: "smart" | "local") => void;
  onSaveBoundary: (id: string, startMs: number, endMs: number, rerenderAfter: boolean) => void;
  primaryReviewAction: (clip: ClipCandidate) => string;
  onApprove: (id: string) => void;
  onSchedule: (id: string) => void;
}) {
  return (
    <aside className="rounded-[28px] border border-white/[0.08] bg-surface p-5 xl:sticky xl:top-5">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-xl font-semibold text-white">Clip Inspector</h3>
          <p className="mt-1 text-sm text-zinc-400">Preview first, edit only what matters for this selected clip.</p>
        </div>
        {clip ? <span className={`w-fit rounded-full border px-3 py-1 text-xs font-semibold ${statusTone(clip.status)}`}>{clip.status.replaceAll("_", " ")}</span> : null}
      </div>
      {clip ? (
        <div className="grid gap-5">
          <div className="grid gap-5 2xl:grid-cols-[minmax(280px,360px)_minmax(0,1fr)] 2xl:items-start">
            <div className="rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Preview</span>
                <span className="text-xs font-medium tabular-nums text-cyan">{formatTimestamp(clip.start_ms)} → {formatTimestamp(clip.end_ms)}</span>
              </div>
              <PreviewPanel clip={clip} statusTone={statusTone} embedded hideHeader />
            </div>
            <ClipSummary
              clip={clip}
              setActiveTab={setActiveTab}
              actionStates={actionStates}
              primaryReviewAction={primaryReviewAction}
              onApprove={onApprove}
              onSchedule={onSchedule}
              onRefreshMetadata={onRefreshMetadata}
              onRerender={onRerender}
            />
          </div>
          <InsightPanel
            clip={clip}
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            captionDraft={captionDraft}
            setCaptionDraft={setCaptionDraft}
            actionStates={actionStates}
            onSaveCaptions={onSaveCaptions}
            onRerender={onRerender}
            onRefreshMetadata={onRefreshMetadata}
            onSaveBoundary={onSaveBoundary}
          />
        </div>
      ) : <EmptyState text="Select a clip to inspect preview, metadata, timing, captions, and publish copy." />}
    </aside>
  );
}

function ClipSummary({
  clip,
  setActiveTab,
  actionStates,
  primaryReviewAction,
  onApprove,
  onSchedule,
  onRefreshMetadata,
  onRerender,
}: {
  clip: ClipCandidate;
  setActiveTab: (tab: DetailTab) => void;
  actionStates: Record<string, ActionUiState>;
  primaryReviewAction: (clip: ClipCandidate) => string;
  onApprove: (id: string) => void;
  onSchedule: (id: string) => void;
  onRefreshMetadata: (id: string, mode?: "smart" | "local") => void;
  onRerender: (id: string) => void;
}) {
  const primaryKey = clip.status === "approved" ? `clip:${clip.id}:schedule` : `clip:${clip.id}:approve`;
  const primaryState = actionStates[primaryKey];
  const metadataState = actionStates[`clip:${clip.id}:metadata`];
  const rerenderState = actionStates[`clip:${clip.id}:rerender`];
  const busy = primaryState?.status === "running" || metadataState?.status === "running" || rerenderState?.status === "running";
  const readiness = clipReadinessItems(clip);
  const nextIssue = firstReadinessBlock(readiness);
  const shouldRepairBeforeApprove = nextIssue && nextIssue.status === "blocked" && clip.status !== "approved";
  const primaryLabel = primaryState?.status === "running"
    ? "Working..."
    : shouldRepairBeforeApprove
      ? nextIssue.id === "captions" ? "Fix captions first" : `Review ${nextIssue.label.toLowerCase()}`
      : canRunPrimaryAction(clip) ? primaryReviewAction(clip) : clip.status === "published" ? "Published" : "Managed";
  const primaryHint = clip.status === "approved"
    ? "Approved clips can be added to the publishing schedule."
    : shouldRepairBeforeApprove
      ? `${nextIssue.note}. Open the editor before approving this clip.`
    : canRunPrimaryAction(clip)
      ? nextIssue ? `${nextIssue.label} may need a final glance, but no blocker is detected.` : "This clip passes visible readiness checks."
      : "This clip is already managed by schedule or publish state.";

  return (
    <div className="grid gap-4 rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h4 className="text-xl font-semibold leading-tight text-white">{clip.title_hook}</h4>
          {clip.caption_corrections?.manual_edit ? <span className="rounded-full border border-cyan/[0.22] bg-teal/[0.08] px-2.5 py-1 text-xs font-semibold text-cyan">Manual edit</span> : null}
        </div>
        <p className="mt-2 text-sm leading-6 text-zinc-400">{clip.hook_subtitle || clip.viral_reason || "No clip description yet."}</p>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 2xl:grid-cols-2">
        <SettingTile label="Score" value={scoreValue(clip.score?.overall_score)} />
        <SettingTile label="QA" value={scoreValue(clip.render_quality?.quality_score)} />
        <SettingTile label="Duration" value={formatDuration(clip.render_quality?.duration_ms || clip.end_ms - clip.start_ms)} />
        <SettingTile label="Caption" value={clip.caption_source || "-"} />
      </div>

      <div className="grid gap-3 rounded-[20px] border border-white/[0.08] bg-black/20 p-3">
        <div>
          <div className="mb-2 flex items-center justify-between gap-3">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Readiness</div>
            <div className="text-xs font-medium text-zinc-500">{readiness.filter((item) => item.status === "ready").length}/{readiness.length} ready</div>
          </div>
          <div className="grid grid-cols-5 gap-1.5">
            {readiness.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setActiveTab(item.tab)}
                className={`grid h-12 place-items-center rounded-[14px] border text-[10px] font-semibold transition ${
                  item.status === "ready"
                    ? "border-teal/[0.24] bg-teal/[0.08] text-teal"
                    : item.status === "blocked"
                      ? "border-danger/[0.24] bg-danger/[0.08] text-danger"
                      : "border-warning/[0.24] bg-warning/[0.08] text-warning"
                }`}
                title={item.note}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Review decision</div>
          <p className="mt-1 text-xs leading-5 text-zinc-500">{primaryHint}</p>
        </div>
        <button
          type="button"
          disabled={busy || !canRunPrimaryAction(clip)}
          onClick={() => {
            if (!canRunPrimaryAction(clip)) return;
            if (shouldRepairBeforeApprove) {
              setActiveTab(nextIssue.tab);
              return;
            }
            if (clip.status === "approved") onSchedule(clip.id);
            else onApprove(clip.id);
          }}
          className="inline-flex h-11 items-center justify-center rounded-[16px] bg-cyan px-3 text-sm font-semibold text-ink transition hover:bg-cyan/90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {primaryLabel}
        </button>
        <div className="border-t border-white/[0.07] pt-3">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Repair tools</div>
          <div className="grid grid-cols-3 gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => onRefreshMetadata(clip.id, "smart")}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-[16px] border border-white/[0.10] px-3 text-xs font-semibold text-zinc-200 transition hover:border-cyan/[0.30] hover:text-cyan disabled:cursor-not-allowed disabled:opacity-40"
          >
            {metadataState?.status === "running" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCcw className="h-3.5 w-3.5" />}
            Metadata
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setActiveTab("timing");
            }}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-[16px] border border-white/[0.10] px-3 text-xs font-semibold text-zinc-200 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Clock3 className="h-3.5 w-3.5" />
            Timing
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onRerender(clip.id)}
            className="h-10 rounded-[16px] border border-white/[0.10] px-3 text-xs font-semibold text-zinc-200 transition hover:border-cyan/[0.30] hover:text-cyan disabled:cursor-not-allowed disabled:opacity-40"
          >
            {rerenderState?.status === "running" ? "Rendering..." : "Re-render"}
          </button>
          </div>
        </div>
      </div>

    </div>
  );
}

function parseTimecode(value: string) {
  const parts = value.trim().split(":").map((part) => Number(part));
  if (!parts.length || parts.some((part) => !Number.isFinite(part) || part < 0)) return null;
  let seconds = 0;
  if (parts.length === 3) seconds = parts[0] * 3600 + parts[1] * 60 + parts[2];
  else if (parts.length === 2) seconds = parts[0] * 60 + parts[1];
  else if (parts.length === 1) seconds = parts[0];
  else return null;
  return Math.round(seconds * 1000);
}

function boundaryValidation(startText: string, endText: string) {
  const startMs = parseTimecode(startText);
  const endMs = parseTimecode(endText);
  if (startMs === null || endMs === null) return {valid: false, message: "Use HH:MM:SS, MM:SS, or seconds.", startMs: 0, endMs: 0};
  if (endMs <= startMs) return {valid: false, message: "End time must be after start time.", startMs, endMs};
  const duration = endMs - startMs;
  if (duration < 20_000 || duration > 180_000) return {valid: false, message: "Duration must stay between 20 seconds and 3 minutes.", startMs, endMs};
  return {valid: true, message: `${formatDuration(duration)} duration`, startMs, endMs};
}

function InsightPanel({
  clip,
  activeTab,
  setActiveTab,
  captionDraft,
  setCaptionDraft,
  actionStates,
  onSaveCaptions,
  onRerender,
  onRefreshMetadata,
  onSaveBoundary,
}: {
  clip?: ClipCandidate;
  activeTab: DetailTab;
  setActiveTab: (tab: DetailTab) => void;
  captionDraft: string;
  setCaptionDraft: (value: string) => void;
  actionStates: Record<string, ActionUiState>;
  onSaveCaptions: (id: string, draft: string) => void;
  onRerender: (id: string) => void;
  onRefreshMetadata: (id: string, mode?: "smart" | "local") => void;
  onSaveBoundary: (id: string, startMs: number, endMs: number, rerenderAfter: boolean) => void;
}) {
  const tabs: {id: DetailTab; label: string}[] = [
    {id: "metadata", label: "Metadata"},
    {id: "timing", label: "Timing"},
    {id: "captions", label: "Captions"},
    {id: "post", label: "Post"},
    {id: "quality", label: "QA"},
  ];
  const tabGroups: {label: string; tabs: {id: DetailTab; label: string}[]}[] = [
    {label: "Content", tabs: tabs.filter((tab) => tab.id === "metadata" || tab.id === "post")},
    {label: "Edit", tabs: tabs.filter((tab) => tab.id === "timing" || tab.id === "captions")},
    {label: "Checks", tabs: tabs.filter((tab) => tab.id === "quality")},
  ];
  const captionCount = clip?.captions?.length || 0;
  const saveState = clip ? actionStates[`caption:${clip.id}:save`] : undefined;
  const rerenderState = clip ? actionStates[`clip:${clip.id}:rerender`] : undefined;
  const metadataState = clip ? actionStates[`clip:${clip.id}:metadata`] : undefined;
  const boundaryState = clip ? actionStates[`clip:${clip.id}:boundary`] : undefined;
  const actionBusy = saveState?.status === "running" || rerenderState?.status === "running" || metadataState?.status === "running" || boundaryState?.status === "running";
  const warnings = clipWarnings(clip);
  const activeTabLabel = tabs.find((tab) => tab.id === activeTab)?.label || "Metadata";
  return (
    <div className="rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
      <div className="mb-4 flex flex-col gap-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Editor</h3>
          <p className="mt-1 text-xs text-zinc-500">Fine-tune the selected clip without leaving review.</p>
        </div>
        <div>
          <div className="mb-2 flex items-center justify-between gap-3">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Editing {activeTabLabel}</span>
            <span className="hidden text-xs text-zinc-600 sm:inline">Switch only when you need a different repair surface.</span>
          </div>
          <div className="grid gap-2 rounded-[18px] border border-white/[0.08] bg-black/24 p-2 lg:grid-cols-[1fr_1fr_auto]">
            {tabGroups.map((group) => (
              <div key={group.label} className="grid gap-1">
                <div className="px-2 text-[10px] font-semibold uppercase tracking-wide text-zinc-600">{group.label}</div>
                <div className="flex gap-1">
                  {group.tabs.map((tab) => (
                    <button key={tab.id} type="button" onClick={() => setActiveTab(tab.id)} className={`h-9 shrink-0 rounded-full px-4 text-xs font-semibold transition ${activeTab === tab.id ? "bg-cyan text-ink shadow-[0_0_18px_rgba(108,226,238,0.18)]" : "text-zinc-400 hover:bg-white/[0.04] hover:text-white"}`}>
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      {clip ? (
        <div className="grid gap-4">
          {activeTab === "metadata" ? (
            <div className="grid gap-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-zinc-500">Hook</p>
                <p className="mt-1 text-lg font-semibold text-white">{clip.title_hook}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-zinc-500">Description</p>
                <p className="mt-1 text-sm leading-6 text-zinc-300">{clip.hook_subtitle || clip.viral_reason || "No reason recorded."}</p>
              </div>
              <button
                type="button"
                disabled={actionBusy}
                onClick={() => onRefreshMetadata(clip.id, "smart")}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-full border border-cyan/[0.30] bg-teal/[0.10] px-4 text-sm font-semibold text-cyan disabled:cursor-not-allowed disabled:opacity-50"
              >
                {metadataState?.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
                {metadataState?.status === "running" ? "Refreshing..." : "Refresh metadata"}
              </button>
            </div>
          ) : null}
          {activeTab === "timing" ? (
            <TimingEditor key={clip.id} clip={clip} actionBusy={actionBusy} boundaryState={boundaryState} onSaveBoundary={onSaveBoundary} />
          ) : null}
          {activeTab === "captions" ? (
            <CaptionEditor clip={clip} captionDraft={captionDraft} setCaptionDraft={setCaptionDraft} actionBusy={actionBusy} captionCount={captionCount} saveState={saveState} rerenderState={rerenderState} onSaveCaptions={onSaveCaptions} onRerender={onRerender} />
          ) : null}
          {activeTab === "post" ? (
            <div className="rounded-[22px] border border-white/[0.08] bg-canvas-deep p-4">
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-white"><MessageSquareText className="h-4 w-4 text-cyan" /> Post copy</div>
              <p className="whitespace-pre-wrap text-sm leading-6 text-zinc-400">{clip.post_caption || "Post caption will appear after render metadata is available."}</p>
            </div>
          ) : null}
          {activeTab === "quality" ? (
            <QualityPanel clip={clip} warnings={warnings} />
          ) : null}
          {metadataState || boundaryState ? (
            <p className={`text-xs font-medium ${metadataState?.status === "failed" || boundaryState?.status === "failed" ? "text-danger" : "text-cyan"}`}>{(metadataState || boundaryState)?.message}</p>
          ) : null}
        </div>
      ) : <EmptyState text="Select a clip to inspect curation, captions, and publish copy." />}
    </div>
  );
}

function CaptionEditor({clip, captionDraft, setCaptionDraft, actionBusy, captionCount, saveState, rerenderState, onSaveCaptions, onRerender}: {
  clip: ClipCandidate;
  captionDraft: string;
  setCaptionDraft: (value: string) => void;
  actionBusy: boolean;
  captionCount: number;
  saveState?: ActionUiState;
  rerenderState?: ActionUiState;
  onSaveCaptions: (id: string, draft: string) => void;
  onRerender: (id: string) => void;
}) {
  return (
    <div className="rounded-[22px] border border-white/[0.08] bg-canvas-deep p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-white">Caption editor</div>
          <p className="mt-1 text-xs text-zinc-500">{captionCount} timed lines · save text, then re-render this item</p>
        </div>
        <button
          type="button"
          disabled={!captionCount || actionBusy}
          onClick={() => onRerender(clip.id)}
          className="shrink-0 rounded-full border border-cyan/[0.30] bg-teal/[0.10] px-3 py-2 text-xs font-semibold text-cyan disabled:cursor-not-allowed disabled:opacity-40"
        >
          {rerenderState?.status === "running" ? <span className="inline-flex items-center gap-1.5"><Loader2 className="h-3 w-3 animate-spin" /> Starting...</span> : "Re-render"}
        </button>
      </div>
      <textarea
        value={captionDraft}
        disabled={!captionCount}
        onChange={(event) => setCaptionDraft(event.target.value)}
        className="min-h-56 w-full resize-y rounded-2xl border border-white/[0.08] bg-black/30 px-3 py-3 text-sm leading-6 text-zinc-200 outline-none focus:border-cyan/[0.35] disabled:cursor-not-allowed disabled:opacity-50"
        spellCheck={false}
      />
      <div className="mt-3 flex items-center justify-between gap-3">
        <p className="text-xs text-zinc-500">One line maps to one timed caption group.</p>
        <button
          type="button"
          disabled={!captionCount || actionBusy}
          onClick={() => onSaveCaptions(clip.id, captionDraft)}
          className="rounded-full bg-cyan px-4 py-2 text-xs font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-40"
        >
          {saveState?.status === "running" ? <span className="inline-flex items-center gap-1.5"><Loader2 className="h-3 w-3 animate-spin" /> Saving...</span> : "Save text edits"}
        </button>
      </div>
    </div>
  );
}

function TimingEditor({clip, actionBusy, boundaryState, onSaveBoundary}: {
  clip: ClipCandidate;
  actionBusy: boolean;
  boundaryState?: ActionUiState;
  onSaveBoundary: (id: string, startMs: number, endMs: number, rerenderAfter: boolean) => void;
}) {
  const [timingStart, setTimingStart] = useState(formatTimestamp(clip.start_ms));
  const [timingEnd, setTimingEnd] = useState(formatTimestamp(clip.end_ms));
  const boundary = boundaryValidation(timingStart, timingEnd);
  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-2 gap-3">
        <label className="grid gap-2 text-sm font-semibold text-zinc-300">
          Start
          <input value={timingStart} onChange={(event) => setTimingStart(event.target.value)} className="h-12 rounded-2xl border border-white/[0.08] bg-canvas-deep px-3 text-white outline-none focus:border-cyan/[0.45]" />
        </label>
        <label className="grid gap-2 text-sm font-semibold text-zinc-300">
          End
          <input value={timingEnd} onChange={(event) => setTimingEnd(event.target.value)} className="h-12 rounded-2xl border border-white/[0.08] bg-canvas-deep px-3 text-white outline-none focus:border-cyan/[0.45]" />
        </label>
      </div>
      <p className={`text-xs font-medium ${boundary.valid ? "text-cyan" : "text-danger"}`}>{boundary.message}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        <button type="button" disabled={!boundary.valid || actionBusy || clip.status === "published"} onClick={() => onSaveBoundary(clip.id, boundary.startMs, boundary.endMs, false)} className="h-11 rounded-full border border-white/[0.10] text-sm font-semibold text-zinc-200 disabled:cursor-not-allowed disabled:opacity-40">Save timing</button>
        <button type="button" disabled={!boundary.valid || actionBusy || clip.status === "published"} onClick={() => onSaveBoundary(clip.id, boundary.startMs, boundary.endMs, true)} className="h-11 rounded-full bg-cyan text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-40">
          {boundaryState?.status === "running" ? "Saving..." : "Save + re-render"}
        </button>
      </div>
      {clip.status === "published" ? <p className="text-xs text-warning">Published clips are locked for audit safety.</p> : null}
    </div>
  );
}

function QualityPanel({clip, warnings}: {clip: ClipCandidate; warnings: {label: string; tone: "warning" | "danger" | "info"}[]}) {
  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-2 gap-2">
        <SettingTile label="Start" value={formatTimestamp(clip.start_ms)} />
        <SettingTile label="End" value={formatTimestamp(clip.end_ms)} />
        <SettingTile label="Cost" value={`$${Number(clip.cost?.estimated_total || 0).toFixed(4)}`} />
        <SettingTile label="Caption" value={clip.caption_source || "-"} />
        <SettingTile label="Coverage" value={`${Math.round((clip.render_quality?.caption_coverage || 0) * 100)}%`} />
        <SettingTile label="Gate" value={clip.quality_gate?.passed ? "Auto eligible" : "Review"} />
      </div>
      <div className="rounded-[22px] border border-white/[0.08] bg-canvas-deep p-4">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
          <CheckCircle2 className="h-4 w-4 text-cyan" />
          Quality checks
        </div>
        {warnings.length ? (
          <div className="grid gap-2">
            {warnings.map((warning) => (
              <div key={warning.label} className="flex items-center justify-between rounded-2xl border border-white/[0.06] bg-black/20 px-3 py-2 text-xs">
                <span className="font-semibold text-zinc-300">{warning.label}</span>
                <span className={warning.tone === "danger" ? "text-danger" : warning.tone === "warning" ? "text-warning" : "text-cyan"}>{warning.tone === "info" ? "noted" : "review"}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm leading-6 text-zinc-400">No visible QA issues on this clip. Still review the first 3 seconds and final sentence before publishing.</p>
        )}
      </div>
    </div>
  );
}

function ScoreBubble({value, label}: {value?: number; label?: string}) {
  const tone = typeof value !== "number" ? "border-surface-strong text-zinc-400" : value >= 80 ? "border-teal text-teal" : value >= 65 ? "border-warning text-white" : "border-danger text-danger";
  return (
    <div className="grid justify-items-center gap-1">
      <span className={`grid h-11 w-11 place-items-center rounded-full border text-sm font-semibold ${tone}`}>{scoreValue(value)}</span>
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
