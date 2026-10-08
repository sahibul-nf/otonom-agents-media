export const COLOR_THEME_STORAGE_KEY = "otonom-color-theme";

export type ColorThemePreference = "system" | "light" | "dark";

export function readColorTheme(): ColorThemePreference {
  if (typeof window === "undefined") return "system";
  try {
    const raw = window.localStorage.getItem(COLOR_THEME_STORAGE_KEY);
    if (raw === "light" || raw === "dark" || raw === "system") return raw;
  } catch {
    /* ignore */
  }
  return "system";
}

export function storeColorTheme(preference: ColorThemePreference) {
  window.localStorage.setItem(COLOR_THEME_STORAGE_KEY, preference);
}

export function applyColorTheme(preference: ColorThemePreference) {
  const root = document.documentElement;
  root.classList.remove("light-theme", "dark-theme");
  if (preference === "light") {
    root.classList.add("light-theme");
    return;
  }
  if (preference === "dark") {
    root.classList.add("dark-theme");
    return;
  }
  if (window.matchMedia("(prefers-color-scheme: light)").matches) {
    root.classList.add("light-theme");
  }
}

/** Inline bootstrap for layout.tsx — must stay in sync with applyColorTheme. */
export const COLOR_THEME_BOOTSTRAP_SCRIPT = `(()=>{try{const k="${COLOR_THEME_STORAGE_KEY}";const s=localStorage.getItem(k);const r=document.documentElement;r.classList.remove("light-theme","dark-theme");if(s==="light")r.classList.add("light-theme");else if(s==="dark")r.classList.add("dark-theme");else if(!s||s==="system"){if(window.matchMedia("(prefers-color-scheme: light)").matches)r.classList.add("light-theme")}}catch(e){}})();`;
