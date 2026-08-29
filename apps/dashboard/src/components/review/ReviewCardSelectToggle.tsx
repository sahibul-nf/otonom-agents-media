"use client";

import {Check} from "lucide-react";

export function ReviewCardSelectToggle({
  selected,
  onToggle,
  label,
}: {
  selected: boolean;
  onToggle: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onToggle();
      }}
      aria-pressed={selected}
      aria-label={selected ? `Deselect ${label}` : `Select ${label}`}
      className={`grid h-8 w-8 place-items-center rounded-full border shadow-md backdrop-blur-md transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan ${
        selected
          ? "border-cyan/50 bg-cyan text-ink"
          : "border-white/10 bg-black/55 text-white/70 hover:bg-black/70 hover:text-white"
      }`}
    >
      {selected ? <Check className="h-3.5 w-3.5 stroke-[2.5]" /> : <span className="h-3.5 w-3.5 rounded-full border border-white/35" />}
    </button>
  );
}
