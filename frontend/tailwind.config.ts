import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172033",
        moss: "#167a61",
        mint: "#dff7ef",
        coral: "#dc4c57",
        amber: "#d99100",
      },
      boxShadow: {
        panel: "0 16px 40px rgba(23, 32, 51, 0.10)",
      },
    },
  },
  plugins: [],
} satisfies Config;
