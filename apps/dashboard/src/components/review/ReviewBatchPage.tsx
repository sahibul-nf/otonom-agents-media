"use client";

import Link from "next/link";
import {useRouter} from "next/navigation";
import {AlertTriangle, ArrowLeft, Loader2} from "lucide-react";
import {useCallback, useEffect, useMemo, useState} from "react";
import {ReviewSelectionChrome} from "@/components/review/ReviewSelectionChrome";
import {ReviewQueueCard} from "@/components/review/ReviewQueueCard";
import {apiGet, apiPost, type ClipCandidate, type DeleteCandidatesResult} from "@/lib/media-api";
import {groupFromClips, reviewEditorHref, reviewStatusTone} from "@/lib/review-groups";
import {useReviewSelection} from "@/lib/use-review-selection";

/** Max columns by viewport — iPad portrait stays 2-up. */
function maxBatchColumnsForWidth(width: number) {
  if (width >= 1280) return 5;
  if (width >= 1024) return 4;
  if (width >= 900) return 3;
  if (width >= 480) return 2;
  return 1;
}

function useBatchColumnCount(itemCount: number) {
  const [maxCols, setMaxCols] = useState(2);

  useEffect(() => {
    function update() {
      setMaxCols(maxBatchColumnsForWidth(window.innerWidth));
    }
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  return Math.max(1, Math.min(itemCount, maxCols));
}

export function ReviewBatchPage({sourceId}: {sourceId: string}) {
  const router = useRouter();
  const [clips, setClips] = useState<ClipCandidate[] | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [batchDeleting, setBatchDeleting] = useState(false);
  const [selectionMode, setSelectionMode] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const rows = await apiGet<ClipCandidate[]>("review");
      setClips(rows);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn’t load this batch.");
      setClips([]);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const group = useMemo(() => (clips ? groupFromClips(clips, sourceId) : null), [clips, sourceId]);
  const columnCount = useBatchColumnCount(group?.clips.length || 0);
  const selectableIds = useMemo(() => group?.clips.map((clip) => clip.id) || [], [group]);
  const selection = useReviewSelection(selectableIds, `${sourceId}:${selectableIds.join(",")}`);

  useEffect(() => {
    setSelectionMode(false);
  }, [sourceId, selectableIds.join(",")]);

  function exitSelectionMode() {
    setSelectionMode(false);
    selection.clearSelection();
  }

  async function deleteClip(clip: ClipCandidate) {
    if (!window.confirm(`Remove “${clip.title_hook}” and its rendered files from this workspace?`)) return;
    setDeletingId(clip.id);
    try {
      await apiPost("delete-candidate", {candidate_id: clip.id, delete_artifacts: true});
      setClips((items) => (items || []).filter((item) => item.id !== clip.id));
      selection.deselect(clip.id);
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  }

  async function deleteSelected() {
    const ids = Array.from(selection.selectedIds);
    if (!ids.length) return;
    if (!window.confirm(`Remove ${ids.length} selected clip${ids.length === 1 ? "" : "s"} and their rendered files from this workspace?`)) return;
    setBatchDeleting(true);
    try {
      const result = await apiPost<DeleteCandidatesResult>("delete-candidates", {candidate_ids: ids, delete_artifacts: true});
      const deleted = new Set(result.deleted_ids);
      setClips((items) => (items || []).filter((item) => !deleted.has(item.id)));
      exitSelectionMode();
      if (result.failed.length) {
        window.alert(`Deleted ${result.deleted_ids.length}; ${result.failed.length} failed.`);
      }
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBatchDeleting(false);
    }
  }

  if (clips === null) {
    return (
      <main className="grid min-h-screen place-items-center bg-canvas-deep text-zinc-100">
        <Loader2 className="h-6 w-6 animate-spin text-cyan" />
      </main>
    );
  }

  if (error) {
    return (
      <main className="grid min-h-screen place-items-center bg-canvas-deep px-5 text-center text-zinc-100">
        <div>
          <p className="text-sm text-danger">{error}</p>
          <Link href="/?section=review" className="mt-6 inline-flex rounded-full bg-cyan px-5 py-2.5 text-sm font-semibold text-ink">
            Back to Review
          </Link>
        </div>
      </main>
    );
  }

  if (!group || group.clips.length === 0) {
    return (
      <main className="grid min-h-screen place-items-center bg-canvas-deep px-5 text-center text-zinc-100">
        <div>
          <AlertTriangle className="mx-auto mb-3 h-6 w-6 text-zinc-600" />
          <h1 className="text-xl font-semibold text-white">This batch is empty</h1>
          <p className="mt-2 text-sm text-zinc-500">Clips may have been deleted or moved out of Review.</p>
          <Link href="/?section=review" className="mt-6 inline-flex rounded-full bg-cyan px-5 py-2.5 text-sm font-semibold text-ink">
            Back to Review
          </Link>
        </div>
      </main>
    );
  }

  // Single remaining clip: skip heavy batch chrome — go straight to editor affinity via inbox pattern.
  if (group.clips.length === 1) {
    const only = group.clips[0];
    return (
      <main className="min-h-screen bg-canvas-deep px-4 py-6 text-zinc-100 sm:px-6 lg:px-8">
        <button
          type="button"
          onClick={() => router.push("/?section=review")}
          className="mb-5 inline-flex items-center gap-2 rounded-full px-2 py-1.5 text-sm text-zinc-400 transition hover:bg-white/[0.06] hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Review
        </button>
        <p className="mb-4 text-xs text-zinc-500">Only one clip left in this source — open it to edit, or return to Review.</p>
        <div className="mx-auto max-w-sm">
          <ReviewQueueCard
            clip={only}
            statusTone={reviewStatusTone}
            editHref={reviewEditorHref(only.id, sourceId)}
            deleting={deletingId === only.id}
            onDelete={deleteClip}
          />
        </div>
      </main>
    );
  }

  const total = group.clips.length;
  const progressLabel = `${group.clearedCount}/${total} cleared`;

  return (
    <main className="min-h-screen bg-canvas-deep text-zinc-100">
      <header className="sticky top-0 z-20 border-b border-white/[0.06] bg-canvas-deep/90 px-4 py-3 backdrop-blur-xl sm:px-6 lg:px-8">
        <div className="flex w-full items-start gap-3">
          <button
            type="button"
            onClick={() => router.push("/?section=review")}
            className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-full text-zinc-400 transition hover:bg-white/[0.06] hover:text-white"
            aria-label="Back to Review"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded-2xl border border-white/[0.08] bg-black/30 sm:h-14 sm:w-14">
            {group.thumbnailUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={group.thumbnailUrl} alt="" className="h-full w-full object-cover" />
            ) : (
              <div className="grid h-full w-full place-items-center text-[10px] font-semibold uppercase tracking-wider text-zinc-600">Src</div>
            )}
          </div>
          <div className="min-w-0 flex-1 pt-0.5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-cyan">Source batch</p>
            <h1 className="truncate text-base font-semibold text-white sm:text-lg">{group.title}</h1>
            <p className="mt-0.5 truncate text-xs text-zinc-500">
              {group.channel ? `${group.channel} · ` : ""}
              {total} clip{total === 1 ? "" : "s"} · {progressLabel}
            </p>
          </div>
          {!selectionMode ? (
            <div className="shrink-0 self-center">
              <ReviewSelectionChrome
                active={false}
                selectedCount={0}
                totalSelectable={selectableIds.length}
                allSelected={false}
                onEnter={() => setSelectionMode(true)}
                onExit={exitSelectionMode}
                onToggleAll={() => undefined}
                onDeleteSelected={() => undefined}
              />
            </div>
          ) : null}
        </div>
        {selectionMode ? (
          <div className="mt-3 border-t border-white/[0.06] pt-3">
            <ReviewSelectionChrome
              active
              selectedCount={selection.selectedCount}
              totalSelectable={selectableIds.length}
              allSelected={selection.allSelected}
              deleting={batchDeleting}
              onEnter={() => setSelectionMode(true)}
              onExit={exitSelectionMode}
              onToggleAll={() => (selection.allSelected ? selection.clearSelection() : selection.selectAll())}
              onDeleteSelected={() => void deleteSelected()}
            />
          </div>
        ) : null}
      </header>

      <section className="w-full px-4 py-6 sm:px-6 lg:px-8">
        <p className="mb-5 text-center text-sm text-zinc-500">
          {selectionMode ? "Tap clips to select, then delete or open Edit when done." : "Review each candidate, then open Edit for captions and finishing."}
        </p>
        <div
          className="mx-auto grid w-fit max-w-full gap-4 sm:gap-5"
          style={{gridTemplateColumns: `repeat(${columnCount}, minmax(0, 22rem))`}}
        >
          {group.clips.map((clip) => (
            <ReviewQueueCard
              key={clip.id}
              clip={clip}
              statusTone={reviewStatusTone}
              editHref={reviewEditorHref(clip.id, sourceId)}
              deleting={deletingId === clip.id}
              onDelete={deleteClip}
              selectable
              selectionMode={selectionMode}
              selected={selection.isSelected(clip.id)}
              onToggleSelect={() => selection.toggle(clip.id)}
            />
          ))}
        </div>
      </section>
    </main>
  );
}
