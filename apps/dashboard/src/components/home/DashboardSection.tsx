"use client";

import {Wand2, ArrowUpRight, Zap, RefreshCcw, Share2} from "lucide-react";
import {ClipCandidate, ScheduledPost} from "@/lib/media-api";

type Section = "dashboard" | "generate" | "explainer" | "templates" | "review" | "calendar" | "publish" | "brand";
type NextAction = {
  label: string;
  detail: string;
  section: Section;
};
type WorkflowStep = {
  id: string;
  label: string;
  status: "ready" | "active" | "blocked" | "idle";
  detail: string;
  section: Section;
};

function WorkflowRail({steps, onSection}: {steps: WorkflowStep[]; onSection: (section: Section) => void}) {
  return (
    <div className="rounded-[32px] border border-white/[0.08] bg-surface/40 p-6 backdrop-blur-md">
      <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold tracking-[-0.02em] text-text-primary">
            This week&apos;s <span className="font-editorial italic font-normal text-cyan">loop</span>
          </h3>
          <p className="mt-0.5 text-xs text-zinc-500">Create → Review → Schedule → Publish</p>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {steps.map((step, index) => {
          const isReady = step.status === "ready";
          const isActive = step.status === "active";
          const isBlocked = step.status === "blocked";

          return (
            <button
              key={step.id}
              type="button"
              onClick={() => onSection(step.section)}
              className={`group relative min-w-0 rounded-[24px] border p-5 text-left transition-all duration-300 hover:-translate-y-0.5 ${
                isReady
                  ? "border-teal/[0.22] bg-teal/[0.04] hover:border-teal/[0.35] hover:bg-teal/[0.08]"
                  : isActive
                    ? "border-cyan/[0.30] bg-cyan/[0.04] shadow-[0_4px_16px_rgba(102,232,249,0.04)] hover:border-cyan/[0.45] hover:bg-cyan/[0.08]"
                    : isBlocked
                      ? "border-danger/[0.20] bg-danger/[0.04] hover:border-danger/[0.30] hover:bg-danger/[0.08]"
                      : "border-border bg-surface-panel hover:border-border-strong hover:bg-surface-strong"
              }`}
            >
              <div className="mb-5 flex items-center justify-between">
                <span className="text-[10px] font-bold tracking-widest text-zinc-500 transition-colors group-hover:text-zinc-400">0{index + 1}</span>
                <span
                  className={`h-2 w-2 rounded-full transition-all duration-300 ${
                    isReady
                      ? "bg-teal shadow-[0_0_8px_rgba(0,194,183,0.5)]"
                      : isActive
                        ? "animate-pulse bg-cyan shadow-[0_0_8px_rgba(98,238,248,0.5)]"
                        : isBlocked
                          ? "bg-danger shadow-[0_0_8px_rgba(254,91,121,0.5)]"
                          : "bg-zinc-700"
                  }`}
                />
              </div>
              <p className="truncate text-sm font-semibold text-text-primary transition-colors group-hover:text-cyan">{step.label}</p>
              <p className="mt-1 truncate text-[11px] text-zinc-500 transition-colors group-hover:text-zinc-400">{step.detail}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function MetricFrame({
  title,
  value,
  detail,
  action,
  icon: Icon,
  onAction,
}: {
  title: string;
  value: string;
  detail: string;
  action: string;
  icon: React.ComponentType<{className?: string}>;
  onAction: () => void;
}) {
  return (
    <div className="relative overflow-hidden rounded-[30px] border border-white/[0.07] bg-surface/30 p-6 backdrop-blur-md transition-all duration-300 hover:border-white/[0.12] hover:bg-surface/40">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-zinc-500">{title}</p>
          <p className="mt-3.5 text-3xl font-semibold tabular-nums tracking-[-0.03em] text-text-primary">{value}</p>
        </div>
        <span className="grid h-10 w-10 place-items-center rounded-2xl border border-border bg-surface-panel text-text-secondary">
          <Icon className="h-5 w-5" />
        </span>
      </div>
      <p className="mt-3.5 max-w-[85%] text-xs leading-relaxed text-zinc-400">{detail}</p>
      <button
        type="button"
        onClick={onAction}
        className="mt-5 inline-flex h-9 items-center gap-1.5 rounded-full border border-border bg-surface-raised px-4 text-xs font-semibold text-text-primary transition-all hover:bg-surface-strong"
      >
        <span>{action}</span>
        <ArrowUpRight className="h-3 w-3 text-zinc-500" />
      </button>
    </div>
  );
}

export function DashboardSection({
  clips,
  schedule,
  nextAction,
  workflowSteps,
  readyPlatforms,
  targetCount,
  activeJobs,
  onSection,
}: {
  clips: ClipCandidate[];
  schedule: ScheduledPost[];
  nextAction: NextAction;
  workflowSteps: WorkflowStep[];
  readyPlatforms: number;
  targetCount: number;
  activeJobs: number;
  onSection: (section: Section) => void;
}) {
  const approvedCount = clips.filter((clip) => clip.status === "approved").length;
  const reviewCount = clips.filter((clip) => ["draft", "rendered", "held", "pending_auto_schedule"].includes(clip.status)).length;

  const statusSummary = [
    {label: "Review Queue", value: reviewCount ? `${reviewCount} clips` : "Clear", active: Boolean(reviewCount), section: "review" as Section},
    {label: "Approved", value: approvedCount ? `${approvedCount} ready` : "None yet", active: Boolean(approvedCount), section: "review" as Section},
    {label: "Schedule", value: schedule.length ? `${schedule.length} posts` : "Empty", active: Boolean(schedule.length), section: "calendar" as Section},
    {label: "Channels", value: `${readyPlatforms}/${targetCount} live`, active: readyPlatforms === targetCount, section: "publish" as Section},
  ];

  return (
    <section className="grid gap-6">
      <div className="relative overflow-hidden rounded-[36px] border border-cyan/[0.18] bg-gradient-to-b from-cyan/[0.04] to-transparent p-6 shadow-[0_20px_50px_rgba(0,0,0,0.3)] sm:p-8">
        <div className="absolute right-0 top-0 -z-10 h-72 w-72 rounded-full bg-cyan/[0.03] blur-[80px]" />

        <div className="flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-cyan/[0.12] text-cyan">
                <Zap className="h-3 w-3 fill-current" />
              </span>
              <p className="text-[10px] font-bold uppercase tracking-widest text-cyan">Next step</p>
            </div>

            <h3 className="mt-4 text-3xl font-semibold leading-tight tracking-[-0.04em] text-text-primary md:text-4xl">
              {nextAction.label.startsWith("Review") ? (
                <>
                  <span className="font-editorial italic font-normal text-cyan">Review</span> {nextAction.label.replace("Review", "").trim()}
                </>
              ) : nextAction.label.startsWith("Generate") ? (
                <>
                  <span className="font-editorial italic font-normal text-cyan">Generate</span> {nextAction.label.replace("Generate", "").trim()}
                </>
              ) : nextAction.label.startsWith("Choose") ? (
                <>
                  <span className="font-editorial italic font-normal text-cyan">Choose</span> {nextAction.label.replace("Choose", "").trim()}
                </>
              ) : nextAction.label.startsWith("Schedule") ? (
                <>
                  <span className="font-editorial italic font-normal text-cyan">Schedule</span> {nextAction.label.replace("Schedule", "").trim()}
                </>
              ) : nextAction.label.startsWith("Connect") ? (
                <>
                  <span className="font-editorial italic font-normal text-cyan">Connect</span> {nextAction.label.replace("Connect", "").trim()}
                </>
              ) : (
                nextAction.label
              )}
            </h3>
            <p className="mt-3.5 max-w-2xl text-sm leading-relaxed text-zinc-400">{nextAction.detail}</p>

            <div className="mt-6 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => onSection(nextAction.section)}
                className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-cyan px-6 text-xs font-bold uppercase tracking-wider text-ink transition-all duration-300 hover:scale-[1.03] hover:shadow-[0_10px_24px_rgba(102,232,249,0.25)]"
              >
                <Wand2 className="h-4 w-4" />
                <span>{nextAction.label}</span>
              </button>
              <button
                type="button"
                onClick={() => onSection("templates")}
                className="text-xs font-medium text-zinc-500 underline-offset-4 transition hover:text-zinc-300 hover:underline"
              >
                Or browse templates
              </button>
            </div>
          </div>

          <div className="grid min-w-full grid-cols-2 gap-2 rounded-[28px] border border-border bg-surface-panel p-3 sm:min-w-0 xl:w-[460px]">
            {statusSummary.map((item) => (
              <button
                key={item.label}
                type="button"
                onClick={() => onSection(item.section)}
                className="group rounded-2xl border border-border bg-surface px-4 py-3.5 text-left transition-all hover:border-cyan/[0.22] hover:bg-surface-raised"
              >
                <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500 transition-colors group-hover:text-cyan">{item.label}</p>
                <p className="mt-1.5 truncate text-base font-semibold tracking-tight text-zinc-100 group-hover:text-white">{item.value}</p>
              </button>
            ))}
          </div>
        </div>
      </div>

      <WorkflowRail steps={workflowSteps} onSection={onSection} />

      <div className="grid gap-4 sm:grid-cols-2">
        <MetricFrame
          title="Clips in progress"
          value={activeJobs ? `${activeJobs} running` : clips.length ? `${clips.length} clips total` : "No active runs"}
          detail={
            activeJobs
              ? "Clips are rendering in the background. Open Review when they land."
              : clips.length
                ? "Clips are ready to approve, fix, or schedule."
                : "Paste a long video on Create when you’re ready for the next batch."
          }
          action="Open Create"
          icon={RefreshCcw}
          onAction={() => onSection("generate")}
        />
        <MetricFrame
          title="Connected accounts"
          value={`${readyPlatforms}/${targetCount} live`}
          detail={
            readyPlatforms === targetCount
              ? "All publish accounts for this workspace are connected."
              : "Connect the remaining accounts so scheduled clips can go live."
          }
          action="Manage accounts"
          icon={Share2}
          onAction={() => onSection("publish")}
        />
      </div>
    </section>
  );
}
