"use client";

import {AlertTriangle, CheckCircle2, Clock3, ListFilter, Loader2, MessageSquareText, MoreHorizontal, RefreshCcw, Scissors, Sparkles, Trash2} from "lucide-react";
import {useEffect, useRef, useState} from "react";
import {ClipCandidate, formatDuration, formatTimestamp, scoreValue} from "@/lib/media-api";
import {PreviewPanel} from "@/components/review/PreviewPanel";
import {FocusModal} from "@/components/FocusModal";
import {SlideToConfirm} from "@/components/shared/SlideToConfirm";

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
  postCopyDraft: string;
  setPostCopyDraft: (value: string) => void;
  statusTone: (status: string) => string;
  formatDeadline: (value?: string) => string;
  primaryReviewAction: (clip: ClipCandidate) => string;
  onApprove: (id: string) => void;
  onSchedule: (id: string) => void;
  onHold: (id: string) => void;
  onDelete: (id: string) => void;
  onClear: () => void;
  onSaveCaptions: (id: string, draft: string) => void;
  onSavePostCopy: (id: string, draft: string) => void;
  onGeneratePostCopy: (id: string) => void;
  onRerender: (id: string) => void;
  onRefreshMetadata: (id: string, mode?: "smart" | "local") => void;
  onSaveBoundary: (id: string, startMs: number, endMs: number, rerenderAfter: boolean) => void;
};

type DetailTab = "summary" | "metadata" | "timing" | "captions" | "post" | "quality";

function clipWarnings(clip?: ClipCandidate) {
  if (!clip) return [];
  const warnings: {label: string; tone: "warning" | "danger" | "info"}[] = [];
  const coverage = clip.render_quality?.caption_coverage;
  const confidence = clip.score?.caption_confidence || clip.score?.asr_confidence;
  if (clip.status === "held") warnings.push({label: "Caption repair needed", tone: "warning"});
  if (typeof coverage === "number" && coverage < 0.9) warnings.push({label: `Coverage ${Math.round(coverage * 100)}%`, tone: "warning"});
  if ((clip.render_quality?.caption_overlap_count || 0) > 0) warnings.push({label: "Caption overlap", tone: "danger"});
  if (typeof confidence === "number" && confidence < 82) warnings.push({label: `ASR ${Math.round(confidence)}`, tone: "warning"});
  if (clip.caption_corrections?.manual_edit) warnings.push({label: "Manual caption edit", tone: "info"});
  return warnings;
}

function canRunPrimaryAction(clip: ClipCandidate) {
  return ["draft", "rendered", "held", "pending_auto_schedule", "approved"].includes(clip.status);
}

function clipReadinessItems(clip: ClipCandidate): ReadinessItem[] {
  const duration = clip.end_ms - clip.start_ms;
  const coverage = clip.render_quality?.caption_coverage;
  const confidence = clip.score?.caption_confidence || clip.score?.asr_confidence;
  const qualityScore = clip.render_quality?.quality_score;
  const captionBlocked = clip.status === "held" || (clip.render_quality?.caption_overlap_count || 0) > 0;
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
  postCopyDraft,
  setPostCopyDraft,
  statusTone,
  formatDeadline,
  primaryReviewAction,
  onApprove,
  onSchedule,
  onHold,
  onDelete,
  onClear,
  onSaveCaptions,
  onSavePostCopy,
  onGeneratePostCopy,
  onRerender,
  onRefreshMetadata,
  onSaveBoundary,
}: Props) {
  const [queueMenuOpen, setQueueMenuOpen] = useState(false);
  const [rowMenuId, setRowMenuId] = useState("");
  const [detailTab, setDetailTab] = useState<DetailTab>("summary");
  const [clipModalOpen, setClipModalOpen] = useState(false);
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
    <section className="grid gap-5">
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <div className="mb-5 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h3 className="text-xl font-semibold text-white">
              Review <span className="font-editorial italic font-normal text-cyan">queue</span>
            </h3>
            <p className="mt-1 text-sm text-zinc-400">Open one clip at a time to approve, fix captions, or send it into Schedule.</p>
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
                onClick={() => {
                  setSelectedId(clip.id);
                  setClipModalOpen(true);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelectedId(clip.id);
                    setClipModalOpen(true);
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
                        if (clip.status === "approved") {
                          onSchedule(clip.id);
                          return;
                        }
                        if (clip.status === "held") {
                          setSelectedId(clip.id);
                          setDetailTab("captions");
                          setClipModalOpen(true);
                          return;
                        }
                        onApprove(clip.id);
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
                        <button type="button" onClick={() => { setRowMenuId(""); setSelectedId(clip.id); setDetailTab("timing"); setClipModalOpen(true); }} className="flex w-full items-center gap-2 rounded-2xl px-3 py-2 text-left text-sm font-medium text-zinc-300 hover:bg-white/[0.05] hover:text-white"><Clock3 className="h-3.5 w-3.5" /> Edit timing</button>
                        <button type="button" onClick={() => { setRowMenuId(""); onRerender(clip.id); }} className="w-full rounded-2xl px-3 py-2 text-left text-sm font-medium text-zinc-300 hover:bg-white/[0.05] hover:text-white">Re-render</button>
                        {clip.status === "scheduled" || clip.status === "ready_to_publish" ? (
                          <button type="button" disabled className="w-full rounded-2xl px-3 py-2 text-left text-sm font-medium text-zinc-500">Managed in Schedule</button>
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
      <FocusModal
        open={clipModalOpen && Boolean(selected)}
        title={selected?.title_hook || "Clip Preview"}
        subtitle={selected?.hook_subtitle || selected?.viral_reason || "Refine this clip's metadata, captions, and publishing details."}
        width="max"
        onClose={() => setClipModalOpen(false)}
      >
        <ReviewDetailPane
          clip={selected}
          statusTone={statusTone}
          activeTab={detailTab}
          setActiveTab={setDetailTab}
          captionDraft={captionDraft}
          setCaptionDraft={setCaptionDraft}
          postCopyDraft={postCopyDraft}
          setPostCopyDraft={setPostCopyDraft}
          actionStates={actionStates}
          onSaveCaptions={onSaveCaptions}
          onSavePostCopy={onSavePostCopy}
          onGeneratePostCopy={onGeneratePostCopy}
          onRerender={onRerender}
          onRefreshMetadata={onRefreshMetadata}
          onSaveBoundary={onSaveBoundary}
          primaryReviewAction={primaryReviewAction}
          onApprove={onApprove}
          onSchedule={onSchedule}
        />
      </FocusModal>
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
  postCopyDraft,
  setPostCopyDraft,
  actionStates,
  onSaveCaptions,
  onSavePostCopy,
  onGeneratePostCopy,
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
  postCopyDraft: string;
  setPostCopyDraft: (value: string) => void;
  actionStates: Record<string, ActionUiState>;
  onSaveCaptions: (id: string, draft: string) => void;
  onSavePostCopy: (id: string, draft: string) => void;
  onGeneratePostCopy: (id: string) => void;
  onRerender: (id: string) => void;
  onRefreshMetadata: (id: string, mode?: "smart" | "local") => void;
  onSaveBoundary: (id: string, startMs: number, endMs: number, rerenderAfter: boolean) => void;
  primaryReviewAction: (clip: ClipCandidate) => string;
  onApprove: (id: string) => void;
  onSchedule: (id: string) => void;
}) {
  const saveState = clip ? actionStates[`caption:${clip.id}:save`] : undefined;
  const rerenderState = clip ? actionStates[`clip:${clip.id}:rerender`] : undefined;
  const metadataState = clip ? actionStates[`clip:${clip.id}:metadata`] : undefined;
  const boundaryState = clip ? actionStates[`clip:${clip.id}:boundary`] : undefined;
  const actionBusy = saveState?.status === "running" || rerenderState?.status === "running" || metadataState?.status === "running" || boundaryState?.status === "running";
  const captionCount = clip?.captions?.length || 0;
  const warnings = clip ? clipWarnings(clip) : [];

  const tabs: {id: DetailTab; label: string}[] = [
    {id: "summary", label: "Summary"},
    {id: "captions", label: "Captions"},
    {id: "timing", label: "Timing"},
    {id: "post", label: "Post Copy"},
    {id: "metadata", label: "Metadata"},
    {id: "quality", label: "QA Checks"},
  ];

  return (
    <div className="grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)] lg:items-start">
      {clip ? (
        <div className="rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Preview</span>
            <span className="text-xs font-medium tabular-nums text-cyan">{formatTimestamp(clip.start_ms)} → {formatTimestamp(clip.end_ms)}</span>
          </div>
          <PreviewPanel clip={clip} statusTone={statusTone} embedded hideHeader />
        </div>
      ) : null}

      {clip ? (
        <div className="rounded-[24px] border border-white/[0.08] bg-canvas-deep p-5 flex flex-col min-h-[460px]">
          {/* Tab Switcher */}
          <div className="flex flex-wrap gap-1.5 border-b border-white/[0.06] pb-4 mb-4">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`h-9 rounded-full px-4 text-xs font-semibold transition ${
                  activeTab === tab.id
                    ? "bg-cyan text-ink shadow-[0_0_12px_rgba(98,238,248,0.18)]"
                    : "text-zinc-400 hover:bg-white/[0.04] hover:text-white"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Active Tab Content */}
          <div className="flex-1 min-h-0">
            {activeTab === "summary" && (
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
            )}
            {activeTab === "metadata" && (
              <div className="grid gap-4">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Hook Title</p>
                  <p className="mt-1 text-lg font-semibold text-white leading-relaxed">{clip.title_hook}</p>
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Viral Reason / Subtitle</p>
                  <p className="mt-1 text-sm leading-6 text-zinc-300">{clip.hook_subtitle || clip.viral_reason || "No reason recorded."}</p>
                </div>
                <button
                  type="button"
                  disabled={actionBusy}
                  onClick={() => onRefreshMetadata(clip.id, "smart")}
                  className="inline-flex h-11 items-center justify-center gap-2 rounded-full border border-cyan/[0.30] bg-teal/[0.10] px-4 text-sm font-semibold text-cyan disabled:cursor-not-allowed disabled:opacity-50 w-fit"
                >
                  {metadataState?.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
                  {metadataState?.status === "running" ? "Refreshing..." : "Refresh metadata"}
                </button>
              </div>
            )}
            {activeTab === "timing" && (
              <TimingEditor key={clip.id} clip={clip} actionBusy={actionBusy} boundaryState={boundaryState} onSaveBoundary={onSaveBoundary} />
            )}
            {activeTab === "captions" && (
              <CaptionEditor clip={clip} captionDraft={captionDraft} setCaptionDraft={setCaptionDraft} actionBusy={actionBusy} captionCount={captionCount} saveState={saveState} rerenderState={rerenderState} onSaveCaptions={onSaveCaptions} onRerender={onRerender} />
            )}
            {activeTab === "post" && (
              <PostCopyEditor clip={clip} draft={postCopyDraft} setDraft={setPostCopyDraft} actionBusy={actionBusy} saveState={actionStates[`post:${clip.id}:save`]} generateState={actionStates[`post:${clip.id}:generate`]} onSavePostCopy={onSavePostCopy} onGeneratePostCopy={onGeneratePostCopy} />
            )}
            {activeTab === "quality" && (
              <QualityPanel clip={clip} warnings={warnings} />
            )}
          </div>

          {(metadataState || boundaryState) && (
            <p className={`text-xs font-medium mt-4 ${metadataState?.status === "failed" || boundaryState?.status === "failed" ? "text-danger" : "text-cyan"}`}>
              {(metadataState || boundaryState)?.message}
            </p>
          )}
        </div>
      ) : (
        <div className="lg:col-span-2">
          <EmptyState text="Select a clip to inspect preview, metadata, timing, captions, and publish copy." />
        </div>
      )}
    </div>
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
    <div className="grid gap-4">
      {clip.caption_corrections?.manual_edit ? (
        <div className="flex items-center gap-2.5 rounded-2xl border border-cyan/15 bg-cyan/[0.04] p-3 text-xs text-cyan">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan animate-pulse shrink-0" />
          <span>Manual corrections are currently applied to this clip's subtitles.</span>
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <SettingTile label="Score" value={scoreValue(clip.score?.overall_score)} />
        <SettingTile label="QA" value={scoreValue(clip.render_quality?.quality_score)} />
        <SettingTile label="Duration" value={formatDuration(clip.render_quality?.duration_ms || clip.end_ms - clip.start_ms)} />
        <SettingTile label="Caption" value={clip.caption_source || "-"} />
      </div>

      <div className="grid gap-3 rounded-[20px] border border-white/[0.08] bg-black/20 p-3">
        <div>
          <div className="mb-2 flex items-center justify-between gap-3">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Readiness Check</div>
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
        <SlideToConfirm
          label={`Slide to ${primaryLabel.toLowerCase()}`}
          activeLabel="Processing decision..."
          onConfirm={() => {
            if (!canRunPrimaryAction(clip)) return;
            if (shouldRepairBeforeApprove) {
              setActiveTab(nextIssue.tab);
              return;
            }
            if (clip.status === "approved") onSchedule(clip.id);
            else onApprove(clip.id);
          }}
          isLoading={busy}
          disabled={!canRunPrimaryAction(clip)}
        />
        <div className="border-t border-white/[0.07] pt-3">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Quick Repair tools</div>
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


function PostCopyEditor({clip, draft, setDraft, actionBusy, saveState, generateState, onSavePostCopy, onGeneratePostCopy}: {
  clip: ClipCandidate;
  draft: string;
  setDraft: (value: string) => void;
  actionBusy: boolean;
  saveState?: ActionUiState;
  generateState?: ActionUiState;
  onSavePostCopy: (id: string, draft: string) => void;
  onGeneratePostCopy: (id: string) => void;
}) {
  const hashtags = Array.from(new Set((draft.match(/(^|\s)(#[\p{L}\p{N}_]+)/gu) || []).map((tag) => tag.trim())));
  const overHashtagLimit = hashtags.length > 5;
  const empty = !draft.trim();
  const locked = clip.status === "published";

  return (
    <div className="rounded-[22px] border border-white/[0.08] bg-canvas-deep p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <MessageSquareText className="h-4 w-4 text-cyan" />
            Post copy
          </div>
          <p className="mt-1 text-xs leading-5 text-zinc-500">Keep it short for cross-platform posting: max 400 characters and 5 hashtags.</p>
        </div>
        <div className="flex shrink-0 items-center gap-2 text-xs font-semibold">
          <span className={`rounded-full border px-2.5 py-1 ${draft.length > 380 ? "border-warning/[0.28] bg-warning/[0.08] text-warning" : "border-teal/[0.24] bg-teal/[0.08] text-teal"}`}>
            {draft.length}/400
          </span>
          <span className={`rounded-full border px-2.5 py-1 ${overHashtagLimit ? "border-danger/[0.28] bg-danger/[0.08] text-danger" : "border-teal/[0.24] bg-teal/[0.08] text-teal"}`}>
            {hashtags.length}/5 tags
          </span>
        </div>
      </div>
      <textarea
        value={draft}
        maxLength={400}
        disabled={locked}
        onChange={(event) => setDraft(event.target.value)}
        className="min-h-40 w-full resize-y rounded-2xl border border-white/[0.08] bg-black/30 px-3 py-3 text-sm leading-6 text-zinc-200 outline-none focus:border-cyan/[0.35] disabled:cursor-not-allowed disabled:opacity-50"
        placeholder="Write a short caption and up to five hashtags..."
      />
      <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className={`text-xs ${overHashtagLimit ? "text-danger" : locked ? "text-warning" : "text-zinc-500"}`}>
          {generateState?.status === "done" ? generateState.message : locked ? "Published post copy is locked for audit safety." : overHashtagLimit ? "Remove extra hashtags before saving." : "This copy is used by scheduled and live publish payloads."}
        </p>
        <div className="flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            disabled={actionBusy || locked}
            onClick={() => onGeneratePostCopy(clip.id)}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-full border border-cyan/[0.28] bg-teal/[0.10] px-5 text-sm font-semibold text-cyan disabled:cursor-not-allowed disabled:opacity-40"
          >
            {generateState?.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {generateState?.status === "running" ? "Generating..." : "Regenerate with AI"}
          </button>
          <button
            type="button"
            disabled={actionBusy || locked || empty || overHashtagLimit}
            onClick={() => onSavePostCopy(clip.id, draft)}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-cyan px-5 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saveState?.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {saveState?.status === "running" ? "Saving..." : "Save post copy"}
          </button>
        </div>
      </div>
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
  const trimStartMs = boundary.startMs || clip.start_ms;
  const trimEndMs = boundary.endMs || clip.end_ms;
  const clipDuration = Math.max(1, clip.end_ms - clip.start_ms);
  const startPercent = Math.max(0, Math.min(100, ((trimStartMs - clip.start_ms) / clipDuration) * 100));
  const endPercent = Math.max(0, Math.min(100, ((trimEndMs - clip.start_ms) / clipDuration) * 100));
  const hasTrimChange = trimStartMs !== clip.start_ms || trimEndMs !== clip.end_ms;
  const controlsDisabled = actionBusy || clip.status === "published";

  function setStartMs(nextMs: number) {
    const clamped = Math.min(Math.max(clip.start_ms, nextMs), trimEndMs - 20_000);
    setTimingStart(formatTimestamp(clamped));
  }

  function setEndMs(nextMs: number) {
    const clamped = Math.max(Math.min(clip.end_ms, nextMs), trimStartMs + 20_000);
    setTimingEnd(formatTimestamp(clamped));
  }

  function nudgeStart(deltaMs: number) {
    setStartMs(trimStartMs + deltaMs);
  }

  function nudgeEnd(deltaMs: number) {
    setEndMs(trimEndMs + deltaMs);
  }

  return (
    <div className="grid gap-4">
      <div className="rounded-[22px] border border-white/[0.08] bg-canvas-deep p-4">
        <div className="mb-3 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-white">
              <Scissors className="h-4 w-4 text-cyan" />
              Trim clip
            </div>
            <p className="mt-1 text-xs leading-5 text-zinc-500">Move the start/end handles, then re-render this clip to produce the trimmed video.</p>
          </div>
          <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${hasTrimChange ? "border-warning/[0.24] bg-warning/[0.08] text-warning" : "border-teal/[0.24] bg-teal/[0.08] text-teal"}`}>
            {hasTrimChange ? "Unsaved trim" : "Current cut"}
          </span>
        </div>
        <div className="relative mt-6 h-12 rounded-[18px] border border-white/[0.08] bg-black/28 px-3">
          <div className="absolute left-4 right-4 top-1/2 h-1 -translate-y-1/2 rounded-full bg-white/[0.08]">
            <div className="absolute top-0 h-full rounded-full bg-cyan" style={{left: `${startPercent}%`, right: `${100 - endPercent}%`}} />
          </div>
          <input
            type="range"
            min={clip.start_ms}
            max={Math.max(clip.start_ms + 20_000, trimEndMs - 20_000)}
            step={500}
            value={Math.max(clip.start_ms, Math.min(trimStartMs, trimEndMs - 20_000))}
            disabled={controlsDisabled}
            onChange={(event) => setStartMs(Number(event.currentTarget.value))}
            className="absolute inset-x-3 top-1/2 z-10 h-1 -translate-y-1/2 cursor-pointer appearance-none bg-transparent accent-[#6ce2ee] disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Trim start"
          />
          <input
            type="range"
            min={Math.min(clip.end_ms - 20_000, trimStartMs + 20_000)}
            max={clip.end_ms}
            step={500}
            value={Math.min(clip.end_ms, Math.max(trimEndMs, trimStartMs + 20_000))}
            disabled={controlsDisabled}
            onChange={(event) => setEndMs(Number(event.currentTarget.value))}
            className="absolute inset-x-3 top-1/2 z-20 h-1 -translate-y-1/2 cursor-pointer appearance-none bg-transparent accent-[#6ce2ee] disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Trim end"
          />
        </div>
        <div className="mt-3 flex items-center justify-between gap-3 text-xs font-medium tabular-nums">
          <span className="text-zinc-500">{formatTimestamp(clip.start_ms)}</span>
          <span className={boundary.valid ? "text-cyan" : "text-danger"}>{boundary.message}</span>
          <span className="text-zinc-500">{formatTimestamp(clip.end_ms)}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <label className="grid gap-2 text-sm font-semibold text-zinc-300">
          Start
          <input value={timingStart} onChange={(event) => setTimingStart(event.target.value)} className="h-12 rounded-2xl border border-white/[0.08] bg-canvas-deep px-3 text-white outline-none focus:border-cyan/[0.45]" />
          <span className="grid grid-cols-2 gap-2">
            <button type="button" disabled={controlsDisabled} onClick={() => nudgeStart(-1000)} className="h-9 rounded-full border border-white/[0.10] text-xs text-zinc-300 disabled:cursor-not-allowed disabled:opacity-40">-1s</button>
            <button type="button" disabled={controlsDisabled} onClick={() => nudgeStart(1000)} className="h-9 rounded-full border border-white/[0.10] text-xs text-zinc-300 disabled:cursor-not-allowed disabled:opacity-40">+1s</button>
          </span>
        </label>
        <label className="grid gap-2 text-sm font-semibold text-zinc-300">
          End
          <input value={timingEnd} onChange={(event) => setTimingEnd(event.target.value)} className="h-12 rounded-2xl border border-white/[0.08] bg-canvas-deep px-3 text-white outline-none focus:border-cyan/[0.45]" />
          <span className="grid grid-cols-2 gap-2">
            <button type="button" disabled={controlsDisabled} onClick={() => nudgeEnd(-1000)} className="h-9 rounded-full border border-white/[0.10] text-xs text-zinc-300 disabled:cursor-not-allowed disabled:opacity-40">-1s</button>
            <button type="button" disabled={controlsDisabled} onClick={() => nudgeEnd(1000)} className="h-9 rounded-full border border-white/[0.10] text-xs text-zinc-300 disabled:cursor-not-allowed disabled:opacity-40">+1s</button>
          </span>
        </label>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <button type="button" disabled={!boundary.valid || controlsDisabled || !hasTrimChange} onClick={() => onSaveBoundary(clip.id, boundary.startMs, boundary.endMs, false)} className="h-11 rounded-full border border-white/[0.10] text-sm font-semibold text-zinc-200 disabled:cursor-not-allowed disabled:opacity-40">Save trim only</button>
        <button type="button" disabled={!boundary.valid || controlsDisabled || !hasTrimChange} onClick={() => onSaveBoundary(clip.id, boundary.startMs, boundary.endMs, true)} className="h-11 rounded-full bg-cyan text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-40">
          {boundaryState?.status === "running" ? "Trimming..." : "Apply trim + re-render"}
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
