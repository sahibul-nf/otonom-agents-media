"use client";

import {useEffect, useRef, useState, type CSSProperties} from "react";
import {EditorLowerPanel} from "@/components/review/editor/EditorLowerPanel";
import {EditorStage} from "@/components/review/editor/EditorStage";
import {SceneInspector} from "@/components/review/editor/SceneInspector";
import {SceneNavigator} from "@/components/review/editor/SceneNavigator";
import type {ReviewEditorWorkspaceProps} from "@/components/review/editor/types";

const LEFT_RAIL_STORAGE_KEY = "otonom.editor.leftRailWidth.v2";
const LEFT_RAIL_MIN = 300;
const LEFT_RAIL_MAX = 560;
const LEFT_RAIL_DEFAULT = LEFT_RAIL_MAX;

function readLeftRailWidth() {
  if (typeof window === "undefined") return LEFT_RAIL_DEFAULT;
  try {
    const stored = window.localStorage.getItem(LEFT_RAIL_STORAGE_KEY);
    if (!stored) return LEFT_RAIL_DEFAULT;
    const parsed = Number(stored);
    if (Number.isFinite(parsed)) return clampLeftWidth(parsed);
  } catch {
    // ignore storage failures
  }
  return LEFT_RAIL_DEFAULT;
}

export function ReviewEditorWorkspace(props: ReviewEditorWorkspaceProps) {
  const longform = props.context.capability === "scene" || props.context.capability === "imported_longform";
  const [leftWidth, setLeftWidth] = useState(readLeftRailWidth);
  const [resizing, setResizing] = useState(false);
  const dragStartX = useRef(0);
  const dragStartWidth = useRef(LEFT_RAIL_DEFAULT);

  useEffect(() => {
    if (!resizing) return;

    function onPointerMove(event: PointerEvent) {
      setLeftWidth(clampLeftWidth(dragStartWidth.current + (event.clientX - dragStartX.current)));
    }

    function onPointerUp() {
      setResizing(false);
      setLeftWidth((current) => {
        try {
          window.localStorage.setItem(LEFT_RAIL_STORAGE_KEY, String(current));
        } catch {
          // ignore storage failures
        }
        return current;
      });
    }

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [resizing]);

  const leftRailStyle = {
    ["--editor-left-rail" as string]: `${leftWidth}px`,
  } as CSSProperties;

  return (
    <div className="relative flex h-full min-h-0 flex-col overflow-y-auto bg-canvas lg:overflow-hidden">
      <div
        className={`pointer-events-none absolute inset-0 ${
          longform
            ? "bg-[radial-gradient(ellipse_at_55%_40%,rgba(98,238,248,0.035),transparent_60%)]"
            : "bg-[radial-gradient(ellipse_at_50%_42%,rgba(98,238,248,0.045),transparent_58%)]"
        }`}
      />

      <div className="relative flex min-h-0 flex-1 flex-col lg:flex-row">
        <div
          className={`relative z-10 min-h-[240px] w-full shrink-0 lg:min-h-0 lg:w-[var(--editor-left-rail)] lg:max-w-[var(--editor-left-rail)] ${
            longform
              ? "bg-gradient-to-r from-canvas-deep/40 via-transparent to-transparent"
              : "bg-gradient-to-r from-canvas-deep/55 via-canvas-deep/20 to-transparent"
          } ${resizing ? "select-none" : ""}`}
          style={leftRailStyle}
        >
          <SceneNavigator
            clip={props.clip}
            context={props.context}
            plan={props.draftPlan}
            captionDraft={props.captionDraft}
            selectedSceneId={props.selectedSceneId}
            selectedCaptionIndex={props.selectedCaptionIndex}
            currentSeconds={props.currentSeconds}
            isPlaying={props.isPlaying}
            onSelectScene={props.onSelectScene}
            onSelectCaption={props.onSelectCaption}
            onHighlightCaption={props.onHighlightCaption}
            onPlanChange={props.onPlanChange}
            onCaptionDraftChange={props.onCaptionDraftChange}
            onSeek={props.onSeek}
            onTogglePlayback={props.onTogglePlayback}
            onRemovePause={props.context.capability === "short" ? props.onRemovePause : undefined}
            removePauseState={
              props.context.capability === "short"
                ? props.actionStates[`clip:${props.clip.id}:remove-pause`]
                : undefined
            }
            onAddScene={props.onAddScene}
            onDuplicateScene={props.onDuplicateScene}
            onDeleteScene={props.onDeleteScene}
            onMoveScene={props.onMoveScene}
          />

          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize script panel"
            aria-valuemin={LEFT_RAIL_MIN}
            aria-valuemax={LEFT_RAIL_MAX}
            aria-valuenow={leftWidth}
            tabIndex={0}
            onPointerDown={(event) => {
              event.preventDefault();
              dragStartX.current = event.clientX;
              dragStartWidth.current = leftWidth;
              setResizing(true);
            }}
            onKeyDown={(event) => {
              if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
              event.preventDefault();
              const delta = event.key === "ArrowRight" ? 16 : -16;
              setLeftWidth((current) => {
                const next = clampLeftWidth(current + delta);
                try {
                  window.localStorage.setItem(LEFT_RAIL_STORAGE_KEY, String(next));
                } catch {
                  // ignore
                }
                return next;
              });
            }}
            className={`absolute inset-y-0 right-0 z-20 hidden w-3 translate-x-1/2 cursor-col-resize touch-none items-stretch justify-center lg:flex ${
              resizing ? "opacity-100" : "opacity-60 hover:opacity-100"
            }`}
          >
            <span className={`my-10 w-px rounded-full transition ${resizing ? "bg-cyan/80" : "bg-white/15 hover:bg-cyan/50"}`} />
          </div>
        </div>

        <div className="relative flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
            <div className={`relative min-w-0 flex-1 ${longform ? "min-h-[360px] lg:min-h-0" : "min-h-[520px] lg:min-h-0"}`}>
              <EditorStage
                clip={props.clip}
                context={props.context}
                currentSeconds={props.currentSeconds}
                seekRequest={props.seekRequest}
                playbackRequest={props.playbackRequest}
                rendering={props.rendering}
                previewEpoch={props.previewEpoch}
                onTimeChange={props.onTimeChange}
                onPlaybackChange={props.onPlaybackChange}
              />
            </div>

            <div className="relative z-10 shrink-0 bg-gradient-to-l from-canvas-deep/40 via-transparent to-transparent lg:pl-1">
              <SceneInspector
                clip={props.clip}
                context={props.context}
                plan={props.draftPlan}
                selectedSceneId={props.selectedSceneId}
                activeTab={props.activeInspectorTab}
                panelOpen={props.inspectorPanelOpen}
                postCopyDraft={props.postCopyDraft}
                templates={props.templates}
                actionStates={props.actionStates}
                onTabChange={props.onInspectorTabChange}
                onPanelOpenChange={props.onInspectorPanelOpenChange}
                onPlanChange={props.onPlanChange}
                onPostCopyChange={props.onPostCopyChange}
                onGeneratePostCopy={props.onGeneratePostCopy}
                onRefreshMetadata={props.onRefreshMetadata}
                onSaveBoundary={props.onSaveBoundary}
                onRerenderShort={props.onRerenderShort}
                onBatchRemovePauses={props.onBatchRemovePauses}
              />
            </div>
          </div>

          <div className={`relative z-10 shrink-0 px-3 pb-3 sm:px-4 ${longform ? "bg-gradient-to-t from-canvas-deep/50 via-transparent to-transparent pt-1" : "bg-gradient-to-t from-canvas-deep/70 via-canvas-deep/25 to-transparent pt-2"}`}>
            <div className={`overflow-hidden ${longform ? "rounded-xl bg-black/15 backdrop-blur-sm" : "rounded-2xl border border-white/[0.05] bg-black/20 shadow-[0_-8px_40px_rgba(0,0,0,0.25)] backdrop-blur-md"}`}>
              <EditorLowerPanel
                clip={props.clip}
                context={props.context}
                plan={props.draftPlan}
                selectedSceneId={props.selectedSceneId}
                selectedCaptionIndex={props.selectedCaptionIndex}
                currentSeconds={props.currentSeconds}
                onSelectScene={props.onSelectScene}
                onSelectCaption={props.onSelectCaption}
                onSeek={props.onSeek}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function clampLeftWidth(value: number) {
  return Math.min(LEFT_RAIL_MAX, Math.max(LEFT_RAIL_MIN, Math.round(value)));
}
