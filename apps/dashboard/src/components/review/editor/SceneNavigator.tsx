"use client";

import {ArrowDown, ArrowUp, Copy, Plus, Trash2} from "lucide-react";
import {useLayoutEffect, useRef, type ReactNode} from "react";
import {CaptionInteractiveDocument} from "@/components/review/editor/CaptionInteractiveDocument";
import {captionRelativeSeconds, joinCaptionsFromSegments, type ActionState} from "@/components/review/editor/types";
import {
  formatTimestamp,
  type ClipCandidate,
  type EditorContext,
  type ExplainerScene,
  type ExplainerScenePlan,
} from "@/lib/media-api";

type Props = {
  clip: ClipCandidate;
  context: EditorContext;
  plan?: ExplainerScenePlan;
  captionDraft: string;
  selectedSceneId?: string;
  selectedCaptionIndex?: number;
  currentSeconds: number;
  isPlaying: boolean;
  onSelectScene: (id: string) => void;
  onSelectCaption: (index: number) => void;
  onHighlightCaption: (index: number) => void;
  onPlanChange: (plan: ExplainerScenePlan) => void;
  onCaptionDraftChange: (value: string) => void;
  onSeek: (seconds: number) => void;
  onTogglePlayback: () => void;
  onRemovePause?: (pause: {atMs: number; gapMs: number; afterCueIndex: number}) => void;
  removePauseState?: ActionState;
  onAddScene: () => void;
  onDuplicateScene: (id: string) => void;
  onDeleteScene: (id: string) => void;
  onMoveScene: (id: string, direction: -1 | 1) => void;
};

export function SceneNavigator({
  clip,
  context,
  plan,
  captionDraft,
  selectedSceneId,
  selectedCaptionIndex,
  currentSeconds,
  isPlaying,
  onSelectScene,
  onSelectCaption,
  onHighlightCaption,
  onPlanChange,
  onCaptionDraftChange,
  onSeek,
  onTogglePlayback,
  onRemovePause,
  removePauseState,
  onAddScene,
  onDuplicateScene,
  onDeleteScene,
  onMoveScene,
}: Props) {
  const title = context.capability === "scene" ? "Script" : context.capability === "short" ? "Captions" : "Transcript";
  const canEditScenes = context.capability === "scene" && context.can_edit_scenes;
  const canEditCaptions = context.capability === "short";
  const captions = clip.captions || [];
  const activeCaption = selectedCaptionIndex !== undefined ? captions[selectedCaptionIndex] : undefined;

  function updateScene(sceneId: string, patch: Partial<ExplainerScene>) {
    if (!plan) return;
    onPlanChange({
      ...plan,
      scenes: plan.scenes.map((scene) => (scene.id === sceneId ? {...scene, ...patch} : scene)),
    });
  }

  return (
    <aside className="flex h-full min-h-0 flex-col">
      <div className="flex h-10 shrink-0 items-center justify-between gap-3 px-4">
        <span className="text-[10px] font-medium uppercase tracking-[0.16em] text-zinc-600">{title}</span>
        {canEditScenes ? (
          <button type="button" onClick={onAddScene} className="text-[11px] font-medium text-zinc-600 transition hover:text-cyan">
            + Add
          </button>
        ) : null}
        {context.capability === "short" && activeCaption ? (
          <span className="font-mono text-[10px] tabular-nums text-zinc-600">
            {formatTimestamp(captionRelativeSeconds(clip, activeCaption) * 1000)}
          </span>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2.5 pb-4 pt-0.5">
        {context.capability === "scene" ? (
          <div className="space-y-0.5">
            {plan?.scenes.map((scene, index) => {
              const selected = selectedSceneId === scene.id;
              const field = primarySceneField(scene);
              return (
                <ParagraphBlock
                  key={scene.id}
                  index={index + 1}
                  selected={selected}
                  editable={canEditScenes}
                  value={scene[field] || ""}
                  placeholder={field === "headline" ? "On-screen line…" : "Continue the script…"}
                  ariaLabel={`${field} for scene ${index + 1}`}
                  onFocus={() => onSelectScene(scene.id)}
                  onChange={(next) => updateScene(scene.id, {[field]: next})}
                  documentMode
                  chrome={
                    canEditScenes ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <select
                          value={scene.type}
                          aria-label={`Scene ${index + 1} type`}
                          onFocus={() => onSelectScene(scene.id)}
                          onChange={(event) => updateScene(scene.id, {type: event.target.value as ExplainerScene["type"]})}
                          className="rounded bg-transparent text-[10px] uppercase tracking-[0.12em] text-zinc-500 outline-none"
                        >
                          <option value="avatar">Avatar</option>
                          <option value="text">Text</option>
                          <option value="broll">B-roll</option>
                        </select>
                        <label className="inline-flex items-center gap-1 text-[10px] tabular-nums text-zinc-600">
                          <input
                            type="number"
                            min={1}
                            step={0.5}
                            value={scene.duration_target}
                            aria-label={`Scene ${index + 1} duration`}
                            onFocus={() => onSelectScene(scene.id)}
                            onChange={(event) => updateScene(scene.id, {duration_target: Math.max(1, Number(event.target.value) || 1)})}
                            className="w-10 bg-transparent text-right outline-none"
                          />
                          s
                        </label>
                        <div className="ml-auto flex items-center gap-0.5">
                          <InlineAction label="Move up" disabled={index === 0} onClick={() => onMoveScene(scene.id, -1)}>
                            <ArrowUp className="h-3 w-3" />
                          </InlineAction>
                          <InlineAction
                            label="Move down"
                            disabled={index === (plan?.scenes.length || 0) - 1}
                            onClick={() => onMoveScene(scene.id, 1)}
                          >
                            <ArrowDown className="h-3 w-3" />
                          </InlineAction>
                          <InlineAction label="Duplicate" onClick={() => onDuplicateScene(scene.id)}>
                            <Copy className="h-3 w-3" />
                          </InlineAction>
                          <InlineAction
                            label="Delete"
                            disabled={(plan?.scenes.length || 0) <= 1}
                            danger
                            onClick={() => onDeleteScene(scene.id)}
                          >
                            <Trash2 className="h-3 w-3" />
                          </InlineAction>
                        </div>
                      </div>
                    ) : null
                  }
                />
              );
            })}
          </div>
        ) : null}

        {context.capability === "short" ? (
          captions.length ? (
            <CaptionInteractiveDocument
              clip={clip}
              captions={captions}
              value={captionDraft}
              editable={canEditCaptions}
              selectedCaptionIndex={selectedCaptionIndex}
              currentSeconds={currentSeconds}
              isPlaying={isPlaying}
              actionMessage={removePauseState?.message}
              actionTone={removePauseState?.status}
              onChange={onCaptionDraftChange}
              onSelectCaption={onSelectCaption}
              onHighlightCaption={onHighlightCaption}
              onSeek={onSeek}
              onTogglePlayback={onTogglePlayback}
              onRemovePause={onRemovePause}
            />
          ) : (
            <p className="px-2 py-6 text-center text-xs leading-5 text-zinc-500">No captions available for this clip.</p>
          )
        ) : null}

        {context.capability === "imported_longform" ? (
          captions.length ? (
            <CaptionInteractiveDocument
              clip={clip}
              captions={captions}
              value={joinCaptionsFromSegments(captions)}
              editable={false}
              selectedCaptionIndex={selectedCaptionIndex}
              currentSeconds={currentSeconds}
              isPlaying={isPlaying}
              onChange={() => undefined}
              onSelectCaption={onSelectCaption}
              onHighlightCaption={onHighlightCaption}
              onSeek={onSeek}
              onTogglePlayback={onTogglePlayback}
            />
          ) : (
            <div className="space-y-1">
              {transcriptSections(clip.transcript_span || "").map((section, index) => (
                <ParagraphBlock
                  key={`${index}-${section.slice(0, 20)}`}
                  index={index + 1}
                  selected={selectedCaptionIndex === index}
                  editable={false}
                  value={section}
                  placeholder=""
                  ariaLabel={`Transcript section ${index + 1}`}
                  onFocus={() => onSelectCaption(index)}
                  onChange={() => undefined}
                />
              ))}
            </div>
          )
        ) : null}

        {canEditScenes ? (
          <button
            type="button"
            onClick={onAddScene}
            className="mt-4 inline-flex items-center gap-2 px-2 text-[13px] font-medium text-zinc-500 transition hover:text-cyan"
          >
            <Plus className="h-4 w-4" />
            Add scene
          </button>
        ) : null}
      </div>
    </aside>
  );
}

function primarySceneField(scene: ExplainerScene): "script" | "headline" {
  if (scene.type === "avatar") return "script";
  return "headline";
}

function ParagraphBlock({
  index,
  selected,
  editable,
  value,
  placeholder,
  ariaLabel,
  hint,
  singleLine,
  documentMode,
  chrome,
  onFocus,
  onChange,
}: {
  index: number;
  selected: boolean;
  editable: boolean;
  value: string;
  placeholder: string;
  ariaLabel: string;
  hint?: string;
  singleLine?: boolean;
  documentMode?: boolean;
  chrome?: ReactNode;
  onFocus: () => void;
  onChange: (value: string) => void;
}) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useLayoutEffect(() => {
    const node = textareaRef.current;
    if (!node) return;
    node.style.height = "0px";
    node.style.height = `${Math.max(28, node.scrollHeight)}px`;
  }, [value]);

  return (
    <div
      className={`group relative px-2 py-1.5 transition ${
        documentMode
          ? selected
            ? "bg-transparent"
            : "hover:bg-white/[0.015]"
          : selected
            ? "rounded-xl bg-white/[0.04]"
            : "rounded-xl hover:bg-white/[0.025]"
      }`}
    >
      {documentMode && selected ? (
        <span className="absolute bottom-2 left-0 top-2 w-0.5 rounded-full bg-cyan/70" aria-hidden />
      ) : null}
      <div className="grid grid-cols-[22px_minmax(0,1fr)] gap-2.5">
        <button
          type="button"
          onClick={onFocus}
          className={`pt-1 text-left text-[11px] font-medium tabular-nums leading-7 ${selected ? "text-cyan" : "text-zinc-700"}`}
          aria-label={`Select item ${index}`}
        >
          {index}
        </button>
        <div className="min-w-0">
          {hint ? (
            <span
              className={`mb-0.5 block text-[10px] tabular-nums text-zinc-600 transition ${
                selected ? "opacity-100" : "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
              }`}
            >
              {hint}
            </span>
          ) : null}
          {editable ? (
            <textarea
              ref={textareaRef}
              value={value}
              rows={1}
              placeholder={placeholder}
              aria-label={ariaLabel}
              onFocus={onFocus}
              onChange={(event) => onChange(singleLine ? event.target.value.replace(/\n/g, " ") : event.target.value)}
              onKeyDown={(event) => {
                if (singleLine && event.key === "Enter") event.preventDefault();
              }}
              className="w-full resize-none overflow-hidden bg-transparent text-[15px] leading-7 text-zinc-100 outline-none placeholder:text-zinc-600"
            />
          ) : (
            <p className="text-[15px] leading-7 text-zinc-400">{value || "—"}</p>
          )}
          {chrome ? (
            <div
              className={`mt-1 transition ${
                selected ? "opacity-100" : "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
              }`}
            >
              {chrome}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function transcriptSections(transcript: string) {
  if (!transcript.trim()) return ["No transcript is available for this video."];
  const paragraphs = transcript.split(/\n{2,}/).map((value) => value.trim()).filter(Boolean);
  if (paragraphs.length > 1) return paragraphs;
  const sentences = transcript.match(/[^.!?]+[.!?]+|[^.!?]+$/g)?.map((value) => value.trim()).filter(Boolean) || [];
  const sections: string[] = [];
  for (let index = 0; index < sentences.length; index += 3) sections.push(sentences.slice(index, index + 3).join(" "));
  return sections.length ? sections : [transcript];
}

function InlineAction({
  label,
  disabled,
  danger,
  onClick,
  children,
}: {
  label: string;
  disabled?: boolean;
  danger?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      aria-label={label}
      title={label}
      className={`grid h-6 w-6 place-items-center rounded disabled:opacity-25 ${
        danger ? "text-danger hover:bg-danger/10" : "text-zinc-500 hover:bg-white/[0.06] hover:text-white"
      }`}
    >
      {children}
    </button>
  );
}
