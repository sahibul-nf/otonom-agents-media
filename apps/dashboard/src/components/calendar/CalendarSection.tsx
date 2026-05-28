"use client";

import {CheckCircle2, Loader2, XCircle, Calendar, Sparkles, Clock, Zap, Flame, Settings2} from "lucide-react";
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
      className={`inline-flex h-8 items-center gap-2.5 rounded-full border px-3 text-xs font-semibold transition-all duration-300 disabled:cursor-not-allowed disabled:opacity-50 ${
        checked 
          ? "border-cyan/[0.45] bg-cyan text-ink shadow-[0_4px_12px_rgba(102,232,249,0.15)]" 
          : "border-white/[0.08] bg-black/24 text-zinc-400 hover:border-white/[0.14]"
      }`}
    >
      <span>{label}</span>
      <span className={`relative h-4 w-7 rounded-full transition-colors ${checked ? "bg-ink/20" : "bg-white/[0.10]"}`}>
        <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-current transition-all ${checked ? "left-3.5 text-ink" : "left-0.5 text-zinc-500"}`} />
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
    <section className="grid gap-6 xl:grid-cols-[1fr_420px]">
      {/* Schedule Queue Section */}
      <div className="rounded-[32px] border border-white/[0.08] bg-surface/30 p-6 backdrop-blur-md">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-white/[0.06] pb-6">
          <div>
            <h3 className="text-2xl font-semibold tracking-[-0.03em] text-white">
              Schedule <span className="font-editorial italic font-normal text-cyan">queue</span>
            </h3>
            <p className="mt-1.5 text-sm text-zinc-400 max-w-xl leading-relaxed">
              Approved production-ready clips waiting for queued publication slots. Cadence is locked to twice daily (09:00 & 19:30 WIB).
            </p>
          </div>
          
          <div className="flex flex-wrap gap-2 self-start sm:self-center">
            <button 
              disabled={dueBusy} 
              onClick={onDryRunDue} 
              className="inline-flex h-10 items-center justify-center gap-1.5 rounded-full border border-white/[0.10] bg-black/24 px-5 text-xs font-bold uppercase tracking-wider text-zinc-300 transition-all hover:bg-white/[0.05] hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {dryRunState?.status === "running" && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              <span>Dry-Run Due</span>
            </button>
            <button 
              disabled={dueBusy} 
              onClick={onPublishDue} 
              className="inline-flex h-10 items-center justify-center gap-1.5 rounded-full bg-cyan px-5 text-xs font-bold uppercase tracking-wider text-ink transition-all hover:scale-[1.02] hover:shadow-[0_8px_20px_-4px_rgba(102,232,249,0.3)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {publishDueState?.status === "running" ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Publishing...</span>
                </>
              ) : (
                <>
                  <Zap className="h-3.5 w-3.5 fill-current" />
                  <span>Publish Due Now</span>
                </>
              )}
            </button>
          </div>
        </div>

        {dryRunState?.status === "running" || publishDueState?.status === "running" ? (
          <div className="mb-5">{renderInlineActionStatus(publishDueState?.status === "running" ? publishDueState : dryRunState)}</div>
        ) : null}

        <div className="grid gap-4">
          {schedule.length ? schedule.map((item) => (
            <div 
              key={item.id} 
              className="relative group overflow-hidden grid gap-4 rounded-[26px] border border-white/[0.06] bg-black/15 p-5 md:grid-cols-[180px_minmax(0,1fr)_140px] md:items-center transition-all duration-300 hover:border-white/[0.12] hover:bg-black/25"
            >
              {/* Dynamic top edge glow indicator */}
              <div className="absolute top-0 left-0 right-0 h-[1.5px] bg-gradient-to-r from-transparent via-cyan/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              
              <div className="flex items-start gap-3">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-cyan/[0.04] border border-cyan/10 text-cyan">
                  <Clock className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-[10px] uppercase font-bold tracking-wider text-zinc-500">Scheduled Time</p>
                  <p className="mt-1 font-bold text-sm text-cyan tracking-tight">{formatSchedule(item.scheduled_at)}</p>
                </div>
              </div>

              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="truncate text-base font-semibold text-white tracking-tight leading-tight">{item.title_hook}</h4>
                  <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${statusTone(item.status)}`}>
                    {formatClipStatus(item.status)}
                  </span>
                </div>
                <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-zinc-400">{item.viral_reason}</p>
                
                <div className="mt-4 flex flex-wrap gap-2">
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
                        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-left text-[11px] font-bold uppercase tracking-wider transition-all duration-200 ${
                          enabled 
                            ? statusTone(platformStatus) 
                            : "border-white/[0.04] bg-white/[0.02] text-zinc-600 hover:border-white/[0.08] hover:text-zinc-500"
                        } disabled:cursor-not-allowed disabled:opacity-50`}
                      >
                        {enabled ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                        <span>
                          {platformAction?.status === "running" ? "Syncing..." : `${platformLabel(platform)} · ${enabled ? cleanPublishStatus(platformStatus) : "Off"}`}
                        </span>
                      </button>
                    );
                  })}
                </div>
                {item.last_error ? (
                  <p className="mt-3.5 text-xs leading-relaxed text-danger border-t border-danger/10 pt-2 flex items-start gap-1.5">
                    <XCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                    <span>{item.last_error}</span>
                  </p>
                ) : null}
              </div>

              <div className="flex justify-end md:justify-center">
                <button
                  type="button"
                  disabled={actionStates[`clip:${item.candidate_id}:unschedule`]?.status === "running"}
                  onClick={() => onUnschedule(item.candidate_id)}
                  className="inline-flex h-9 items-center justify-center gap-1.5 rounded-full border border-white/[0.10] bg-black/10 px-4 text-xs font-bold uppercase tracking-wider text-zinc-300 hover:bg-white/[0.05] hover:text-white transition-all disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {actionStates[`clip:${item.candidate_id}:unschedule`]?.status === "running" && <Loader2 className="h-3 w-3 animate-spin" />}
                  <span>{actionStates[`clip:${item.candidate_id}:unschedule`]?.status === "running" ? "Removing..." : "Unschedule"}</span>
                </button>
              </div>
            </div>
          )) : (
            renderEmptyState("No scheduled posts found", "Approve pending clips inside the Workspace deck first, then assign them a release slot.")
          )}
        </div>
      </div>

      {/* Sidebar Approved Clips Area */}
      <div className="rounded-[32px] border border-white/[0.08] bg-surface/30 p-6 backdrop-blur-md xl:self-start">
        <h3 className="text-lg font-semibold text-white tracking-[-0.02em] mb-1.5">
          Approved <span className="font-editorial italic font-normal text-cyan">clips</span>
        </h3>
        <p className="text-xs text-zinc-400 leading-relaxed">
          These clips have been signed off. Slot them directly into the automated schedule timeline.
        </p>

        {/* Targets Switch Control Box */}
        <div className="mt-6 rounded-[22px] border border-white/[0.06] bg-black/20 p-4">
          <div className="flex items-center gap-1.5 mb-3">
            <Settings2 className="h-4 w-4 text-cyan" />
            <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Default Release Targets</p>
          </div>
          <p className="text-[11px] leading-relaxed text-zinc-500 mb-4">
            New additions automatically inherit active targets.
          </p>
          <div className="grid gap-2">
            {targets.map((target) => {
              const active = selectedPlatforms.includes(target.platform);
              const targetState = actionStates[`target:${target.platform}`];
              return (
                <div
                  key={target.platform}
                  className={`flex items-center justify-between rounded-2xl border px-3 py-2 text-left text-xs font-semibold transition-all duration-300 ${
                    active ? "border-cyan/[0.45] bg-cyan/[0.04] text-white" : "border-white/[0.04] bg-black/20 text-zinc-500"
                  }`}
                >
                  <span className="text-xs tracking-tight">{platformLabel(target.platform)}</span>
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

        {/* Ready to Schedule Clips List */}
        <div className="mt-6 grid gap-3">
          <p className="text-[10px] uppercase font-bold tracking-wider text-zinc-500 px-1">Waiting Pool</p>
          {approved.length ? approved.map((clip) => (
            <div key={clip.id} className="group relative overflow-hidden rounded-[22px] border border-white/[0.05] bg-black/15 p-5 transition-all hover:border-white/[0.12] hover:bg-black/24">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="truncate font-semibold text-sm text-white group-hover:text-cyan transition-colors">{clip.title_hook}</p>
                  <p className="mt-1 text-xs text-zinc-500 tabular-nums">
                    {formatTimestamp(clip.start_ms)} → {formatTimestamp(clip.end_ms)}
                  </p>
                </div>
                <div className="shrink-0">
                  {renderScoreBubble(clip.score?.overall_score)}
                </div>
              </div>
              
              <button
                type="button"
                disabled={actionStates[`clip:${clip.id}:schedule`]?.status === "running" || !selectedPlatforms.length}
                onClick={() => onSchedule(clip.id)}
                className="mt-4 inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-full bg-cyan px-4 text-xs font-bold uppercase tracking-wider text-ink transition-all hover:scale-[1.01] hover:shadow-[0_4px_12px_rgba(102,232,249,0.15)] disabled:cursor-not-allowed disabled:opacity-40"
              >
                {actionStates[`clip:${clip.id}:schedule`]?.status === "running" ? (
                  <>
                    <Loader2 className="h-3 w-3 animate-spin" />
                    <span>Scheduling...</span>
                  </>
                ) : (
                  <>
                    <Calendar className="h-3.5 w-3.5" />
                    <span>{selectedPlatforms.length ? "Schedule Next Slot" : "Enable a target platform"}</span>
                  </>
                )}
              </button>
            </div>
          )) : (
            renderEmptyState("No approved clips ready", "Proceed to Review Workspace to sign off active clips.")
          )}
        </div>
      </div>
    </section>
  );
}
