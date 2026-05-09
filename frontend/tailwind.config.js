/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#0a0b0e",
        surface: { DEFAULT: "#101218", elevated: "#161922", card: "#1a1f2e" },
        panel:    "#101218",
        panelHi:  "#161922",
        hairline: {
          DEFAULT: "#1f2330",
          soft:    "rgba(255,255,255,0.06)",
          strong:  "rgba(255,255,255,0.14)",
        },
        hairline2: "#2a2f3e",
        ink:   "#f4f4f6",
        body:  "#c8cad2",
        mute:  "#7c818f",
        ash:   "#6a6b6c",
        stone: "#525766",
        accent: {
          blue:          "#5fb8ff",
          "blue-soft":   "rgba(95,184,255,0.08)",
          "blue-dim":    "#2a4d6e",
          red:           "#ff6b6b",
          "red-soft":    "rgba(255,107,107,0.08)",
          "red-dim":     "#4a1f1f",
          green:         "#6ee7a7",
          "green-soft":  "rgba(110,231,167,0.08)",
          "green-dim":   "#1f4d3a",
          yellow:        "#fbbf57",
          "yellow-soft": "rgba(251,191,87,0.08)",
          "yellow-dim":  "#4a3a1a",
        },
        score: {
          low:  "#ff6b6b",
          mid:  "#fbbf57",
          good: "#5fb8ff",
          high: "#6ee7a7",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: { "2xl": "1rem", "3xl": "1.25rem" },
      boxShadow: {
        glow:        "0 0 0 1px rgba(95,184,255,0.22), 0 8px 32px rgba(95,184,255,0.1)",
        "glow-sm":   "0 0 0 1px rgba(95,184,255,0.15), 0 4px 16px rgba(95,184,255,0.07)",
        "glow-cta":  "0 0 24px rgba(95,184,255,0.35)",
        "cta":       "0 0 0 1px rgba(255,255,255,0.12), 0 8px 28px rgba(255,255,255,0.07)",
        "cta-hover": "0 0 0 1px rgba(255,255,255,0.22), 0 12px 40px rgba(255,255,255,0.14)",
      },
      animation: {
        "fade-in":    "fadeIn 0.35s ease-out both",
        "fade-in-up": "fadeInUp 0.45s ease-out both",
        "blink":      "blink 1.4s ease-in-out infinite",
      },
      keyframes: {
        fadeIn:   { "0%": { opacity: "0", transform: "translateY(4px)" },  "100%": { opacity: "1", transform: "translateY(0)" } },
        fadeInUp: { "0%": { opacity: "0", transform: "translateY(14px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
        blink:    { "0%, 100%": { opacity: "1" }, "50%": { opacity: "0.15" } },
      },
    },
  },
  plugins: [],
};
