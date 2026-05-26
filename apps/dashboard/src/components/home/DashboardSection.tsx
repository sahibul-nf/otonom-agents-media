"use client";

import {Sparkles, Wand2} from "lucide-react";
import {ClipCandidate, ScheduledPost} from "@/lib/media-api";

type Section = "dashboard" | "generate" | "templates" | "review" | "calendar" | "publish" | "brand";
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
    <details className="rounded-[28px] border border-white/[0.08] bg-surface p-4">
      <summary className="mb-4 flex cursor-pointer list-none items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-white">Production pipeline</h3>
          <p className="mt-1 text-sm text-zinc-500">Expand when you need bottleneck detail.</p>
        </div>
      </summary>
      <div className="grid gap-2 md:grid-cols-3 2xl:grid-cols-6">
        {steps.map((step, index) => (
          <button
            key={step.id}
            type="button"
            onClick={() => onSection(step.section)}
            className={`min-w-0 rounded-[22px] border p-4 text-left transition ${
              step.status === "ready"
                ? "border-teal/[0.22] bg-teal/[0.07]"
                : step.status === "active"
                  ? "border-cyan/[0.34] bg-cyan/[0.10]"
                  : step.status === "blocked"
                    ? "border-warning/[0.24] bg-warning/[0.08]"
                    : "border-white/[0.08] bg-canvas-deep"
            }`}
          >
            <div className="mb-4 flex items-center justify-between gap-3">
              <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">0{index + 1}</span>
              <span className={`h-2.5 w-2.5 rounded-full ${step.status === "ready" ? "bg-teal" : step.status === "active" ? "bg-cyan" : step.status === "blocked" ? "bg-warning" : "bg-white/[0.18]"}`} />
            </div>
            <p className="truncate font-semibold text-white">{step.label}</p>
            <p className="mt-1 truncate text-xs text-zinc-500">{step.detail}</p>
          </button>
        ))}
      </div>
    </details>
  );
}

function StateCard({title, value, detail, action, onAction}: {title: string; value: string; detail: string; action: string; onAction: () => void}) {
  return (
    <div className="rounded-[28px] border border-white/[0.08] bg-surface p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{title}</p>
      <p className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-white">{value}</p>
      <p className="mt-2 min-h-10 text-sm leading-5 text-zinc-400">{detail}</p>
      <button type="button" onClick={onAction} className="mt-4 rounded-full border border-cyan/[0.22] bg-teal/[0.08] px-4 py-2 text-sm font-semibold text-cyan">
        {action}
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
    {label: "Review queue", value: reviewCount ? `${reviewCount} need action` : "Clear"},
    {label: "Approved", value: approvedCount ? `${approvedCount} ready` : "None yet"},
    {label: "Schedule", value: schedule.length ? `${schedule.length} slots` : "No slots"},
    {label: "Channels", value: `${readyPlatforms}/${targetCount} ready`},
  ];
  return (
    <section className="grid gap-5">
      <div className="grid gap-5">
        <div className="overflow-hidden rounded-[30px] border border-cyan/[0.18] bg-[radial-gradient(circle_at_12%_0%,rgba(108,226,238,.16),transparent_34%),linear-gradient(180deg,rgba(255,255,255,.04),rgba(255,255,255,.015))] p-5 shadow-glow">
          <div className="grid gap-5">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-cyan">Next best action</p>
              <h3 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-white md:text-4xl">{nextAction.label}</h3>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-300">{nextAction.detail}</p>
              <div className="mt-5 flex flex-wrap gap-3">
                <button onClick={() => onSection(nextAction.section)} className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-cyan px-5 text-sm font-semibold text-ink">
                  <Wand2 className="h-4 w-4" />
                  Continue
                </button>
                <button onClick={() => onSection("templates")} className="inline-flex h-12 items-center justify-center gap-2 rounded-full border border-white/[0.10] bg-canvas-deep px-5 text-sm font-semibold text-zinc-200">
                  <Sparkles className="h-4 w-4" />
                  Browse templates
                </button>
              </div>
            </div>
            <div className="grid gap-2 rounded-[24px] border border-white/[0.08] bg-black/20 p-3 md:grid-cols-2 xl:grid-cols-4">
              {statusSummary.map((item) => (
                <div key={item.label} className="rounded-2xl border border-white/[0.08] bg-canvas-deep px-3 py-2">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">{item.label}</p>
                  <p className="mt-1 truncate text-sm font-semibold text-zinc-200">{item.value}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <WorkflowRail steps={workflowSteps} onSection={onSection} />

        <div className="grid gap-4 xl:grid-cols-2">
          <StateCard title="Current batch" value={activeJobs ? `${activeJobs} running` : clips.length ? `${clips.length} clips ready` : "No batch"} detail={activeJobs ? "Generation is still processing." : clips.length ? "Open Review to approve or repair." : "Create a batch from a source video."} action="Open Create" onAction={() => onSection("generate")} />
          <StateCard title="Channels" value={`${readyPlatforms}/${targetCount} ready`} detail={readyPlatforms === targetCount ? "Publishing targets are configured." : "Connect remaining platform accounts."} action="Open Channels" onAction={() => onSection("publish")} />
        </div>
      </div>
    </section>
  );
}
