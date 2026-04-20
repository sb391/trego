import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#081C31",
        navy: "#0A2540",
        navySoft: "#153757",
        cloud: "#F8FAFC",
        mist: "#E2E8F0",
        steel: "#5B6776",
        gold: "#C8A96A",
        goldSoft: "#E9D2A6",
      },
      fontFamily: {
        sans: ["var(--font-body)", "sans-serif"],
        display: ["var(--font-display)", "serif"],
      },
      boxShadow: {
        luxe: "0 32px 80px rgba(8, 28, 49, 0.14)",
        panel: "0 22px 50px rgba(10, 37, 64, 0.12)",
      },
      backgroundImage: {
        "hero-grid":
          "linear-gradient(rgba(255,255,255,0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.07) 1px, transparent 1px)",
      },
      keyframes: {
        "drift-slow": {
          "0%, 100%": { transform: "translate3d(0, 0, 0)" },
          "50%": { transform: "translate3d(0, 12px, 0)" },
        },
      },
      animation: {
        "drift-slow": "drift-slow 8s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
