"use client";

import {Calendar, Loader2, X, Zap} from "lucide-react";
import {useEffect, useMemo, useState} from "react";
import {createPortal} from "react-dom";
import {ScheduleWhenFields} from "@/components/calendar/ScheduleWhenFields";
import {fromJakartaDatetimeLocal, nextCadenceSlot, toJakartaDatetimeLocal} from "@/components/calendar/schedule-when";
import {platformLabel, platformMatchesClipOrientation, type ClipCandidate} from "@/lib/media-api";

export type ReviewDistributeIntent = "schedule" | "publish" | "reschedule" | "republish";

const COPY: Record<
  ReviewDistributeIntent,
  {title: string; hint: string; action: string; icon: "calendar" | "zap"}
> = {
  schedule: {
    title: "Schedule",
    hint: "Pick destinations and a time. Postiz will hold the post until that slot.",
    action: "Schedule",
    icon: "calendar",
  },
  reschedule: {
    title: "Reschedule",
    hint: "Choose a new slot and destinations. Live posts already on platforms stay up.",
    action: "Save schedule",
    icon: "calendar",
  },
  publish: {
    title: "Publish now",
    hint: "Send immediately via Postiz. Success means accepted — not live yet.",
    action: "Send now",
    icon: "zap",
  },
  republish: {
    title: "Republish",
    hint: "Posts again as a new delivery. Existing live posts stay up.",
    action: "Republish now",
    icon: "zap",
  },
};

export function ReviewDistributeDialog({
  clip,
  intent,
  publishTargets,
  defaultPlatforms,
  busy = false,
  onClose,
  onSchedule,
  onPublish,
}: {
  clip: ClipCandidate;
  intent: ReviewDistributeIntent;
  publishTargets: string[];
  defaultPlatforms: string[];
  busy?: boolean;
  onClose: () => void;
  onSchedule: (scheduledAt: string, platforms: string[]) => void;
  onPublish: (platforms: string[]) => void;
}) {
  const copy = COPY[intent];
  const timed = intent === "schedule" || intent === "reschedule";
  const compatibleTargets = useMemo(
    () => publishTargets.filter((platform) => platformMatchesClipOrientation(platform, clip)),
    [publishTargets, clip],
  );
  const [selectedPlatforms, setSelectedPlatforms] = useState(() =>
    defaultPlatforms.length ? defaultPlatforms.filter((platform) => compatibleTargets.includes(platform)) : compatibleTargets,
  );
  const [when, setWhen] = useState(() => toJakartaDatetimeLocal(nextCadenceSlot()));

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previous;
    };
  }, [onClose]);

  function togglePlatform(platform: string) {
    setSelectedPlatforms((current) => {
      if (current.includes(platform)) {
        if (current.length === 1) return current;
        return current.filter((item) => item !== platform);
      }
      return [...current, platform];
    });
  }

  function submit() {
    if (!selectedPlatforms.length) return;
    if (timed) {
      onSchedule(fromJakartaDatetimeLocal(when), selectedPlatforms);
      return;
    }
    onPublish(selectedPlatforms);
  }

  if (typeof document === "undefined") return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[70] grid place-items-end bg-black/65 p-4 backdrop-blur-sm sm:place-items-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="distribute-title"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-md rounded-[28px] border border-white/[0.10] bg-surface p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-cyan/[0.12] text-cyan">
            {copy.icon === "calendar" ? <Calendar className="h-5 w-5" /> : <Zap className="h-5 w-5" />}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-9 w-9 place-items-center rounded-full text-zinc-400 transition hover:bg-white/[0.06] hover:text-white"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <h3 id="distribute-title" className="mt-4 text-xl font-semibold text-white">
          {copy.title}
        </h3>
        <p className="mt-1 line-clamp-2 text-sm text-zinc-300">{clip.title_hook}</p>
        <p className="mt-2 text-sm leading-6 text-zinc-400">{copy.hint}</p>

        <p className="mt-5 text-[11px] font-bold uppercase tracking-wider text-zinc-500">Destinations</p>
        {compatibleTargets.length ? (
          <div className="mt-2 grid grid-cols-2 gap-2">
            {compatibleTargets.map((platform) => {
              const selected = selectedPlatforms.includes(platform);
              return (
                <button
                  key={platform}
                  type="button"
                  disabled={busy || (selected && selectedPlatforms.length === 1)}
                  onClick={() => togglePlatform(platform)}
                  className={`h-11 rounded-2xl border px-3 text-left text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
                    selected
                      ? "border-cyan/[0.40] bg-cyan/[0.12] text-cyan"
                      : "border-white/[0.08] bg-black/20 text-zinc-400 hover:text-white"
                  }`}
                >
                  {platformLabel(platform)}
                </button>
              );
            })}
          </div>
        ) : (
          <p className="mt-2 text-sm text-zinc-500">No compatible destinations for this clip format. Check Channels.</p>
        )}

        {timed ? (
          <div className="mt-5">
            <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-zinc-500">When</p>
            <ScheduleWhenFields value={when} onChange={setWhen} disabled={busy} showCommit={false} />
          </div>
        ) : null}

        <div className="mt-6 grid gap-2 sm:grid-cols-2">
          <button
            type="button"
            onClick={onClose}
            className="h-11 rounded-full border border-white/[0.10] text-sm font-semibold text-zinc-300 hover:bg-white/[0.04]"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={busy || !selectedPlatforms.length || !compatibleTargets.length || (timed && !when)}
            onClick={submit}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-cyan text-sm font-semibold text-ink disabled:opacity-40"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : copy.icon === "calendar" ? <Calendar className="h-4 w-4" /> : <Zap className="h-4 w-4" />}
            {copy.action}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
