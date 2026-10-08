"use client";

import {Monitor, Moon, Sun} from "lucide-react";
import {useEffect, useState} from "react";
import {
  applyColorTheme,
  type ColorThemePreference,
  COLOR_THEME_STORAGE_KEY,
  readColorTheme,
  storeColorTheme,
} from "@/lib/color-theme";

const OPTIONS: {id: ColorThemePreference; label: string; icon: typeof Sun}[] = [
  {id: "system", label: "System", icon: Monitor},
  {id: "light", label: "Light", icon: Sun},
  {id: "dark", label: "Dark", icon: Moon},
];

export function ColorThemeToggle({compact = false}: {compact?: boolean}) {
  const [preference, setPreference] = useState<ColorThemePreference>("system");

  useEffect(() => {
    setPreference(readColorTheme());
    const media = window.matchMedia("(prefers-color-scheme: light)");
    const onMedia = () => {
      if (readColorTheme() === "system") applyColorTheme("system");
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === COLOR_THEME_STORAGE_KEY) setPreference(readColorTheme());
    };
    media.addEventListener("change", onMedia);
    window.addEventListener("storage", onStorage);
    return () => {
      media.removeEventListener("change", onMedia);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  function select(next: ColorThemePreference) {
    storeColorTheme(next);
    applyColorTheme(next);
    setPreference(next);
  }

  return (
    <div
      className={`inline-flex items-center gap-0.5 rounded-full border border-border bg-surface/80 p-0.5 ${compact ? "" : ""}`}
      role="group"
      aria-label="Color theme"
    >
      {OPTIONS.map((opt) => {
        const Icon = opt.icon;
        const active = preference === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            title={opt.label}
            aria-label={opt.label}
            aria-pressed={active}
            onClick={() => select(opt.id)}
            className={`inline-flex h-8 items-center gap-1 rounded-full px-2.5 text-xs font-semibold transition ${
              active ? "bg-cyan text-ink shadow-sm" : "text-zinc-500 hover:text-zinc-200"
            }`}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
            {!compact ? <span className="hidden sm:inline">{opt.label}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
