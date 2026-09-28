"use client";

import {CheckCircle2, Clapperboard,
  FileText,
  Loader2,
  Palette,
  RefreshCcw,
  Scissors,
  ShieldCheck,
  Sparkles,
  Timer,
  type LucideIcon,
} from "lucide-react";
import {useMemo, useState, type ReactNode} from "react";
import type {ClipCandidate, EditorContext, ExplainerScene, ExplainerScenePlan, HyperframesTemplate} from "@/lib/media-api";
import {clipAutonomyThreshold, clipHygieneFlags, clipHygieneGate, clipHygieneLabel, clipHygieneTone, clipMeetsAutonomyThreshold, clipOverallScore, savedBrandKitsForUi, templateSupportsFormat} from "@/lib/media-api";
import {qaCaptionPipelineLines, qaCaptionPipelineSummary} from "@/lib/caption-pipeline-status";
import type {BrandTemplate} from "@/lib/media-api";
import {CAPTION_PAUSE_GAP_MS, captionWordPauseMarks, editorLookFromContext, pendingLookDirty, pendingLookFromTemplate, type ActionState, type EditorActionStates, type InspectorTab, type PendingEditorLook} from "@/components/review/editor/types";
import {HyperframesTemplatePickerModal} from "@/components/templates/HyperframesTemplatePickerModal";
import {TemplatePreview} from "@/components/templates/TemplatePreview";

type Props = {
  clip: ClipCandidate;
  context: EditorContext;
  plan?: ExplainerScenePlan;
  selectedSceneId?: string;
  activeTab: InspectorTab;
  panelOpen: boolean;
  postCopyDraft: string;
  metadataTitleDraft: string;
  metadataSubtitleDraft: string;
  templates: HyperframesTemplate[];
  brandLibrary: BrandTemplate[];
  actionStates: EditorActionStates;
  onTabChange: (tab: InspectorTab) => void;
  onPanelOpenChange: (open: boolean) => void;
  onPlanChange: (plan: ExplainerScenePlan) => void;
  onPostCopyChange: (value: string) => void;
  onMetadataTitleChange: (value: string) => void;
  onMetadataSubtitleChange: (value: string) => void;
  onGeneratePostCopy: () => void;
  onRefreshMetadata: (rerenderAfter?: boolean) => void;
  onSaveBoundary: (startMs: number, endMs: number, rerenderAfter: boolean) => void;
  onRerenderShort: () => void;
  onBatchRemovePauses: (minGapMs: number) => void;
  pendingLook?: PendingEditorLook;
  onPendingLookChange?: (look: PendingEditorLook) => void;
};

export function SceneInspector(props: Props) {
  const tools = inspectorTools(props.context);
  const selectedScene = props.plan?.scenes.find((scene) => scene.id === props.selectedSceneId);
  const activeTool = tools.find((tool) => tool.id === props.activeTab) || tools[0];

  function selectTool(id: InspectorTab) {
    if (props.activeTab === id && props.panelOpen) {
      props.onPanelOpenChange(false);
      return;
    }
    props.onTabChange(id);
    props.onPanelOpenChange(true);
  }

  return (
    <aside className="flex h-full min-h-[240px] max-h-full shrink-0 lg:min-h-0 lg:py-3 lg:pr-3">
      {props.panelOpen ? (
        <div className="mr-2 flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/[0.05] bg-black/25 shadow-[0_12px_40px_rgba(0,0,0,0.28)] backdrop-blur-md lg:w-[300px] lg:flex-none">
          <div className="flex h-10 shrink-0 items-center justify-between px-4">
            <span className="text-[10px] font-medium uppercase tracking-[0.16em] text-zinc-600">{activeTool?.label || "Tools"}</span>
            <button
              type="button"
              onClick={() => props.onPanelOpenChange(false)}
              className="text-[11px] font-medium text-zinc-600 transition hover:text-zinc-300"
            >
              Hide
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
            {props.activeTab === "scene" && selectedScene && props.plan ? <SceneFields {...props} scene={selectedScene} plan={props.plan} /> : null}
            {props.activeTab === "trim" ? <TrimFields clip={props.clip} state={props.actionStates[`clip:${props.clip.id}:boundary`]} onSave={props.onSaveBoundary} /> : null}
            {props.activeTab === "silence" ? (
              <SilenceFields
                clip={props.clip}
                state={props.actionStates[`clip:${props.clip.id}:remove-pauses-batch`]}
                onApply={props.onBatchRemovePauses}
              />
            ) : null}
            {props.activeTab === "look" && props.pendingLook && props.onPendingLookChange ? (
              <LookFields
                context={props.context}
                templates={props.templates}
                brandLibrary={props.brandLibrary}
                pendingLook={props.pendingLook}
                rerenderState={props.actionStates[`clip:${props.clip.id}:rerender`]}
                onPendingLookChange={props.onPendingLookChange}
                onRerenderShort={props.onRerenderShort}
              />
            ) : null}
            {props.activeTab === "metadata" ? <MetadataFields {...props} /> : null}
            {props.activeTab === "post" ? <PostFields {...props} /> : null}
            {props.activeTab === "qa" ? <QaFields clip={props.clip} context={props.context} /> : null}
          </div>
        </div>
      ) : null}

      <nav
        className="flex w-full gap-1 overflow-x-auto rounded-2xl border border-white/[0.05] bg-black/25 p-1.5 shadow-[0_12px_40px_rgba(0,0,0,0.22)] backdrop-blur-md lg:w-14 lg:flex-col lg:overflow-x-visible lg:overflow-y-auto"
        aria-label="Editor tools"
      >
        {tools.map((tool) => {
          const active = props.panelOpen && props.activeTab === tool.id;
          const Icon = tool.icon;
          return (
            <button
              key={tool.id}
              type="button"
              onClick={() => selectTool(tool.id)}
              aria-pressed={active}
              title={tool.label}
              className={`flex min-w-[3.75rem] flex-col items-center gap-1 rounded-xl px-1.5 py-2 transition lg:min-w-0 lg:w-full ${
                active
                  ? "bg-cyan/[0.12] text-cyan"
                  : "text-zinc-500 hover:bg-white/[0.05] hover:text-zinc-200"
              }`}
            >
              <Icon className="h-4 w-4" />
              <span className="text-[8px] font-medium leading-tight tracking-wide">{tool.short}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}

function inspectorTools(context: EditorContext): {id: InspectorTab; label: string; short: string; icon: LucideIcon}[] {
  if (context.capability === "scene") {
    return [
      {id: "scene", label: "Scene", short: "Scene", icon: Clapperboard},
      {id: "metadata", label: "Metadata", short: "Meta", icon: FileText},
      {id: "post", label: "Post copy", short: "Post", icon: Sparkles},
      {id: "qa", label: "QA", short: "QA", icon: ShieldCheck},
    ];
  }
  if (context.capability === "short") {
    const tools: {id: InspectorTab; label: string; short: string; icon: LucideIcon}[] = [];
    if (context.can_trim) tools.push({id: "trim", label: "Trim", short: "Trim", icon: Scissors});
    tools.push(
      {id: "silence", label: "Silence", short: "Pause", icon: Timer},
      {id: "look", label: "Look", short: "Look", icon: Palette},
      {id: "metadata", label: "Metadata", short: "Meta", icon: FileText},
      {id: "post", label: "Post copy", short: "Post", icon: Sparkles},
      {id: "qa", label: "QA", short: "QA", icon: ShieldCheck},
    );
    return tools;
  }
  return [
    {id: "metadata", label: "Metadata", short: "Meta", icon: FileText},
    {id: "post", label: "Post copy", short: "Post", icon: Sparkles},
    {id: "qa", label: "QA", short: "QA", icon: ShieldCheck},
  ];
}

function SceneFields({scene, plan, context, templates, onPlanChange}: Props & {scene: ExplainerScene; plan: ExplainerScenePlan}) {
  const disabled = !context.can_edit_scenes;
  const update = (patch: Partial<ExplainerScene>) => onPlanChange({...plan, scenes: plan.scenes.map((item) => item.id === scene.id ? {...item, ...patch} : item)});
  const templateEntries: [string, {id: string; label: string}][] = templates.map(
    (item): [string, {id: string; label: string}] => [item.id, {id: item.id, label: item.label}],
  );
  const templateOptions = Array.from(new Map(templateEntries).values());
  return (
    <div className="grid gap-4">
      <p className="text-sm leading-6 text-zinc-500">Type the main scene text in the Script list. Use this panel for secondary settings.</p>
      <Field label="Narration">
        <textarea value={scene.narration || ""} disabled={disabled} onChange={(event) => update({narration: event.target.value})} className={`${inputClass} min-h-28 py-3`} placeholder="Voice-over narration" />
      </Field>
      {scene.type === "avatar" ? (
        <Field label="Headline">
          <input value={scene.headline || ""} disabled={disabled} onChange={(event) => update({headline: event.target.value})} className={inputClass} placeholder="Optional on-screen headline" />
        </Field>
      ) : (
        <Field label="Script notes">
          <textarea value={scene.script || ""} disabled={disabled} onChange={(event) => update({script: event.target.value})} className={`${inputClass} min-h-24 py-3`} placeholder="Optional direction notes" />
        </Field>
      )}
      <Field label="Template">
        <select value={scene.template || ""} disabled={disabled} onChange={(event) => update({template: event.target.value || undefined})} className={inputClass}>
          <option value="">Use plan default</option>
          {templateOptions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
      </Field>
      {scene.clip_file || scene.audio_file ? (
        <p className="text-xs leading-5 text-zinc-500">Existing generated clip and audio references stay attached when this plan is saved.</p>
      ) : null}
    </div>
  );
}

function TrimFields({clip, state, onSave}: {clip: ClipCandidate; state?: ActionState; onSave: Props["onSaveBoundary"]}) {
  const [start, setStart] = useState(clip.start_ms);
  const [end, setEnd] = useState(clip.end_ms);
  const valid = end > start;
  return (
    <div className="grid gap-4">
      <Field label="Start (seconds)"><input type="number" min={0} step={0.5} value={start / 1000} onChange={(event) => setStart(Math.round(Number(event.target.value) * 1000))} className={inputClass} /></Field>
      <Field label="End (seconds)"><input type="number" min={0} step={0.5} value={end / 1000} onChange={(event) => setEnd(Math.round(Number(event.target.value) * 1000))} className={inputClass} /></Field>
      {!valid ? <p className="text-xs text-danger">End must be after start.</p> : null}
      <button type="button" disabled={!valid || state?.status === "running"} onClick={() => onSave(start, end, true)} className={primaryButton}>
        {state?.status === "running" ? "Applying…" : "Apply trim"}
      </button>
    </div>
  );
}

function SilenceFields({
  clip,
  state,
  onApply,
}: {
  clip: ClipCandidate;
  state?: ActionState;
  onApply: (minGapMs: number) => void;
}) {
  const [thresholdSeconds, setThresholdSeconds] = useState(0.5);
  const minGapMs = Math.round(thresholdSeconds * 1000);
  const marks = useMemo(
    () => captionWordPauseMarks(clip.captions || [], Math.max(40, minGapMs || CAPTION_PAUSE_GAP_MS)),
    [clip.captions, minGapMs],
  );
  const removableMs = marks.reduce((total, mark) => total + Math.max(0, mark.gapMs - 140), 0);
  const valid = minGapMs >= 40;
  const busy = state?.status === "running";

  return (
    <div className="grid gap-4">
      <p className="text-sm leading-6 text-zinc-500">
        Remove every Pause chip at or above a threshold — same keep-plan path as single Remove Pause.
      </p>
      <Field label="Remove gaps ≥ (seconds)">
        <input
          type="number"
          min={0.04}
          step={0.1}
          value={thresholdSeconds}
          onChange={(event) => setThresholdSeconds(Number(event.target.value) || 0)}
          className={inputClass}
        />
      </Field>
      {!valid ? <p className="text-xs text-danger">Threshold must be at least 0.04s.</p> : null}
      <div className="rounded-2xl border border-white/[0.05] bg-white/[0.02] px-3.5 py-3">
        <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-zinc-600">Preview</p>
        <p className="mt-2 text-sm text-zinc-100">
          <span className="font-semibold tabular-nums text-cyan">{marks.length}</span> pause
          {marks.length === 1 ? "" : "s"} match
        </p>
        <p className="mt-1 text-xs tabular-nums text-zinc-500">
          ~{formatRemovedLabel(removableMs)} removable (keeps ~140ms breath each)
        </p>
      </div>
      {state?.message ? (
        <p className={`text-xs ${state.status === "failed" ? "text-danger" : state.status === "done" ? "text-cyan" : "text-warning"}`}>
          {state.message}
        </p>
      ) : null}
      <button
        type="button"
        disabled={!valid || busy || marks.length === 0}
        onClick={() => onApply(minGapMs)}
        className={primaryButton}
      >
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Timer className="h-4 w-4" />}
        {busy ? "Removing…" : marks.length ? `Remove ${marks.length} pause${marks.length === 1 ? "" : "s"}` : "No matches"}
      </button>
    </div>
  );
}

function formatRemovedLabel(ms: number) {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(ms >= 10_000 ? 0 : 1)}s`;
}

function mergeBrandTemplatesForLook(
  templates: HyperframesTemplate[],
  brandLibrary: BrandTemplate[],
  look?: EditorContext["look"],
): HyperframesTemplate[] {
  const items = savedBrandKitsForUi(templates, brandLibrary);
  const byId = new Map(items.map((item) => [item.id, item]));
  const brandId = (look?.brand_system_template_id || "").trim();
  if (brandId.startsWith("brand:") && !byId.has(brandId)) {
    byId.set(brandId, {
      id: brandId,
      label: look?.label || brandId.replace("brand:", "").replace(/_/g, " "),
      category: "Brand",
      best_for: "Saved brand system template",
      effects: [],
      caption_style: "Brand captions",
      default_genres: [],
      status: "ready",
      tone: "Brand",
      source: "brand_system",
      brand_template_path: look?.brand_template_path,
      formats: ["short_9_16", "long_16_9"],
    });
  }
  return [...byId.values()];
}

function LookFields({
  context,
  templates,
  brandLibrary,
  pendingLook,
  rerenderState,
  onPendingLookChange,
  onRerenderShort,
}: {
  context: EditorContext;
  templates: HyperframesTemplate[];
  brandLibrary: BrandTemplate[];
  pendingLook: PendingEditorLook;
  rerenderState?: ActionState;
  onPendingLookChange: (look: PendingEditorLook) => void;
  onRerenderShort: () => void;
}) {
  const lookBaseline = useMemo(() => editorLookFromContext(context.look), [context.look]);
  const brandTemplates = useMemo(
    () => mergeBrandTemplatesForLook(templates, brandLibrary, context.look),
    [templates, brandLibrary, context.look],
  );
  const recipeTemplates = useMemo(
    () => templates.filter((item) => item.source !== "brand_system" && templateSupportsFormat(item, "short_9_16")),
    [templates],
  );
  const [presetPickerOpen, setPresetPickerOpen] = useState(false);
  const [brandPickerOpen, setBrandPickerOpen] = useState(false);
  const lookDirty = pendingLookDirty(pendingLook, lookBaseline);
  const activeId = lookDirty
    ? (pendingLook.brand_system_template_id || pendingLook.hyperframes_template)
    : "";
  const previewTemplate = lookDirty
    ? (templates.find((item) => item.id === activeId) || brandTemplates.find((item) => item.id === activeId))
    : undefined;
  const rendering = Boolean(context.job && ["queued", "running", "rendering", "processing"].includes(context.job.status));
  const rerendering = rerenderState?.status === "running" || rendering;
  const locked = !context.can_rerender || rerendering;
  const selectedLabel = lookDirty ? pendingLook.label : (context.look?.label || "Default look");

  return (
    <div className="grid gap-3">
      <div className="rounded-2xl border border-white/[0.06] bg-black/25 px-3 py-2.5">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-500">On this clip</p>
        <p className="mt-1 truncate text-sm font-semibold text-white">{context.look?.label || "Default look"}</p>
        <p className="mt-1 text-[11px] leading-4 text-zinc-500">Captions and trim stay. Re-render only swaps the visual style.</p>
      </div>

      <div className="grid gap-2">
        <button
          type="button"
          disabled={locked}
          onClick={() => setPresetPickerOpen(true)}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-full border border-cyan/[0.24] bg-black/20 px-3 text-xs font-semibold text-cyan disabled:opacity-40"
        >
          <Sparkles className="h-3.5 w-3.5" />
          Browse preset templates
        </button>
        <button
          type="button"
          disabled={locked}
          onClick={() => setBrandPickerOpen(true)}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-full border border-white/[0.10] bg-white/[0.04] px-3 text-xs font-semibold text-zinc-200 disabled:opacity-40 hover:border-cyan/[0.22] hover:text-white"
        >
          <Palette className="h-3.5 w-3.5" />
          Browse saved brands ({brandTemplates.length})
        </button>
      </div>

      <div className="rounded-2xl border border-white/[0.06] bg-black/20 px-3 py-2.5">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-500">Selected for re-render</p>
        <p className="mt-1 truncate text-sm font-semibold text-white">{selectedLabel}</p>
        {lookDirty ? (
          <button type="button" onClick={() => onPendingLookChange(editorLookFromContext(context.look))} disabled={locked} className="mt-2 text-[11px] font-semibold text-zinc-500 hover:text-zinc-300">
            Reset to current look
          </button>
        ) : (
          <p className="mt-1 text-[11px] text-zinc-600">Pick a preset or brand above to change the look.</p>
        )}
      </div>

      {lookDirty && previewTemplate ? (
        <div className="overflow-hidden rounded-2xl border border-white/[0.06] bg-black/30">
          <TemplatePreview template={previewTemplate} compact frame="short" gridCard hideFooterLabel spacing="none" flush />
        </div>
      ) : null}

      {rerenderState?.message && rerenderState.status !== "running" ? (
        <p className={`text-xs ${rerenderState.status === "failed" ? "text-danger" : "text-cyan"}`}>{rerenderState.message}</p>
      ) : null}
      <button type="button" onClick={onRerenderShort} disabled={locked || !lookDirty} className={secondaryButton}>
        {rerendering ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
        {rerendering ? "Rendering…" : "Re-render with this look"}
      </button>

      <HyperframesTemplatePickerModal
        open={presetPickerOpen}
        title="Choose preset template"
        subtitle="Built-in recipes for caption motion, grade, and overlays."
        templates={recipeTemplates}
        selectedId={lookDirty && !pendingLook.brand_system_template_id ? activeId : undefined}
        frame="short"
        onClose={() => setPresetPickerOpen(false)}
        onSelect={(template) => {
          onPendingLookChange(pendingLookFromTemplate(template));
          setPresetPickerOpen(false);
        }}
      />
      <HyperframesTemplatePickerModal
        open={brandPickerOpen}
        title="Choose saved brand"
        subtitle="Watermark, fonts, CTA, and starter recipe from Brand Builder."
        templates={brandTemplates}
        selectedId={lookDirty ? pendingLook.brand_system_template_id || undefined : undefined}
        frame="short"
        onClose={() => setBrandPickerOpen(false)}
        onSelect={(template) => {
          onPendingLookChange(pendingLookFromTemplate(template));
          setBrandPickerOpen(false);
        }}
      />
    </div>
  );
}

function MetadataFields(props: Props) {
  const metadataState = props.actionStates[`clip:${props.clip.id}:metadata`];
  const canRerender = props.context.capability === "short" && props.context.can_rerender;
  const rendering = Boolean(props.context.job && ["queued", "running", "rendering", "processing"].includes(props.context.job.status));
  const busy = metadataState?.status === "running" || rendering;
  const titleSource = String(props.clip.curation_metadata?.title_source || "");
  const subtitleSource = String(props.clip.curation_metadata?.subtitle_source || "");
  const heuristicHook = titleSource === "heuristic_span" || subtitleSource === "heuristic_span";
  const manualHook = titleSource === "manual_edit" || subtitleSource === "manual_edit";

  return (
    <div className="grid gap-5">
      <Field label="Title">
        <input
          value={props.metadataTitleDraft}
          maxLength={160}
          disabled={busy}
          onChange={(event) => props.onMetadataTitleChange(event.target.value)}
          className={inputClass}
          placeholder="On-video hook title"
        />
      </Field>
      <Field label="Description">
        <textarea
          value={props.metadataSubtitleDraft}
          maxLength={500}
          disabled={busy}
          onChange={(event) => props.onMetadataSubtitleChange(event.target.value)}
          className={`${inputClass} min-h-[5.5rem] py-3`}
          placeholder="Warm subtitle shown in metadata and overlays"
        />
      </Field>
      <p className="text-sm leading-6 text-zinc-500">
        Use <span className="font-semibold text-zinc-300">Save changes</span> in the header to keep edits. After you change the hook title, use{" "}
        <span className="font-semibold text-zinc-300">Re-render</span> so the rendered video updates.
      </p>
      {heuristicHook && !manualHook ? (
        <p className="text-sm leading-6 text-amber-100/90">
          Hook copy was auto-generated from transcript. Edit above or refresh with AI.
        </p>
      ) : null}
      {!canRerender && !heuristicHook ? (
        <p className="text-sm leading-6 text-zinc-500">Regenerate hook title and description from the transcript with AI.</p>
      ) : null}
      <button type="button" onClick={() => props.onRefreshMetadata(false)} disabled={busy} className={primaryButton}>
        {metadataState?.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
        {metadataState?.status === "running" ? "Refreshing…" : "Refresh metadata"}
      </button>
      {metadataState?.message && metadataState.status !== "running" ? (
        <p className={`text-sm ${metadataState.status === "failed" ? "text-danger" : "text-cyan"}`}>{metadataState.message}</p>
      ) : null}
    </div>
  );
}

function PostFields(props: Props) {
  const generateState = props.actionStates[`post:${props.clip.id}:generate`];
  return (
    <div className="grid gap-4">
      <textarea value={props.postCopyDraft} maxLength={400} onChange={(event) => props.onPostCopyChange(event.target.value)} className={`${inputClass} min-h-48 py-3`} placeholder="Cross-platform post copy" />
      <p className="text-right text-[10px] tabular-nums text-zinc-600">{props.postCopyDraft.length}/400</p>
      <p className="text-xs leading-5 text-zinc-500">Use Save changes in the header to keep post copy with the rest of your edits.</p>
      <button type="button" onClick={props.onGeneratePostCopy} disabled={generateState?.status === "running"} className={secondaryButton}>
        <Sparkles className="h-4 w-4" /> {generateState?.status === "running" ? "Generating…" : "Generate with AI"}
      </button>
    </div>
  );
}

function QaFields({clip, context}: {clip: ClipCandidate; context: EditorContext}) {
  const checks = clip.quality_gate?.checks || {};
  const scores = clip.quality_gate?.scores || {};
  const thresholds = clip.quality_gate?.thresholds || clip.quality_gate?.settings || {};
  const overall = clipOverallScore(clip);
  const autoQualified = clipMeetsAutonomyThreshold(clip);
  const overallThreshold = clipAutonomyThreshold(clip);
  const hygieneGate = clipHygieneGate(clip);
  const hygieneFlags = clipHygieneFlags(clip);
  const breakdown = [
    {label: "Hook", value: scores.hook ?? clip.score?.hook_score, threshold: thresholds.hook ?? thresholds.hook_threshold},
    {label: "Pacing", value: scores.pacing ?? clip.score?.pacing_score, threshold: null},
    {label: "Niche resonance", value: scores.resonance ?? scores.viral ?? clip.score?.resonance_score ?? clip.score?.viral_score, threshold: null},
    {label: "Context payoff", value: clip.score?.context_score, threshold: null},
    {label: "Retention", value: scores.retention ?? clip.score?.retention_score, threshold: null},
    {
      label: "ASR confidence",
      value: scores.caption ?? clip.score?.caption_confidence ?? clip.score?.asr_confidence,
      threshold: thresholds.caption ?? thresholds.caption_threshold,
    },
    {label: "Boundary", value: scores.boundary, threshold: thresholds.boundary ?? thresholds.boundary_threshold},
  ].filter((item) => typeof item.value === "number");
  const pipelineLines = qaCaptionPipelineLines(clip);
  const pipelineSummary = qaCaptionPipelineSummary(clip);

  return (
    <div className="grid gap-4">
      {overall != null ? (
        <div
          className={`rounded-2xl border px-4 py-3 ${
            autoQualified ? "border-teal/[0.28] bg-teal/[0.08]" : "border-amber-400/25 bg-amber-500/10"
          }`}
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Performance score</p>
              <p className="mt-1 text-2xl font-bold tabular-nums text-white">{overall}</p>
            </div>
            <div className="text-right">
              <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Threshold</p>
              <p className="mt-1 text-sm font-semibold tabular-nums text-zinc-300">{overallThreshold}</p>
            </div>
          </div>
          {hygieneGate ? (
            <p className={`mt-3 inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold ${clipHygieneTone(hygieneGate)}`}>
              {clipHygieneLabel(hygieneGate)}
            </p>
          ) : null}
          {hygieneFlags.length ? (
            <p className="mt-2 text-[11px] leading-5 text-zinc-500">Hygiene flags: {hygieneFlags.join(", ")}</p>
          ) : null}
          <p className={`mt-2 inline-flex items-center gap-1.5 text-xs font-semibold ${autoQualified ? "text-teal" : "text-warning"}`}>
            {autoQualified ? <CheckCircle2 className="h-3.5 w-3.5" /> : null}
            {autoQualified ? "Auto-qualified for autonomy" : "Below autonomy threshold — manual review"}
          </p>
          {clip.status === "pending_auto_schedule" ? (
            <p className="mt-1 text-[11px] text-zinc-500">Pending auto-schedule after grace window.</p>
          ) : null}
        </div>
      ) : null}
      {breakdown.length ? (
        <ul className="grid gap-2">
          {breakdown.map((item) => {
            const passed = item.threshold == null || Number(item.value) >= Number(item.threshold);
            return (
              <li key={item.label} className="flex items-center justify-between border-b border-white/[0.05] py-2 text-xs last:border-b-0">
                <span className="text-zinc-300">{item.label}</span>
                <span className={passed ? "text-teal" : "text-warning"}>
                  {item.value}
                  {item.threshold != null ? ` / ${item.threshold}` : ""}
                </span>
              </li>
            );
          })}
        </ul>
      ) : null}
      {pipelineLines.length ? (
        <div className="rounded-2xl border border-white/[0.08] bg-black/20 px-4 py-3">
          <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">AI & captions</p>
          {pipelineSummary ? (
            <p className="mt-2 text-[11px] leading-5 text-amber-100/90">{pipelineSummary}</p>
          ) : null}
          <ul className="mt-3 grid gap-1.5">
            {pipelineLines.map((item) => (
              <li key={item.label} className="flex items-start justify-between gap-3 text-[11px] leading-5">
                <span className="shrink-0 text-zinc-500">{item.label}</span>
                <span
                  className={`text-right ${item.tone === "ok" ? "text-teal" : item.tone === "warn" ? "text-amber-200" : "text-zinc-400"}`}
                >
                  {item.value}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <p className="text-sm leading-6 text-zinc-400">Check the opening, cuts, captions, audio, and final frame before approval.</p>
      {Object.keys(checks).length ? (
        <ul className="grid gap-2">
          {Object.entries(checks).map(([label, passed]) => (
            <li key={label} className="flex items-center justify-between border-b border-white/[0.05] py-2 text-xs last:border-b-0">
              <span className="text-zinc-300">{label.replaceAll("_", " ")}</span>
              <span className={passed ? "text-teal" : "text-warning"}>{passed ? "Pass" : "Review"}</span>
            </li>
          ))}
        </ul>
      ) : (
        <Empty text="No automated QA checks were returned. Complete a manual review." />
      )}
      {context.job?.error ? <p className="text-xs leading-5 text-danger">{context.job.error}</p> : null}
    </div>
  );
}

function Field({label, children}: {label: string; children: ReactNode}) {
  return (
    <label className="grid gap-2.5 text-sm font-semibold text-zinc-400">
      <span>{label}</span>
      {children}
    </label>
  );
}

function Empty({text}: {text: string}) {
  return <p className="py-6 text-center text-xs leading-5 text-zinc-500">{text}</p>;
}

const inputClass =
  "w-full min-h-11 rounded-2xl border border-white/[0.08] bg-white/[0.04] px-4 py-2.5 text-[15px] leading-6 text-zinc-100 outline-none transition focus:border-cyan/[0.28] focus:bg-white/[0.05] disabled:cursor-not-allowed disabled:opacity-50";
const readOnlyFieldClass =
  "w-full rounded-2xl border border-white/[0.08] bg-white/[0.04] px-4 py-3 text-[15px] leading-6 text-zinc-100";
const primaryButton =
  "inline-flex h-11 w-full items-center justify-center gap-2 rounded-full bg-cyan px-4 text-sm font-bold text-ink shadow-[0_10px_24px_rgba(102,232,249,0.16)] disabled:cursor-not-allowed disabled:opacity-45";
const secondaryButton =
  "inline-flex h-11 w-full items-center justify-center gap-2 rounded-full border border-white/[0.10] px-4 text-sm font-semibold text-zinc-200 transition hover:border-cyan/[0.28] hover:text-white disabled:cursor-not-allowed disabled:opacity-45";
