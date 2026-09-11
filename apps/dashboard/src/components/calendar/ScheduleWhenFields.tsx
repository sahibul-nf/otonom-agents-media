"use client";

import {Loader2} from "lucide-react";
import {fromJakartaDatetimeLocal, nextJakartaSlot, toJakartaDatetimeLocal} from "@/components/calendar/schedule-when";

export function ScheduleWhenFields({
  value,
  onChange,
  onCommit,
  disabled = false,
  busy = false,
  commitLabel = "Save time",
  showCommit = true,
  commitOnShortcut = false,
}: {
  value: string;
  onChange: (datetimeLocal: string) => void;
  onCommit?: (iso: string) => void;
  disabled?: boolean;
  busy?: boolean;
  commitLabel?: string;
  showCommit?: boolean;
  commitOnShortcut?: boolean;
}) {
  function pickSlot(hour: number, minute: number) {
    const next = nextJakartaSlot(hour, minute);
    onChange(toJakartaDatetimeLocal(next));
    if (commitOnShortcut) {
      onCommit?.(next);
    }
  }

  return (
    <div className="grid gap-2">
      <input
        type="datetime-local"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 w-full rounded-xl border border-white/[0.10] bg-black/30 px-2 text-[11px] text-white outline-none focus:border-cyan/40 disabled:opacity-40"
      />
      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          disabled={disabled}
          onClick={() => pickSlot(9, 0)}
          className="rounded-full border border-white/[0.10] px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-zinc-400 hover:text-white disabled:opacity-40"
        >
          Next 09:00
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() => pickSlot(19, 30)}
          className="rounded-full border border-white/[0.10] px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-zinc-400 hover:text-white disabled:opacity-40"
        >
          Next 19:30
        </button>
        {showCommit && onCommit ? (
          <button
            type="button"
            disabled={disabled || busy || !value}
            onClick={() => onCommit(fromJakartaDatetimeLocal(value))}
            className="inline-flex items-center gap-1 rounded-full border border-cyan/20 bg-cyan/[0.08] px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-cyan disabled:opacity-40"
          >
            {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
            {commitLabel}
          </button>
        ) : null}
      </div>
    </div>
  );
}
