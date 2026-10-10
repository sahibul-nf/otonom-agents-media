// Pure flow/navigation logic for the studio shell (no React) so it can be unit-tested.
import type {ClipCandidate, GenerationJob} from "./media-api";

export type Section = "dashboard" | "generate" | "explainer" | "templates" | "review" | "calendar" | "publish" | "brand";
export type CreateMode = "clips" | "packages" | "watch";

export const SECTION_IDS: readonly Section[] = ["dashboard", "generate", "explainer", "templates", "review", "calendar", "publish", "brand"];
export const CREATE_MODE_IDS: readonly CreateMode[] = ["clips", "packages", "watch"];

export type NextAction = {
  label: string;
  detail: string;
  section: Section;
  tone: "primary" | "warning" | "ready";
};

export type WorkflowStep = {
  id: string;
  label: string;
  status: "ready" | "active" | "blocked" | "idle";
  detail: string;
  section: Section;
};

export type FlowInput = {
  clips: Pick<ClipCandidate, "status">[];
  jobs: Pick<GenerationJob, "status">[];
  approvedCount: number;
  scheduledCount: number;
  readyPlatforms: number;
  targetCount: number;
  engineReady: boolean;
  hasTemplate: boolean;
};

const REVIEW_STATUSES = ["draft", "rendered", "held", "pending_auto_schedule"];
const ACTIVE_JOB_STATUSES = ["queued", "running"];

export function isSection(value: string | null | undefined): value is Section {
  return Boolean(value) && (SECTION_IDS as readonly string[]).includes(value as string);
}

/** Section requested via `?section=`; falls back to Home for missing/unknown values. */
export function sectionFromSearch(search: string): Section {
  const value = new URLSearchParams(search).get("section");
  return isSection(value) ? value : "dashboard";
}

/** Returns a search string for `section`, preserving unrelated params (e.g. `ops=1`). Home has no param. */
export function searchForSection(search: string, section: Section): string {
  const params = new URLSearchParams(search);
  if (section === "dashboard") {
    params.delete("section");
    params.delete("create");
  } else {
    params.set("section", section);
    if (section !== "generate") params.delete("create");
  }
  const next = params.toString();
  return next ? `?${next}` : "";
}

export function isCreateMode(value: string | null | undefined): value is CreateMode {
  return Boolean(value) && (CREATE_MODE_IDS as readonly string[]).includes(value as string);
}

/** Create sub-mode via `?create=`; defaults to clips. */
export function createModeFromSearch(search: string): CreateMode {
  const value = new URLSearchParams(search).get("create");
  return isCreateMode(value) ? value : "clips";
}

export function searchForCreateMode(search: string, mode: CreateMode): string {
  const params = new URLSearchParams(search);
  params.set("section", "generate");
  if (mode === "clips") params.delete("create");
  else params.set("create", mode);
  const next = params.toString();
  return next ? `?${next}` : "";
}

function plural(count: number, noun: string) {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

export function getNextAction(input: FlowInput): NextAction {
  const {clips, jobs, approvedCount, scheduledCount, readyPlatforms, targetCount, engineReady, hasTemplate} = input;
  const reviewCount = clips.filter((clip) => REVIEW_STATUSES.includes(clip.status)).length;
  const heldCount = clips.filter((clip) => clip.status === "held").length;
  const failedClips = clips.filter((clip) => clip.status === "failed").length;
  const partialPublish = clips.filter((clip) => clip.status === "partial_failed").length;
  const activeJobs = jobs.filter((job) => ACTIVE_JOB_STATUSES.includes(job.status)).length;
  const failedJobs = jobs.filter((job) => job.status === "failed").length;

  if (!engineReady) {
    return {label: "Check Create readiness", detail: "Make sure the media engine is running before you create clips.", section: "generate", tone: "warning"};
  }
  if (failedClips > 0) {
    return {label: `Fix ${plural(failedClips, "failed clip")}`, detail: "Open Review to re-render or remove clips that failed.", section: "review", tone: "warning"};
  }
  if (partialPublish > 0) {
    return {label: `Retry ${plural(partialPublish, "partly published clip")}`, detail: "Some platforms failed. Check Schedule and retry.", section: "calendar", tone: "warning"};
  }
  if (reviewCount > 0) {
    return {
      label: `Review ${plural(reviewCount, "clip")}`,
      detail: heldCount ? `Approve or skip the clips. ${heldCount} have unusable captions.` : "Approve or skip the strongest candidates.",
      section: "review",
      tone: "primary",
    };
  }
  if (activeJobs > 0) {
    return {label: "Clips are generating", detail: `${plural(activeJobs, "job")} running. Review opens once clips land.`, section: "generate", tone: "primary"};
  }
  if (!clips.length && failedJobs > 0) {
    return {label: "Check failed generation", detail: "The last batch failed. Open Create to see why and retry.", section: "generate", tone: "warning"};
  }
  if (!clips.length && !hasTemplate) {
    return {label: "Choose a visual style", detail: "Pick a template so new clips match your brand look.", section: "templates", tone: "primary"};
  }
  if (!clips.length) {
    return {label: "Create first clips", detail: "Paste a long YouTube video and land candidates in Review.", section: "generate", tone: "primary"};
  }
  if (approvedCount > 0 && targetCount > 0 && readyPlatforms === 0) {
    return {label: "Connect an account first", detail: "Connect at least one publish account before scheduling approved clips.", section: "publish", tone: "warning"};
  }
  if (approvedCount > 0) {
    return {
      label: `Schedule ${plural(approvedCount, "approved clip")}`,
      detail: scheduledCount > 0 ? `${scheduledCount} already scheduled. Place the rest into publishing slots.` : "Place approved clips into the next publishing slots.",
      section: "calendar",
      tone: "ready",
    };
  }
  if (targetCount > 0 && readyPlatforms < targetCount) {
    return {label: `Connect ${plural(targetCount - readyPlatforms, "publish account")}`, detail: "Connect the remaining accounts so scheduled clips can go live.", section: "publish", tone: "warning"};
  }
  return {label: "Create next batch", detail: "Queue is clear — create the next set of clips when you’re ready.", section: "generate", tone: "primary"};
}

/** Main loop only: Create → Review → Schedule → Publish. Setup items live in `buildSetupDetails`. */
export function buildWorkflowSteps(input: FlowInput): WorkflowStep[] {
  const {clips, jobs, approvedCount, scheduledCount, readyPlatforms, targetCount, engineReady, hasTemplate} = input;
  const reviewCount = clips.filter((clip) => REVIEW_STATUSES.includes(clip.status)).length;
  const activeJobs = jobs.filter((job) => ACTIVE_JOB_STATUSES.includes(job.status)).length;
  return [
    {
      id: "generate",
      label: "Create",
      status: activeJobs ? "active" : clips.length ? "ready" : engineReady && hasTemplate ? "active" : "blocked",
      detail: activeJobs ? `${plural(activeJobs, "job")} running` : clips.length ? plural(clips.length, "clip") : "No batch yet",
      section: "generate",
    },
    {
      id: "review",
      label: "Review",
      status: reviewCount ? "active" : approvedCount || scheduledCount ? "ready" : "idle",
      detail: reviewCount ? `${reviewCount} need action` : approvedCount ? `${approvedCount} approved` : "Waiting",
      section: "review",
    },
    {
      id: "schedule",
      label: "Schedule",
      status: scheduledCount ? "ready" : approvedCount ? "active" : "idle",
      detail: scheduledCount ? `${scheduledCount} queued` : approvedCount ? "Ready to slot" : "Waiting",
      section: "calendar",
    },
    {
      id: "publish",
      label: "Publish",
      status: targetCount && readyPlatforms >= targetCount ? "ready" : targetCount ? "active" : "idle",
      detail: targetCount ? `${readyPlatforms}/${targetCount} accounts connected` : "No accounts",
      section: "publish",
    },
  ];
}

/** Sidebar sub-labels for the Setup group (not part of the main loop). */
export function buildSetupDetails(hasTemplate: boolean): Partial<Record<Section, string>> {
  return {
    brand: hasTemplate ? "Style ready" : "Pick a preset",
    templates: hasTemplate ? "Available" : "Choose first",
    explainer: "Topic to video",
  };
}
