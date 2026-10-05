// Maps a raw publish error to the one recovery action the UI should offer.
// Rules mirror `publishActionHint` in MediaStudioApp so hint text and button agree.

export type PublishRecoveryKind = "reconnect" | "rerender" | "retry";

export type PublishRecovery = {kind: PublishRecoveryKind; label: string};

const LABELS: Record<PublishRecoveryKind, string> = {
  reconnect: "Reconnect account",
  rerender: "Re-render in Review",
  retry: "Retry now",
};

export function classifyPublishError(error?: string | null): PublishRecovery | null {
  const value = String(error || "").toLowerCase().trim();
  if (!value) return null;

  // Needs a human outside this app (TikTok audit) — no one-click fix.
  if (value.includes("unaudited_client_can_only_post_to_private_accounts")) return null;
  // Cooling down: retrying immediately would just skip again.
  if (value.includes("cooldown") || value.includes("cooling down")) return null;

  if (
    value.includes("401")
    || value.includes("unauthorized")
    || value.includes("token")
    || value.includes("invalid credentials")
    || value.includes("autherror")
    || value.includes("reconnect")
  ) {
    return {kind: "reconnect", label: LABELS.reconnect};
  }
  if (value.includes("rendered video file") || (value.includes("above") && value.includes("after compression"))) {
    return {kind: "rerender", label: LABELS.rerender};
  }
  return {kind: "retry", label: LABELS.retry};
}
