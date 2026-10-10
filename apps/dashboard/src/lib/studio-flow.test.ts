import assert from "node:assert/strict";
import {describe, it} from "node:test";
import {
  buildSetupDetails,
  buildWorkflowSteps,
  createModeFromSearch,
  getNextAction,
  searchForCreateMode,
  searchForSection,
  sectionFromSearch,
  type FlowInput,
} from "./studio-flow.ts";

const base: FlowInput = {
  clips: [],
  jobs: [],
  approvedCount: 0,
  scheduledCount: 0,
  readyPlatforms: 0,
  targetCount: 0,
  engineReady: true,
  hasTemplate: true,
};
const clip = (status: string) => ({status});
const job = (status: string) => ({status});

describe("getNextAction", () => {
  it("blocks on engine first", () => {
    const action = getNextAction({...base, engineReady: false, clips: [clip("failed")]});
    assert.equal(action.section, "generate");
    assert.equal(action.tone, "warning");
  });

  it("surfaces failed clips before review work", () => {
    const action = getNextAction({...base, clips: [clip("failed"), clip("rendered")]});
    assert.equal(action.section, "review");
    assert.equal(action.tone, "warning");
    assert.match(action.label, /1 failed clip$/);
  });

  it("surfaces partly published clips with Schedule as the target", () => {
    const action = getNextAction({...base, clips: [clip("partial_failed")]});
    assert.equal(action.section, "calendar");
    assert.equal(action.tone, "warning");
  });

  it("asks for review and mentions held clips", () => {
    const action = getNextAction({...base, clips: [clip("rendered"), clip("held")]});
    assert.equal(action.section, "review");
    assert.equal(action.label, "Review 2 clips");
    assert.match(action.detail, /1 have unusable captions/);
  });

  it("reports a running generation job when nothing to review", () => {
    const action = getNextAction({...base, jobs: [job("running")]});
    assert.equal(action.label, "Clips are generating");
    assert.equal(action.section, "generate");
  });

  it("prefers review over a running job when clips already wait", () => {
    const action = getNextAction({...base, clips: [clip("rendered")], jobs: [job("running")]});
    assert.equal(action.section, "review");
  });

  it("flags a failed generation only when there are no clips", () => {
    assert.equal(getNextAction({...base, jobs: [job("failed")]}).label, "Check failed generation");
    const withClips = getNextAction({...base, jobs: [job("failed")], clips: [clip("approved")], approvedCount: 1});
    assert.notEqual(withClips.label, "Check failed generation");
  });

  it("asks for a template, then first clips", () => {
    assert.equal(getNextAction({...base, hasTemplate: false}).section, "templates");
    assert.equal(getNextAction(base).label, "Create first clips");
  });

  it("asks to connect an account before scheduling when none is ready", () => {
    const action = getNextAction({...base, clips: [clip("approved")], approvedCount: 1, targetCount: 3, readyPlatforms: 0});
    assert.equal(action.section, "publish");
    assert.equal(action.tone, "warning");
  });

  it("schedules approved clips when at least one account is ready", () => {
    const action = getNextAction({...base, clips: [clip("approved")], approvedCount: 1, targetCount: 3, readyPlatforms: 1});
    assert.equal(action.section, "calendar");
    assert.equal(action.label, "Schedule 1 approved clip");
  });

  it("keeps scheduling when approved clips are partly scheduled", () => {
    const action = getNextAction({
      ...base,
      clips: [clip("approved"), clip("approved"), clip("scheduled")],
      approvedCount: 2,
      scheduledCount: 1,
      targetCount: 1,
      readyPlatforms: 1,
    });
    assert.equal(action.section, "calendar");
    assert.match(action.detail, /1 already scheduled/);
  });

  it("nudges remaining accounts once everything is scheduled", () => {
    const action = getNextAction({...base, clips: [clip("scheduled")], scheduledCount: 1, targetCount: 3, readyPlatforms: 1});
    assert.equal(action.section, "publish");
    assert.equal(action.label, "Connect 2 publish accounts");
  });

  it("falls back to the next batch", () => {
    const action = getNextAction({...base, clips: [clip("published")], targetCount: 1, readyPlatforms: 1});
    assert.equal(action.label, "Create next batch");
  });
});

describe("buildWorkflowSteps", () => {
  it("contains only the main loop in order", () => {
    assert.deepEqual(
      buildWorkflowSteps(base).map((step) => step.label),
      ["Create", "Review", "Schedule", "Publish"],
    );
  });

  it("marks Create active while a job runs and describes accounts clearly", () => {
    const steps = buildWorkflowSteps({...base, jobs: [job("queued")], targetCount: 3, readyPlatforms: 2});
    assert.equal(steps[0].status, "active");
    assert.equal(steps[3].detail, "2/3 accounts connected");
    assert.equal(steps[3].status, "active");
  });

  it("marks Publish ready when all accounts are connected", () => {
    const steps = buildWorkflowSteps({...base, targetCount: 2, readyPlatforms: 2});
    assert.equal(steps[3].status, "ready");
  });
});

describe("buildSetupDetails", () => {
  it("describes Brand and Templates by template availability", () => {
    assert.equal(buildSetupDetails(true).brand, "Style ready");
    assert.equal(buildSetupDetails(false).templates, "Choose first");
  });
});

describe("section URL helpers", () => {
  it("reads a valid section and falls back to dashboard", () => {
    assert.equal(sectionFromSearch("?section=review"), "review");
    assert.equal(sectionFromSearch("?section=nope"), "dashboard");
    assert.equal(sectionFromSearch(""), "dashboard");
  });

  it("writes the section while preserving other params", () => {
    assert.equal(searchForSection("", "review"), "?section=review");
    assert.equal(searchForSection("?ops=1", "calendar"), "?ops=1&section=calendar");
    assert.equal(searchForSection("?section=review&ops=1", "dashboard"), "?ops=1");
    assert.equal(searchForSection("?section=review", "dashboard"), "");
  });

  it("clears create mode when leaving Create", () => {
    assert.equal(searchForSection("?section=generate&create=packages", "review"), "?section=review");
  });

  it("reads and writes Create mode", () => {
    assert.equal(createModeFromSearch(""), "clips");
    assert.equal(createModeFromSearch("?create=packages"), "packages");
    assert.equal(searchForCreateMode("", "packages"), "?section=generate&create=packages");
    assert.equal(searchForCreateMode("?section=generate&create=watch", "clips"), "?section=generate");
  });
});
