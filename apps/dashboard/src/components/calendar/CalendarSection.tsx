"use client";

import {CheckCircle2, Loader2, XCircle} from "lucide-react";
import type {ReactNode} from "react";
import {platformLabel, formatTimestamp, type ClipCandidate, type PublishTarget, type ScheduledPost} from "@/lib/media-api";

type ActionUiState = {status: "running" | "done" | "failed"; message: string};

function SwitchControl({checked, disabled, label, onChange}: {checked: boolean; disabled?: boolean; label: string; onChange: () => void}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={onChange}
      className={`inline-flex h-8 items-center gap-2 rounded-full border px-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
        checked ? "border-cyan/[0.45] bg-cyan text-ink" : "border-white/[0.12] bg-white/[0.04] text-zinc-400"
      }`}
    >
      <span>{label}</span>
      <span className={`relative h-5 w-9 rounded-full transition ${checked ? "bg-ink/25" : "bg-white/[0.10]"}`}>
        <span className={`absolute top-1 h-3 w-3 rounded-full bg-current transition ${checked ? "left-5 text-ink" : "left-1 text-zinc-500"}`} />
      </span>
    </button>
  );
}

export function CalendarSection({
  schedule,
  approved,
  targets,
  selectedPlatforms,
  actionStates,
  onToggleDefaultPlatform,
  onSchedule,
  onUnschedule,
  onUpdateSchedulePlatforms,
  onPublishDue,
  onDryRunDue,
  formatSchedule,
  formatClipStatus,
  cleanPublishStatus,
  statusTone,
  renderScoreBubble,
  renderInlineActionStatus,
  renderEmptyState,
}: {
  schedule: ScheduledPost[];
  approved: ClipCandidate[];
  targets: PublishTarget[];
  selectedPlatforms: string[];
  actionStates: Record<string, ActionUiState>;
  onToggleDefaultPlatform: (platform: string) => void;
  onSchedule: (id: string) => void;
  onUnschedule: (id: string) => void;
  onUpdateSchedulePlatforms: (scheduleId: string, platforms: string[]) => void;
  onPublishDue: () => void;
  onDryRunDue: () => void;
  formatSchedule: (value: string) => string;
  formatClipStatus: (status?: string) => string;
  cleanPublishStatus: (status?: string) => string;
  statusTone: (status: string) => string;
  renderScoreBubble: (value?: number) => ReactNode;
  renderInlineActionStatus: (state?: ActionUiState) => ReactNode;
  renderEmptyState: (title: string, text: string) => ReactNode;
}) {
  function toggleSchedulePlatform(item: ScheduledPost, platform: string) {
    const current = item.platforms || [];
    const next = current.includes(platform) ? current.filter((value) => value !== platform) : [...current, platform];
    if (!next.length) return;
    onUpdateSchedulePlatforms(item.id, next);
  }
  const dryRunState = actionStates["publish:due:dry"];
  const publishDueState = actionStates["publish:due:live"];
  const dueBusy = dryRunState?.status === "running" || publishDueState?.status === "running";

  return (
    <section className="grid gap-5 xl:grid-cols-[1fr_420px]">
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-xl font-semibold text-white">Schedule queue</h3>
            <p className="mt-1 text-sm text-zinc-400">Approved clips waiting for guarded publish slots. Default cadence is 2 posts per day at 09:00 and 19:30 WIB.</p>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <button disabled={dueBusy} onClick={onDryRunDue} className="inline-flex items-center justify-center gap-2 rounded-full border border-white/[0.10] px-4 py-2 text-sm font-semibold text-zinc-300 disabled:cursor-not-allowed disabled:opacity-50">
              {dryRunState?.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Dry-run due
            </button>
            <button disabled={dueBusy} onClick={onPublishDue} className="inline-flex items-center justify-center gap-2 rounded-full bg-cyan px-4 py-2 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50">
              {publishDueState?.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {publishDueState?.status === "running" ? "Publishing..." : "Publish due now"}
            </button>
          </div>
        </div>
        {dryRunState?.status === "running" || publishDueState?.status === "running" ? (
          <div className="mb-4">{renderInlineActionStatus(publishDueState?.status === "running" ? publishDueState : dryRunState)}</div>
        ) : null}
        <div className="grid gap-3">
          {schedule.length ? schedule.map((item) => (
            <div key={item.id} className="grid gap-3 rounded-[24px] border border-white/[0.08] bg-canvas-deep p-4 md:grid-cols-[160px_minmax(0,1fr)_140px] md:items-center">
              <div>
                <p className="text-xs uppercase tracking-wide text-zinc-500">Scheduled</p>
                <p className="mt-1 font-semibold text-cyan">{formatSchedule(item.scheduled_at)}</p>
              </div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="truncate text-base font-semibold text-white">{item.title_hook}</h4>
                  <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusTone(item.status)}`}>{formatClipStatus(item.status)}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-sm leading-5 text-zinc-400">{item.viral_reason}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {targets.map((target) => {
                    const platform = target.platform;
                    const enabled = item.platforms.includes(platform);
                    const result = item.platform_results?.[platform];
                    const platformAction = actionStates[`schedule:${item.id}:platforms`];
                    const platformStatus = result?.status || (item.status === "published" ? "published" : "pending");
                    return (
                      <button
                        key={platform}
                        onClick={() => toggleSchedulePlatform(item, platform)}
                        disabled={platformAction?.status === "running"}
                        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-left text-xs font-semibold transition ${
                          enabled ? statusTone(platformStatus) : "border-white/[0.08] bg-white/[0.03] text-zinc-500"
                        } disabled:cursor-not-allowed disabled:opacity-50`}
                      >
                        {enabled ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                        {platformAction?.status === "running" ? "Updating..." : `${platformLabel(platform)} · ${enabled ? cleanPublishStatus(platformStatus) : "Off"}`}
                      </button>
                    );
                  })}
                </div>
                {item.last_error ? <p className="mt-2 line-clamp-2 text-xs text-danger">{item.last_error}</p> : null}
              </div>
              <button
                disabled={actionStates[`clip:${item.candidate_id}:unschedule`]?.status === "running"}
                onClick={() => onUnschedule(item.candidate_id)}
                className="inline-flex items-center justify-center gap-2 rounded-full border border-white/[0.10] px-4 py-2 text-sm font-semibold text-zinc-300 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {actionStates[`clip:${item.candidate_id}:unschedule`]?.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {actionStates[`clip:${item.candidate_id}:unschedule`]?.status === "running" ? "Removing..." : "Unschedule"}
              </button>
            </div>
          )) : renderEmptyState("No scheduled posts", "Approve clips first, then assign the next open slot.")}
        </div>
      </div>
      <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
        <h3 className="text-lg font-semibold text-white">Approved clips</h3>
        <p className="mt-1 text-sm text-zinc-400">Add approved clips to the next available workspace slot.</p>
        <div className="mt-5 rounded-[22px] border border-white/[0.08] bg-canvas-deep p-4">
          <p className="text-sm font-semibold text-white">Default publish targets</p>
          <p className="mt-1 text-xs leading-5 text-zinc-500">Used when you schedule a clip. You can still override each scheduled item.</p>
          <div className="mt-3 grid gap-2">
            {targets.map((target) => {
              const active = selectedPlatforms.includes(target.platform);
              const targetState = actionStates[`target:${target.platform}`];
              return (
                <div
                  key={target.platform}
                  className={`flex items-center justify-between rounded-2xl border px-3 py-2 text-left text-xs font-semibold transition ${
                    active ? "border-cyan/[0.45] bg-teal/[0.14] text-cyan" : "border-white/[0.08] bg-black/20 text-zinc-500"
                  }`}
                >
                  <span>{platformLabel(target.platform)}</span>
                  <SwitchControl
                    checked={active}
                    disabled={targetState?.status === "running"}
                    label={targetState?.status === "running" ? "Saving" : active ? "On" : "Off"}
                    onChange={() => onToggleDefaultPlatform(target.platform)}
                  />
                </div>
              );
            })}
          </div>
        </div>
        <div className="mt-5 grid gap-3">
          {approved.length ? approved.map((clip) => (
            <div key={clip.id} className="rounded-[22px] border border-white/[0.08] bg-canvas-deep p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-semibold text-white">{clip.title_hook}</p>
                  <p className="mt-1 text-xs text-zinc-500">{formatTimestamp(clip.start_ms)} → {formatTimestamp(clip.end_ms)}</p>
                </div>
                {renderScoreBubble(clip.score?.overall_score)}
              </div>
              <button
                disabled={actionStates[`clip:${clip.id}:schedule`]?.status === "running" || !selectedPlatforms.length}
                onClick={() => onSchedule(clip.id)}
                className="mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-full bg-cyan text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50"
              >
                {actionStates[`clip:${clip.id}:schedule`]?.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {actionStates[`clip:${clip.id}:schedule`]?.status === "running" ? "Scheduling..." : selectedPlatforms.length ? "Schedule next slot" : "Turn on a target first"}
              </button>
            </div>
          )) : renderEmptyState("No approved clips", "Review and approve a rendered clip before scheduling.")}
        </div>
      </div>
    </section>
  );
}
