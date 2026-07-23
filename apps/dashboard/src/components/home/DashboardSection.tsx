"use client";

import {Sparkles, Wand2, ArrowUpRight, Zap, RefreshCcw, Calendar, Share2, Palette} from "lucide-react";
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
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold text-white tracking-[-0.02em]">
            Production <span className="font-editorial italic font-normal text-cyan">pipeline</span>
          </h3>
          <p className="text-xs text-zinc-500 mt-0.5">Real-time status of your end-to-end automated media workflow</p>
        </div>
        <div className="flex items-center gap-1.5 self-start">
          <span className="h-2 w-2 rounded-full bg-cyan animate-pulse" />
          <span className="text-[10px] uppercase font-bold tracking-wider text-cyan">Live Sync</span>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-6">
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
                  ? "border-teal/[0.22] bg-teal/[0.04] hover:bg-teal/[0.08] hover:border-teal/[0.35]"
                  : isActive
                    ? "border-cyan/[0.30] bg-cyan/[0.04] hover:bg-cyan/[0.08] hover:border-cyan/[0.45] shadow-[0_4px_16px_rgba(102,232,249,0.04)]"
                    : isBlocked
                      ? "border-danger/[0.20] bg-danger/[0.04] hover:bg-danger/[0.08] hover:border-danger/[0.30]"
                      : "border-white/[0.05] bg-black/15 hover:border-white/[0.12] hover:bg-black/24"
              }`}
            >
              <div className="mb-5 flex items-center justify-between">
                <span className="text-[10px] font-bold tracking-widest text-zinc-500 group-hover:text-zinc-400 transition-colors">0{index + 1}</span>
                <span className={`h-2 w-2 rounded-full transition-all duration-300 ${
                  isReady 
                    ? "bg-teal shadow-[0_0_8px_rgba(0,194,183,0.5)]" 
                    : isActive 
                      ? "bg-cyan shadow-[0_0_8px_rgba(98,238,248,0.5)] animate-pulse" 
                      : isBlocked 
                        ? "bg-danger shadow-[0_0_8px_rgba(254,91,121,0.5)]" 
                        : "bg-zinc-700"
                }`} />
              </div>
              <p className="font-semibold text-sm text-white group-hover:text-cyan transition-colors truncate">{step.label}</p>
              <p className="mt-1 text-[11px] text-zinc-500 group-hover:text-zinc-400 transition-colors truncate">{step.detail}</p>
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
          <p className="mt-3.5 text-3xl font-semibold tracking-[-0.03em] text-white tabular-nums">{value}</p>
        </div>
        <span className="grid h-10 w-10 place-items-center rounded-2xl border border-white/[0.06] bg-black/20 text-zinc-400">
          <Icon className="h-5 w-5" />
        </span>
      </div>
      <p className="mt-3.5 text-xs text-zinc-400 leading-relaxed max-w-[85%]">{detail}</p>
      <button
        type="button"
        onClick={onAction}
        className="mt-5 inline-flex h-9 items-center gap-1.5 rounded-full border border-white/[0.10] bg-black/24 px-4 text-xs font-semibold text-zinc-200 transition-all hover:bg-white/[0.06] hover:text-white"
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
      {/* Prime Next-Best-Action Editorial Block */}
      <div className="relative overflow-hidden rounded-[36px] border border-cyan/[0.18] bg-gradient-to-b from-cyan/[0.04] to-transparent p-6 sm:p-8 shadow-[0_20px_50px_rgba(0,0,0,0.3)]">
        {/* Ambient backing glow */}
        <div className="absolute right-0 top-0 -z-10 h-72 w-72 rounded-full bg-cyan/[0.03] blur-[80px]" />
        
        <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-6">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-cyan/[0.12] text-cyan">
                <Zap className="h-3 w-3 fill-current" />
              </span>
              <p className="text-[10px] font-bold uppercase tracking-widest text-cyan">Next Best Action</p>
            </div>
            
            <h3 className="mt-4 text-3xl font-semibold tracking-[-0.04em] text-white md:text-4xl leading-tight">
              {nextAction.label.startsWith("Review") ? (
                <>
                  <span className="font-editorial italic font-normal text-cyan">Review</span>{" "}
                  {nextAction.label.replace("Review", "").trim()}
                </>
              ) : nextAction.label.startsWith("Generate") ? (
                <>
                  <span className="font-editorial italic font-normal text-cyan">Generate</span>{" "}
                  {nextAction.label.replace("Generate", "").trim()}
                </>
              ) : nextAction.label.startsWith("Choose") ? (
                <>
                  <span className="font-editorial italic font-normal text-cyan">Choose</span>{" "}
                  {nextAction.label.replace("Choose", "").trim()}
                </>
              ) : (
                nextAction.label
              )}
            </h3>
            <p className="mt-3.5 max-w-2xl text-sm leading-relaxed text-zinc-400">
              {nextAction.detail}
            </p>
            
            <div className="mt-6 flex flex-wrap gap-3">
              <button
                onClick={() => onSection(nextAction.section)}
                className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-cyan px-6 text-xs font-bold uppercase tracking-wider text-ink transition-all duration-300 hover:scale-[1.03] hover:shadow-[0_10px_24px_rgba(102,232,249,0.25)]"
              >
                <Wand2 className="h-4 w-4" />
                <span>Continue Pipeline</span>
              </button>
              <button
                onClick={() => onSection("templates")}
                className="inline-flex h-12 items-center justify-center gap-2 rounded-full border border-white/[0.10] bg-black/24 px-6 text-xs font-bold uppercase tracking-wider text-zinc-200 transition-all hover:bg-white/[0.05] hover:text-white"
              >
                <Sparkles className="h-4 w-4 text-zinc-400" />
                <span>Browse Templates</span>
              </button>
            </div>
          </div>

          {/* Quick status timeline summary */}
          <div className="grid grid-cols-2 gap-2 rounded-[28px] border border-white/[0.06] bg-black/25 p-3 min-w-full sm:min-w-0 xl:w-[460px]">
            {statusSummary.map((item) => (
              <button
                key={item.label}
                type="button"
                onClick={() => onSection(item.section)}
                className="group rounded-2xl border border-white/[0.05] bg-canvas-deep/50 px-4 py-3.5 text-left transition-all hover:border-cyan/[0.22] hover:bg-black/10"
              >
                <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500 group-hover:text-cyan transition-colors">{item.label}</p>
                <p className="mt-1.5 truncate text-base font-semibold text-zinc-100 group-hover:text-white tracking-tight">{item.value}</p>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Workflow Rails */}
      <WorkflowRail steps={workflowSteps} onSection={onSection} />

      {/* Modular Metrics Frame Row */}
      <div className="grid gap-4 sm:grid-cols-2">
        <MetricFrame
          title="Current Batch Status"
          value={activeJobs ? `${activeJobs} running` : clips.length ? `${clips.length} clips total` : "No active runs"}
          detail={
            activeJobs
              ? "The media engine is currently rendering clips in the background. Open workspace when ready."
              : clips.length
                ? "Your raw generated clips are ready for review. Access the editor workspace to fine-tune."
                : "No generation processes are currently active. Choose a template to launch a batch."
          }
          action="Open Generation Deck"
          icon={RefreshCcw}
          onAction={() => onSection("generate")}
        />
        <MetricFrame
          title="Connected Accounts"
          value={`${readyPlatforms}/${targetCount} live`}
          detail={
            readyPlatforms === targetCount
              ? "All designated social platform channels are fully authenticated and waiting for clips."
              : "Some of your production output networks require credential authentication to authorize posts."
          }
          action="Manage Channels"
          icon={Share2}
          onAction={() => onSection("publish")}
        />
      </div>
    </section>
  );
}
