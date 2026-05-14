import type { Config } from "tailwindcss";

/**
 * Tokens from screens/stitch_groww_ai_research_terminal/DESIGN.md
 * (Groww RAG Dark — Manrope + Inter, charcoal surfaces, primary accent).
 */
const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#10131a",
        "on-background": "#e1e2eb",
        surface: "#10131a",
        "surface-container-lowest": "#0b0e14",
        "surface-container-low": "#191c22",
        "surface-container": "#1d2026",
        "surface-container-high": "#272a31",
        "surface-container-highest": "#32353c",
        "surface-variant": "#32353c",
        "on-surface": "#e1e2eb",
        "on-surface-variant": "#bacac1",
        outline: "#85948c",
        "outline-variant": "#3c4a43",
        primary: "#44edb7",
        "on-primary": "#003828",
        "primary-container": "#00d09c",
        secondary: "#c4c6ce",
        error: "#ffb4ab",
      },
      fontFamily: {
        display: ["var(--font-manrope)", "system-ui", "sans-serif"],
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      maxWidth: {
        chat: "800px",
      },
      boxShadow: {
        glow: "0 0 15px rgba(68, 237, 183, 0.25)",
        card: "0px 4px 20px rgba(0, 0, 0, 0.2)",
        input: "0px 10px 32px rgba(0, 0, 0, 0.2)",
      },
    },
  },
  plugins: [],
};

export default config;
