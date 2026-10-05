import assert from "node:assert/strict";
import {describe, it} from "node:test";
import {classifyPublishError} from "./publish-recovery.ts";

describe("classifyPublishError", () => {
  it("returns null for empty errors", () => {
    assert.equal(classifyPublishError(""), null);
    assert.equal(classifyPublishError(undefined), null);
  });

  it("asks to reconnect on auth failures", () => {
    assert.equal(classifyPublishError("HTTP 401 Unauthorized")?.kind, "reconnect");
    assert.equal(classifyPublishError("invalid credentials for youtube")?.kind, "reconnect");
    assert.equal(classifyPublishError("token expired")?.label, "Reconnect account");
  });

  it("asks to re-render when the video file is the problem", () => {
    assert.equal(classifyPublishError("rendered video file missing")?.kind, "rerender");
    assert.equal(classifyPublishError("Telegram copy above 49MB after compression")?.kind, "rerender");
  });

  it("offers retry for transient failures", () => {
    assert.equal(classifyPublishError("Telegram upload was interrupted: broken pipe")?.kind, "retry");
    assert.equal(classifyPublishError("something unexpected")?.kind, "retry");
  });

  it("offers no one-click fix for TikTok audit or cooldown", () => {
    assert.equal(classifyPublishError("unaudited_client_can_only_post_to_private_accounts"), null);
    assert.equal(classifyPublishError("platform cooldown active"), null);
  });
});
