/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          base: "#151210",
          surface: "#1D1916",
          raised: "#26211C",
          "raised-hover": "#2E2822",
        },
        hairline: "#3A3229",
        ember: {
          DEFAULT: "#C1662E",
          bright: "#E08A4C",
          deep: "#7A3E1A",
        },
        iron: {
          teal: "#4F7A6E",
          "teal-bright": "#6FA093",
        },
        crimson: {
          DEFAULT: "#B14434",
          bright: "#D65C46",
        },
        frost: "#5C8B94",
        ink: {
          DEFAULT: "#F3EDE4",
          mute: "#A69A8A",
          dim: "#6B6055",
        },
        rarity: {
          common: "#8B8478",
          rare: "#5B8FB0",
          epic: "#9B5FC0",
          legendary: "#E8A23D",
        },
      },
      fontFamily: {
        display: ["'Fraunces'", "Georgia", "serif"],
        body: ["'Hanken Grotesk'", "system-ui", "sans-serif"],
        mono: ["'Space Mono'", "ui-monospace", "monospace"],
      },
      boxShadow: {
        "glow-rare": "0 0 20px -6px rgba(91,143,176,0.45)",
        "glow-epic": "0 0 24px -6px rgba(155,95,192,0.5)",
        "glow-legendary": "0 0 30px -6px rgba(232,162,61,0.6)",
        "glow-ember": "0 8px 18px -8px rgba(193,102,46,0.6)",
      },
      animation: {
        "legendary-breathe": "legendaryBreathe 2.6s ease-in-out infinite",
        shimmer: "shimmer 1.8s linear infinite",
        "reward-glow": "rewardGlow 2.6s ease-in-out infinite",
        "ray-twinkle": "rayTwinkle 2.6s ease-in-out infinite",
        "chest-shake": "chestShake 0.42s ease-in-out infinite",
        "card-pop-in": "cardPopIn 0.85s cubic-bezier(0.22,1.4,0.36,1) both",
        "reveal-flash": "revealFlash 0.6s ease-out both",
      },
      keyframes: {
        legendaryBreathe: {
          "0%, 100%": { opacity: "0.75", boxShadow: "0 0 30px -6px rgba(232,162,61,0.6)" },
          "50%": { opacity: "1", boxShadow: "0 0 42px -4px rgba(232,162,61,0.85)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-400px 0" },
          "100%": { backgroundPosition: "400px 0" },
        },
        // Chest Opening's reveal glow — deliberately a breathing scale/opacity
        // pulse, never a rotation (the earlier spinning conic-gradient
        // "radar" was explicitly rejected during the Ember & Iron v3 review).
        rewardGlow: {
          "0%, 100%": { opacity: "0.75", transform: "scale(1)" },
          "50%": { opacity: "1", transform: "scale(1.06)" },
        },
        rayTwinkle: {
          "0%, 100%": { opacity: "0.25" },
          "50%": { opacity: "0.7" },
        },
        // Chest Opening's pre-reveal suspense beat — a nervous jitter
        // (translate + a couple degrees of tilt), never a spin. Finite by
        // construction: the "opening" stage that applies this class only
        // lasts ~1s before the reveal, it isn't meant to loop forever.
        chestShake: {
          "0%, 100%": { transform: "translateX(0) rotate(0deg)" },
          "25%": { transform: "translateX(-3px) rotate(-1.5deg)" },
          "75%": { transform: "translateX(3px) rotate(1.5deg)" },
        },
        // The reward card's one-shot entrance — scale/opacity pop with a
        // slight overshoot, not a flip or rotation.
        cardPopIn: {
          "0%": { opacity: "0", transform: "scale(0.55)" },
          "60%": { opacity: "1", transform: "scale(1.08)" },
          "80%": { transform: "scale(0.97)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        // A brief bright burst timed with the card's entrance — opacity
        // only (no movement/rotation), so the reveal reads as a punctuated
        // "moment" rather than the card just quietly fading in.
        revealFlash: {
          "0%": { opacity: "0" },
          "15%": { opacity: "1" },
          "100%": { opacity: "0" },
        },
      },
    },
  },
  plugins: [],
};
