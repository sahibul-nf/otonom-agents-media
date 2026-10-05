"use client";

import {Loader2, XCircle, Zap} from "lucide-react";
import {useEffect, useMemo, useState} from "react";
import {ScheduleWhenFields} from "@/components/calendar/ScheduleWhenFields";
import {toJakartaDatetimeLocal} from "@/components/calendar/schedule-when";
import {RecoveryAction} from "@/components/shared/StudioPrimitives";
import {
  humanizePublishError,
  platformLabel,
  platformShortLabel,
  publishStatusHint,
  type PublishTarget,
  type ScheduledPost,
} from "@/lib/media-api";
import {classifyPublishError} from "@/lib/publish-recovery";

type ActionUiState = {status: "running" | "done" | "failed"; message: string};

function destinationLive(status?: string) {
  return status === "live" || status === "published";
}

function hasLiveDestination(item: ScheduledPost) {
  return Object.values(item.platform_results || {}).some((result) => destinationLive(result?.status));
}

function chipStatusLabel(status: string) {
  if (status === "cooldown") return "wait 12m";
  if (status === "queued") return "queued";
  if (status === "published" || status === "live") return "live";
  if (status === "failed" || status === "blocked") return "error";
  if (status === "accepted") return "sent";
  if (status === "pending") return "pending";
  if (status === "skipped") return "skip";
  return status.replaceAll("_", " ");
}

export function ScheduleQueueCard({
  item,
  targets,
  actionStates,
  onUnschedule,
  onUpdateSchedulePlatforms,
  onUpdateScheduleTime,
  onPublishNow,
  formatSchedule,
  formatClipStatus,
  statusTone,
}: {
  item: ScheduledPost;
  targets: PublishTarget[];
  actionStates: Record<string, ActionUiState>;
  onUnschedule: (id: string) => void;
  onUpdateSchedulePlatforms: (scheduleId: string, platforms: string[]) => void;
  onUpdateScheduleTime: (scheduleId: string, scheduledAt: string) => void;
  onPublishNow: (scheduleId: string) => void;
  formatSchedule: (value: string) => string;
  formatClipStatus: (status?: string) => string;
  statusTone: (status: string) => string;
}) {
  const [when, setWhen] = useState(() => toJakartaDatetimeLocal(item.scheduled_at));
  const [confirmNow, setConfirmNow] = useState(false);
  const [editTime, setEditTime] = useState(false);
  const [showMoreDestinations, setShowMoreDestinations] = useState(false);
  const [showErrorDetail, setShowErrorDetail] = useState(false);
  const timeBusy = actionStates[`schedule:${item.id}:time`]?.status === "running";
  const publishBusy = actionStates[`schedule:${item.id}:publish-now`]?.status === "running";
  const platformsBusy = actionStates[`schedule:${item.id}:platforms`]?.status === "running";
  const unscheduleBusy = actionStates[`clip:${item.candidate_id}:unschedule`]?.status === "running";
  const liveDest = hasLiveDestination(item);
  const canEdit = !["published", "publishing", "live"].includes(item.status) && !liveDest;
  const allPlatforms = targets.length ? targets.map((target) => target.platform) : item.platforms;
  const hiddenPlatforms = allPlatforms.filter((platform) => !item.platforms.includes(platform));
  const coolingDownPlatforms = useMemo(
    () =>
      item.platforms.filter((platform) => item.platform_results?.[platform]?.status === "cooldown"),
    [item.platforms, item.platform_results],
  );
  const errorSummary = humanizePublishError(item.last_error);
  const recovery = errorSummary ? classifyPublishError(item.last_error) : null;

  useEffect(() => {
    setWhen(toJakartaDatetimeLocal(item.scheduled_at));
  }, [item.scheduled_at]);

  function togglePlatform(platform: string) {
    const selected = item.platforms.includes(platform);
    const next = selected ? item.platforms.filter((value) => value !== platform) : [...item.platforms, platform];
    if (!next.length) return;
    onUpdateSchedulePlatforms(item.id, next);
  }

  function renderChip(platform: string, selected: boolean) {
    const result = item.platform_results?.[platform];
    const platformStatus = result?.status || (item.status === "published" ? "published" : selected ? "pending" : "off");
    const statusHint = selected ? publishStatusHint(platformStatus, result) : `Add ${platformLabel(platform)}`;
    return (
      <button
        key={platform}
        type="button"
        disabled={!canEdit || platformsBusy || (selected && item.platforms.length === 1)}
        onClick={() => togglePlatform(platform)}
        title={statusHint}
        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold disabled:cursor-not-allowed ${
          selected ? statusTone(platformStatus) : "border-white/[0.08] text-zinc-500"
        }`}
      >
        {platformShortLabel(platform)}
        {selected ? (
          <span className="text-[10px] font-bold uppercase tracking-wider opacity-80">{chipStatusLabel(platformStatus)}</span>
        ) : (
          <span className="text-[10px] font-bold uppercase tracking-wider opacity-60">off</span>
        )}
      </button>
    );
  }

  return (
    <article className="rounded-[22px] border border-white/[0.07] bg-black/20 p-4 transition hover:border-white/[0.12]">
      <div className="flex items-start gap-3">
        <div className="min-w-[7.5rem] shrink-0">
          <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Slot</p>
          <p className="mt-0.5 text-sm font-semibold tabular-nums text-cyan">{formatSchedule(item.scheduled_at)}</p>
          {canEdit ? (
            <button
              type="button"
              onClick={() => setEditTime((open) => !open)}
              className="mt-1 text-[11px] font-semibold text-zinc-500 transition hover:text-cyan"
            >
              {editTime ? "Hide time" : "Change time"}
            </button>
          ) : null}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h4 className="truncate text-sm font-semibold text-white">{item.title_hook}</h4>
                <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${statusTone(item.status)}`}>
                  {formatClipStatus(item.status)}
                </span>
              </div>
            </div>
            {canEdit ? (
              <div className="flex shrink-0 items-center gap-1.5">
                <button
                  type="button"
                  disabled={publishBusy}
                  onClick={() => setConfirmNow(true)}
                  className="inline-flex h-8 items-center gap-1.5 rounded-full bg-cyan px-3 text-[10px] font-bold uppercase tracking-wider text-ink disabled:opacity-50"
                >
                  {publishBusy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Zap className="h-3 w-3" />}
                  {publishBusy ? "Sending" : "Now"}
                </button>
                <button
                  type="button"
                  disabled={unscheduleBusy}
                  onClick={() => onUnschedule(item.candidate_id)}
                  className="inline-flex h-8 items-center rounded-full border border-white/[0.10] px-3 text-[10px] font-bold uppercase tracking-wider text-zinc-400 transition hover:text-white disabled:opacity-50"
                >
                  {unscheduleBusy ? "…" : "Remove"}
                </button>
              </div>
            ) : null}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            {item.platforms.map((platform) => renderChip(platform, true))}
            {canEdit && hiddenPlatforms.length ? (
              <button
                type="button"
                onClick={() => setShowMoreDestinations((open) => !open)}
                className="rounded-full border border-dashed border-white/[0.12] px-2.5 py-1 text-[11px] font-semibold text-zinc-500 hover:text-zinc-300"
              >
                {showMoreDestinations ? "Hide" : `+ ${hiddenPlatforms.length}`}
              </button>
            ) : null}
            {showMoreDestinations ? hiddenPlatforms.map((platform) => renderChip(platform, false)) : null}
          </div>
        </div>
      </div>

      {editTime && canEdit ? (
        <div className="mt-3 border-t border-white/[0.06] pt-3">
          <ScheduleWhenFields
            value={when}
            onChange={setWhen}
            onCommit={(iso) => {
              onUpdateScheduleTime(item.id, iso);
              setEditTime(false);
            }}
            busy={timeBusy}
            commitOnShortcut
          />
        </div>
      ) : null}

      {confirmNow ? (
        <div className="mt-3 rounded-2xl border border-cyan/20 bg-cyan/[0.06] p-3">
          <p className="text-[12px] font-semibold text-white">Send now via Postiz?</p>
          <p className="mt-1 text-[11px] leading-relaxed text-zinc-400">
            {item.platforms.map((platform) => platformShortLabel(platform)).join(" · ")} · accepted ≠ live.
            {coolingDownPlatforms.length
              ? ` ${coolingDownPlatforms.map((platform) => platformShortLabel(platform)).join(", ")} still cooling down will skip.`
              : ""}
          </p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              disabled={publishBusy}
              onClick={() => {
                setConfirmNow(false);
                onPublishNow(item.id);
              }}
              className="inline-flex h-8 items-center rounded-full bg-cyan px-3 text-[10px] font-bold uppercase tracking-wider text-ink disabled:opacity-50"
            >
              Send now
            </button>
            <button
              type="button"
              onClick={() => setConfirmNow(false)}
              className="inline-flex h-8 items-center rounded-full border border-white/[0.10] px-3 text-[10px] font-bold uppercase tracking-wider text-zinc-400"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {item.status === "partial_failed" ? (
        <p className="mt-3 text-[11px] text-zinc-500">One destination errored. Check the live page before unschedule or resend.</p>
      ) : null}

      {coolingDownPlatforms.length && !item.last_error ? (
        <p className="mt-3 text-[11px] text-zinc-500">
          {coolingDownPlatforms.map((platform) => platformShortLabel(platform)).join(", ")} cooling down — retry after ~12 min.
        </p>
      ) : null}

      {errorSummary ? (
        <div className="mt-3 flex items-start gap-1.5 text-[11px] text-danger">
          <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <div className="min-w-0">
            <p className={showErrorDetail ? "whitespace-pre-wrap break-words" : "line-clamp-2"}>{errorSummary}</p>
            {item.last_error && item.last_error !== errorSummary ? (
              <button
                type="button"
                onClick={() => setShowErrorDetail((open) => !open)}
                className="mt-1 font-semibold text-zinc-500 hover:text-zinc-300"
              >
                {showErrorDetail ? "Hide detail" : "Show detail"}
              </button>
            ) : null}
            {showErrorDetail && item.last_error !== errorSummary ? (
              <p className="mt-1 break-all text-[10px] leading-relaxed text-zinc-500">{item.last_error}</p>
            ) : null}
          </div>
        </div>
      ) : null}

      {recovery ? (
        <div className="mt-2">
          {recovery.kind === "retry" ? (
            <RecoveryAction label={publishBusy ? "Sending…" : recovery.label} disabled={publishBusy || !canEdit} onClick={() => onPublishNow(item.id)} />
          ) : recovery.kind === "rerender" ? (
            <RecoveryAction label={recovery.label} href={`/review/${encodeURIComponent(item.candidate_id)}`} />
          ) : (
            <RecoveryAction label={recovery.label} href="/?section=publish" />
          )}
        </div>
      ) : null}
    </article>
  );
}
