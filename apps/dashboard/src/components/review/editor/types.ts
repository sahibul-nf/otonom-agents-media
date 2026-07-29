import type {
  CaptionSegment,
  ClipCandidate,
  EditorCapability,
  EditorContext,
  ExplainerScene,
  ExplainerScenePlan,
  HyperframesTemplate,
} from "@/lib/media-api";
import type {PreviewPlaybackRequest, PreviewSeekRequest} from "@/components/review/PreviewPanel";

export type ActionState = {
  status: "running" | "done" | "failed";
  message: string;
};

export type InspectorTab = "scene" | "captions" | "trim" | "silence" | "metadata" | "post" | "qa";

export type EditorActionStates = Record<string, ActionState>;

export type ReviewEditorWorkspaceProps = {
  clip: ClipCandidate;
  context: EditorContext;
  draftPlan?: ExplainerScenePlan;
  templates: HyperframesTemplate[];
  selectedSceneId?: string;
  selectedCaptionIndex?: number;
  activeInspectorTab: InspectorTab;
  inspectorPanelOpen: boolean;
  captionDraft: string;
  postCopyDraft: string;
  currentSeconds: number;
  seekRequest?: PreviewSeekRequest;
  playbackRequest?: PreviewPlaybackRequest;
  isPlaying: boolean;
  dirty: boolean;
  rendering: boolean;
  actionStates: EditorActionStates;
  onSelectScene: (sceneId: string) => void;
  onSelectCaption: (index: number) => void;
  onHighlightCaption: (index: number) => void;
  onInspectorTabChange: (tab: InspectorTab) => void;
  onInspectorPanelOpenChange: (open: boolean) => void;
  onPlanChange: (plan: ExplainerScenePlan) => void;
  onAddScene: () => void;
  onDuplicateScene: (sceneId: string) => void;
  onDeleteScene: (sceneId: string) => void;
  onMoveScene: (sceneId: string, direction: -1 | 1) => void;
  onCaptionDraftChange: (value: string) => void;
  onPostCopyChange: (value: string) => void;
  onSeek: (seconds: number) => void;
  onTogglePlayback: () => void;
  onPlaybackChange: (playing: boolean) => void;
  onTimeChange: (seconds: number) => void;
  onRemovePause: (pause: {atMs: number; gapMs: number; afterCueIndex: number}) => void;
  onGeneratePostCopy: () => void;
  onRefreshMetadata: () => void;
  onSaveBoundary: (startMs: number, endMs: number, rerenderAfter: boolean) => void;
  onRerenderShort: () => void;
  onBatchRemovePauses: (minGapMs: number) => void;
  previewEpoch?: number;
};

export function isRenderingContext(context?: EditorContext) {
  return Boolean(context?.job && ["queued", "running", "rendering", "processing"].includes(context.job.status));
}

export function sceneDurationSeconds(scene: ExplainerScene) {
  return Number.isFinite(scene.duration_target) ? Math.max(1, scene.duration_target) : 1;
}

export function totalSceneDuration(plan?: ExplainerScenePlan) {
  return plan?.scenes.reduce((total, scene) => total + sceneDurationSeconds(scene), 0) || 0;
}

export function capabilityLabel(capability: EditorCapability) {
  switch (capability) {
    case "scene":
      return "AI scene edit";
    case "short":
      return "Short-form edit";
    case "imported_longform":
      return "Long-form review";
    default: {
      const exhaustive: never = capability;
      return exhaustive;
    }
  }
}

export function captionRelativeSeconds(clip: ClipCandidate, caption: CaptionSegment) {
  const offset = caption.startMs >= Math.max(0, clip.start_ms - 1_000) ? clip.start_ms : 0;
  return Math.max(0, caption.startMs - offset) / 1_000;
}

/** Join timed captions into one continuous paragraph for the Script rail. */
export function joinCaptionDocument(texts: string[]) {
  return texts.map((text) => text.replace(/\s+/g, " ").trim()).filter(Boolean).join(" ");
}

export function joinCaptionsFromSegments(captions: CaptionSegment[]) {
  return joinCaptionDocument(captions.map((caption) => caption.text));
}

/** Minimum silence between cues before we show an inline Pause chip (ms). */
export const CAPTION_PAUSE_GAP_MS = 450;

export type CaptionWordTiming = {
  text: string;
  startMs: number;
  endMs: number;
  cueIndex: number;
};

export type CaptionPauseMark = {
  afterCueIndex: number;
  gapMs: number;
  atMs: number;
};

/**
 * Flatten caption words in timeline order (clip-relative ms).
 * Falls back to cue windows when word timings are missing.
 */
export function flattenCaptionWords(captions: CaptionSegment[]): CaptionWordTiming[] {
  const words: CaptionWordTiming[] = [];
  captions.forEach((caption, cueIndex) => {
    const timed = caption.words?.filter((word) => Number.isFinite(word.startMs) && Number.isFinite(word.endMs)) || [];
    if (timed.length) {
      timed.forEach((word) => {
        words.push({
          text: String(word.text || "").trim(),
          startMs: Number(word.startMs),
          endMs: Number(word.endMs),
          cueIndex,
        });
      });
      return;
    }
    const text = String(caption.text || "").trim();
    if (!text) return;
    words.push({
      text,
      startMs: caption.startMs,
      endMs: caption.endMs,
      cueIndex,
    });
  });
  return words;
}

/** Pause marks from word-level gaps (works even when cue windows are bridged). */
export function captionWordPauseMarks(
  captions: CaptionSegment[],
  minGapMs: number = CAPTION_PAUSE_GAP_MS,
): CaptionPauseMark[] {
  const words = flattenCaptionWords(captions);
  const marks: CaptionPauseMark[] = [];
  for (let index = 0; index < words.length - 1; index += 1) {
    const current = words[index];
    const next = words[index + 1];
    const gapMs = Math.max(0, next.startMs - current.endMs);
    if (gapMs < minGapMs) continue;
    marks.push({
      afterCueIndex: current.cueIndex,
      gapMs,
      atMs: current.endMs,
    });
  }
  return marks;
}

/** True when at least one cue carries real word timings (karaoke-capable). */
export function captionsHaveWordTimings(captions: CaptionSegment[]) {
  return captions.some((caption) => Boolean(caption.words?.some((word) => Number.isFinite(word.startMs) && Number.isFinite(word.endMs))));
}

/**
 * Index into `flattenCaptionWords(captions)` for the spoken word at `ms`.
 * Returns undefined when word timings are missing.
 */
export function activeCaptionWordIndexAtMs(captions: CaptionSegment[], ms: number): number | undefined {
  if (!captionsHaveWordTimings(captions)) return undefined;
  const words = flattenCaptionWords(captions);
  if (!words.length) return undefined;
  const t = Math.max(0, ms);
  const exact = words.findIndex((word) => t >= word.startMs && t < word.endMs);
  if (exact >= 0) return exact;
  if (t < words[0].startMs) return 0;
  for (let index = words.length - 1; index >= 0; index -= 1) {
    if (t >= words[index].startMs) return index;
  }
  return words.length - 1;
}

/**
 * Split a continuous caption draft into per-cue text slices using the same
 * duration weighting as redistribute-on-save.
 */
export function splitCaptionDocumentTexts(base: CaptionSegment[], draft: string): string[] {
  if (!base.length) return [];
  const words = draft.replace(/\s+/g, " ").trim().split(" ").filter(Boolean);
  if (base.length === 1) return [words.join(" ")];

  const weights = base.map((caption) => Math.max(1, caption.endMs - caption.startMs));
  const totalWeight = weights.reduce((sum, weight) => sum + weight, 0);
  const counts = allocateByWeight(words.length, weights, totalWeight);

  let offset = 0;
  return counts.map((count) => {
    const text = words.slice(offset, offset + count).join(" ");
    offset += count;
    return text;
  });
}

/**
 * Map a continuous caption draft back onto the original timed cues.
 * Words are allocated by cue duration so timing windows stay intact.
 */
export function redistributeCaptionDocument(base: CaptionSegment[], draft: string): CaptionSegment[] {
  if (!base.length) return [];
  const texts = splitCaptionDocumentTexts(base, draft);
  return base.map((caption, index) => ({
    ...caption,
    text: texts[index] || "",
    timestampMs: caption.timestampMs ?? caption.startMs,
  }));
}

/** Gap after cue `index` before the next cue starts (0 if last or no gap). */
export function captionGapAfterMs(captions: CaptionSegment[], index: number) {
  const current = captions[index];
  const next = captions[index + 1];
  if (!current || !next) return 0;
  return Math.max(0, next.startMs - current.endMs);
}

export function captionIndexAtDocumentOffset(base: CaptionSegment[], draft: string, offset: number) {
  if (!base.length) return 0;
  const words = draft.replace(/\s+/g, " ").trim().split(" ").filter(Boolean);
  if (!words.length) return 0;

  const clamped = Math.max(0, Math.min(offset, draft.length));
  const prefix = draft.slice(0, clamped).replace(/\s+/g, " ").trim();
  const wordIndex = prefix ? prefix.split(" ").filter(Boolean).length - 1 : 0;

  const weights = base.map((caption) => Math.max(1, caption.endMs - caption.startMs));
  const totalWeight = weights.reduce((sum, weight) => sum + weight, 0);
  const counts = allocateByWeight(words.length, weights, totalWeight);

  let cursor = 0;
  for (let index = 0; index < counts.length; index += 1) {
    cursor += counts[index] ?? 0;
    if (wordIndex < cursor) return index;
  }
  return base.length - 1;
}

export function captionIndexAtSeconds(clip: ClipCandidate, captions: CaptionSegment[], seconds: number) {
  if (!captions.length) return undefined;
  const ms = seconds * 1_000;
  const offset = captions[0].startMs >= Math.max(0, clip.start_ms - 1_000) ? clip.start_ms : 0;
  const absolute = ms + offset;
  const match = captions.findIndex((caption) => absolute >= caption.startMs && absolute < caption.endMs);
  if (match >= 0) return match;
  if (absolute < captions[0].startMs) return 0;
  return captions.length - 1;
}

function allocateByWeight(total: number, weights: number[], totalWeight: number) {
  if (total <= 0) return weights.map(() => 0);
  const raw = weights.map((weight) => (weight / totalWeight) * total);
  const counts = raw.map((value) => Math.floor(value));
  let assigned = counts.reduce((sum, count) => sum + count, 0);
  const remainders = raw
    .map((value, index) => ({index, fraction: value - Math.floor(value)}))
    .sort((left, right) => right.fraction - left.fraction || left.index - right.index);
  let cursor = 0;
  while (assigned < total && remainders.length) {
    counts[remainders[cursor % remainders.length].index] += 1;
    assigned += 1;
    cursor += 1;
  }
  return counts;
}
