"use client";

import {AlertTriangle, ListFilter, MessageSquareText, MoreHorizontal, Trash2} from "lucide-react";
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

type Props = {
  clips: ClipCandidate[];
  selected?: ClipCandidate;
  rerendering: Record<string, RerenderState>;
  filter: string;
  reviewFilters: readonly ReviewFilter[];
  setFilter: (value: string) => void;
  setSelectedId: (id: string) => void;
  captionDraft: string;
  setCaptionDraft: (value: string) => void;
  statusTone: (status: string) => string;
  formatDeadline: (value?: string) => string;
  primaryReviewAction: (clip: ClipCandidate) => string;
  onApprove: (id: string) => void;
  onSchedule: (id: string) => void;
  onHold: (id: string) => void;
  onReject: (id: string) => void;
  onDelete: (id: string) => void;
  onClear: () => void;
  onSaveCaptions: (id: string, draft: string) => void;
  onRerender: (id: string) => void;
};

export function ReviewStudioSection({
  clips,
  selected,
  rerendering,
  filter,
  reviewFilters,
  setFilter,
  setSelectedId,
  captionDraft,
  setCaptionDraft,
  statusTone,
  formatDeadline,
  primaryReviewAction,
  onApprove,
  onSchedule,
  onHold,
  onReject,
  onDelete,
  onClear,
  onSaveCaptions,
  onRerender,
}: Props) {
  const [queueMenuOpen, setQueueMenuOpen] = useState(false);
  const [rowMenuId, setRowMenuId] = useState("");
  const queueMenuRef = useRef<HTMLDivElement>(null);
  const rowMenuRef = useRef<HTMLDivElement>(null);
  const activeFilter = reviewFilters.find((item) => item.id === filter) || reviewFilters[0];

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
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_430px]">
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
                <div className="mt-2 border-t border-white/[0.08] pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setQueueMenuOpen(false);
                      onClear();
                    }}
                    className="inline-flex w-full items-center gap-2 rounded-[18px] px-4 py-3 text-sm font-semibold text-danger hover:bg-danger/[0.10]"
                  >
                    <Trash2 className="h-4 w-4" /> Clear queue
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <div className="grid gap-2">
          {clips.length ? clips.map((clip) => {
            const renderState = rerendering[clip.id];
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
                    {clip.status !== "draft" ? <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${statusTone(clip.status)}`}>{clip.status}</span> : null}
                    {renderState ? <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${statusTone(renderState.status === "running" ? "running" : renderState.status === "failed" ? "failed" : "completed")}`}>{renderState.status === "running" ? "rendering" : renderState.status}</span> : null}
                  </div>
                  <p className="mt-1 line-clamp-2 text-sm leading-5 text-zinc-400">{renderState?.message || clip.viral_reason || "No curation reason yet."}</p>
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
                        if (clip.status === "approved") onSchedule(clip.id);
                        else onApprove(clip.id);
                      }}
                      disabled={renderState?.status === "running"}
                      className="rounded-full border border-teal/[0.30] bg-teal/[0.10] px-3 py-2 text-xs font-semibold text-teal disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {primaryReviewAction(clip)}
                    </button>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        setRowMenuId(rowMenuId === clip.id ? "" : clip.id);
                      }}
                      className="rounded-full border border-white/[0.10] bg-surface px-3 py-2 text-zinc-300 hover:text-white"
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
                        <button type="button" onClick={() => { setRowMenuId(""); onRerender(clip.id); }} className="w-full rounded-2xl px-3 py-2 text-left text-sm font-medium text-zinc-300 hover:bg-white/[0.05] hover:text-white">Re-render</button>
                        {clip.status !== "rejected" ? (
                          <button type="button" onClick={() => { setRowMenuId(""); onReject(clip.id); }} className="w-full rounded-2xl px-3 py-2 text-left text-sm font-medium text-danger hover:bg-danger/[0.10]">Reject</button>
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
      <div className="grid gap-5">
        <PreviewPanel clip={selected} statusTone={statusTone} />
        <InsightPanel
          clip={selected}
          captionDraft={captionDraft}
          setCaptionDraft={setCaptionDraft}
          onSaveCaptions={onSaveCaptions}
          onRerender={onRerender}
        />
      </div>
    </section>
  );
}

function InsightPanel({
  clip,
  captionDraft,
  setCaptionDraft,
  onSaveCaptions,
  onRerender,
}: {
  clip?: ClipCandidate;
  captionDraft: string;
  setCaptionDraft: (value: string) => void;
  onSaveCaptions: (id: string, draft: string) => void;
  onRerender: (id: string) => void;
}) {
  const captionCount = clip?.captions?.length || 0;
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
            <SettingTile label="Cost" value={`$${Number(clip.cost?.estimated_total || 0).toFixed(4)}`} />
            <SettingTile label="Caption" value={clip.caption_source || "-"} />
            <SettingTile label="Coverage" value={`${Math.round((clip.render_quality?.caption_coverage || 0) * 100)}%`} />
            <SettingTile label="Gate" value={clip.quality_gate?.passed ? "Auto eligible" : "Review"} />
            <SettingTile label="Corrections" value={clip.caption_corrections?.manual_edit ? "Manual edit" : clip.caption_corrections?.correction_count || 0} />
          </div>
          <div className="rounded-[22px] border border-white/[0.08] bg-canvas-deep p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-white">Caption editor</div>
                <p className="mt-1 text-xs text-zinc-500">{captionCount} timed lines · save text, then re-render this item</p>
              </div>
              <button
                type="button"
                disabled={!captionCount}
                onClick={() => onRerender(clip.id)}
                className="shrink-0 rounded-full border border-cyan/[0.30] bg-teal/[0.10] px-3 py-2 text-xs font-semibold text-cyan disabled:cursor-not-allowed disabled:opacity-40"
              >
                Re-render
              </button>
            </div>
            <textarea
              value={captionDraft}
              disabled={!captionCount}
              onChange={(event) => setCaptionDraft(event.target.value)}
              className="min-h-40 w-full resize-y rounded-2xl border border-white/[0.08] bg-black/30 px-3 py-3 text-sm leading-6 text-zinc-200 outline-none focus:border-cyan/[0.35] disabled:cursor-not-allowed disabled:opacity-50"
              spellCheck={false}
            />
            <div className="mt-3 flex items-center justify-between gap-3">
              <p className="text-xs text-zinc-500">One line maps to one timed caption group.</p>
              <button
                type="button"
                disabled={!captionCount}
                onClick={() => onSaveCaptions(clip.id, captionDraft)}
                className="rounded-full bg-cyan px-4 py-2 text-xs font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-40"
              >
                Save text edits
              </button>
            </div>
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
