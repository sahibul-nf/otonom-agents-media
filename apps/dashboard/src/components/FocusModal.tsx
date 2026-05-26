"use client";

import {X} from "lucide-react";
import {type ReactNode, useEffect, useRef} from "react";

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

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    const previousPosition = document.body.style.position;
    const previousTop = document.body.style.top;
    const previousWidth = document.body.style.width;
    const scrollY = window.scrollY;
    document.body.style.overflow = "hidden";
    document.body.style.position = "fixed";
    document.body.style.top = `-${scrollY}px`;
    document.body.style.width = "100%";
    const autoFocusTarget = panelRef.current?.querySelector<HTMLElement>("[data-autofocus]");
    (autoFocusTarget || closeRef.current)?.focus({preventScroll: true});
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.body.style.position = previousPosition;
      document.body.style.top = previousTop;
      document.body.style.width = previousWidth;
      window.scrollTo(0, scrollY);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  if (!open) return null;

  const widthClass =
    width === "max"
      ? "sm:max-w-[min(1320px,calc(100vw-48px))]"
      : width === "wide"
        ? "sm:max-w-[min(1120px,calc(100vw-48px))]"
        : "sm:max-w-[min(860px,calc(100vw-48px))]";

  return (
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
        aria-label={title}
        className={`absolute inset-0 flex h-full w-full flex-col overflow-hidden border-white/[0.10] bg-surface shadow-glow sm:inset-x-6 sm:inset-y-6 sm:mx-auto sm:h-[calc(100vh-48px)] sm:rounded-[30px] sm:border ${widthClass}`}
      >
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-white/[0.08] bg-canvas-deep/70 px-5 py-4 backdrop-blur-xl">
          <div className="min-w-0">
            <h2 className="text-xl font-semibold text-white">{title}</h2>
            {subtitle ? <p className="mt-1 max-w-3xl text-sm leading-6 text-zinc-400">{subtitle}</p> : null}
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
    </div>
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
