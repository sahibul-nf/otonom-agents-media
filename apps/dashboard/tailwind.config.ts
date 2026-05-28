import type {Config} from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        canvas: "var(--canvas)",
        "canvas-deep": "var(--canvas-deep)",
        surface: "var(--surface)",
        "surface-raised": "var(--surface-raised)",
        "surface-panel": "var(--surface-panel)",
        "surface-strong": "var(--surface-strong)",
        cyan: "var(--cyan)",
        teal: "var(--teal)",
        danger: "var(--danger)",
        warning: "var(--warning)",
        ink: "var(--ink)",
        border: "var(--border)",
        "border-strong": "var(--border-strong)",
        "text-primary": "var(--text-primary)",
        "text-secondary": "var(--text-secondary)",
        "text-tertiary": "var(--text-tertiary)",
      },
      borderColor: {
        DEFAULT: "var(--border)",
      },
      fontFamily: {
        sans: ["HarmonyOS Sans", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        editorial: ["Lora", "Georgia", "ui-serif", "serif"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(98,238,248,.16), 0 22px 70px rgba(0,194,183,.08)",
      },
    },
  },
  plugins: [],
};

export default config;
