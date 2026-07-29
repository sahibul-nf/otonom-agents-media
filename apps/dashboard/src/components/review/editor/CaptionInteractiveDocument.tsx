"use client";

import {LocateFixed, Pause, Play, Scissors} from "lucide-react";
import {useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode} from "react";
import {
  CAPTION_PAUSE_GAP_MS,
  activeCaptionWordIndexAtMs,
  captionWordPauseMarks,
  captionsHaveWordTimings,
  flattenCaptionWords,
  joinCaptionsFromSegments,
  splitCaptionDocumentTexts,
} from "@/components/review/editor/types";
import type {CaptionSegment, ClipCandidate} from "@/lib/media-api";

type SelectionToolbar = {
  top: number;
  left: number;
  cueIndex: number;
};

type PauseMenu = {
  top: number;
  left: number;
  atMs: number;
  gapMs: number;
  afterCueIndex: number;
};

type Props = {
  clip: ClipCandidate;
  captions: CaptionSegment[];
  value: string;
  editable: boolean;
  selectedCaptionIndex?: number;
  currentSeconds: number;
  isPlaying: boolean;
  actionMessage?: string;
  actionTone?: "running" | "done" | "failed";
  onChange: (value: string) => void;
  onSelectCaption: (index: number) => void;
  onHighlightCaption: (index: number) => void;
  onSeek: (seconds: number) => void;
  onTogglePlayback: () => void;
  onRemovePause?: (pause: {atMs: number; gapMs: number; afterCueIndex: number}) => void;
};

export function CaptionInteractiveDocument({
  captions,
  value,
  editable,
  selectedCaptionIndex,
  currentSeconds,
  isPlaying,
  actionMessage,
  actionTone,
  onChange,
  onSelectCaption,
  onHighlightCaption,
  onSeek,
  onTogglePlayback,
  onRemovePause,
}: Props) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const editableRef = useRef<HTMLDivElement | null>(null);
  const focusedRef = useRef(false);
  const lastEmittedRef = useRef(value);
  const lastScrolledWordRef = useRef<number | undefined>(undefined);
  const [toolbar, setToolbar] = useState<SelectionToolbar | null>(null);
  const [pauseMenu, setPauseMenu] = useState<PauseMenu | null>(null);

  const cueTexts = useMemo(() => splitCaptionDocumentTexts(captions, value), [captions, value]);
  const pristine = useMemo(
    () => normalizeDoc(value) === normalizeDoc(joinCaptionsFromSegments(captions)),
    [captions, value],
  );
  const pauseMarks = useMemo(() => captionWordPauseMarks(captions, CAPTION_PAUSE_GAP_MS), [captions]);
  const karaokeEnabled = pristine && captionsHaveWordTimings(captions);
  const activeWordIndex = useMemo(() => {
    if (!karaokeEnabled || !isPlaying) return undefined;
    return activeCaptionWordIndexAtMs(captions, currentSeconds * 1000);
  }, [captions, currentSeconds, isPlaying, karaokeEnabled]);

  useLayoutEffect(() => {
    const node = editableRef.current;
    if (!node) return;
    if (focusedRef.current && value === lastEmittedRef.current) return;
    rebuildEditableDocument(node, {
      cueTexts,
      captions,
      selectedCaptionIndex,
      activeWordIndex,
      pristine,
      pauseMarks,
      karaokeEnabled,
    });
    // Playhead word/cue classes sync separately so typing caret is not reset every tick.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [captions, cueTexts, karaokeEnabled, pauseMarks, pristine, value]);

  useLayoutEffect(() => {
    const node = editableRef.current;
    if (!node) return;
    syncActiveHighlightClasses(node, {
      selectedCaptionIndex,
      activeWordIndex,
      karaokeEnabled,
    });
    if (
      karaokeEnabled &&
      isPlaying &&
      activeWordIndex !== undefined &&
      !focusedRef.current &&
      lastScrolledWordRef.current !== activeWordIndex
    ) {
      const word = node.querySelector<HTMLElement>(`[data-word-index="${activeWordIndex}"]`);
      if (word) {
        word.scrollIntoView({block: "nearest", inline: "nearest"});
        lastScrolledWordRef.current = activeWordIndex;
      }
    }
    if (!isPlaying) lastScrolledWordRef.current = undefined;
  }, [activeWordIndex, isPlaying, karaokeEnabled, selectedCaptionIndex]);

  useEffect(() => {
    function clearMenusOnOutside(event: Event) {
      const root = rootRef.current;
      if (!root || !(event.target instanceof Node) || root.contains(event.target)) return;
      setToolbar(null);
      setPauseMenu(null);
    }
    // Only dismiss on outside pointer press. Capture-phase scroll clears the menu
    // immediately when the overflow rail scroll-into-views a pause chip on click.
    document.addEventListener("mousedown", clearMenusOnOutside);
    return () => {
      document.removeEventListener("mousedown", clearMenusOnOutside);
    };
  }, []);

  function emitFromDom() {
    const node = editableRef.current;
    if (!node) return;
    const next = serializeCueTexts(node);
    lastEmittedRef.current = next;
    onChange(next);
  }

  function openPauseMenu(chip: HTMLElement) {
    const atMs = Number(chip.dataset.pauseAtMs);
    const gapMs = Number(chip.dataset.pauseGapMs);
    const cueIndex = Number(chip.dataset.pauseAfterCue);
    if (!Number.isFinite(atMs)) return;
    const chipRect = chip.getBoundingClientRect();
    setToolbar(null);
    setPauseMenu({
      // Prefer below the chip so overflow rails do not clip the menu away.
      top: Math.min(window.innerHeight - 52, chipRect.bottom + 8),
      left: Math.min(window.innerWidth - 16, Math.max(16, chipRect.left + chipRect.width / 2)),
      atMs,
      gapMs: Number.isFinite(gapMs) ? gapMs : 0,
      afterCueIndex: Number.isFinite(cueIndex) ? cueIndex : 0,
    });
  }

  function refreshToolbar() {
    const root = rootRef.current;
    const selection = window.getSelection();
    if (!root || !selection || selection.isCollapsed || selection.rangeCount === 0) {
      setToolbar(null);
      return;
    }
    const range = selection.getRangeAt(0);
    if (!root.contains(range.commonAncestorContainer)) {
      setToolbar(null);
      return;
    }
    const rect = range.getBoundingClientRect();
    if (rect.width < 2 && rect.height < 2) {
      setToolbar(null);
      return;
    }
    const cueIndex = cueIndexFromNode(selection.anchorNode) ?? selectedCaptionIndex ?? 0;
    setToolbar({
      top: Math.max(8, rect.top - 44),
      left: Math.min(window.innerWidth - 16, Math.max(16, rect.left + rect.width / 2)),
      cueIndex,
    });
  }

  function seekToPause(atMs: number, cueIndex: number) {
    onHighlightCaption(cueIndex);
    onSeek(Math.max(0, atMs / 1000));
  }

  return (
    <div ref={rootRef} className="relative px-2 py-1.5">
      <p className="mb-3 text-[11px] leading-5 text-zinc-600">
        Continuous copy · {captions.length} timed cue{captions.length === 1 ? "" : "s"}
        {karaokeEnabled ? " · word follow" : ""}
        {pauseMarks.length ? ` · ${pauseMarks.length} pause mark${pauseMarks.length === 1 ? "" : "s"}` : ""} · select text for
        playhead actions
      </p>
      {actionMessage ? (
        <p
          className={`mb-3 text-[11px] font-medium ${
            actionTone === "failed" ? "text-danger" : actionTone === "done" ? "text-cyan" : "text-warning"
          }`}
          role="status"
        >
          {actionMessage}
        </p>
      ) : null}

      <div
        ref={editableRef}
        role="textbox"
        aria-label="Caption document"
        aria-multiline="true"
        contentEditable={editable}
        suppressContentEditableWarning
        spellCheck
        className="min-h-[180px] whitespace-pre-wrap break-words text-[15px] leading-7 text-zinc-100 outline-none empty:before:text-zinc-600 empty:before:content-[attr(data-placeholder)]"
        data-placeholder="Write captions as continuous copy…"
        onFocus={() => {
          focusedRef.current = true;
        }}
        onBlur={() => {
          focusedRef.current = false;
          setToolbar(null);
        }}
        onInput={() => {
          if (!editable) return;
          emitFromDom();
        }}
        onMouseDown={(event) => {
          const target = event.target as HTMLElement | null;
          const pause = target?.closest<HTMLElement>("[data-pause-at-ms]");
          if (!pause) return;
          // Keep contentEditable from stealing focus / scrolling the chip away.
          event.preventDefault();
          event.stopPropagation();
        }}
        onClick={(event) => {
          const target = event.target as HTMLElement | null;
          if (!target) return;
          const pause = target.closest<HTMLElement>("[data-pause-at-ms]");
          if (pause) {
            event.preventDefault();
            event.stopPropagation();
            openPauseMenu(pause);
            return;
          }
          setPauseMenu(null);
          const index = cueIndexFromNode(target);
          if (index === undefined) return;
          onSelectCaption(index);
        }}
        onKeyUp={() => {
          if (!editable) return;
          const selection = window.getSelection();
          const index = cueIndexFromNode(selection?.anchorNode ?? null);
          if (index !== undefined) onHighlightCaption(index);
          refreshToolbar();
        }}
        onMouseUp={() => refreshToolbar()}
        onTouchEnd={() => {
          window.setTimeout(() => refreshToolbar(), 0);
        }}
      />

      {pauseMenu ? (
        <div
          role="menu"
          aria-label="Pause actions"
          className="fixed z-[80] flex -translate-x-1/2 items-center gap-0.5 rounded-full border border-white/[0.08] bg-canvas-deep/95 p-1 shadow-[0_12px_40px_rgba(0,0,0,0.45)] backdrop-blur-xl"
          style={{top: pauseMenu.top, left: pauseMenu.left}}
          onMouseDown={(event) => event.preventDefault()}
        >
          <ToolbarButton
            label="Seek to pause"
            onClick={() => {
              seekToPause(pauseMenu.atMs, pauseMenu.afterCueIndex);
              setPauseMenu(null);
            }}
          >
            <LocateFixed className="h-3.5 w-3.5" />
            <span className="text-[11px] font-medium">Seek</span>
          </ToolbarButton>
          {onRemovePause ? (
            <ToolbarButton
              label="Remove pause"
              onClick={() => {
                onRemovePause({
                  atMs: pauseMenu.atMs,
                  gapMs: pauseMenu.gapMs,
                  afterCueIndex: pauseMenu.afterCueIndex,
                });
                setPauseMenu(null);
              }}
            >
              <Scissors className="h-3.5 w-3.5" />
              <span className="text-[11px] font-medium">Remove</span>
            </ToolbarButton>
          ) : null}
        </div>
      ) : null}

      {toolbar ? (
        <div
          role="toolbar"
          aria-label="Caption selection actions"
          className="fixed z-[80] flex -translate-x-1/2 items-center gap-0.5 rounded-full border border-white/[0.08] bg-canvas-deep/95 p-1 shadow-[0_12px_40px_rgba(0,0,0,0.45)] backdrop-blur-xl"
          style={{top: toolbar.top, left: toolbar.left}}
          onMouseDown={(event) => event.preventDefault()}
        >
          <ToolbarButton label={isPlaying ? "Pause preview" : "Play preview"} onClick={() => onTogglePlayback()}>
            {isPlaying ? <Pause className="h-3.5 w-3.5" /> : <Play className="ml-0.5 h-3.5 w-3.5" />}
            <span className="text-[11px] font-medium">{isPlaying ? "Pause" : "Play"}</span>
          </ToolbarButton>
          <ToolbarButton
            label="Seek to selection"
            onClick={() => {
              onSelectCaption(toolbar.cueIndex);
              setToolbar(null);
            }}
          >
            <LocateFixed className="h-3.5 w-3.5" />
            <span className="text-[11px] font-medium">Seek</span>
          </ToolbarButton>
        </div>
      ) : null}
    </div>
  );
}

function ToolbarButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="inline-flex h-8 items-center gap-1.5 rounded-full px-2.5 text-zinc-200 transition hover:bg-white/[0.08] hover:text-white"
    >
      {children}
    </button>
  );
}

function rebuildEditableDocument(
  node: HTMLDivElement,
  options: {
    cueTexts: string[];
    captions: CaptionSegment[];
    selectedCaptionIndex?: number;
    activeWordIndex?: number;
    pristine: boolean;
    pauseMarks: ReturnType<typeof captionWordPauseMarks>;
    karaokeEnabled: boolean;
  },
) {
  const {cueTexts, captions, selectedCaptionIndex, activeWordIndex, pristine, pauseMarks, karaokeEnabled} = options;
  node.replaceChildren();

  const words = flattenCaptionWords(captions);
  const useWordLayout = karaokeEnabled && words.length > 0;

  if (useWordLayout) {
    const pauseByAfterIndex = new Map<number, (typeof pauseMarks)[number]>();
    words.forEach((word, index) => {
      if (index >= words.length - 1) return;
      const next = words[index + 1];
      const gapMs = Math.max(0, next.startMs - word.endMs);
      if (gapMs < CAPTION_PAUSE_GAP_MS) return;
      pauseByAfterIndex.set(index, {afterCueIndex: word.cueIndex, gapMs, atMs: word.endMs});
    });

    words.forEach((word, index) => {
      const span = document.createElement("span");
      span.dataset.cueIndex = String(word.cueIndex);
      span.dataset.wordIndex = String(index);
      span.className = wordClassName({
        cueActive: word.cueIndex === selectedCaptionIndex,
        wordActive: index === activeWordIndex,
      });
      span.textContent = word.text || "\u200b";
      node.appendChild(span);

      const pause = pauseByAfterIndex.get(index);
      if (pause) {
        appendPauseChip(node, pause.afterCueIndex, pause.gapMs, pause.atMs);
      } else if (index < words.length - 1) {
        node.appendChild(document.createTextNode(" "));
      }
    });
    return;
  }

  const pauseByCue = new Map<number, (typeof pauseMarks)[number]>();
  pauseMarks.forEach((mark) => {
    const existing = pauseByCue.get(mark.afterCueIndex);
    if (!existing || mark.gapMs > existing.gapMs) pauseByCue.set(mark.afterCueIndex, mark);
  });

  cueTexts.forEach((text, index) => {
    const span = document.createElement("span");
    span.dataset.cueIndex = String(index);
    span.className = cueClassName(index === selectedCaptionIndex);
    span.textContent = text || "\u200b";
    node.appendChild(span);

    const pause = pauseByCue.get(index);
    if (pause && index < cueTexts.length - 1) {
      appendPauseChip(node, pause.afterCueIndex, pause.gapMs, pause.atMs);
    } else if (index < cueTexts.length - 1) {
      node.appendChild(document.createTextNode(" "));
    }
  });
}

function appendPauseChip(node: HTMLDivElement, cueIndex: number, gapMs: number, atMs: number) {
  node.appendChild(document.createTextNode(" "));
  const chip = document.createElement("button");
  chip.type = "button";
  chip.contentEditable = "false";
  chip.dataset.pauseAfterCue = String(cueIndex);
  chip.dataset.pauseAtMs = String(atMs);
  chip.dataset.pauseGapMs = String(gapMs);
  const label = formatGapLabel(gapMs);
  chip.className =
    "mx-0.5 inline-flex translate-y-[-1px] items-center rounded-md border border-white/[0.08] bg-white/[0.06] px-1.5 py-0.5 align-middle font-mono text-[11px] leading-none tabular-nums text-zinc-500 transition hover:border-cyan/35 hover:text-cyan";
  chip.setAttribute("aria-label", `Pause ${label}`);
  chip.title = `Pause ${label} · click for actions`;
  chip.textContent = label;
  node.appendChild(chip);
  node.appendChild(document.createTextNode(" "));
}

function syncActiveHighlightClasses(
  node: HTMLDivElement,
  options: {
    selectedCaptionIndex?: number;
    activeWordIndex?: number;
    karaokeEnabled: boolean;
  },
) {
  const {selectedCaptionIndex, activeWordIndex, karaokeEnabled} = options;
  if (karaokeEnabled) {
    node.querySelectorAll<HTMLElement>("[data-word-index]").forEach((span) => {
      const wordIndex = Number(span.dataset.wordIndex);
      const cueIndex = Number(span.dataset.cueIndex);
      span.className = wordClassName({
        cueActive: cueIndex === selectedCaptionIndex,
        wordActive: wordIndex === activeWordIndex,
      });
    });
    return;
  }
  node.querySelectorAll<HTMLElement>("[data-cue-index]").forEach((span) => {
    const index = Number(span.dataset.cueIndex);
    span.className = cueClassName(index === selectedCaptionIndex);
  });
}

function wordClassName({cueActive, wordActive}: {cueActive: boolean; wordActive: boolean}) {
  if (wordActive) {
    return "mx-0.5 inline rounded-md bg-cyan px-1.5 py-0.5 font-semibold text-ink shadow-[0_0_0_1px_rgba(98,238,248,0.35)] transition-colors";
  }
  if (cueActive) {
    return "rounded-sm bg-cyan/[0.08] text-zinc-100 transition-colors";
  }
  return "rounded-sm text-zinc-100 transition-colors hover:bg-white/[0.03]";
}

function cueClassName(active: boolean) {
  return active
    ? "rounded-sm bg-cyan/[0.14] text-white transition-colors"
    : "rounded-sm text-zinc-100 transition-colors hover:bg-white/[0.03]";
}

function serializeCueTexts(node: HTMLDivElement) {
  const parts: string[] = [];
  node.querySelectorAll<HTMLElement>("[data-cue-index]").forEach((span) => {
    const text = (span.textContent || "").replace(/\u200b/g, "").replace(/\s+/g, " ").trim();
    if (text) parts.push(text);
  });
  return parts.join(" ");
}

function formatGapLabel(gapMs: number) {
  const seconds = gapMs / 1000;
  if (seconds >= 10) return `${seconds.toFixed(0)}s`;
  return `${seconds.toFixed(seconds >= 1 ? 1 : 2)}s`;
}

function cueIndexFromNode(node: Node | null | undefined) {
  if (!node) return undefined;
  const element = node.nodeType === Node.ELEMENT_NODE ? (node as HTMLElement) : node.parentElement;
  const cue = element?.closest<HTMLElement>("[data-cue-index]");
  if (!cue) return undefined;
  const index = Number(cue.dataset.cueIndex);
  return Number.isFinite(index) ? index : undefined;
}

function normalizeDoc(value: string) {
  return value.replace(/\s+/g, " ").trim();
}
