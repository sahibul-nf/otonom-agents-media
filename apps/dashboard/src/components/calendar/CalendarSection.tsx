"use client";

import {ArrowUpRight, Calendar, Loader2, Settings2, Zap} from "lucide-react";
import {useMemo, useState, type ReactNode} from "react";
import {ScheduleWhenFields} from "@/components/calendar/ScheduleWhenFields";
import {ScheduleQueueCard} from "@/components/calendar/ScheduleQueueCard";
import {fromJakartaDatetimeLocal, nextCadenceSlot, toJakartaDatetimeLocal} from "@/components/calendar/schedule-when";
import {
  formatTimestamp,
  platformLabel,
  type ClipCandidate,
  type CredentialStatus,
  type PublishTarget,
  type ScheduledPost,
} from "@/lib/media-api";

function calendarHealth(credentials: CredentialStatus | null): string {
  const postiz = credentials?.postiz;
  if (!postiz?.connected) {
    return "Postiz is not connected. Schedule stays in Otonom until you connect it in Channels.";
  }
  const mapped = Object.keys(postiz.channels || {}).length;
  if (!mapped) {
    return "Postiz is connected. Map YouTube/Facebook in Channels before those posts can leave Otonom.";
  }
  return `Postiz connected · ${mapped} mapped channel${mapped === 1 ? "" : "s"}`;
}

type ActionUiState = {status: "running" | "done" | "failed"; message: string};

type CalendarSectionProps = {
  schedule: ScheduledPost[];
  approved: ClipCandidate[];
  targets: PublishTarget[];
  selectedPlatforms: string[];
  actionStates: Record<string, ActionUiState>;
  onToggleDefaultPlatform: (platform: string) => void;
  onSchedule: (id: string, scheduledAt: string) => void;
  onUnschedule: (id: string) => void;
  onUpdateSchedulePlatforms: (scheduleId: string, platforms: string[]) => void;
  onUpdateScheduleTime: (scheduleId: string, scheduledAt: string) => void;
  onPublishNow: (scheduleId: string) => void;
  onPublishDue: () => void;
  onDryRunDue: () => void;
  formatSchedule: (value: string) => string;
  formatClipStatus: (status?: string) => string;
  cleanPublishStatus: (status?: string) => string;
  statusTone: (status: string) => string;
  renderScoreBubble: (value?: number) => ReactNode;
  renderInlineActionStatus: (state?: ActionUiState) => ReactNode;
  renderEmptyState: (title: string, text: string) => ReactNode;
  credentials?: CredentialStatus | null;
  showRecoveryTools?: boolean;
};

export function CalendarSection({
  schedule,
  approved,
  targets,
  selectedPlatforms,
  actionStates,
  onSchedule,
  onUnschedule,
  onUpdateSchedulePlatforms,
  onUpdateScheduleTime,
  onPublishNow,
  onPublishDue,
  onDryRunDue,
  formatSchedule,
  formatClipStatus,
  cleanPublishStatus: _cleanPublishStatus,
  statusTone,
  renderScoreBubble,
  renderInlineActionStatus,
  renderEmptyState,
  credentials = null,
  showRecoveryTools = false,
}: CalendarSectionProps) {
  const dryRunState = actionStates["publish:due:dry"];
  const publishDueState = actionStates["publish:due:live"];
  const dueBusy = dryRunState?.status === "running" || publishDueState?.status === "running";
  const selectedTargets = targets.filter((target) => selectedPlatforms.includes(target.platform));
  const nextSlot = useMemo(() => nextCadenceSlot(), []);

  return (
    <section className="grid gap-6 xl:grid-cols-[1fr_420px]">
      {/* Approved Waiting Pool */}
      <div className="order-1 rounded-[32px] border border-white/[0.08] bg-surface/30 p-6 backdrop-blur-md xl:order-2 xl:self-start">
        <div className="border-b border-white/[0.06] pb-5">
          <h3 className="text-xl font-semibold tracking-[-0.02em] text-white">
            Approved <span className="font-editorial italic font-normal text-cyan">waiting pool</span>
          </h3>
          <p className="mt-1.5 text-xs leading-relaxed text-zinc-400">
            Production-ready clips waiting for their next release slot.
          </p>
        </div>

        <div className="mt-5 rounded-[20px] border border-white/[0.06] bg-black/20 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-1.5">
                <Settings2 className="h-4 w-4 text-cyan" />
                <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Publishing destinations</p>
              </div>
              <p className="mt-1.5 text-[11px] leading-relaxed text-zinc-500">
                Read-only here. Channel settings control where newly scheduled clips publish.
              </p>
            </div>
            <a
              href="?section=publish"
              className="inline-flex shrink-0 items-center gap-1 text-[11px] font-semibold text-cyan transition hover:text-white"
            >
              Edit in Channels
              <ArrowUpRight className="h-3.5 w-3.5" />
            </a>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {selectedTargets.length ? selectedTargets.map((target) => (
              <span
                key={target.platform}
                className="inline-flex items-center rounded-full border border-cyan/[0.24] bg-cyan/[0.06] px-2.5 py-1 text-[11px] font-semibold text-cyan"
              >
                {platformLabel(target.platform)}
              </span>
            )) : (
              <span className="text-xs text-warning">No publishing destinations enabled.</span>
            )}
          </div>
        </div>

        <div className="mt-5 grid gap-3">
          {approved.length ? approved.map((clip) => (
            <WaitingPoolCard
              key={clip.id}
              clip={clip}
              defaultSlot={nextSlot}
              canSchedule={Boolean(selectedPlatforms.length)}
              busy={actionStates[`clip:${clip.id}:schedule`]?.status === "running"}
              formatSchedule={formatSchedule}
              onSchedule={onSchedule}
              renderScoreBubble={renderScoreBubble}
            />
          )) : (
            renderEmptyState("No approved clips ready", "Approve clips in Review, then schedule their next slot here.")
          )}
        </div>
      </div>

      {/* Schedule Queue Section */}
      <div className="order-2 rounded-[32px] border border-white/[0.08] bg-surface/30 p-6 backdrop-blur-md xl:order-1">
        <div className="mb-5 border-b border-white/[0.06] pb-6">
          <div>
            <h3 className="text-2xl font-semibold tracking-[-0.03em] text-white">
              Schedule <span className="font-editorial italic font-normal text-cyan">queue</span>
            </h3>
            <p className="mt-1.5 text-sm text-zinc-400 max-w-xl leading-relaxed">
              Twice daily (09:00 & 19:30 WIB). Publish now sends immediately via Postiz.
            </p>
            <p className="mt-2 text-[11px] leading-relaxed text-zinc-500">{calendarHealth(credentials)}</p>
          </div>
        </div>

        {showRecoveryTools ? (
        <details className="group mb-5 rounded-[20px] border border-white/[0.06] bg-black/15">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-xs font-semibold text-zinc-500 transition hover:text-zinc-300">
            <span className="inline-flex items-center gap-2">
              <Settings2 className="h-4 w-4 text-zinc-600" />
              Recovery tools
            </span>
            <span className="text-[10px] uppercase tracking-wider text-zinc-600 group-open:hidden">Show</span>
            <span className="hidden text-[10px] uppercase tracking-wider text-zinc-600 group-open:inline">Hide</span>
          </summary>
          <div className="flex flex-wrap gap-2 border-t border-white/[0.06] p-4">
            <p className="mb-1 w-full text-[11px] leading-relaxed text-zinc-500">
              Rare manual catch-up if automation missed a due slot.
            </p>
            <button
              type="button"
              disabled={dueBusy}
              onClick={onDryRunDue}
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-full border border-white/[0.10] bg-black/24 px-4 text-xs font-semibold text-zinc-400 transition-all hover:bg-white/[0.05] hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {dryRunState?.status === "running" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
              <span>Preview due posts</span>
            </button>
            <button
              type="button"
              disabled={dueBusy}
              onClick={onPublishDue}
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-full border border-white/[0.10] bg-black/24 px-4 text-xs font-semibold text-zinc-300 transition-all hover:bg-white/[0.05] hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {publishDueState?.status === "running" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5" />}
              <span>{publishDueState?.status === "running" ? "Publishing..." : "Publish due now"}</span>
            </button>
          </div>
        </details>
        ) : null}

        {dryRunState?.status === "running" || publishDueState?.status === "running" ? (
          <div className="mb-5">{renderInlineActionStatus(publishDueState?.status === "running" ? publishDueState : dryRunState)}</div>
        ) : null}

        <div className="grid gap-4">
          {schedule.length ? schedule.map((item) => (
            <ScheduleQueueCard
              key={item.id}
              item={item}
              targets={targets}
              actionStates={actionStates}
              onUnschedule={onUnschedule}
              onUpdateSchedulePlatforms={onUpdateSchedulePlatforms}
              onUpdateScheduleTime={onUpdateScheduleTime}
              onPublishNow={onPublishNow}
              formatSchedule={formatSchedule}
              formatClipStatus={formatClipStatus}
              statusTone={statusTone}
            />
          )) : (
            renderEmptyState("No scheduled posts yet", "Approve clips in Review, then assign them a release slot.")
          )}
        </div>
      </div>
    </section>
  );
}

function WaitingPoolCard({
  clip,
  defaultSlot,
  canSchedule,
  busy,
  formatSchedule,
  onSchedule,
  renderScoreBubble,
}: {
  clip: ClipCandidate;
  defaultSlot: string;
  canSchedule: boolean;
  busy: boolean;
  formatSchedule: (value: string) => string;
  onSchedule: (id: string, scheduledAt: string) => void;
  renderScoreBubble: (value?: number) => ReactNode;
}) {
  const [when, setWhen] = useState(() => toJakartaDatetimeLocal(defaultSlot));

  return (
    <div className="group relative overflow-hidden rounded-[22px] border border-white/[0.05] bg-black/15 p-5 transition-all hover:border-white/[0.12] hover:bg-black/24">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white transition-colors group-hover:text-cyan">{clip.title_hook}</p>
          <p className="mt-1 text-xs tabular-nums text-zinc-500">
            {formatTimestamp(clip.start_ms)} → {formatTimestamp(clip.end_ms)}
          </p>
        </div>
        <div className="shrink-0">
          {renderScoreBubble(clip.score?.overall_score)}
        </div>
      </div>
      <div className="mt-4">
        <ScheduleWhenFields value={when} onChange={setWhen} disabled={!canSchedule || busy} showCommit={false} />
      </div>
      <button
        type="button"
        disabled={busy || !canSchedule || !when}
        onClick={() => onSchedule(clip.id, fromJakartaDatetimeLocal(when))}
        className="mt-3 inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-full bg-cyan px-4 text-xs font-bold uppercase tracking-wider text-ink transition-all hover:scale-[1.01] hover:shadow-[0_4px_12px_rgba(102,232,249,0.15)] disabled:cursor-not-allowed disabled:opacity-40"
      >
        {busy ? (
          <>
            <Loader2 className="h-3 w-3 animate-spin" />
            <span>Scheduling...</span>
          </>
        ) : (
          <>
            <Calendar className="h-3.5 w-3.5" />
            <span>{canSchedule ? `Schedule ${formatSchedule(fromJakartaDatetimeLocal(when) || defaultSlot)}` : "Set destinations in Channels"}</span>
          </>
        )}
      </button>
    </div>
  );
}
