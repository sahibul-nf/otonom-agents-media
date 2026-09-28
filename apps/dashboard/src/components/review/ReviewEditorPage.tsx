"use client";

import Link from "next/link";
import {useRouter} from "next/navigation";
import {ArrowLeft, ChevronLeft, ChevronRight, Loader2, MoreHorizontal} from "lucide-react";
import {useCallback, useEffect, useMemo, useState} from "react";
import {EditorHeaderActions} from "@/components/review/editor/EditorHeaderActions";
import {ReviewEditorWorkspace} from "@/components/review/editor/ReviewEditorWorkspace";
import {captionIndexAtSeconds, captionRelativeSeconds, editorLookFromContext, isRenderingContext, joinCaptionsFromSegments, pendingLookDirty, redistributeCaptionDocument, type ActionState, type InspectorTab, type PendingEditorLook} from "@/components/review/editor/types";
import {
  apiGet,
  apiPost,
  canMakeShortsFromClip,
  fetchHyperframesTemplatesWithBrands,
  type CaptionPolishResult,
  type ClipCandidate,
  type EditorContext,
  type ExplainerScene,
  type ExplainerScenePlan,
  type BrandTemplate,
  type HyperframesTemplate,
  type MakeShortsFromLongformResult,
  type PublishTarget,
  type SaveScenePlanResponse,
} from "@/lib/media-api";
import {reviewBatchHref, reviewEditorHref} from "@/lib/review-groups";

type ScenePlanResult = Partial<SaveScenePlanResponse> & {plan: ExplainerScenePlan};
type RerenderJob = {id: string; status: string; error?: string; message?: string; progress?: number};
type MetadataRefreshResult = {
  title_hook: string;
  hook_subtitle: string;
  viral_reason: string;
  curation_metadata?: ClipCandidate["curation_metadata"];
  rerender_job?: RerenderJob;
};
type HookMetadataSaveResult = MetadataRefreshResult;

export function ReviewEditorPage({
  clipId,
  fromBatch = false,
  batchSourceId = "",
}: {
  clipId: string;
  fromBatch?: boolean;
  batchSourceId?: string;
}) {
  const router = useRouter();
  const backHref = fromBatch && batchSourceId ? reviewBatchHref(batchSourceId) : "/?section=review";
  const backLabel = fromBatch && batchSourceId ? "Back to batch" : "Back to Review";
  const [clip, setClip] = useState<ClipCandidate | null>();
  const [clips, setClips] = useState<ClipCandidate[]>([]);
  const [context, setContext] = useState<EditorContext | null>();
  const [cleanPlan, setCleanPlan] = useState<ExplainerScenePlan>();
  const [draftPlan, setDraftPlan] = useState<ExplainerScenePlan>();
  const [templates, setTemplates] = useState<HyperframesTemplate[]>([]);
  const [brandLibrary, setBrandLibrary] = useState<BrandTemplate[]>([]);
  const [schedulePlatforms, setSchedulePlatforms] = useState<string[]>([]);
  const [cleanCaptionDraft, setCleanCaptionDraft] = useState("");
  const [captionDraft, setCaptionDraft] = useState("");
  const [cleanPostCopy, setCleanPostCopy] = useState("");
  const [postCopyDraft, setPostCopyDraft] = useState("");
  const [cleanMetadataTitle, setCleanMetadataTitle] = useState("");
  const [metadataTitleDraft, setMetadataTitleDraft] = useState("");
  const [cleanMetadataSubtitle, setCleanMetadataSubtitle] = useState("");
  const [metadataSubtitleDraft, setMetadataSubtitleDraft] = useState("");
  const [selectedSceneId, setSelectedSceneId] = useState<string>();
  const [selectedCaptionIndex, setSelectedCaptionIndex] = useState<number>();
  const [activeInspectorTab, setActiveInspectorTab] = useState<InspectorTab>("scene");
  const [inspectorPanelOpen, setInspectorPanelOpen] = useState(false);
  const [currentSeconds, setCurrentSeconds] = useState(0);
  const [seekRequest, setSeekRequest] = useState<{id: number; seconds: number}>();
  const [playbackRequest, setPlaybackRequest] = useState<{id: number; action: "toggle" | "play" | "pause"}>();
  const [isPlaying, setIsPlaying] = useState(false);
  const [actionStates, setActionStates] = useState<Record<string, ActionState>>({});
  const [menuOpen, setMenuOpen] = useState(false);
  const [previewEpoch, setPreviewEpoch] = useState(0);
  const [cleanLookBaseline, setCleanLookBaseline] = useState<PendingEditorLook>(() => editorLookFromContext());
  const [pendingLook, setPendingLook] = useState<PendingEditorLook>(() => editorLookFromContext());

  const planDirty = useMemo(() => JSON.stringify(draftPlan) !== JSON.stringify(cleanPlan), [cleanPlan, draftPlan]);
  const captionsDirty = captionDraft !== cleanCaptionDraft;
  const postCopyDirty = postCopyDraft !== cleanPostCopy;
  const metadataDirty = metadataTitleDraft !== cleanMetadataTitle || metadataSubtitleDraft !== cleanMetadataSubtitle;
  const lookDirty = useMemo(() => pendingLookDirty(pendingLook, cleanLookBaseline), [cleanLookBaseline, pendingLook]);
  const contentDirty = planDirty || captionsDirty || postCopyDirty || metadataDirty;
  const dirty = contentDirty || lookDirty;

  const syncLookFromContext = useCallback((next: EditorContext) => {
    const baseline = editorLookFromContext(next.look);
    setCleanLookBaseline(baseline);
    setPendingLook(baseline);
  }, []);
  const rendering = isRenderingContext(context || undefined);

  const applyContext = useCallback((next: EditorContext, resetPlan: boolean) => {
    setContext(next);
    if (next.plan && resetPlan) {
      setCleanPlan(structuredClone(next.plan));
      setDraftPlan(structuredClone(next.plan));
      setSelectedSceneId((current) => next.plan?.scenes.some((scene) => scene.id === current) ? current : next.plan?.scenes[0]?.id);
    }
    setActiveInspectorTab((current) => {
      if (next.capability === "scene") return current === "scene" || current === "metadata" || current === "post" || current === "qa" ? current : "scene";
      if (next.capability === "short") {
        if (current === "scene" || current === "captions") return next.can_trim ? "trim" : "silence";
        if (current === "silence" || current === "look" || current === "trim" || current === "metadata" || current === "post" || current === "qa") return current;
        return next.can_trim ? "trim" : "silence";
      }
      return current === "scene" || current === "captions" || current === "trim" || current === "silence" ? "metadata" : current;
    });
  }, []);

  const loadInitial = useCallback(async () => {
    try {
      const [reviewItems, editorContext, targets, templateBundle] = await Promise.all([
        apiGet<ClipCandidate[]>("review"),
        apiGet<EditorContext>(`editor-context?candidate_id=${encodeURIComponent(clipId)}`),
        apiGet<PublishTarget[]>("targets"),
        fetchHyperframesTemplatesWithBrands(),
      ]);
      const nextClip = reviewItems.find((item) => item.id === clipId) || null;
      setClips(reviewItems);
      setClip(nextClip);
      setTemplates(templateBundle.templates);
      setBrandLibrary(templateBundle.brandLibrary);
      setSchedulePlatforms(targets.filter((target) => target.mode !== "off").map((target) => target.platform));
      if (nextClip) {
        const captions = joinCaptionsFromSegments(nextClip.captions || []);
        const postCopy = nextClip.post_caption || "";
        const metadataTitle = nextClip.title_hook || "";
        const metadataSubtitle = nextClip.hook_subtitle || nextClip.viral_reason || "";
        setCleanCaptionDraft(captions);
        setCaptionDraft(captions);
        setCleanPostCopy(postCopy);
        setPostCopyDraft(postCopy);
        setCleanMetadataTitle(metadataTitle);
        setMetadataTitleDraft(metadataTitle);
        setCleanMetadataSubtitle(metadataSubtitle);
        setMetadataSubtitleDraft(metadataSubtitle);
        if (editorContext.capability !== "scene" && (captions || nextClip.transcript_span?.trim())) {
          setSelectedCaptionIndex(0);
        }
      }
      applyContext(editorContext, true);
      syncLookFromContext(editorContext);
    } catch {
      setClip(null);
      setContext(null);
    }
  }, [applyContext, clipId, syncLookFromContext]);

  const refreshClip = useCallback(async () => {
    const reviewItems = await apiGet<ClipCandidate[]>("review");
    const nextClip = reviewItems.find((item) => item.id === clipId) || null;
    setClips(reviewItems);
    setClip(nextClip);
    if (nextClip) {
      const captions = joinCaptionsFromSegments(nextClip.captions || []);
      const postCopy = nextClip.post_caption || "";
      const metadataTitle = nextClip.title_hook || "";
      const metadataSubtitle = nextClip.hook_subtitle || nextClip.viral_reason || "";
      setCaptionDraft((current) => current === cleanCaptionDraft ? captions : current);
      setCleanCaptionDraft(captions);
      setPostCopyDraft((current) => current === cleanPostCopy ? postCopy : current);
      setCleanPostCopy(postCopy);
      setMetadataTitleDraft((current) => current === cleanMetadataTitle ? metadataTitle : current);
      setCleanMetadataTitle(metadataTitle);
      setMetadataSubtitleDraft((current) => current === cleanMetadataSubtitle ? metadataSubtitle : current);
      setCleanMetadataSubtitle(metadataSubtitle);
    }
  }, [cleanCaptionDraft, cleanMetadataSubtitle, cleanMetadataTitle, cleanPostCopy, clipId]);

  useEffect(() => {
    void loadInitial();
  }, [loadInitial]);

  useEffect(() => {
    if (activeInspectorTab !== "look") return;
    void fetchHyperframesTemplatesWithBrands()
      .then((bundle) => {
        setTemplates(bundle.templates);
        setBrandLibrary(bundle.brandLibrary);
      })
      .catch(() => undefined);
  }, [activeInspectorTab]);

  useEffect(() => {
    if (!contentDirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [contentDirty]);

  useEffect(() => {
    if (!rendering) return;
    const timer = window.setInterval(() => {
      void apiGet<EditorContext>(`editor-context?candidate_id=${encodeURIComponent(clipId)}`)
        .then(async (next) => {
          const stillRendering = isRenderingContext(next);
          applyContext(next, !dirty);
          if (!stillRendering) {
            await refreshClip();
            syncLookFromContext(next);
            setPreviewEpoch((value) => value + 1);
            setSeekRequest({id: Date.now(), seconds: 0});
            setPlaybackRequest({id: Date.now(), action: "pause"});
            if (next.job?.error) {
              setActionStates((items) => ({
                ...items,
                [`clip:${clipId}:rerender`]: {status: "failed", message: next.job?.error || "Re-render failed"},
              }));
            }
          }
        })
        .catch(() => undefined);
    }, 2_000);
    return () => window.clearInterval(timer);
  }, [applyContext, clipId, dirty, refreshClip, rendering, syncLookFromContext]);

  useEffect(() => {
    if (!clip?.captions?.length) return;
    if (context?.capability === "scene") return;
    const index = captionIndexAtSeconds(clip, clip.captions, currentSeconds);
    if (index !== undefined) setSelectedCaptionIndex(index);
  }, [clip, context?.capability, currentSeconds]);

  async function applyRerenderJob(job: RerenderJob) {
    const nextContext = await apiGet<EditorContext>(`editor-context?candidate_id=${encodeURIComponent(clipId)}`);
    applyContext(
      {
        ...nextContext,
        job: nextContext.job || {
          job_id: job.id,
          status: job.status || "queued",
          error: job.error || "",
          progress: job.progress,
          message: job.message || "Re-rendering…",
        },
      },
      false,
    );
  }

  async function queueRerender() {
    if (!context?.can_rerender || context.capability !== "short" || !clip) return;
    const payload: Record<string, string> = {
      candidate_id: clip.id,
      renderer: "hyperframes",
      quality: "production",
      style: "auto",
    };
    if (lookDirty) {
      if (pendingLook.brand_system_template_id) {
        payload.hyperframes_template = pendingLook.brand_system_template_id;
        payload.brand_system_template_id = pendingLook.brand_system_template_id;
        if (pendingLook.brand_template_path) payload.style = pendingLook.brand_template_path;
      } else if (pendingLook.hyperframes_template && pendingLook.hyperframes_template !== "auto") {
        payload.hyperframes_template = pendingLook.hyperframes_template;
        payload.brand_system_template_id = "";
      }
    }
    const job = await apiPost<RerenderJob>("rerender", payload);
    await applyRerenderJob(job);
  }

  async function refreshMetadata(rerenderAfter: boolean) {
    if (!clip) return;
    const result = await apiPost<MetadataRefreshResult>("metadata-refresh", {
      candidate_id: clip.id,
      mode: "smart",
      rerender_after: rerenderAfter,
      renderer: "hyperframes",
      quality: "production",
      style: "auto",
    });
    const subtitle = result.hook_subtitle || result.viral_reason || "";
    setCleanMetadataTitle(result.title_hook);
    setMetadataTitleDraft(result.title_hook);
    setCleanMetadataSubtitle(subtitle);
    setMetadataSubtitleDraft(subtitle);
    setClip((current) =>
      current
        ? {
            ...current,
            title_hook: result.title_hook,
            hook_subtitle: result.hook_subtitle,
            viral_reason: result.viral_reason,
            curation_metadata: result.curation_metadata || current.curation_metadata,
          }
        : current,
    );
    if (rerenderAfter && result.rerender_job) {
      await applyRerenderJob(result.rerender_job);
    }
  }

  async function runAction(key: string, pending: string, action: () => Promise<void>, done: string, refresh = true) {
    setActionStates((items) => ({...items, [key]: {status: "running", message: pending}}));
    try {
      await action();
      setActionStates((items) => ({...items, [key]: {status: "done", message: done}}));
      if (refresh) await refreshClip();
    } catch (error) {
      setActionStates((items) => ({...items, [key]: {status: "failed", message: error instanceof Error ? error.message : "Action failed"}}));
    }
  }

  async function polishCaptions() {
    if (!clip?.captions?.length) return;
    await runAction(
      `clip:${clip.id}:caption-polish`,
      "Polishing captions…",
      async () => {
        const result = await apiPost<CaptionPolishResult>("caption-polish", {candidate_id: clip.id});
        const nextCaptions = result.captions || [];
        const joined = joinCaptionsFromSegments(nextCaptions);
        setClip((current) => (current ? {...current, captions: nextCaptions, caption_corrections: result.caption_corrections} : current));
        setCaptionDraft(joined);
        setCleanCaptionDraft(joined);
      },
      "Captions polished",
      false,
    );
  }

  async function makeShortsFromLongform() {
    if (!clip || !canMakeShortsFromClip(clip)) return;
    const key = `clip:${clip.id}:shorts`;
    setActionStates((items) => ({...items, [key]: {status: "running", message: "Queuing shorts…"}}));
    try {
      const result = await apiPost<MakeShortsFromLongformResult>("make-shorts-from-longform", {candidate_id: clip.id});
      setActionStates((items) => ({...items, [key]: {status: "done", message: result.message}}));
      if (result.route === "generation_job") {
        router.push("/?section=generate");
        return;
      }
      await refreshClip();
      if (fromBatch && batchSourceId) {
        router.push(reviewBatchHref(batchSourceId));
      } else {
        router.push("/?section=review");
      }
    } catch (error) {
      setActionStates((items) => ({
        ...items,
        [key]: {status: "failed", message: error instanceof Error ? error.message : "Make shorts failed"},
      }));
    }
  }

  function navigate(href?: string) {
    if (!href) return;
    if (contentDirty && !window.confirm("Discard unsaved editor changes?")) return;
    router.push(href);
  }

  async function savePlan(rerender: boolean) {
    if (!draftPlan || !context) return;
    await runAction("plan", rerender ? "Saving and rendering…" : "Saving plan…", async () => {
      const result = await apiPost<ScenePlanResult>("explainer-scene-plan", {
        candidate_id: clipId,
        title: draftPlan.title,
        scenes: draftPlan.scenes,
        rerender_after: rerender,
        prefer_hyperframes: rerender,
      });
      const nextContext: EditorContext = {
        ...context,
        ...result,
        candidate_id: result.candidate_id || context.candidate_id,
        capability: result.capability || context.capability,
        can_edit_scenes: result.can_edit_scenes ?? context.can_edit_scenes,
        can_trim: result.can_trim ?? context.can_trim,
        can_rerender: result.can_rerender ?? context.can_rerender,
        plan: result.plan,
      };
      applyContext(nextContext, true);
    }, rerender ? "Full render started" : "Plan saved", false);
  }

  async function saveAllChanges() {
    await runAction("plan", "Saving editor changes…", async () => {
      if (planDirty && draftPlan && context) {
        const result = await apiPost<ScenePlanResult>("explainer-scene-plan", {
          candidate_id: clipId,
          title: draftPlan.title,
          scenes: draftPlan.scenes,
          rerender_after: false,
        });
        applyContext({...context, ...result, plan: result.plan}, true);
      }
      if (captionsDirty && clip) {
        const nextCaptions = redistributeCaptionDocument(clip.captions || [], captionDraft);
        await apiPost("caption-corrections", {candidate_id: clip.id, captions: nextCaptions});
        setCleanCaptionDraft(joinCaptionsFromSegments(nextCaptions));
        setCaptionDraft(joinCaptionsFromSegments(nextCaptions));
        setClip((current) => current ? {...current, captions: nextCaptions} : current);
      }
      if (postCopyDirty && clip) {
        await apiPost("post-copy", {candidate_id: clip.id, post_caption: postCopyDraft});
        setCleanPostCopy(postCopyDraft);
        setClip((current) => current ? {...current, post_caption: postCopyDraft} : current);
      }
      if (metadataDirty && clip) {
        const title = metadataTitleDraft.trim();
        const subtitle = metadataSubtitleDraft.trim();
        if (!title) {
          throw new Error("Title is required");
        }
        const result = await apiPost<HookMetadataSaveResult>("hook-metadata", {
          candidate_id: clip.id,
          title_hook: title,
          hook_subtitle: subtitle,
        });
        setCleanMetadataTitle(result.title_hook);
        setMetadataTitleDraft(result.title_hook);
        const savedSubtitle = result.hook_subtitle || result.viral_reason || "";
        setCleanMetadataSubtitle(savedSubtitle);
        setMetadataSubtitleDraft(savedSubtitle);
        setClip((current) =>
          current
            ? {
                ...current,
                title_hook: result.title_hook,
                hook_subtitle: result.hook_subtitle,
                viral_reason: result.viral_reason,
                curation_metadata: result.curation_metadata || current.curation_metadata,
              }
            : current,
        );
      }
    }, "Editor changes saved", false);
  }

  function updateSceneList(updater: (scenes: ExplainerScene[]) => ExplainerScene[]) {
    if (!draftPlan) return;
    setDraftPlan({...draftPlan, scenes: updater(draftPlan.scenes)});
  }

  if (clip === undefined || context === undefined) return <div className="grid min-h-screen place-items-center bg-canvas-deep"><Loader2 className="h-6 w-6 animate-spin text-cyan" /></div>;
  if (!clip || !context) return <Unavailable />;

  const navClips =
    fromBatch && batchSourceId
      ? clips.filter((item) => (item.source_id || item.source?.id || "").trim() === batchSourceId.trim())
      : clips;
  const clipIndex = navClips.findIndex((item) => item.id === clip.id);
  const previousClip = navClips[clipIndex - 1];
  const nextClip = navClips[clipIndex + 1];
  const editorLink = (id: string) => (fromBatch && batchSourceId ? reviewEditorHref(id, batchSourceId) : `/review/${encodeURIComponent(id)}`);

  return (
    <main className="flex h-dvh min-h-0 flex-col overflow-hidden bg-canvas text-zinc-100">
      <header className="z-40 shrink-0 bg-gradient-to-b from-canvas-deep/80 via-canvas/40 to-transparent px-3 py-2.5 sm:px-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <button type="button" onClick={() => navigate(backHref)} className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-zinc-400 transition hover:bg-white/[0.06] hover:text-white" aria-label={backLabel}><ArrowLeft className="h-4 w-4" /></button>
            <div className="min-w-0">
              <h1 className="truncate text-sm font-semibold tracking-tight text-white">{draftPlan?.title || metadataTitleDraft || clip.title_hook}</h1>
              <p className="truncate text-[11px] text-zinc-600">{Math.max(clipIndex, 0) + 1}/{navClips.length || 1} · canvas</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden items-center rounded-full border border-white/[0.05] bg-black/20 p-0.5 backdrop-blur-md md:flex">
              <button type="button" disabled={!previousClip} onClick={() => navigate(previousClip ? editorLink(previousClip.id) : undefined)} className="grid h-8 w-8 place-items-center rounded-full text-zinc-500 transition hover:bg-white/[0.06] hover:text-white disabled:opacity-25" aria-label="Previous review item"><ChevronLeft className="h-4 w-4" /></button>
              <button type="button" disabled={!nextClip} onClick={() => navigate(nextClip ? editorLink(nextClip.id) : undefined)} className="grid h-8 w-8 place-items-center rounded-full text-zinc-500 transition hover:bg-white/[0.06] hover:text-white disabled:opacity-25" aria-label="Next review item"><ChevronRight className="h-4 w-4" /></button>
            </div>
            <EditorHeaderActions
              clip={clip}
              context={context}
              dirty={contentDirty}
              lookChanged={lookDirty}
              rendering={rendering}
              actionStates={actionStates}
              onSave={() => void saveAllChanges()}
              onRender={() => void savePlan(true)}
              onRerender={
                context.can_rerender && context.capability === "short"
                  ? () => {
                      void runAction(
                        `clip:${clip.id}:rerender`,
                        "Starting re-render…",
                        () => queueRerender(),
                        "Re-render started — preview updates when ready.",
                        false,
                      );
                    }
                  : undefined
              }
              onPolishCaptions={
                context.capability === "short" && clip.captions?.length
                  ? () => {
                      void polishCaptions();
                    }
                  : undefined
              }
              onApprove={() => void runAction(`clip:${clip.id}:approve`, "Approving…", () => apiPost("approve", {candidate_id: clip.id}), "Approved")}
              onSchedule={() => void runAction(`clip:${clip.id}:schedule`, "Scheduling…", () => apiPost("schedule-next", {candidate_id: clip.id, platforms: schedulePlatforms}), "Scheduled")}
            />
            <div className="relative">
              <button type="button" onClick={() => setMenuOpen((open) => !open)} className="grid h-9 w-9 place-items-center rounded-full text-zinc-400 transition hover:bg-white/[0.06] hover:text-white" aria-label="More review actions" aria-expanded={menuOpen}><MoreHorizontal className="h-4 w-4" /></button>
              {menuOpen ? <div className="absolute right-0 top-11 z-50 w-52 overflow-hidden rounded-2xl border border-white/[0.06] bg-canvas-deep/95 p-1 shadow-2xl backdrop-blur-xl">
                {canMakeShortsFromClip(clip) ? (
                  <button
                    type="button"
                    disabled={actionStates[`clip:${clip.id}:shorts`]?.status === "running"}
                    onClick={() => { setMenuOpen(false); void makeShortsFromLongform(); }}
                    className="w-full rounded-xl px-3 py-2 text-left text-sm text-cyan hover:bg-cyan/[0.08] disabled:opacity-40"
                  >
                    {actionStates[`clip:${clip.id}:shorts`]?.status === "running" ? "Queuing shorts…" : "Make shorts"}
                  </button>
                ) : null}
                <button type="button" onClick={() => { setMenuOpen(false); void runAction(`clip:${clip.id}:hold`, "Holding…", () => apiPost("hold", {candidate_id: clip.id}), "Held"); }} className="w-full rounded-xl px-3 py-2 text-left text-sm text-warning hover:bg-warning/[0.08]">Hold for later</button>
                <button type="button" onClick={() => { setMenuOpen(false); if (window.confirm("Delete this item and rendered files?")) void runAction(`clip:${clip.id}:delete`, "Deleting…", async () => { await apiPost("delete-candidate", {candidate_id: clip.id, delete_artifacts: true}); router.push(backHref); }, "Deleted", false); }} className="w-full rounded-xl px-3 py-2 text-left text-sm text-danger hover:bg-danger/[0.08]">Delete item</button>
              </div> : null}
            </div>
          </div>
        </div>
      </header>

      <div className="min-h-0 flex-1">
        <ReviewEditorWorkspace
          clip={clip}
          context={context}
          draftPlan={draftPlan}
          templates={templates}
          brandLibrary={brandLibrary}
          selectedSceneId={selectedSceneId}
          selectedCaptionIndex={selectedCaptionIndex}
          activeInspectorTab={activeInspectorTab}
          inspectorPanelOpen={inspectorPanelOpen}
          captionDraft={captionDraft}
          postCopyDraft={postCopyDraft}
          metadataTitleDraft={metadataTitleDraft}
          metadataSubtitleDraft={metadataSubtitleDraft}
          currentSeconds={currentSeconds}
          seekRequest={seekRequest}
          playbackRequest={playbackRequest}
          isPlaying={isPlaying}
          dirty={contentDirty}
          rendering={rendering}
          actionStates={actionStates}
          pendingLook={pendingLook}
          onPendingLookChange={setPendingLook}
          onSelectScene={(id) => { setSelectedSceneId(id); setActiveInspectorTab("scene"); setInspectorPanelOpen(true); }}
          onSelectCaption={(index) => {
            setSelectedCaptionIndex(index);
            const caption = clip.captions?.[index];
            if (caption) {
              setSeekRequest({id: Date.now(), seconds: captionRelativeSeconds(clip, caption)});
            }
            if (context.capability === "short") {
              setActiveInspectorTab((current) => (current === "captions" ? (context.can_trim ? "trim" : "metadata") : current));
            }
          }}
          onHighlightCaption={setSelectedCaptionIndex}
          onInspectorTabChange={setActiveInspectorTab}
          onInspectorPanelOpenChange={setInspectorPanelOpen}
          onPlanChange={setDraftPlan}
          onAddScene={() => {
            const scene: ExplainerScene = {id: `scene-${crypto.randomUUID()}`, type: "text", duration_target: 5, headline: "", script: "", narration: ""};
            updateSceneList((scenes) => [...scenes, scene]);
            setSelectedSceneId(scene.id);
            setActiveInspectorTab("scene");
            setInspectorPanelOpen(true);
          }}
          onDuplicateScene={(id) => updateSceneList((scenes) => {
            const index = scenes.findIndex((scene) => scene.id === id);
            if (index < 0) return scenes;
            const copy = {...scenes[index], id: `scene-${crypto.randomUUID()}`};
            setSelectedSceneId(copy.id);
            return [...scenes.slice(0, index + 1), copy, ...scenes.slice(index + 1)];
          })}
          onDeleteScene={(id) => updateSceneList((scenes) => {
            if (scenes.length <= 1) return scenes;
            const index = scenes.findIndex((scene) => scene.id === id);
            const next = scenes.filter((scene) => scene.id !== id);
            setSelectedSceneId(next[Math.min(index, next.length - 1)]?.id);
            return next;
          })}
          onMoveScene={(id, direction) => updateSceneList((scenes) => {
            const index = scenes.findIndex((scene) => scene.id === id);
            const target = index + direction;
            if (index < 0 || target < 0 || target >= scenes.length) return scenes;
            const next = [...scenes];
            [next[index], next[target]] = [next[target], next[index]];
            return next;
          })}
          onCaptionDraftChange={setCaptionDraft}
          onPostCopyChange={setPostCopyDraft}
          onMetadataTitleChange={setMetadataTitleDraft}
          onMetadataSubtitleChange={setMetadataSubtitleDraft}
          onSeek={(seconds) => setSeekRequest({id: Date.now(), seconds})}
          onTogglePlayback={() => setPlaybackRequest({id: Date.now(), action: "toggle"})}
          onPlaybackChange={setIsPlaying}
          onTimeChange={setCurrentSeconds}
          onRemovePause={(pause) => {
            if (captionsDirty) {
              window.alert("Save or discard caption text edits before removing a pause.");
              return;
            }
            if (rendering) {
              window.alert("Wait for the current render to finish before removing another pause.");
              return;
            }
            void runAction(
              `clip:${clip.id}:remove-pause`,
              "Removing pause…",
              async () => {
                type RemovePauseResult = {
                  captions: NonNullable<ClipCandidate["captions"]>;
                  removed_ms?: number;
                  rerender_job?: {id?: string; status?: string; error?: string; message?: string; progress?: number};
                  rerender_error?: string;
                };
                const result = await apiPost<RemovePauseResult>("remove-pause", {
                  candidate_id: clip.id,
                  pause_at_ms: pause.atMs,
                  gap_ms: pause.gapMs,
                  rerender_after: true,
                  renderer: "hyperframes",
                  quality: "production",
                  style: "auto",
                });
                const nextCaptions = result.captions || [];
                const nextDraft = joinCaptionsFromSegments(nextCaptions);
                setClip((current) => (current ? {...current, captions: nextCaptions} : current));
                setCleanCaptionDraft(nextDraft);
                setCaptionDraft(nextDraft);
                setSeekRequest({id: Date.now(), seconds: Math.max(0, pause.atMs / 1000)});
                setPlaybackRequest({id: Date.now(), action: "pause"});
                if (result.rerender_error) {
                  throw new Error(result.rerender_error);
                }
                const nextContext = await apiGet<EditorContext>(`editor-context?candidate_id=${encodeURIComponent(clip.id)}`);
                const job = result.rerender_job;
                applyContext(
                  {
                    ...nextContext,
                    job: nextContext.job || (job?.id
                      ? {
                          job_id: job.id,
                          status: job.status || "queued",
                          error: job.error || "",
                          progress: job.progress,
                          message: job.message || "Re-rendering after pause removal…",
                        }
                      : nextContext.job),
                  },
                  false,
                );
              },
              "Pause removed. Re-render started — preview updates when ready.",
              false,
            );
          }}
          onBatchRemovePauses={(minGapMs) => {
            if (captionsDirty) {
              window.alert("Save or discard caption text edits before removing pauses.");
              return;
            }
            if (rendering) {
              window.alert("Wait for the current render to finish before removing pauses.");
              return;
            }
            void runAction(
              `clip:${clip.id}:remove-pauses-batch`,
              "Removing pauses…",
              async () => {
                type BatchResult = {
                  captions: NonNullable<ClipCandidate["captions"]>;
                  match_count?: number;
                  removed_ms?: number;
                  rerender_job?: {id?: string; status?: string; error?: string; message?: string; progress?: number};
                  rerender_error?: string;
                };
                const result = await apiPost<BatchResult>("remove-pauses-batch", {
                  candidate_id: clip.id,
                  min_gap_ms: minGapMs,
                  dry_run: false,
                  rerender_after: true,
                  renderer: "hyperframes",
                  quality: "production",
                  style: "auto",
                });
                const nextCaptions = result.captions || [];
                const nextDraft = joinCaptionsFromSegments(nextCaptions);
                setClip((current) => (current ? {...current, captions: nextCaptions} : current));
                setCleanCaptionDraft(nextDraft);
                setCaptionDraft(nextDraft);
                setSeekRequest({id: Date.now(), seconds: 0});
                setPlaybackRequest({id: Date.now(), action: "pause"});
                setActiveInspectorTab("silence");
                setInspectorPanelOpen(true);
                if (result.rerender_error) {
                  throw new Error(result.rerender_error);
                }
                const nextContext = await apiGet<EditorContext>(`editor-context?candidate_id=${encodeURIComponent(clip.id)}`);
                const job = result.rerender_job;
                applyContext(
                  {
                    ...nextContext,
                    job: nextContext.job || (job?.id
                      ? {
                          job_id: job.id,
                          status: job.status || "queued",
                          error: job.error || "",
                          progress: job.progress,
                          message: job.message || "Re-rendering after batch pause removal…",
                        }
                      : nextContext.job),
                  },
                  false,
                );
              },
              "Pauses removed. Re-render started — preview updates when ready.",
              false,
            );
          }}
          onGeneratePostCopy={() => void runAction(`post:${clip.id}:generate`, "Generating post copy…", async () => { const result = await apiPost<{post_caption: string}>("post-copy-generate", {candidate_id: clip.id, llm_provider: "deepseek"}); setPostCopyDraft(result.post_caption); }, "Post copy generated", false)}
          onRefreshMetadata={(rerenderAfter = false) =>
            void runAction(
              `clip:${clip.id}:metadata`,
              rerenderAfter ? "Refreshing metadata and re-rendering…" : "Refreshing metadata…",
              () => refreshMetadata(rerenderAfter),
              rerenderAfter ? "Metadata refreshed — re-render started" : "Metadata refreshed",
              !rerenderAfter,
            )
          }
          onSaveBoundary={(startMs, endMs, rerenderAfter) => void runAction(`clip:${clip.id}:boundary`, "Saving trim…", () => apiPost("clip-boundary", {candidate_id: clip.id, start_ms: startMs, end_ms: endMs, rerender_after: rerenderAfter, renderer: "hyperframes", quality: "production", style: "auto"}), "Trim saved")}
          onRerenderShort={() => {
            if (!context.can_rerender || context.capability !== "short") return;
            void runAction(
              `clip:${clip.id}:rerender`,
              "Starting re-render…",
              () => queueRerender(),
              "Re-render started — preview updates when ready.",
              false,
            );
          }}
          previewEpoch={previewEpoch}
        />
      </div>
    </main>
  );
}

function Unavailable() {
  return <main className="grid min-h-screen place-items-center bg-canvas-deep px-5 text-center"><div><p className="text-xs font-semibold uppercase tracking-[0.16em] text-danger">Review unavailable</p><h1 className="mt-3 text-2xl font-semibold text-white">This item or its editor context could not be loaded.</h1><Link href="/?section=review" className="mt-6 inline-flex rounded-full bg-cyan px-5 py-2.5 text-sm font-semibold text-ink">Back to Review</Link></div></main>;
}
