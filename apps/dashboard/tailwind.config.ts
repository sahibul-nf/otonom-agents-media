import type {Config} from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#17171A",
        "canvas-deep": "#101114",
        surface: "#202024",
        "surface-raised": "#252529",
        "surface-panel": "#2E2E33",
        "surface-strong": "#36363D",
        cyan: "#62EEF8",
        teal: "#00C2B7",
        danger: "#FE5B79",
        warning: "#FF910E",
        ink: "#001F29",
      },
      fontFamily: {
        sans: ["HarmonyOS Sans", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(98,238,248,.16), 0 22px 70px rgba(0,194,183,.08)",
      },
    },
  },
  plugins: [],
};

export default config;
