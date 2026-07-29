"use client";

import {ReviewTimeStrip} from "@/components/review/ReviewTimeStrip";
import {formatTimestamp, type ClipCandidate, type EditorContext, type ExplainerScenePlan} from "@/lib/media-api";
import {sceneDurationSeconds, totalSceneDuration} from "@/components/review/editor/types";

export function EditorLowerPanel({
  clip,
  context,
  plan,
  selectedSceneId,
  selectedCaptionIndex,
  currentSeconds,
  onSelectScene,
  onSelectCaption,
  onSeek,
}: {
  clip: ClipCandidate;
  context: EditorContext;
  plan?: ExplainerScenePlan;
  selectedSceneId?: string;
  selectedCaptionIndex?: number;
  currentSeconds: number;
  onSelectScene: (id: string) => void;
  onSelectCaption: (index: number) => void;
  onSeek: (seconds: number) => void;
}) {
  const longform = context.capability === "scene" || context.capability === "imported_longform";

  return (
    <section className="shrink-0">
      <div className="flex h-10 items-center justify-between px-4">
        <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-zinc-500">Timeline</span>
        <span className="font-mono text-[11px] tabular-nums text-zinc-500">
          {formatTimestamp(currentSeconds * 1000)}
          {context.capability === "scene" ? ` / ${formatTimestamp(totalSceneDuration(plan) * 1000)}` : ""}
        </span>
      </div>
      {context.capability !== "scene" && clip.captions?.length ? (
        <ReviewTimeStrip
          clip={clip}
          currentSeconds={currentSeconds}
          onSeek={onSeek}
          selectedCaptionIndex={selectedCaptionIndex}
          onSelectCaption={onSelectCaption}
        />
      ) : null}
      {context.capability === "scene" ? (
        <SceneTimeline plan={plan} selectedSceneId={selectedSceneId} currentSeconds={currentSeconds} onSelectScene={onSelectScene} onSeek={onSeek} />
      ) : null}
      {longform && context.capability === "imported_longform" && !clip.captions?.length ? (
        <div className="flex h-14 items-center px-4 text-sm text-zinc-500">
          Read-only long-form source · {formatTimestamp(clip.end_ms - clip.start_ms)}
        </div>
      ) : null}
      {context.capability === "short" && !clip.captions?.length ? (
        <div className="flex h-14 items-center px-4 text-sm text-zinc-500">
          No caption cues yet · {formatTimestamp(clip.end_ms - clip.start_ms)}
        </div>
      ) : null}
    </section>
  );
}

function SceneTimeline({
  plan,
  selectedSceneId,
  currentSeconds,
  onSelectScene,
  onSeek,
}: {
  plan?: ExplainerScenePlan;
  selectedSceneId?: string;
  currentSeconds: number;
  onSelectScene: (id: string) => void;
  onSeek: (seconds: number) => void;
}) {
  const total = Math.max(1, totalSceneDuration(plan));
  let cursor = 0;
  const progress = Math.max(0, Math.min(100, (currentSeconds / total) * 100));
  return (
    <div className="px-4 pb-4">
      <div className="relative flex h-16 overflow-hidden rounded-xl bg-white/[0.02]">
        {plan?.scenes.map((scene, index) => {
          const start = cursor;
          const duration = sceneDurationSeconds(scene);
          cursor += duration;
          const selected = selectedSceneId === scene.id;
          const label = scene.headline || scene.script || scene.narration || scene.type;
          return (
            <button
              key={scene.id}
              type="button"
              onClick={() => {
                onSelectScene(scene.id);
                onSeek(start);
              }}
              style={{width: `${(duration / total) * 100}%`}}
              className={`min-w-12 overflow-hidden border-r border-white/[0.04] px-2.5 py-2 text-left transition last:border-r-0 ${
                selected ? "bg-cyan/[0.14] text-cyan" : "bg-transparent text-zinc-500 hover:bg-white/[0.05] hover:text-zinc-300"
              }`}
            >
              <span className="block truncate text-[11px] font-semibold">
                {index + 1}
                <span className="ml-1.5 font-normal opacity-70">{scene.type}</span>
              </span>
              <span className="mt-1 block truncate text-[11px] leading-4 opacity-75">{label}</span>
            </button>
          );
        })}
        <div className="pointer-events-none absolute bottom-0 top-0 z-10 w-px bg-cyan" style={{left: `${progress}%`}}>
          <span className="absolute -left-1.5 top-0 h-3 w-3 rounded-full bg-cyan" />
        </div>
      </div>
    </div>
  );
}
