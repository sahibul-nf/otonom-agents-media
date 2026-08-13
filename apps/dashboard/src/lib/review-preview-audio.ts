/** Exclusive Review gallery playback — only one card should emit audio at a time. */

type PauseFn = () => void;

let activePause: PauseFn | null = null;

export function claimReviewPreviewPlayback(pause: PauseFn) {
  if (activePause && activePause !== pause) activePause();
  activePause = pause;
}

export function releaseReviewPreviewPlayback(pause: PauseFn) {
  if (activePause === pause) activePause = null;
}
