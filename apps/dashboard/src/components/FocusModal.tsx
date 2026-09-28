"use client";

import {X} from "lucide-react";
import {type ReactNode, useEffect, useId, useRef} from "react";
import {createPortal} from "react-dom";

const focusableSelector = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export function FocusModal({
  open,
  title,
  subtitle,
  children,
  footer,
  onClose,
  width = "wide",
}: {
  open: boolean;
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
  width?: "default" | "wide" | "max";
}) {
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  const titleId = useId();
  const subtitleId = useId();

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    const previousPosition = document.body.style.position;
    const previousTop = document.body.style.top;
    const previousWidth = document.body.style.width;
    const scrollY = window.scrollY;
    document.body.style.overflow = "hidden";
    document.body.style.position = "fixed";
    document.body.style.top = `-${scrollY}px`;
    document.body.style.width = "100%";
    const autoFocusTarget = panelRef.current?.querySelector<HTMLElement>("[data-autofocus]:not(:disabled)");
    (autoFocusTarget || closeRef.current || panelRef.current)?.focus({preventScroll: true});
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;
      const focusable = Array.from(panelRef.current.querySelectorAll<HTMLElement>(focusableSelector)).filter(
        (element) => element.getClientRects().length > 0 && element.getAttribute("aria-hidden") !== "true",
      );
      if (!focusable.length) {
        event.preventDefault();
        panelRef.current.focus({preventScroll: true});
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === panelRef.current)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.body.style.position = previousPosition;
      document.body.style.top = previousTop;
      document.body.style.width = previousWidth;
      window.scrollTo(0, scrollY);
      document.removeEventListener("keydown", onKeyDown);
      if (previouslyFocused?.isConnected) previouslyFocused.focus({preventScroll: true});
    };
  }, [open]);

  if (!open) return null;
  if (typeof document === "undefined") return null;

  const widthClass =
    width === "max"
      ? "sm:max-w-[min(1320px,calc(100vw-48px))]"
      : width === "wide"
        ? "sm:max-w-[min(1120px,calc(100vw-48px))]"
        : "sm:max-w-[min(860px,calc(100vw-48px))]";

  return createPortal(
    <div className="fixed inset-0 z-[80]">
      <button
        type="button"
        aria-label="Close modal"
        className="absolute inset-0 h-full w-full cursor-default bg-black/72 backdrop-blur-sm"
        onClick={onClose}
      />
      <section
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={subtitle ? subtitleId : undefined}
        tabIndex={-1}
        className={`absolute inset-0 flex h-full w-full flex-col overflow-hidden border-white/[0.10] bg-surface shadow-glow sm:inset-x-6 sm:inset-y-6 sm:mx-auto sm:h-[calc(100vh-48px)] sm:rounded-[30px] sm:border ${widthClass}`}
      >
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-white/[0.08] bg-canvas-deep/70 px-5 py-4 backdrop-blur-xl">
          <div className="min-w-0">
            <h2 id={titleId} className="text-xl font-semibold text-white">{title}</h2>
            {subtitle ? <p id={subtitleId} className="mt-1 max-w-3xl text-sm leading-6 text-zinc-400">{subtitle}</p> : null}
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-white/[0.10] bg-surface text-zinc-300 transition hover:border-cyan/[0.25] hover:text-white"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 pb-[calc(1.25rem+env(safe-area-inset-bottom))]">{children}</div>
        {footer ? <footer className="shrink-0 border-t border-white/[0.08] bg-canvas-deep/70 px-5 py-4 pb-[calc(1rem+env(safe-area-inset-bottom))] backdrop-blur-xl">{footer}</footer> : null}
      </section>
    </div>,
    document.body,
  );
}

export function ModalTabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: {id: T; label: string}[];
  active: T;
  onChange: (id: T) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2 rounded-[18px] border border-white/[0.08] bg-black/24 p-2">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={`h-10 rounded-full px-4 text-sm font-semibold transition ${
            active === tab.id ? "bg-cyan text-ink shadow-[0_0_18px_rgba(108,226,238,0.18)]" : "text-zinc-400 hover:bg-white/[0.04] hover:text-white"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
